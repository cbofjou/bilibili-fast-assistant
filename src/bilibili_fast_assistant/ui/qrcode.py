"""在本地生成二维码图片。

刻意不走在线二维码服务：登录二维码里带着 ``qrcode_key``，
发到第三方服务等于把登录会话交给别人。
"""

from __future__ import annotations

import io

import qrcode

_DEFAULT_TARGET = 248


def qr_png(data: str, *, target: int = _DEFAULT_TARGET) -> bytes:
    """把文本画成 PNG 二维码，返回图片字节。"""
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # 反推每个色块的像素大小，让成品刚好接近 target，避免缩放导致锯齿
    modules = qr.modules_count + qr.border * 2
    qr.box_size = max(2, target // modules)

    image = qr.make_image(fill_color="#18191C", back_color="white").convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
