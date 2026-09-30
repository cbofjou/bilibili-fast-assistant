"""详情视图：一部国创的所有季 + 每一季的所有集 + 三连选择器。"""

from __future__ import annotations

import asyncio
from typing import Callable

import flet as ft

from ... import config, theme
from ...api import get_api
from ...models import ArcGroup, Episode, SeasonBrief, SeasonDetail
from ...models.actions import EpisodeTask, TripleSelection
from ...services import build_episodes, build_season_detail, group_arcs
from ...services.executor import selected_kinds
from ..images import DETAIL_THUMB_WIDTH, thumb
from ..components import TripleActionBar, loading_block, notice_block, season_header
from ..components.cards import episode_chip, style_episode_chip
from .execution_view import ExecutionView


class DetailView:
    def __init__(
        self,
        page: ft.Page,
        season_id: int,
        *,
        on_back: Callable[[], None],
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        self._page = page
        self._season_id = season_id
        self._on_back = on_back
        self._on_finished = on_finished
        self._detail: SeasonDetail | None = None
        # season_id -> (集列表, 篇章分组)
        self._episodes_by_season: dict[int, tuple[list[Episode], tuple[ArcGroup, ...]]] = {}

        # 选集状态
        self._selected: set[int] = set()                       # 选中的 ep_id
        self._chips: dict[int, ft.Container] = {}              # ep_id -> 集数方块
        self._episodes_by_ep_id: dict[int, Episode] = {}       # ep_id -> 剧集
        self._ordered_ep_ids: list[int] = []                   # 界面上的先后顺序
        self._ep_ids_by_season: dict[int, list[int]] = {}      # season_id -> [ep_id]
        self._select_all_buttons: dict[int, ft.TextButton] = {}  # season_id -> 全选按钮
        self._summary_text: ft.Text | None = None
        self._submit_hint: ft.Text | None = None
        self._exec_view: ExecutionView | None = None

        self._action_bar = TripleActionBar(page, on_change=self._on_selection_change)
        self._content = ft.Container(content=loading_block("正在加载剧集…"))

        self._root = ft.Column(
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=[
                ft.Row(
                    controls=[
                        ft.TextButton(
                            content="← 返回搜索",
                            on_click=lambda _event: self._on_back(),
                            style=ft.ButtonStyle(
                                color=theme.PINK_DEEP,
                                padding=ft.Padding.symmetric(vertical=8, horizontal=10),
                            ),
                        )
                    ]
                ),
                self._content,
            ],
        )

    # ------------------------------------------------------------ 对外
    @property
    def control(self) -> ft.Control:
        return self._root

    def start(self) -> None:
        """开始后台加载。"""
        self._page.run_task(self._load)

    # ------------------------------------------------------------ 加载
    async def _load(self) -> None:
        api = get_api()
        try:
            raw = await asyncio.to_thread(
                api.bangumi.season, season_id=self._season_id
            )
            detail = build_season_detail(raw)
            self._episodes_by_season[detail.season_id] = (
                list(detail.episodes),
                detail.arcs,
            )

            others = [s for s in detail.seasons if s.season_id != detail.season_id]
            for index, brief in enumerate(others, start=1):
                self._set_loading(f"正在加载「{brief.title}」（{index}/{len(others)}）…")
                try:
                    raw_list = await asyncio.to_thread(
                        api.bangumi.ep_list, brief.season_id
                    )
                except Exception:  # 个别季拿不到不影响整体
                    continue
                episodes = build_episodes(raw_list.get("episodes"))
                self._episodes_by_season[brief.season_id] = (
                    episodes,
                    group_arcs(episodes),
                )

            self._detail = detail
            self._render()
        except Exception as exc:
            self._content.content = notice_block(f"加载失败：{exc}", kind="error")
        self._page.update()

    def _set_loading(self, text: str) -> None:
        self._content.content = loading_block(text)
        self._page.update()

    # ------------------------------------------------------------ 渲染
    def _render(self) -> None:
        detail = self._detail
        assert detail is not None
        # 重新渲染时重建索引，避免 _restore_detail 之后重复累积
        self._episodes_by_ep_id = {}
        self._ordered_ep_ids = []
        self._content.content = ft.Column(
            spacing=16,
            controls=[
                self._header_block(detail),
                self._action_area(),
                *self._season_blocks(detail),
            ],
        )

    # ------------------------------------------------------------ 选择与提交
    def _action_area(self) -> ft.Control:
        """三连选择器 + 提交框。

        两者之间特意留出比默认更大的间距，让"选操作"和"确认提交"在视觉上分开。
        """
        return ft.Column(
            spacing=22,
            controls=[self._action_bar.control, self._submit_box()],
        )

    def _submit_box(self) -> ft.Control:
        self._summary_text = ft.Text("", size=13, color=theme.TEXT_PRIMARY)
        self._submit_hint = ft.Text("", size=12, color=theme.DANGER)
        self._refresh_summary()

        return ft.Container(
            bgcolor=theme.SURFACE,
            border_radius=theme.RADIUS_LG,
            padding=ft.Padding.symmetric(vertical=16, horizontal=18),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        spacing=4,
                        controls=[self._summary_text, self._submit_hint],
                    ),
                    ft.Button(
                        content="提交",
                        icon=ft.Icons.SEND,
                        on_click=self._on_submit,
                        style=ft.ButtonStyle(
                            bgcolor=theme.PINK,
                            color=ft.Colors.WHITE,
                            padding=ft.Padding.symmetric(vertical=16, horizontal=28),
                            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS),
                        ),
                    ),
                ],
            ),
        )

    def _refresh_summary(self) -> None:
        if self._summary_text is None:
            return
        labels = self._action_bar.selection.action_labels()
        action_text = " · ".join(labels) if labels else "未选择操作"
        self._summary_text.value = f"已选 {len(self._selected)} 集　→　{action_text}"

    def _toggle_episode(self, ep_id: int) -> None:
        if ep_id in self._selected:
            self._selected.discard(ep_id)
        else:
            self._selected.add(ep_id)
        self._apply_chip_style(ep_id)
        self._after_selection_changed()

    def _toggle_season(self, season_id: int) -> None:
        ep_ids = self._ep_ids_by_season.get(season_id) or []
        if not ep_ids:
            return
        # 已经全选就取消全选，否则全选
        select_all = not all(ep_id in self._selected for ep_id in ep_ids)
        if select_all:
            self._selected.update(ep_ids)
        else:
            self._selected.difference_update(ep_ids)
        for ep_id in ep_ids:
            self._apply_chip_style(ep_id)
        self._after_selection_changed()

    def _apply_chip_style(self, ep_id: int) -> None:
        chip = self._chips.get(ep_id)
        if chip is not None:
            style_episode_chip(chip, selected=ep_id in self._selected)

    def _after_selection_changed(self) -> None:
        self._refresh_select_all_labels()
        self._refresh_summary()
        if self._submit_hint is not None:
            self._submit_hint.value = ""
        self._page.update()

    def _refresh_select_all_labels(self) -> None:
        """每一季的按钮按"是否已全选"显示不同文案。"""
        for season_id, button in self._select_all_buttons.items():
            ep_ids = self._ep_ids_by_season.get(season_id) or []
            all_selected = bool(ep_ids) and all(
                ep_id in self._selected for ep_id in ep_ids
            )
            button.content = "取消全选" if all_selected else "全选"

    def _on_submit(self, _event: ft.ControlEvent) -> None:
        """提交按钮。真正的请求后面再接，这里先把选择结果确认清楚。"""
        selection = self._action_bar.selection
        if not self._selected:
            self._warn_submit("还没有选中任何剧集，点集数方块或用「全选」")
            return
        if selection.is_empty:
            self._warn_submit("还没有选择要执行的操作（点赞 / 投币 / 收藏）")
            return

        if self._submit_hint is not None:
            self._submit_hint.value = ""
        self._show_submit_preview(selection)

    def _warn_submit(self, message: str) -> None:
        if self._submit_hint is not None:
            self._submit_hint.value = message
        self._page.update()

    def _show_submit_preview(self, selection: TripleSelection) -> None:
        actions = " · ".join(selection.action_labels())
        count = len(self._selected)
        # 每集大约 3 秒：三条写请求之间的间隔 + 每集停顿
        minutes = round(count * 3 / 60)
        self._page.show_dialog(
            ft.AlertDialog(
                modal=True,
                bgcolor=theme.SURFACE,
                title=ft.Text("确认执行", size=16, weight=ft.FontWeight.BOLD),
                content=ft.Column(
                    width=300,
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(f"剧集：已选 {count} 集", size=13),
                        ft.Text(f"操作：{actions}", size=13),
                        ft.Text(
                            f"请求是逐集串行发送的，每集间隔约 3 秒，"
                            f"预计需要 {minutes} 分钟左右；执行前会先检查这一集"
                            "是否已经操作过，不会重复投币。",
                            size=11,
                            color=theme.TEXT_TERTIARY,
                        ),
                        ft.Text(
                            "投币会真实消耗硬币，且不可撤销。",
                            size=11,
                            color=theme.WARNING,
                        ),
                    ],
                ),
                actions=[
                    ft.TextButton(
                        content="取消",
                        on_click=lambda _event: self._close_dialog(),
                    ),
                    ft.Button(
                        content="开始执行",
                        on_click=lambda _event: self._start_execution(selection),
                        style=ft.ButtonStyle(
                            bgcolor=theme.PINK,
                            color=ft.Colors.WHITE,
                            padding=ft.Padding.symmetric(vertical=10, horizontal=20),
                            shape=ft.RoundedRectangleBorder(radius=theme.RADIUS),
                        ),
                    ),
                ],
            )
        )

    # ------------------------------------------------------------ 执行
    def _start_execution(self, selection: TripleSelection) -> None:
        self._close_dialog()
        tasks = self._build_tasks(selection)
        if not tasks:
            self._warn_submit("没有可执行的剧集")
            return

        view = ExecutionView(
            self._page,
            on_back=self._restore_detail,
            on_finished=self._on_finished,
            dry_run=config.dry_run_enabled(),
        )
        self._exec_view = view
        self._content.content = view.control
        self._page.update()
        view.start(tasks, selection)

    def _build_tasks(self, selection: TripleSelection) -> list[EpisodeTask]:
        kinds = selected_kinds(selection)
        tasks: list[EpisodeTask] = []
        for ep_id in self._ordered_ep_ids:
            if ep_id not in self._selected:
                continue
            episode = self._episodes_by_ep_id.get(ep_id)
            if episode is None:
                continue
            tasks.append(
                EpisodeTask.create(
                    len(tasks),
                    ep_id=episode.ep_id,
                    aid=episode.aid,
                    # 第一个框显示的是集数，不是内部的 ep_id
                    number=episode.title or str(episode.number),
                    title=episode.display_title,
                    selected=kinds,
                )
            )
        return tasks

    def _restore_detail(self) -> None:
        self._exec_view = None
        if self._detail is not None:
            self._render()
            self._page.update()

    def stop(self) -> None:
        """外部导航离开时调用，避免后台还在继续跑。"""
        if self._exec_view is not None:
            self._exec_view.stop()

    def _close_dialog(self) -> None:
        try:
            self._page.pop_dialog()
        except Exception:
            return
        self._page.update()

    def _header_block(self, detail: SeasonDetail) -> ft.Control:
        info: list[ft.Control] = [
            ft.Text(detail.title, size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
        ]

        chips: list[ft.Control] = [_pill(detail.type_name, theme.PINK_LIGHT, theme.PINK_DEEP)]
        if detail.score > 0:
            chips.append(
                _pill(f"{detail.score:.1f} 分", theme.PINK_LIGHT, theme.PINK_DEEP)
            )
        chips.append(_pill(detail.index_show, theme.BG, theme.TEXT_SECONDARY))
        info.append(ft.Row(spacing=8, controls=chips))

        meta_parts = [part for part in (detail.areas, detail.styles) if part]
        if detail.publish_text:
            meta_parts.append(f"首播 {detail.publish_text}")
        if meta_parts:
            info.append(
                ft.Text(" · ".join(meta_parts), size=12, color=theme.TEXT_SECONDARY)
            )

        stat = detail.stat
        stat_text = (
            f"{_human(stat.views)} 播放 · {_human(stat.likes)} 点赞 · "
            f"{_human(stat.coins)} 投币 · {stat.follow_text or '—'}"
        )
        info.append(ft.Text(stat_text, size=12, color=theme.TEXT_TERTIARY))

        if detail.evaluate:
            info.append(
                ft.Text(
                    detail.evaluate,
                    size=12,
                    color=theme.TEXT_TERTIARY,
                    max_lines=3,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )

        return ft.Container(
            bgcolor=theme.SURFACE,
            border_radius=theme.RADIUS_LG,
            padding=ft.Padding.all(16),
            content=ft.Row(
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Image(
                        src=thumb(detail.cover, DETAIL_THUMB_WIDTH),
                        width=theme.DETAIL_COVER_WIDTH,
                        height=theme.DETAIL_COVER_HEIGHT,
                        # 同样等比完整显示，不裁切
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=theme.RADIUS,
                        error_content=ft.Container(
                            width=theme.DETAIL_COVER_WIDTH,
                            height=theme.DETAIL_COVER_HEIGHT,
                            bgcolor=theme.PINK_LIGHT,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text("暂无封面", size=12, color=theme.TEXT_TERTIARY),
                        ),
                    ),
                    ft.Column(spacing=6, expand=True, controls=info),
                ],
            ),
        )

    def _season_blocks(self, detail: SeasonDetail) -> list[ft.Control]:
        ordered = sorted(
            detail.seasons, key=lambda brief: (not brief.is_current, brief.season_id)
        )
        if not ordered:
            ordered = [
                SeasonBrief(
                    season_id=detail.season_id,
                    title=detail.title,
                    cover=detail.cover,
                    index_show=detail.index_show,
                    is_current=True,
                )
            ]

        return [
            self._season_block(brief, current=detail)
            for brief in ordered
            if brief.season_id in self._episodes_by_season
        ]

    def _season_block(self, brief: SeasonBrief, *, current: SeasonDetail) -> ft.Control:
        episodes, arcs = self._episodes_by_season[brief.season_id]
        is_current = brief.season_id == current.season_id
        self._ep_ids_by_season[brief.season_id] = [ep.ep_id for ep in episodes]

        select_all = ft.TextButton(
            content="全选",
            on_click=lambda _event, sid=brief.season_id: self._toggle_season(sid),
            style=ft.ButtonStyle(
                color=theme.PINK_DEEP,
                padding=ft.Padding.symmetric(vertical=4, horizontal=10),
            ),
        )
        self._select_all_buttons[brief.season_id] = select_all

        body: list[ft.Control] = [
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    season_header(
                        brief.title,
                        subtitle=f"{brief.index_show} · 共 {len(episodes)} 话",
                        is_current=is_current,
                    ),
                    ft.Row(
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                f"共 {len(episodes)} 话",
                                size=12,
                                color=theme.TEXT_TERTIARY,
                            ),
                            select_all,
                        ],
                    ),
                ],
            )
        ]

        for arc in arcs:
            body.append(self._arc_block(arc, show_title=not arc.is_flat))

        if is_current and current.sections:
            section_text = " · ".join(
                f"{section.title} {len(section.episodes)}"
                for section in current.sections
                if section.episodes
            )
            if section_text:
                body.append(
                    ft.Text(
                        f"另有非正片内容：{section_text}",
                        size=11,
                        color=theme.TEXT_TERTIARY,
                    )
                )

        return ft.Container(
            bgcolor=theme.SURFACE,
            border_radius=theme.RADIUS_LG,
            padding=ft.Padding.all(16),
            content=ft.Column(spacing=12, controls=body),
        )

    def _arc_block(self, arc: ArcGroup, *, show_title: bool) -> ft.Control:
        chips = ft.Row(
            wrap=True,
            spacing=8,
            run_spacing=8,
            controls=[self._build_chip(episode) for episode in arc.episodes],
        )
        if not show_title:
            return chips
        return ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(width=3, height=14, bgcolor=theme.PINK),
                        ft.Text(
                            arc.name,
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_PRIMARY,
                        ),
                        ft.Text(arc.episode_range, size=11, color=theme.TEXT_TERTIARY),
                    ],
                ),
                chips,
            ],
        )

    def _on_selection_change(self, selection: TripleSelection) -> None:
        """三连选择器变化时同步提交框里的摘要。"""
        self._refresh_summary()
        if self._submit_hint is not None:
            self._submit_hint.value = ""

    def _build_chip(self, episode: Episode) -> ft.Container:
        chip = episode_chip(
            episode,
            selected=episode.ep_id in self._selected,
            on_click=lambda _event, ep_id=episode.ep_id: self._toggle_episode(ep_id),
        )
        self._chips[episode.ep_id] = chip
        self._episodes_by_ep_id[episode.ep_id] = episode
        self._ordered_ep_ids.append(episode.ep_id)
        return chip


def _pill(text: str, bgcolor: str, color: str) -> ft.Control:
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=3, horizontal=8),
        bgcolor=bgcolor,
        border_radius=10,
        content=ft.Text(text, size=11, color=color),
    )


def _human(value: int) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}亿"
    if value >= 10_000:
        return f"{value / 10_000:.1f}万"
    return str(value)
