"""搜索相关接口。

B 站搜索分成三条独立通道（见 docs/bilibili-api-research.md 第 8 节）：

* ``media_bangumi`` —— 番剧 + 国创
* ``media_ft``      —— 电影 / 电视剧 / 纪录片 / 综艺
* ``video``         —— UP 主投稿

搜索接口必须带 WBI 签名，否则番剧 / 影视通道会直接返回 HTTP 412。
"""

from __future__ import annotations

from typing import Any, Iterable

from .. import config
from ..models import SearchCard
from .http import BiliHttp, strip_html
from .wbi import WbiSigner

SEARCH_TYPE_BANGUMI = "media_bangumi"
SEARCH_TYPE_FT = "media_ft"
SEARCH_TYPE_VIDEO = "video"

_SEARCH_URL = f"{config.API_BASE}/x/web-interface/wbi/search/type"


class SearchApi:
    def __init__(self, http: BiliHttp, signer: WbiSigner) -> None:
        self._http = http
        self._signer = signer

    # ------------------------------------------------------------ 原始结果
    def raw(
        self,
        keyword: str,
        *,
        search_type: str = SEARCH_TYPE_BANGUMI,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """返回某一通道的原始结果列表。"""
        keyword = keyword.strip()
        if not keyword:
            return []

        params = self._signer.sign(
            {"search_type": search_type, "keyword": keyword, "page": page}
        )
        data = self._http.get_data(_SEARCH_URL, params) or {}
        # 没有结果时 result 可能是 null
        return list(data.get("result") or [])

    # ------------------------------------------------------------ 结构化结果
    def bangumi_cards(
        self,
        keyword: str,
        *,
        season_types: Iterable[int] | None = None,
        page: int = 1,
    ) -> list[SearchCard]:
        """搜索番剧 / 国创，并按 ``season_type`` 过滤。

        ``media_bangumi`` 通道同时包含番剧(1)和国创(4)，只能靠 season_type 区分。
        """
        wanted = set(season_types) if season_types else None
        cards: list[SearchCard] = []
        for item in self.raw(keyword, search_type=SEARCH_TYPE_BANGUMI, page=page):
            season_type = int(item.get("season_type") or 0)
            if wanted is not None and season_type not in wanted:
                continue
            cards.append(
                SearchCard.from_search_result(item, title=strip_html(item.get("title", "")))
            )
        return cards
