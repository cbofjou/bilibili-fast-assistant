"""三连的**写**接口：点赞、投币、收藏。

全部需要登录 Cookie，并且 ``csrf`` 参数必须是 Cookie 里的 ``bili_jct``。

接口细节见 docs/bilibili-api-research.md 第 5 节，其中收藏要特别注意：
番剧 / 影视单集在收藏接口里的资源类型是 ``type=42``（``type=2`` 是普通稿件），
而且必须给一个收藏夹 id。
"""

from __future__ import annotations

from typing import Any, Sequence

from .. import config
from .errors import BiliApiError
from .http import BiliHttp

_LIKE_URL = f"{config.API_BASE}/x/web-interface/archive/like"
_COIN_URL = f"{config.API_BASE}/x/web-interface/coin/add"
_FAV_DEAL_URL = f"{config.API_BASE}/x/v3/fav/resource/deal"
_FAV_LIST_URL = f"{config.API_BASE}/x/v3/fav/folder/created/list-all"

# 点赞时前端把 65006 当作"已经赞过"，不算硬失败
ALREADY_LIKED_CODE = 65006


class ActionApi:
    def __init__(self, http: BiliHttp) -> None:
        self._http = http

    # ------------------------------------------------------------ 前置条件
    @property
    def csrf(self) -> str:
        """写操作必需，取自 Cookie 里的 ``bili_jct``。"""
        token = self._http.get_cookie("bili_jct")
        if not token:
            raise BiliApiError(-101, "缺少登录凭据（bili_jct），请先扫码登录")
        return token

    @property
    def user_mid(self) -> int:
        raw = self._http.get_cookie("DedeUserID")
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise BiliApiError(-101, "缺少登录凭据（DedeUserID），请先扫码登录") from None

    # ------------------------------------------------------------ 写操作
    def like(self, aid: int, *, like: bool = True) -> None:
        """点赞 / 取消点赞。"""
        self._http.post_data(
            _LIKE_URL,
            {"aid": aid, "like": 1 if like else 2, "csrf": self.csrf},
        )

    def add_coin(self, aid: int, *, count: int = 1, also_like: bool = False) -> None:
        """投币。``count`` 只能是 1 或 2，每个稿件累计上限是 2。"""
        if count not in (1, 2):
            raise ValueError("投币数量只能是 1 或 2")
        self._http.post_data(
            _COIN_URL,
            {
                "aid": aid,
                "multiply": count,
                # 点赞由独立请求处理，这里不让服务端顺带点赞，避免重复
                "select_like": 1 if also_like else 0,
                "csrf": self.csrf,
            },
        )

    def favorite(self, aid: int, *, media_ids: Sequence[int]) -> None:
        """收藏到指定收藏夹。番剧单集的资源类型固定是 42。"""
        if not media_ids:
            raise ValueError("收藏需要一个收藏夹 id")
        self._http.post_data(
            _FAV_DEAL_URL,
            {
                "rid": aid,
                "type": config.FAV_TYPE_PGC,
                "add_media_ids": ",".join(str(int(m)) for m in media_ids),
                "del_media_ids": "",
                "platform": "web",
                "csrf": self.csrf,
            },
        )

    # ------------------------------------------------------------ 收藏夹
    def favorite_folders(
        self,
        *,
        resource_id: int = 0,
        resource_type: int = config.FAV_TYPE_PGC,
    ) -> list[dict[str, Any]]:
        data = self._http.get_data(
            _FAV_LIST_URL,
            {
                "up_mid": self.user_mid,
                "rid": resource_id,
                "type": resource_type,
            },
        )
        return list((data or {}).get("list") or [])

    def default_favorite_folder_id(self) -> int | None:
        """默认收藏夹的 id。

        B 站前端对 ``attr`` 的解读是：``isPrivate = attr % 2``，
        右移一位后 ``isDefault = attr % 2 == 0``。
        """
        for folder in self.favorite_folders():
            try:
                attr = int(folder.get("attr") or 0)
            except (TypeError, ValueError):
                continue
            if (attr >> 1) % 2 == 0 and folder.get("id"):
                return int(folder["id"])
        return None
