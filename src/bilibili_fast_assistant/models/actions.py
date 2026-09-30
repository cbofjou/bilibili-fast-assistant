"""用户选择的"要执行哪些操作"。

目前只承载 UI 选择状态，真正的三连请求后续再实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

COIN_NONE = 0
COIN_ONE = 1
COIN_TWO = 2

# B 站每个稿件最多投 2 个币
COIN_CHOICES: tuple[int, ...] = (COIN_ONE, COIN_TWO)


class ActionKind(StrEnum):
    """三类可执行的操作。"""

    LIKE = "like"
    COIN = "coin"
    FAVORITE = "favorite"

    @property
    def label(self) -> str:
        return {"like": "点赞", "coin": "投币", "favorite": "收藏"}[self.value]


class ActionState(StrEnum):
    """单个操作框的状态，决定了它在界面上长什么样。"""

    DISABLED = "disabled"    # 用户没选这个操作：淡灰
    PENDING = "pending"      # 排队中
    RUNNING = "running"      # 请求中：从下往上渐变
    SKIPPED = "skipped"      # 之前已经操作过：粉色框线，不重复执行
    DONE = "done"            # 执行成功：整框粉色
    FAILED = "failed"        # 执行失败：红色

    @property
    def is_final(self) -> bool:
        return self in (ActionState.SKIPPED, ActionState.DONE, ActionState.FAILED)


ALL_ACTIONS: tuple[ActionKind, ...] = (
    ActionKind.LIKE,
    ActionKind.COIN,
    ActionKind.FAVORITE,
)


@dataclass(slots=True)
class EpisodeTask:
    """一集的执行任务：既有输入（要做什么），也挂执行结果。"""

    index: int
    ep_id: int
    aid: int
    number: str
    """显示用的集数，比如 "1"、"193"；电影是 "正片"。"""
    title: str
    """剧集名，用于悬浮提示和失败日志。"""
    states: dict[ActionKind, ActionState]
    messages: dict[ActionKind, str]

    @classmethod
    def create(
        cls,
        index: int,
        *,
        ep_id: int,
        aid: int,
        number: str,
        title: str,
        selected: tuple[ActionKind, ...],
    ) -> "EpisodeTask":
        return cls(
            index=index,
            ep_id=ep_id,
            aid=aid,
            number=number,
            title=title,
            states={
                kind: (
                    ActionState.PENDING
                    if kind in selected
                    else ActionState.DISABLED
                )
                for kind in ALL_ACTIONS
            },
            messages={kind: "" for kind in ALL_ACTIONS},
        )

    @property
    def selected_kinds(self) -> tuple[ActionKind, ...]:
        return tuple(
            kind
            for kind in ALL_ACTIONS
            if self.states[kind] is not ActionState.DISABLED
        )


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """执行过程中推给界面的一次状态变化。"""

    index: int
    kind: ActionKind
    state: ActionState
    message: str = ""


@dataclass(slots=True)
class RunSummary:
    total_episodes: int = 0
    done: int = 0
    skipped: int = 0
    failed: int = 0
    stopped: bool = False
    stop_reason: str = ""
    log_path: str = ""


@dataclass
class TripleSelection:
    """点赞 / 投币 / 收藏 三项选择。"""

    like: bool = False
    coin: int = COIN_NONE
    favorite: bool = False

    @property
    def is_empty(self) -> bool:
        return not (self.like or self.coin or self.favorite)

    @property
    def coin_selected(self) -> bool:
        return self.coin > COIN_NONE

    def toggle_like(self) -> None:
        self.like = not self.like

    def toggle_favorite(self) -> None:
        self.favorite = not self.favorite

    def set_coin(self, value: int) -> None:
        self.coin = value if value in COIN_CHOICES else COIN_NONE

    def clear(self) -> None:
        self.like = False
        self.coin = COIN_NONE
        self.favorite = False

    def action_labels(self) -> list[str]:
        """只返回操作名，方便拼到别的句子里。"""
        labels: list[str] = []
        if self.like:
            labels.append("点赞")
        if self.coin_selected:
            labels.append(f"投币 ×{self.coin}")
        if self.favorite:
            labels.append("收藏")
        return labels

    def describe(self) -> str:
        labels = self.action_labels()
        if not labels:
            return "还没有选择任何操作"
        return "已选：" + " · ".join(labels)
