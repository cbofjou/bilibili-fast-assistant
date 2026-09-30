"""点赞 / 投币 / 收藏选择器。

交互对齐 B 站：三项都可以点选，投币点击后弹出 1 币 / 2 币的选择。
这里只负责"记住用户想做什么"，真正的请求后续再实现。
"""

from __future__ import annotations

from typing import Callable

import flet as ft

from ... import theme
from ...models.actions import COIN_CHOICES, TripleSelection


class TripleActionBar:
    def __init__(
        self,
        page: ft.Page,
        *,
        on_change: Callable[[TripleSelection], None] | None = None,
    ) -> None:
        self._page = page
        self._on_change = on_change
        self.selection = TripleSelection()
        self._root = ft.Container(
            bgcolor=theme.SURFACE,
            border_radius=theme.RADIUS_LG,
            padding=ft.Padding.symmetric(vertical=14, horizontal=16),
            content=ft.Column(spacing=10),
        )
        # 构造阶段不触发刷新，等挂到页面上之后由外部统一渲染
        self._refresh(schedule=False)

    # ------------------------------------------------------------ 对外
    @property
    def control(self) -> ft.Control:
        return self._root

    def reset(self) -> None:
        self.selection.clear()
        self._notify()

    # ------------------------------------------------------------ 渲染
    def _rebuild(self) -> None:
        """只重建按钮内容，不触发界面刷新。"""
        self._root.content = ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    spacing=10,
                    controls=[
                        self._action_button(
                            icon=ft.Icons.THUMB_UP if self.selection.like else ft.Icons.THUMB_UP_OUTLINED,
                            label="点赞",
                            active=self.selection.like,
                            on_click=self._toggle_like,
                        ),
                        self._action_button(
                            icon=(
                                ft.Icons.MONETIZATION_ON
                                if self.selection.coin_selected
                                else ft.Icons.MONETIZATION_ON_OUTLINED
                            ),
                            label=(
                                f"投币 ×{self.selection.coin}"
                                if self.selection.coin_selected
                                else "投币"
                            ),
                            active=self.selection.coin_selected,
                            on_click=self._open_coin_dialog,
                        ),
                        self._action_button(
                            icon=ft.Icons.STAR if self.selection.favorite else ft.Icons.STAR_BORDER,
                            label="收藏",
                            active=self.selection.favorite,
                            on_click=self._toggle_favorite,
                        ),
                    ],
                ),
                ft.Text(
                    self.selection.describe(),
                    size=12,
                    color=(
                        theme.TEXT_SECONDARY if self.selection.is_empty else theme.PINK_DEEP
                    ),
                ),
            ],
        )

    def _refresh(self, *, schedule: bool = True) -> None:
        self._rebuild()
        if schedule:
            self._page.update()

    def _action_button(
        self,
        *,
        icon: ft.IconData,
        label: str,
        active: bool,
        on_click,
    ) -> ft.Control:
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=8, horizontal=16),
            bgcolor=theme.PINK if active else theme.SURFACE,
            border=ft.Border.all(1, theme.PINK if active else theme.BORDER),
            border_radius=22,
            ink=True,
            on_click=on_click,
            content=ft.Row(
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(icon, size=17, color=ft.Colors.WHITE if active else theme.PINK),
                    ft.Text(
                        label,
                        size=13,
                        color=ft.Colors.WHITE if active else theme.TEXT_PRIMARY,
                        weight=ft.FontWeight.BOLD if active else None,
                    ),
                ],
            ),
        )

    # ------------------------------------------------------------ 事件
    def _toggle_like(self, _event: ft.ControlEvent) -> None:
        self.selection.toggle_like()
        self._notify()

    def _toggle_favorite(self, _event: ft.ControlEvent) -> None:
        self.selection.toggle_favorite()
        self._notify()

    def _open_coin_dialog(self, _event: ft.ControlEvent) -> None:
        """点击投币 -> 像 B 站那样选 1 个还是 2 个。"""

        def choose(value: int) -> None:
            self.selection.set_coin(value)
            self._close_dialog()
            self._notify()

        actions: list[ft.Control] = [
            ft.TextButton(
                content=f"{value} 个币",
                on_click=lambda _e, v=value: choose(v),
            )
            for value in COIN_CHOICES
        ]
        if self.selection.coin_selected:
            actions.append(
                ft.TextButton(
                    content="取消投币",
                    on_click=lambda _e: choose(0),
                )
            )
        actions.append(
            ft.TextButton(content="关闭", on_click=lambda _e: self._close_dialog())
        )

        self._page.show_dialog(
            ft.AlertDialog(
                modal=True,
                bgcolor=theme.SURFACE,
                title=ft.Text("投币数量", size=16, weight=ft.FontWeight.BOLD),
                content=ft.Text(
                    "每个稿件最多投 2 个币，投币不可撤销。",
                    size=13,
                    color=theme.TEXT_SECONDARY,
                ),
                actions=actions,
            )
        )

    def _close_dialog(self) -> None:
        try:
            self._page.pop_dialog()
        except Exception:  # 没有打开的对话框时忽略
            return
        self._page.update()

    def _notify(self) -> None:
        """先让外部同步（比如提交框里的摘要），最后再统一刷一次界面。

        顺序很重要：如果先刷新再通知外部，外部改的文案要等到下一次
        交互才会显示出来——表现就是"操作状态永远慢一拍"。
        """
        if self._on_change:
            self._on_change(self.selection)
        self._refresh()
