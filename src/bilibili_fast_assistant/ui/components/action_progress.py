"""三连执行时的状态框。

只有颜色变化，没有动画：

* 淡灰：用户没勾这个操作，不执行
* 普通：排队中
* 浅粉：正在请求
* **粉色框线**：之前已经操作过，不需要再动
* 整框粉色：成功
* 整框红色：失败
"""

from __future__ import annotations

import flet as ft

from ... import theme
from ...models.actions import ActionKind, ActionState

BOX_WIDTH = 74
BOX_HEIGHT = 30
CHIP_WIDTH = 66


def _box_style(state: ActionState) -> tuple[str, str, str]:
    """返回（背景色, 边框色, 文字色）。"""
    if state is ActionState.DISABLED:
        return "#F7F8FA", "#EFF0F2", "#C4C7CC"
    if state is ActionState.RUNNING:
        return theme.PINK_LIGHT, theme.PINK, theme.PINK_DEEP
    if state is ActionState.SKIPPED:
        return theme.SURFACE, theme.PINK, theme.PINK_DEEP
    if state is ActionState.DONE:
        return theme.PINK, theme.PINK, ft.Colors.WHITE
    if state is ActionState.FAILED:
        return theme.DANGER, theme.DANGER, ft.Colors.WHITE
    return theme.SURFACE, theme.BORDER, theme.TEXT_PRIMARY


class ActionBox:
    """一个操作状态框。"""

    def __init__(self, kind: ActionKind, *, initial: ActionState) -> None:
        self.kind = kind
        self.state = initial

        self._label = ft.Text(
            kind.label,
            size=12,
            weight=ft.FontWeight.BOLD,
        )
        self.control = ft.Container(
            width=BOX_WIDTH,
            height=BOX_HEIGHT,
            alignment=ft.Alignment.CENTER,
            border_radius=theme.RADIUS,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=self._label,
        )
        self._apply(initial)

    # ------------------------------------------------------------ 对外
    def set_state(self, state: ActionState, message: str = "") -> None:
        self.state = state
        self._apply(state)
        self.control.tooltip = (
            f"{self.kind.label}：{message}" if message else self.kind.label
        )

    # ------------------------------------------------------------ 内部
    def _apply(self, state: ActionState) -> None:
        bgcolor, border_color, text_color = _box_style(state)
        self.control.bgcolor = bgcolor
        self.control.border = ft.Border.all(1, border_color)
        self._label.color = text_color


def episode_number_chip(number: str, title: str) -> ft.Container:
    """条目最左边的集数框。

    显示的是**集数**（第几话），不是内部的 ``ep_id``；
    鼠标悬浮能看到这一集的完整名字。
    """
    return ft.Container(
        width=CHIP_WIDTH,
        height=BOX_HEIGHT,
        alignment=ft.Alignment.CENTER,
        bgcolor=theme.BG,
        border_radius=theme.RADIUS,
        tooltip=title,
        content=ft.Text(
            str(number),
            size=12,
            weight=ft.FontWeight.BOLD,
            color=theme.TEXT_SECONDARY,
        ),
    )
