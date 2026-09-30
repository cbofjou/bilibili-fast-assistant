"""搜索结果卡片、选集小方块等展示组件。"""

from __future__ import annotations

import flet as ft

from ... import theme
from ...models import Episode, SearchCard
from ..images import CARD_THUMB_WIDTH, thumb


def bangumi_card(card: SearchCard, *, on_click) -> ft.Control:
    """一张番剧 / 国创卡片。点击进入详情。"""
    cover = ft.Image(
        src=thumb(card.cover, CARD_THUMB_WIDTH),
        width=theme.CARD_WIDTH,
        height=theme.COVER_HEIGHT,
        # CONTAIN 保证整张图等比完整显示；封面是 3:4，正好贴合不裁切
        fit=ft.BoxFit.CONTAIN,
        error_content=ft.Container(
            bgcolor=theme.PINK_LIGHT,
            alignment=ft.Alignment.CENTER,
            content=ft.Text("暂无封面", size=12, color=theme.TEXT_TERTIARY),
        ),
    )

    meta_row: list[ft.Control] = [
        ft.Text(card.score_text, size=12, weight=ft.FontWeight.BOLD, color=theme.PINK),
    ]
    if card.index_show:
        meta_row.append(ft.Text(card.index_show, size=12, color=theme.TEXT_SECONDARY))

    info_controls: list[ft.Control] = [
        ft.Text(
            card.title,
            size=14,
            weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY,
            # 名字再长也只占一行，超出用省略号，保证卡片高度一致
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        ft.Row(controls=meta_row, spacing=8),
    ]
    if card.meta_line:
        info_controls.append(
            ft.Text(
                card.meta_line,
                size=11,
                color=theme.TEXT_TERTIARY,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )

    return ft.Container(
        width=theme.CARD_WIDTH,
        height=theme.COVER_HEIGHT + theme.CARD_INFO_HEIGHT,
        # 打个标记，方便测试和后续做"按卡片操作"时定位
        data={"kind": "bangumi_card", "season_id": card.season_id},
        bgcolor=theme.SURFACE,
        border_radius=theme.RADIUS_LG,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        ink=True,
        on_click=on_click,
        shadow=theme.card_shadow(),
        tooltip=card.desc or card.title,
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Stack(
                    controls=[
                        ft.Container(
                            width=theme.CARD_WIDTH,
                            height=theme.COVER_HEIGHT,
                            bgcolor=theme.COVER_BG,
                            content=cover,
                        )
                    ]
                    + ([_badge(card.badge)] if card.badge else []),
                    alignment=ft.Alignment.TOP_LEFT,
                ),
                ft.Container(
                    height=theme.CARD_INFO_HEIGHT,
                    padding=ft.Padding.only(
                        left=theme.CARD_INFO_PADDING[0],
                        top=theme.CARD_INFO_PADDING[1],
                        right=theme.CARD_INFO_PADDING[2],
                        bottom=theme.CARD_INFO_PADDING[3],
                    ),
                    content=ft.Column(spacing=8, controls=info_controls),
                ),
            ],
        ),
    )


def _badge(text: str) -> ft.Control:
    return ft.Container(
        margin=ft.Margin.all(6),
        padding=ft.Padding.symmetric(vertical=2, horizontal=6),
        bgcolor=theme.BLUE,
        border_radius=4,
        content=ft.Text(text, size=10, color=ft.Colors.WHITE),
    )


def season_header(title: str, *, subtitle: str = "", is_current: bool = False) -> ft.Control:
    """详情页里每个季的标题行。"""
    title_row: list[ft.Control] = [
        ft.Text(
            title,
            size=16,
            weight=ft.FontWeight.BOLD,
            color=theme.TEXT_PRIMARY,
        )
    ]
    if is_current:
        title_row.append(
            ft.Container(
                padding=ft.Padding.symmetric(vertical=2, horizontal=8),
                bgcolor=theme.PINK_LIGHT,
                border_radius=10,
                content=ft.Text("当前", size=11, color=theme.PINK_DEEP),
            )
        )

    return ft.Row(
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=title_row
        + ([ft.Text(subtitle, size=12, color=theme.TEXT_TERTIARY)] if subtitle else []),
    )


def episode_chip(
    episode: Episode,
    *,
    on_click=None,
    selected: bool = False,
    width: int = 58,
) -> ft.Container:
    """选集面板里的一个小方块，显示集数，悬浮显示标题。"""
    label = episode.title or str(episode.number)
    chip = ft.Container(
        width=width,
        height=34,
        alignment=ft.Alignment.CENTER,
        bgcolor=theme.SURFACE,
        border=ft.Border.all(1, theme.BORDER),
        border_radius=theme.RADIUS,
        ink=True if on_click else False,
        on_click=on_click,
        tooltip=f"{episode.display_title}（{episode.duration_text}）",
        content=ft.Text(label, size=12, color=theme.TEXT_PRIMARY),
    )
    style_episode_chip(chip, selected=selected)
    return chip


def style_episode_chip(chip: ft.Container, *, selected: bool) -> None:
    """就地切换方块的选中样式。

    刻意不重建控件：重建会让整片选集列表闪一下，滚动位置也容易跳。
    """
    chip.bgcolor = theme.PINK if selected else theme.SURFACE
    chip.border = ft.Border.all(1, theme.PINK if selected else theme.BORDER)
    if isinstance(chip.content, ft.Text):
        chip.content.color = ft.Colors.WHITE if selected else theme.TEXT_PRIMARY
