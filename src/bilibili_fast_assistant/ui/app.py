"""应用外壳：顶部品牌区 + 分区栏 + 内容区。

导航是手写的（不依赖路由库），只维护两个状态：

* 当前分区（国创 / 番剧 / UP）
* 当前内容区是某个分区的搜索页，还是一部作品的详情页

这样切换分区时各自的搜索状态都能保留。
"""

from __future__ import annotations

import flet as ft

from .. import config, theme
from ..models import SearchCard
from ..services import PARTITIONS, Partition, PartitionMeta, get_meta
from .components import AccountBar, empty_block
from .views import DetailView, SearchView


class BiliAssistantApp:
    def __init__(self, page: ft.Page) -> None:
        self._page = page
        self._active = Partition.GUOCHUANG
        self._detail_view: DetailView | None = None
        self._account_bar = AccountBar(page, on_change=self._on_account_change)
        # 顶部那行字的占位，登录后会换成硬币余额
        self._header_slot = ft.Container()

        # 每个分区一个搜索视图实例，切换回来时结果还在
        self._search_views: dict[Partition, SearchView] = {
            meta.key: SearchView(page, meta.key, on_open_detail=self._open_detail)
            for meta in PARTITIONS
        }

        self._partition_bar = ft.Row(spacing=10)
        self._body = ft.Container(expand=True)
        self._root = self._build_root()

    # ------------------------------------------------------------ 挂载
    def mount(self) -> None:
        page = self._page
        page.title = config.APP_TITLE
        page.theme = theme.build_theme()
        page.bgcolor = theme.BG
        page.padding = 0
        page.add(self._root)
        self._switch(self._active)
        self._account_bar.refresh()

    # ------------------------------------------------------------ 骨架
    def _build_root(self) -> ft.Control:
        self._header_slot.content = self._header_slot_content()
        header = ft.Container(
            bgcolor=theme.SURFACE,
            padding=ft.Padding.symmetric(vertical=14, horizontal=24),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                "哔哩哔哩",
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                color=theme.PINK,
                            ),
                            ft.Text(
                                "快捷助手",
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            self._header_slot,
                            self._account_bar.control,
                        ],
                    ),
                    self._partition_bar,
                ],
            ),
        )
        return ft.Column(
            spacing=0,
            expand=True,
            controls=[
                header,
                ft.Divider(height=1, thickness=1, color=theme.BORDER),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(vertical=16, horizontal=24),
                    content=self._body,
                ),
            ],
        )

    # ------------------------------------------------------------ 导航
    def _on_account_change(self, _account) -> None:
        self._header_slot.content = self._header_slot_content()
        self._page.update()

    def _header_slot_content(self) -> ft.Control:
        """未登录显示标语；登录后换成硬币余额。"""
        account = self._account_bar.account
        if self._account_bar.is_logged_in and account.coin_balance is not None:
            return ft.Row(
                tight=True,
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.MONETIZATION_ON, size=15, color=theme.PINK),
                    ft.Text(
                        f"硬币 {account.coin_balance}",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=theme.TEXT_SECONDARY,
                    ),
                ],
            )
        return ft.Text(
            "给一部动漫批量点赞 · 投币 · 收藏",
            size=12,
            color=theme.TEXT_TERTIARY,
        )

    def _switch(self, partition: Partition) -> None:
        self._stop_detail()
        self._active = partition
        self._render_partition_bar()

        meta = get_meta(partition)
        if meta.enabled:
            self._body.content = self._search_views[partition].control
        else:
            self._body.content = self._coming_soon(meta)
        self._page.update()

    def _open_detail(self, card: SearchCard) -> None:
        self._stop_detail()
        view = DetailView(
            self._page,
            card.season_id,
            on_back=lambda: self._switch(self._active),
            on_finished=self._account_bar.refresh,
        )
        self._detail_view = view
        self._body.content = view.control
        self._page.update()
        view.start()

    def _stop_detail(self) -> None:
        """离开详情页时，别让后台的三连任务继续跑。"""
        if self._detail_view is not None:
            self._detail_view.stop()
            self._detail_view = None

    # ------------------------------------------------------------ 分区栏
    def _render_partition_bar(self) -> None:
        self._partition_bar.controls = [self._pill(meta) for meta in PARTITIONS]

    def _pill(self, meta: PartitionMeta) -> ft.Control:
        active = meta.key == self._active
        color = ft.Colors.WHITE if active else theme.TEXT_PRIMARY
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=8, horizontal=18),
            bgcolor=theme.PINK if active else theme.SURFACE,
            border=ft.Border.all(1, theme.PINK if active else theme.BORDER),
            border_radius=20,
            ink=True,
            on_click=lambda _event, key=meta.key: self._switch(key),
            tooltip=meta.hint,
            content=ft.Row(
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(meta.icon, size=14),
                    ft.Text(
                        meta.label,
                        size=14,
                        color=color,
                        weight=ft.FontWeight.BOLD if active else None,
                    ),
                ],
            ),
        )

    def _coming_soon(self, meta: PartitionMeta) -> ft.Control:
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=empty_block(
                f"「{meta.label}」分区正在开发中",
                "先把「国创」分区的搜索和详情做扎实，随后再接入这个分区。",
            ),
        )
