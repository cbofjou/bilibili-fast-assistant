"""番剧 / 影视（PGC）接口。

全部为只读接口，不需要登录态，也不需要 WBI 签名。
"""

from __future__ import annotations

from typing import Any

from .. import config
from ..models.bangumi import EpisodeInteraction
from .http import BiliHttp

_SEASON_URL = f"{config.API_BASE}/pgc/view/web/season"
_EP_LIST_URL = f"{config.API_BASE}/pgc/view/web/ep/list"
_EPISODE_INFO_URL = f"{config.API_BASE}/pgc/season/episode/web/info"
_VIEW_URL = f"{config.API_BASE}/x/web-interface/view"


class BangumiApi:
    def __init__(self, http: BiliHttp) -> None:
        self._http = http

    # ------------------------------------------------------------ 整季结构
    def season(
        self,
        *,
        season_id: int | None = None,
        ep_id: int | None = None,
    ) -> dict[str, Any]:
        """按季号或集号拿整季结构（两个参数二选一，传 ep_id 返回的仍是整季）。"""
        if season_id is None and ep_id is None:
            raise ValueError("season_id 和 ep_id 至少要给一个")
        params: dict[str, Any] = {}
        if season_id is not None:
            params["season_id"] = season_id
        else:
            params["ep_id"] = ep_id
        return self._http.get_data(_SEASON_URL, params) or {}

    def ep_list(self, season_id: int) -> dict[str, Any]:
        """只取剧集列表，比 season 接口轻量得多。"""
        return self._http.get_data(_EP_LIST_URL, {"season_id": season_id}) or {}

    # ------------------------------------------------------------ 单集
    def episode_info(self, ep_id: int) -> dict[str, Any]:
        """单集的统计 + 当前登录用户的互动状态（``user_community``）。"""
        return self._http.get_data(_EPISODE_INFO_URL, {"ep_id": ep_id}) or {}

    def episode_interaction(self, ep_id: int) -> EpisodeInteraction:
        """当前登录用户对该集的点赞 / 投币 / 收藏状态。"""
        info = self.episode_info(ep_id)
        return EpisodeInteraction.from_raw((info or {}).get("user_community"))

    def video_view(self, *, aid: int | None = None, bvid: str | None = None) -> dict[str, Any]:
        """稿件详情。番剧单集也能查，关键在于返回里的 ``redirect_url``。"""
        params: dict[str, Any] = {}
        if aid is not None:
            params["aid"] = aid
        elif bvid:
            params["bvid"] = bvid
        else:
            raise ValueError("aid 和 bvid 至少要给一个")
        return self._http.get_data(_VIEW_URL, params) or {}
