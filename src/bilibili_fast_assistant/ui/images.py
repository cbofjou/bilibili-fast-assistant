"""图片地址处理。

B 站图床（hdslb.com）支持在 URL 后拼处理参数直接拿缩略图，
例如 ``xxx.png@400w.webp`` 会把 750KB 的原图压到 30KB 左右，
列表页体验差别很大。

这里只用"只限宽度"的写法（``@400w``）：
``@400w_533h_1c`` 这种带高和 ``1c`` 的写法会让图床**按框裁切**，
封面比例一旦不是设计比例就会被切掉，所以不要用。
"""

from __future__ import annotations

_THUMB_TEMPLATE = "@{width}w.webp"

# 封面是 3:4 竖版海报（实测原图 480x640），按显示宽度的 1.8 倍取图
CARD_THUMB_WIDTH = 400
DETAIL_THUMB_WIDTH = 300


def thumb(url: str, width: int) -> str:
    """按宽度取等比缩略图；地址本身带处理参数时原样返回。"""
    if not url:
        return ""
    if url.startswith("//"):
        url = f"https:{url}"
    elif url.startswith("http://"):
        url = f"https://{url[len('http://'):]}"

    filename = url.rsplit("/", 1)[-1]
    if "@" in filename:
        return url
    return f"{url}{_THUMB_TEMPLATE.format(width=width)}"
