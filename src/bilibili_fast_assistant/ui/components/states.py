"""加载 / 空状态 / 提示信息的通用占位组件。"""

from __future__ import annotations

import flet as ft

from ... import theme


def loading_block(text: str = "正在加载…") -> ft.Control:
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=48, horizontal=24),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            controls=[
                ft.ProgressRing(width=26, height=26, stroke_width=3, color=theme.PINK),
                ft.Text(text, size=13, color=theme.TEXT_SECONDARY),
            ],
        ),
    )


def empty_block(title: str, hint: str = "") -> ft.Control:
    controls: list[ft.Control] = [
        ft.Text("🔍", size=40),
        ft.Text(title, size=15, color=theme.TEXT_SECONDARY),
    ]
    if hint:
        controls.append(
            ft.Text(hint, size=12, color=theme.TEXT_TERTIARY, text_align=ft.TextAlign.CENTER)
        )
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=56, horizontal=24),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10, controls=controls
        ),
    )


def notice_block(text: str, *, kind: str = "info") -> ft.Control:
    palette = {
        "info": (theme.PINK_LIGHT, theme.PINK_DEEP),
        "warning": ("#FFF7E8", theme.WARNING),
        "error": ("#FFF0F4", theme.DANGER),
        "success": ("#EEFBF2", theme.SUCCESS),
    }
    bgcolor, color = palette.get(kind, palette["info"])
    return ft.Container(
        bgcolor=bgcolor,
        border_radius=theme.RADIUS,
        padding=ft.Padding.symmetric(vertical=10, horizontal=14),
        content=ft.Text(text, size=13, color=color),
    )
