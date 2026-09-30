"""WBI 签名。

B 站部分接口（尤其是搜索）要求在 query 里带 ``wts`` + ``w_rid``，
否则直接返回 HTTP 412。密钥来自 ``x/web-interface/nav``，
未登录也能取到，所以不需要 Cookie 就能签名。
"""

from __future__ import annotations

import hashlib
import time
import urllib.parse
from typing import Any, Mapping

from .. import config
from .http import BiliHttp

# 官方前端里的固定置换表
_MIXIN_KEY_ENC_TAB = (
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
)

NAV_URL = f"{config.API_BASE}/x/web-interface/nav"

# 密钥多久刷新一次（秒）
_KEY_TTL = 6 * 3600


class WbiSigner:
    """负责获取并缓存 wbi 密钥，然后给参数签名。"""

    def __init__(self, http: BiliHttp) -> None:
        self._http = http
        self._mixin_key: str | None = None
        self._fetched_at = 0.0

    # ------------------------------------------------------------ 对外
    def sign(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """返回带 ``wts`` / ``w_rid`` 的新参数字典。"""
        signed = {k: v for k, v in params.items() if v is not None}
        signed["wts"] = int(time.time())

        query = urllib.parse.urlencode(
            sorted(signed.items()), quote_via=urllib.parse.quote, safe=""
        )
        signed["w_rid"] = hashlib.md5(
            f"{query}{self._get_mixin_key()}".encode()
        ).hexdigest()
        return signed

    def refresh(self) -> None:
        """强制重新拉取密钥。"""
        self._mixin_key = None
        self._fetched_at = 0.0

    # ------------------------------------------------------------ 内部
    def _get_mixin_key(self) -> str:
        fresh = self._mixin_key and (time.time() - self._fetched_at) < _KEY_TTL
        if not fresh:
            self._mixin_key = self._fetch_mixin_key()
            self._fetched_at = time.time()
        assert self._mixin_key
        return self._mixin_key

    def _fetch_mixin_key(self) -> str:
        payload = self._http.get(NAV_URL)
        wbi_img = (payload.get("data") or {}).get("wbi_img") or {}
        img_key = _filename_stem(wbi_img.get("img_url", ""))
        sub_key = _filename_stem(wbi_img.get("sub_url", ""))
        if not img_key or not sub_key:
            raise RuntimeError("没能从 nav 接口取到 wbi 密钥")

        raw = img_key + sub_key
        return "".join(raw[index] for index in _MIXIN_KEY_ENC_TAB)[:32]


def _filename_stem(url: str) -> str:
    """``.../7cd084941338484aae1ad9425b84077c.png`` -> ``7cd0...077c``"""
    if not url:
        return ""
    return url.rsplit("/", 1)[-1].split(".", 1)[0]
