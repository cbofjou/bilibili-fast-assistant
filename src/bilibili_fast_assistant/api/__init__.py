"""接口层：所有对 B 站的网络请求都收敛在这里。"""

from __future__ import annotations

from typing import Any

from .bangumi import BangumiApi
from .auth import AuthApi
from .actions import ActionApi
from .errors import (
    BiliApiError,
    BiliError,
    BiliNetworkError,
    BiliRiskError,
    is_risk_error,
)
from .http import BiliHttp, strip_html
from .search import (
    SEARCH_TYPE_BANGUMI,
    SEARCH_TYPE_FT,
    SEARCH_TYPE_VIDEO,
    SearchApi,
)
from .wbi import WbiSigner


class BiliApi:
    """把各个子模块接口聚合成一个门面，全应用共用一个连接池。"""

    def __init__(self, cookies: dict[str, str] | None = None) -> None:
        self.http = BiliHttp(cookies=cookies)
        self._signer = WbiSigner(self.http)
        self.search = SearchApi(self.http, self._signer)
        self.bangumi = BangumiApi(self.http)
        self.auth = AuthApi(self.http)
        self.actions = ActionApi(self.http)

    def set_cookies(self, cookies: dict[str, str]) -> None:
        self.http.set_cookies(cookies)
        self._signer.refresh()

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "BiliApi":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """给临时探索用：直接打一个接口并返回 data。"""
        return self.http.get_data(url, params)


_default_api: BiliApi | None = None


def get_api() -> BiliApi:
    """进程级单例，避免每个视图各建一个 HTTP 连接池。"""
    global _default_api
    if _default_api is None:
        _default_api = BiliApi()
    return _default_api


__all__ = [
    "BiliApi",
    "BiliApiError",
    "BiliError",
    "BiliHttp",
    "BiliNetworkError",
    "BiliRiskError",
    "BangumiApi",
    "AuthApi",
    "ActionApi",
    "SEARCH_TYPE_BANGUMI",
    "SEARCH_TYPE_FT",
    "SEARCH_TYPE_VIDEO",
    "SearchApi",
    "WbiSigner",
    "is_risk_error",
    "get_api",
    "strip_html",
]
