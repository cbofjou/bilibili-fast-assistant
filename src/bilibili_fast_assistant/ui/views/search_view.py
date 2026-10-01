"""搜索视图：一个分区对应一个实例，负责输入框 + 结果卡片列表。"""

from __future__ import annotations

import asyncio
from typing import Callable

import flet as ft

from ... import theme
from ...api import get_api
from ...models import SearchCard
from ...services import Partition, get_meta, search_in_partition
from ..components import bangumi_card, empty_block, loading_block, notice_block


class SearchView:
    def __init__(
        self,
        page: ft.Page,
        partition: Partition,
        *,
        on_open_detail: Callable[[SearchCard], None],
    ) -> None:
        self._page = page
        self.partition = partition
        self.meta = get_meta(partition)
        self._on_open_detail = on_open_detail

        self._field = ft.TextField(
            hint_text=self.meta.hint,
            expand=True,
            # 边框按状态分别配置；直接写 border_color / border_radius 在 1.0 已废弃
            border={
                ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                    side=ft.BorderSide(1, theme.BORDER),
                    border_radius=ft.BorderRadius.all(theme.RADIUS),
                ),
                ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                    side=ft.BorderSide(1, theme.PINK),
                    border_radius=ft.BorderRadius.all(theme.RADIUS),
                ),
            },
            cursor_color=theme.PINK,
            prefix_icon=ft.Icons.SEARCH,
            text_size=14,
            content_padding=ft.Padding.symmetric(vertical=14, horizontal=12),
            on_submit=lambda _event: self.search(),
        )
        self._search_button = ft.Button(
            content="搜索",
            icon=ft.Icons.SEARCH,
            on_click=lambda _event: self.search(),
            style=ft.ButtonStyle(
                bgcolor=theme.PINK,
                color=ft.Colors.WHITE,
                padding=ft.Padding.symmetric(vertical=18, horizontal=22),
                shape=ft.RoundedRectangleBorder(radius=theme.RADIUS),
            ),
        )

        self._notice = ft.Container(visible=False)
        self._results = ft.Container(content=self._idle_block())

        self._root = ft.Column(
            spacing=16,
            # 注意用 ScrollMode（auto/always/hidden/adaptive），
            # 老的 ScrollDirection 不属于这个字段，传了不会生效
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=[
                ft.Container(
                    bgcolor=theme.SURFACE,
                    border_radius=theme.RADIUS_LG,
                    padding=ft.Padding.all(16),
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row(
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[self._field, self._search_button],
                            ),
                            ft.Text(
                                "支持两种方式：粘贴 BV / av / ep / ss 链接精准空降，"
                                "或直接输入名字模糊搜索",
                                size=12,
                                color=theme.TEXT_TERTIARY,
                            ),
                        ],
                    ),
                ),
                self._notice,
                self._results,
            ],
        )

    # ------------------------------------------------------------ 对外
    @property
    def control(self) -> ft.Control:
        return self._root

    def search(self, text: str | None = None) -> None:
        query = (text if text is not None else self._field.value or "").strip()
        if not query:
            self._show_notice(
                f"先输入点什么吧～ 比如一部{self.meta.label}的名字，或者一集的链接。",
                "warning",
            )
            self._results.content = self._idle_block()
            self._page.update()
            return

        self._field.value = query
        self._show_notice("")
        self._results.content = loading_block("正在搜索…")
        self._page.update()
        # 用 asyncio.to_thread 把阻塞的 HTTP 请求丢出事件循环，
        # 请求结束后回到事件循环里更新界面。
        self._page.run_task(self._do_search, query)

    # ------------------------------------------------------------ 内部
    async def _do_search(self, query: str) -> None:
        try:
            outcome = await asyncio.to_thread(
                search_in_partition, get_api(), self.partition, query
            )
        except Exception as exc:  # 网络异常等，不让界面崩掉
            self._show_notice(f"搜索失败：{exc}", "error")
            self._results.content = empty_block("没能拿到结果", "检查一下网络后再试试")
            self._page.update()
            return

        self._render_outcome(outcome)
        self._page.update()

    def _render_outcome(self, outcome) -> None:
        if outcome.notice:
            kind = "info" if outcome.cards else "warning"
            self._show_notice(outcome.notice, kind)
        else:
            self._show_notice("")

        if not outcome.cards:
            self._results.content = empty_block(
                f"没有找到「{self.meta.label}」相关内容", self.meta.empty_text
            )
            return

        self._results.content = ft.Column(
            spacing=14,
            controls=[
                ft.Text(
                    f"找到 {len(outcome.cards)} 个结果",
                    size=13,
                    color=theme.TEXT_SECONDARY,
                ),
                ft.Row(
                    wrap=True,
                    spacing=theme.CARD_GAP,
                    run_spacing=theme.CARD_GAP,
                    controls=[
                        bangumi_card(
                            card,
                            on_click=lambda _event, c=card: self._on_open_detail(c),
                        )
                        for card in outcome.cards
                    ],
                ),
            ],
        )

    def _show_notice(self, text: str, kind: str = "info") -> None:
        if not text:
            self._notice.visible = False
            self._notice.content = None
            return
        self._notice.visible = True
        self._notice.content = notice_block(text, kind=kind)

    def _idle_block(self) -> ft.Control:
        return empty_block(
            f"在「{self.meta.label}」分区搜索", self.meta.empty_text
        )
