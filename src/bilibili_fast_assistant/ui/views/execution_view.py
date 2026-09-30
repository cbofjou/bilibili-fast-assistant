"""三连执行面板：按集列出每个操作的状态。"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from typing import Callable, Sequence

import flet as ft

from ... import theme
from ...api import get_api
from ...models.actions import (
    ActionKind,
    ActionState,
    EpisodeTask,
    ExecutionEvent,
    RunSummary,
    TripleSelection,
)
from ...services.executor import TripleExecutor
from ..components.action_progress import ActionBox, episode_number_chip

_DRAIN_INTERVAL = 0.05


class ExecutionView:
    def __init__(
        self,
        page: ft.Page,
        *,
        on_back: Callable[[], None],
        on_finished: Callable[[], None] | None = None,
        dry_run: bool = False,
    ) -> None:
        self._page = page
        self._on_back = on_back
        self._on_finished = on_finished
        self._dry_run = dry_run

        self._queue: queue.Queue[ExecutionEvent] = queue.Queue()
        self._stopped = False
        self._worker_done = False
        self._error: Exception | None = None
        self._summary: RunSummary | None = None
        self._started_at = 0.0

        self._boxes: dict[tuple[int, ActionKind], ActionBox] = {}
        self._tasks: list[EpisodeTask] = []
        self._selection: TripleSelection | None = None

        self._progress_text = ft.Text("", size=12, color=theme.TEXT_SECONDARY)
        self._banner = ft.Container(visible=False)
        self._rows = ft.Column(spacing=6)
        self._stop_button = ft.TextButton(
            content="停止",
            on_click=lambda _event: self.stop(),
            style=ft.ButtonStyle(
                color=theme.DANGER,
                padding=ft.Padding.symmetric(vertical=6, horizontal=12),
            ),
        )

        self._root = ft.Column(
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.TextButton(
                                    content="← 返回详情",
                                    on_click=lambda _event: self._go_back(),
                                    style=ft.ButtonStyle(
                                        color=theme.PINK_DEEP,
                                        padding=ft.Padding.symmetric(
                                            vertical=8, horizontal=10
                                        ),
                                    ),
                                ),
                                self._progress_text,
                            ],
                        ),
                        self._stop_button,
                    ],
                ),
                self._banner,
                ft.Container(
                    bgcolor=theme.SURFACE,
                    border_radius=theme.RADIUS_LG,
                    padding=ft.Padding.all(16),
                    content=self._rows,
                ),
            ],
        )

    # ------------------------------------------------------------ 对外
    @property
    def control(self) -> ft.Control:
        return self._root

    def start(
        self,
        tasks: Sequence[EpisodeTask],
        selection: TripleSelection,
        *,
        executor: TripleExecutor | None = None,
    ) -> None:
        self._tasks = list(tasks)
        self._selection = selection
        self._build_rows(self._tasks)
        self._refresh_progress()
        if self._dry_run:
            self._show_banner(
                "演练模式：不会真的发请求，只走一遍流程。", kind="warning"
            )

        runner = executor or TripleExecutor(get_api(), dry_run=self._dry_run)
        self._started_at = time.monotonic()
        threading.Thread(
            target=self._work,
            args=(runner, tasks, selection),
            name="triple-executor",
            daemon=True,
        ).start()
        self._page.run_task(self._pump)

    def stop(self) -> None:
        self._stopped = True

    # ------------------------------------------------------------ 渲染
    def _build_rows(self, tasks: Sequence[EpisodeTask]) -> None:
        rows: list[ft.Control] = []
        for task in tasks:
            boxes: list[ft.Control] = [episode_number_chip(task.number, task.title)]
            for kind in (ActionKind.LIKE, ActionKind.COIN, ActionKind.FAVORITE):
                box = ActionBox(kind, initial=task.states[kind])
                self._boxes[(task.index, kind)] = box
                boxes.append(box.control)
            rows.append(ft.Row(spacing=8, controls=boxes))
        self._rows.controls = rows

    def _refresh_progress(self) -> None:
        # 只看用户勾选的那些操作：没勾的框永远是 DISABLED，
        # 如果把它也算进去，进度永远到不了 100%
        finished = sum(
            1
            for task in self._tasks
            if task.selected_kinds
            and all(task.states[kind].is_final for kind in task.selected_kinds)
        )
        total = len(self._tasks)
        label = "演练" if self._dry_run else "执行"
        self._progress_text.value = f"{label}中 {finished}/{total} 集"

    def _show_banner(self, text: str, *, kind: str = "info") -> None:
        palette = {
            "info": (theme.PINK_LIGHT, theme.PINK_DEEP),
            "success": ("#EEFBF2", theme.SUCCESS),
            "warning": ("#FFF7E8", theme.WARNING),
            "error": ("#FFF0F4", theme.DANGER),
        }
        bgcolor, color = palette.get(kind, palette["info"])
        self._banner.visible = True
        self._banner.bgcolor = bgcolor
        self._banner.border_radius = theme.RADIUS
        self._banner.padding = ft.Padding.symmetric(vertical=10, horizontal=14)
        self._banner.content = ft.Text(text, size=13, color=color)

    # ------------------------------------------------------------ 执行
    def _work(
        self,
        executor: TripleExecutor,
        tasks: Sequence[EpisodeTask],
        selection: TripleSelection,
    ) -> None:
        try:
            self._summary = executor.run(
                tasks,
                selection,
                self._queue.put,
                should_stop=lambda: self._stopped,
            )
        except Exception as exc:  # 兜底，别让线程静默死掉
            self._error = exc
        finally:
            self._worker_done = True

    async def _pump(self) -> None:
        while True:
            applied = False
            while True:
                try:
                    event = self._queue.get_nowait()
                except queue.Empty:
                    break
                self._apply(event)
                applied = True

            if applied:
                self._refresh_progress()
                self._page.update()

            if self._worker_done and self._queue.empty():
                break
            await asyncio.sleep(_DRAIN_INTERVAL)

        self._page.update()
        self._finish()

    def _apply(self, event: ExecutionEvent) -> None:
        box = self._boxes.get((event.index, event.kind))
        if box is not None:
            box.set_state(event.state, event.message)

    def _finish(self) -> None:
        self._stop_button.visible = False
        elapsed = time.monotonic() - self._started_at

        if self._error is not None:
            self._show_banner(f"执行中断：{self._error}", kind="error")
            return

        summary = self._summary or RunSummary()
        parts = [f"成功 {summary.done}", f"无需操作 {summary.skipped}"]
        if summary.failed:
            parts.append(f"失败 {summary.failed}")
        head = "演练完成" if self._dry_run else "执行完成"
        if summary.stopped:
            head = "已停止" if not summary.stop_reason else "已自动停止"
        text = f"{head}：{' · '.join(parts)}　用时 {elapsed:.0f} 秒"
        if summary.stop_reason:
            text += f"\n{summary.stop_reason}"
        if summary.failed and summary.log_path:
            text += f"\n失败原因已写入：{summary.log_path}"
        self._show_banner(
            text,
            kind="error" if (summary.failed or summary.stop_reason) else "success",
        )
        self._page.update()

        # 投币会改变硬币余额，跑完通知外层刷新一次
        if self._should_refresh_balance() and self._on_finished is not None:
            self._on_finished()

    def _should_refresh_balance(self) -> bool:
        """只有真的投出过币才需要刷新余额，避免无谓的请求。"""
        if self._selection is None or not self._selection.coin_selected:
            return False

        # 读视图自己的状态框，而不是执行器那边的任务对象 ——
        # 界面呈现的状态以这里为准，两边不必互相依赖。
        return any(
            box.state is ActionState.DONE
            for (_index, kind), box in self._boxes.items()
            if kind is ActionKind.COIN
        )

    def _go_back(self) -> None:
        self.stop()
        self._on_back()
