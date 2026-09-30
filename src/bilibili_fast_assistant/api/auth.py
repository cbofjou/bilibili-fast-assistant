"""登录相关接口：扫码登录 + 账号信息。

用的是 B 站**官方 Web 端扫码登录流程**（手机 App 扫一下、在手机上确认），
全程不需要用户输入账号密码，也不是逆向出来的接口。

流程：

1. ``GET passport.bilibili.com/x/passport-login/web/qrcode/generate``
   拿到 ``qrcode_key`` 和一个会被画成二维码的 ``url``
2. 轮询 ``.../qrcode/poll?qrcode_key=``
   * 86101 未扫码 / 86090 已扫码待确认 / 86038 已失效 / 0 成功
3. 成功后服务端通过 ``Set-Cookie`` 下发 SESSDATA、bili_jct 等，
   httpx 的 cookie jar 会自动收下

注意：开放平台的 OAuth ``access_token`` 是另一套凭证，
``x/web-interface/*`` 这些接口只认 Cookie，不认 Bearer token。
"""

from __future__ import annotations

from typing import Any

from .. import config
from ..models.account import (
    Account,
    QrPollResult,
    QrSession,
    parse_coin_balance,
    qr_state_from_code,
)
from ..config import COOKIE_KEYS
from .http import BiliHttp

_QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
_QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
_NAV_URL = f"{config.API_BASE}/x/web-interface/nav"
_FINGER_URL = f"{config.API_BASE}/x/frontend/finger/spi"
_COIN_URL = "https://account.bilibili.com/site/getCoin"

_QR_MESSAGES = {
    "pending": "请用 B 站手机客户端扫码",
    "scanned": "已扫码，请在手机上点「确认登录」",
    "confirmed": "登录成功",
    "expired": "二维码已失效，请刷新",
    "unknown": "登录状态未知",
}


class AuthApi:
    def __init__(self, http: BiliHttp) -> None:
        self._http = http

    # ------------------------------------------------------------ 扫码登录
    def create_qr_session(self) -> QrSession:
        data = self._http.get_data(_QR_GENERATE_URL) or {}
        key = str(data.get("qrcode_key") or "")
        url = str(data.get("url") or "")
        if not key or not url:
            raise RuntimeError("没能取到二维码，请稍后重试")
        return QrSession(qrcode_key=key, url=url)

    def poll_qr(self, qrcode_key: str) -> QrPollResult:
        data = self._http.get_data(_QR_POLL_URL, {"qrcode_key": qrcode_key}) or {}
        code = int(data.get("code") or 0)
        state = qr_state_from_code(code)
        return QrPollResult(
            state=state,
            message=str(data.get("message") or _QR_MESSAGES.get(state.value, "")),
            cookies=self._http.cookies_snapshot(COOKIE_KEYS),
        )

    # ------------------------------------------------------------ 设备指纹
    def ensure_device_cookies(self) -> dict[str, str]:
        """补上 buvid3 / buvid4，能降低后续写操作触发风控的概率。"""
        snapshot = self._http.cookies_snapshot(COOKIE_KEYS)
        if snapshot.get("buvid3"):
            return snapshot
        try:
            data = self._http.get_data(_FINGER_URL) or {}
        except Exception:
            return snapshot

        pairs = {"buvid3": data.get("b_3"), "buvid4": data.get("b_4")}
        self._http.set_cookies({k: str(v) for k, v in pairs.items() if v})
        return self._http.cookies_snapshot(COOKIE_KEYS)

    # ------------------------------------------------------------ 账号信息
    def current_account(self) -> Account | None:
        payload: dict[str, Any] = self._http.get(_NAV_URL)
        data = payload.get("data") or {}
        if not data.get("isLogin"):
            return None
        level_info = data.get("level_info") or {}
        account = Account(
            mid=int(data.get("mid") or 0),
            name=str(data.get("uname") or ""),
            face=str(data.get("face") or ""),
            level=int(level_info.get("current_level") or 0),
            coin_balance=parse_coin_balance(data.get("money")),
        )
        # nav 没给余额时再问一次专用接口，两个来源都试过才不会显示空白
        if account.coin_balance is None:
            account.coin_balance = self.fetch_coin_balance()
        return account

    def fetch_coin_balance(self) -> int | None:
        """硬币余额。数据源是 ``account.bilibili.com/site/getCoin``。"""
        try:
            payload = self._http.get(_COIN_URL)
        except Exception:
            return None
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("coin", "money", "balance"):
                if key in data:
                    return parse_coin_balance(data.get(key))
        return parse_coin_balance(data)

    def collect_cookies(self) -> dict[str, str]:
        return self._http.cookies_snapshot(COOKIE_KEYS)
