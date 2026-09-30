"""统一的 HTTP 客户端。

对 B 站接口做一层薄封装：带好 UA / Referer、统一超时、统一解析 JSON、
统一在 ``code != 0`` 时抛 :class:`BiliApiError`。
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import httpx

from .. import config
from .errors import BiliApiError, BiliNetworkError, BiliRiskError, RISK_HTTP_STATUS


class BiliHttp:
    """同步 HTTP 客户端。

    之所以用同步而不是异步：Flet 的事件回调里用 ``page.run_thread`` 把
    请求丢到线程池执行，同步写法更直观，也方便写单元测试。
    """

    def __init__(
        self,
        *,
        timeout: float = config.REQUEST_TIMEOUT,
        cookies: Mapping[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
            headers={
                "User-Agent": config.USER_AGENT,
                "Referer": config.REFERER,
                "Origin": config.ORIGIN,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        if cookies:
            self.set_cookies(cookies)

    # ------------------------------------------------------------ 生命周期
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BiliHttp":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------ 登录态
    def set_cookies(self, cookies: Mapping[str, str]) -> None:
        """设置登录 Cookie（后续做三连时才需要）。"""
        for key, value in cookies.items():
            self._client.cookies.set(key, value, domain=".bilibili.com")

    def clear_cookies(self) -> None:
        """退出登录：清空本客户端持有的全部 Cookie。"""
        self._client.cookies.clear()

    def get_cookie(self, name: str) -> str:
        return self._client.cookies.get(name, domain=".bilibili.com") or ""

    def cookies_snapshot(self, names: Iterable[str] | None = None) -> dict[str, str]:
        """把 cookie jar 里的内容读出来（可按名字过滤）。"""
        wanted = set(names) if names is not None else None
        snapshot: dict[str, str] = {}
        for cookie in self._client.cookies.jar:
            if wanted is not None and cookie.name not in wanted:
                continue
            snapshot.setdefault(cookie.name, cookie.value)
        return snapshot

    # ------------------------------------------------------------ 请求
    def get(self, url: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """发 GET，返回原始响应体（不检查 code）。"""
        return self._request("GET", url, params=params)

    def resolve_redirect(self, url: str, *, max_hops: int = 5) -> str:
        """跟随短链（如 b23.tv）拿到最终地址，不下载页面正文。"""
        current = url
        for _ in range(max_hops):
            try:
                response = self._client.get(
                    current, follow_redirects=False, headers={"Accept": "*/*"}
                )
            except httpx.HTTPError as exc:
                raise BiliNetworkError(f"展开短链失败：{exc}") from exc

            location = response.headers.get("location")
            if not location or response.status_code < 300 or response.status_code >= 400:
                return str(response.url)
            current = str(httpx.URL(current).join(location))
        return current

    def post(self, url: str, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """发 POST，返回原始响应体（不检查 code）。"""
        return self._request("POST", url, data=data)

    def get_data(self, url: str, params: Mapping[str, Any] | None = None) -> Any:
        """发 GET 并返回 ``data`` / ``result``；code 非 0 时抛异常。"""
        return _unwrap(self.get(url, params), url)

    def post_data(self, url: str, data: Mapping[str, Any] | None = None) -> Any:
        """发 POST 并返回 ``data`` / ``result``；code 非 0 时抛异常。"""
        return _unwrap(self.post(url, data), url)

    # ------------------------------------------------------------ 内部
    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not url.startswith("http"):
            url = f"{config.API_BASE}/{url.lstrip('/')}"

        try:
            response = self._client.request(method, url, params=params, data=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in RISK_HTTP_STATUS:
                # 被 WAF 直接挡下，连 JSON 都没有，也得当成风控
                raise BiliRiskError(
                    status, f"HTTP {status}：请求被拦截（可能触发了风控）"
                ) from exc
            raise BiliNetworkError(f"请求 B 站失败：{exc}") from exc
        except httpx.HTTPError as exc:  # 连接、超时、非 2xx 都在这里
            raise BiliNetworkError(f"请求 B 站失败：{exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BiliNetworkError(f"B 站返回了非 JSON 内容（HTTP {response.status_code}）") from exc

        if not isinstance(payload, dict):
            raise BiliNetworkError("B 站返回了意料之外的数据结构")
        return payload


def _unwrap(payload: dict[str, Any], url: str) -> Any:
    """把 ``{"code":0, "data":...}`` 拆出 data；B 站有的接口用 result 字段。"""
    code = payload.get("code", 0)
    if code != 0:
        message = str(payload.get("message") or payload.get("msg") or "未知错误")
        raise BiliApiError(int(code), message, url=url)
    if "data" in payload:
        return payload["data"]
    if "result" in payload:
        return payload["result"]
    return None


def strip_html(text: str) -> str:
    """去掉搜索结果标题里的 ``<em class="keyword">`` 高亮标签。"""
    if not text:
        return ""
    out: list[str] = []
    skip = False
    for char in text:
        if char == "<":
            skip = True
        elif char == ">":
            skip = False
        elif not skip:
            out.append(char)
    return "".join(out)
