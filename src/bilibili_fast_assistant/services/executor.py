"""逐集执行点赞 / 投币 / 收藏。

三条核心原则：

1. **先查后做**。动手之前先看这一集有没有操作过，操作过就只标成"无需操作"。
   投币尤其重要——重复投是真扣硬币的。
2. **查不到就不做**。状态查询失败时跳过这一集，绝不"盲投"。
3. **限速**。写操作比查询敏感得多，两次写请求之间留最小间隔，每集之后再停顿。

关于风控的判定，见 :meth:`TripleExecutor._update_breaker`：
只有"这一集所有要做的动作全都被拦下"才认为是账号级风控；
个别动作被拦（比如某部番的点赞被限制，投币收藏却正常）属于内容限制，
不该连累其它操作，也不该让整批停下。
"""

from __future__ import annotations

import random
import time
from typing import Callable, Iterable, Sequence

from .. import config
from ..api import BiliApi, BiliApiError, is_risk_error
from ..api.errors import RISK_HINT
from ..models import EpisodeInteraction
from ..models.actions import (
    ActionKind,
    ActionState,
    EpisodeTask,
    ExecutionEvent,
    RunSummary,
    TripleSelection,
)
from . import run_log

# 点赞接口用这个码表示"已经赞过"
_ALREADY_LIKED_CODE = 65006

# 单个动作的结局
_OK = "ok"
_BLOCKED = "blocked"    # 被风控 / 限流挡下
_FAILED = "failed"      # 其它失败

Emit = Callable[[ExecutionEvent], None]


def selected_kinds(selection: TripleSelection) -> tuple[ActionKind, ...]:
    """用户勾选了哪些操作。"""
    kinds: list[ActionKind] = []
    if selection.like:
        kinds.append(ActionKind.LIKE)
    if selection.coin_selected:
        kinds.append(ActionKind.COIN)
    if selection.favorite:
        kinds.append(ActionKind.FAVORITE)
    return tuple(kinds)


def _already_done(interaction: EpisodeInteraction, kind: ActionKind) -> bool:
    """这一集的这个操作之前做过吗。"""
    if kind is ActionKind.LIKE:
        return interaction.liked
    if kind is ActionKind.COIN:
        # 只要投过币就跳过：再投会继续扣硬币，宁可保守
        return interaction.coin > 0
    return interaction.favorited


def _describe(exc: BaseException, *, blocked: bool) -> str:
    """把异常翻译成一句能指导用户下一步怎么办的话。"""
    message = str(exc)
    if blocked:
        message = f"{message}（{RISK_HINT}）"
    return message


class TripleExecutor:
    def __init__(
        self,
        api: BiliApi,
        *,
        dry_run: bool = False,
        request_gap: float = config.ACTION_REQUEST_GAP,
        episode_pause: float = config.ACTION_EPISODE_PAUSE,
        jitter: float = config.ACTION_JITTER,
        risk_streak_limit: int = config.ACTION_RISK_STREAK_LIMIT,
        max_request_gap: float = config.ACTION_MAX_REQUEST_GAP,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api = api
        self._dry_run = dry_run
        self._request_gap = request_gap
        self._episode_pause = episode_pause
        self._jitter = jitter
        self._risk_streak_limit = risk_streak_limit
        self._max_request_gap = max_request_gap
        self._sleep = sleep
        self._clock = clock
        # 上一次真正发出写请求的时刻，用来保证写请求之间不会挤在一起
        self._last_write_at: float | None = None
        # "颗粒无收"的连续集数：整集所有动作都被风控拦下才算一次
        self._risk_streak = 0
        self._abort_reason = ""

    # ------------------------------------------------------------ 主流程
    def run(
        self,
        tasks: Sequence[EpisodeTask],
        selection: TripleSelection,
        emit: Emit,
        *,
        should_stop: Callable[[], bool] = lambda: False,
    ) -> RunSummary:
        summary = RunSummary(total_episodes=len(tasks))
        kinds = selected_kinds(selection)

        folder_id = self._prepare_folder(kinds, tasks, emit)
        run_log.record_run_start(
            len(tasks), " · ".join(kind.label for kind in kinds) or "无"
        )

        for position, task in enumerate(tasks):
            if should_stop() or self._abort_reason:
                summary.stopped = True
                break
            self._run_episode(task, selection, folder_id, emit, summary, should_stop)
            if position < len(tasks) - 1 and not should_stop():
                self._wait(
                    self._episode_pause + random.uniform(0, self._jitter), should_stop
                )

        if should_stop():
            summary.stopped = True
        if self._abort_reason:
            summary.stopped = True
            summary.stop_reason = self._abort_reason
        summary.log_path = str(run_log.failure_log_path())
        return summary

    # ------------------------------------------------------------ 单集
    def _run_episode(
        self,
        task: EpisodeTask,
        selection: TripleSelection,
        folder_id: int | None,
        emit: Emit,
        summary: RunSummary,
        should_stop: Callable[[], bool],
    ) -> None:
        kinds = task.selected_kinds
        if not kinds:
            return

        # 1) 先查这一集的状态
        try:
            interaction = self._api.bangumi.episode_interaction(task.ep_id)
        except Exception as exc:
            # 查不到就无法判断有没有操作过 —— 为了不重复扣币，整集跳过
            message = f"状态查询失败，已跳过以免重复操作（{exc}）"
            for kind in kinds:
                self._fail(task, kind, message, emit, summary)
            return

        # 2) 逐个动作执行
        blocked = 0
        succeeded = 0
        for kind in kinds:
            if should_stop():
                return
            if _already_done(interaction, kind):
                self._emit(emit, task, kind, ActionState.SKIPPED, "之前已经操作过")
                summary.skipped += 1
                continue
            if kind is ActionKind.FAVORITE and folder_id is None:
                self._fail(task, kind, "没有可用的收藏夹", emit, summary)
                continue

            outcome = self._perform_action(task, kind, selection, folder_id, emit, summary)
            if outcome is _OK:
                succeeded += 1
            elif outcome is _BLOCKED:
                blocked += 1

        self._update_breaker(blocked, succeeded)

    def _perform_action(
        self,
        task: EpisodeTask,
        kind: ActionKind,
        selection: TripleSelection,
        folder_id: int | None,
        emit: Emit,
        summary: RunSummary,
    ) -> str:
        self._emit(emit, task, kind, ActionState.RUNNING)
        try:
            self._send(task, kind, selection, folder_id)
        except BiliApiError as exc:
            if kind is ActionKind.LIKE and exc.code == _ALREADY_LIKED_CODE:
                self._emit(emit, task, kind, ActionState.SKIPPED, "之前已经操作过")
                summary.skipped += 1
                return _OK
            blocked = is_risk_error(exc)
            self._fail(task, kind, _describe(exc, blocked=blocked), emit, summary)
            return _BLOCKED if blocked else _FAILED
        except Exception as exc:
            self._fail(task, kind, str(exc), emit, summary)
            return _FAILED

        self._emit(emit, task, kind, ActionState.DONE)
        summary.done += 1
        return _OK

    def _send(
        self,
        task: EpisodeTask,
        kind: ActionKind,
        selection: TripleSelection,
        folder_id: int | None,
    ) -> None:
        if self._dry_run:
            # 演练模式：不发请求，只留一点耗时让状态变化看得出来
            self._sleep(0.25)
            return
        # 真正要发请求了，先过一道限速闸
        self._throttle()
        if kind is ActionKind.LIKE:
            self._api.actions.like(task.aid)
        elif kind is ActionKind.COIN:
            self._api.actions.add_coin(task.aid, count=selection.coin)
        else:
            self._api.actions.favorite(task.aid, media_ids=[int(folder_id or 0)])

    # ------------------------------------------------------------ 风控与熔断
    def _update_breaker(self, blocked: int, succeeded: int) -> None:
        """判断这一集是不是"整集被拦"。

        只有**这一集要做的动作全都被拦下、一个都没成功**时，才认为是账号级风控，
        才需要降速和计数。像"某部番的点赞被内容方限制、投币收藏却正常"这种，
        属于单点问题，不该连累其它操作，也不该让整批停下来。
        """
        if blocked and not succeeded:
            self._note_risk()
        else:
            self._risk_streak = 0

    def _note_risk(self) -> None:
        """记一次"整集被拦"：降速，连续太多次就整批停下。"""
        self._risk_streak += 1
        self._slow_down()
        if self._risk_streak >= self._risk_streak_limit:
            self._abort_reason = (
                f"连续 {self._risk_streak} 集所有操作都被拦下（疑似账号被风控），已自动停止。"
                "建议过一段时间（比如几小时）再试，不要连续重试。"
            )

    def _slow_down(self) -> None:
        """撞了风控就降速：写请求间隔翻倍，直到上限。"""
        self._request_gap = min(self._request_gap * 2, self._max_request_gap)

    # ------------------------------------------------------------ 准备
    def _prepare_folder(
        self,
        kinds: Iterable[ActionKind],
        tasks: Sequence[EpisodeTask],
        emit: Emit,
    ) -> int | None:
        """收藏需要先拿一个收藏夹 id；拿不到就把收藏这一列整列标失败。"""
        if ActionKind.FAVORITE not in kinds:
            return None
        if self._dry_run:
            return -1
        try:
            folder_id = self._api.actions.default_favorite_folder_id()
        except Exception:
            folder_id = None
        if folder_id is not None:
            return folder_id
        for task in tasks:
            if task.states[ActionKind.FAVORITE] is ActionState.DISABLED:
                continue
            self._emit(
                emit, task, ActionKind.FAVORITE, ActionState.FAILED, "没有可用的收藏夹"
            )
        return None

    # ------------------------------------------------------------ 工具
    def _emit(
        self,
        emit: Emit,
        task: EpisodeTask,
        kind: ActionKind,
        state: ActionState,
        message: str = "",
    ) -> None:
        task.states[kind] = state
        task.messages[kind] = message
        emit(ExecutionEvent(task.index, kind, state, message))

    def _fail(
        self,
        task: EpisodeTask,
        kind: ActionKind,
        message: str,
        emit: Emit,
        summary: RunSummary,
    ) -> None:
        self._emit(emit, task, kind, ActionState.FAILED, message)
        summary.failed += 1
        try:
            run_log.record_failure(
                ep_id=task.ep_id,
                title=task.title,
                action=kind.label,
                message=message,
            )
        except OSError:
            # 日志写不进去不能影响主流程
            pass

    def _wait(self, seconds: float, should_stop: Callable[[], bool]) -> None:
        """可被打断的等待。"""
        remaining = seconds
        while remaining > 0:
            if should_stop():
                return
            step = min(0.2, remaining)
            self._sleep(step)
            remaining -= step

    def _throttle(self) -> None:
        """保证任意两次写请求之间至少隔 ``request_gap`` 秒。

        没有这道闸的话，同一集的三条写请求会在 200ms 内连着发出去，
        这种突发比平均速率更容易被风控盯上。
        """
        now = self._clock()
        if self._last_write_at is not None:
            wait = self._request_gap - (now - self._last_write_at)
            if wait > 0:
                self._wait(wait, lambda: False)
                now = self._clock()
        self._last_write_at = now
