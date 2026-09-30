"""配色与尺寸：整体以 B 站的粉色 + 白色为基准。"""

from __future__ import annotations

import flet as ft

# ---------------------------------------------------------------- 颜色
PINK = "#FB7299"          # B 站主粉，按钮 / 强调色
PINK_DEEP = "#D44E7D"     # 夜间模式的粉，用于 hover / 深色文字
PINK_LIGHT = "#FFF3F6"    # 极浅粉，选中背景
PINK_SOFT = "#FFE4EC"     # 次级粉，边框 / 分隔

BLUE = "#00AEEC"          # B 站蓝，链接类信息
TEXT_PRIMARY = "#18191C"
TEXT_SECONDARY = "#61666D"
TEXT_TERTIARY = "#9499A0"

SURFACE = "#FFFFFF"
BG = "#F6F7F8"
BORDER = "#E3E5E7"

SUCCESS = "#2AC864"
WARNING = "#FF7F50"
DANGER = "#F25D8E"

# ---------------------------------------------------------------- 尺寸
RADIUS = 8
RADIUS_LG = 12

# B 站的番剧 / 国创封面基本统一是 3:4 的竖版海报，
# 所以图片框也按 3:4 来，配合 BoxFit.CONTAIN 既完整又不裁切。
CARD_WIDTH = 224
COVER_HEIGHT = 300
# 标题 1 行 + 评分 1 行 + 地区风格 1 行。
# 底部特意留足空间，最后一行文字不会贴着卡片边缘。
CARD_INFO_HEIGHT = 104
CARD_INFO_PADDING = (12, 10, 12, 16)  # left, top, right, bottom
CARD_GAP = 14

# 封面留白处的底色（图片比例和框不完全一致时用得上）
COVER_BG = "#F1F2F4"
DETAIL_COVER_WIDTH = 150
DETAIL_COVER_HEIGHT = 200

CONTENT_MAX_WIDTH = 1180


def build_theme() -> ft.Theme:
    """构造 Flet 主题，统一字体与主色。"""
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=PINK,
            on_primary=ft.Colors.WHITE,
            secondary=PINK_DEEP,
            surface=SURFACE,
            on_surface=TEXT_PRIMARY,
        ),
    )


def page_padding() -> ft.Padding:
    return ft.Padding.symmetric(vertical=16, horizontal=24)


def card_shadow() -> ft.BoxShadow:
    return ft.BoxShadow(
        blur_radius=10,
        spread_radius=0,
        color="#14000000",
        offset=ft.Offset(0, 2),
    )
