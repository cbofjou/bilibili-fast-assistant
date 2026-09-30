"""把"精准空降"输入解析成具体的 ``season_id``。

核心链路（见 docs 第 8.7 节）：

    av/BV 号 -> x/web-interface/view -> redirect_url -> ep_id -> season
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..api import BiliApi, BiliError
from .input_parser import InputKind, ParsedInput, parse_input

_EP_IN_REDIRECT_RE = re.compile(r"/bangumi/play/ep(\d+)")


class DirectLinkError(BiliError):
    """输入是直达链接，但没法解析成一部番剧 / 国创。"""


@dataclass(frozen=True, slots=True)
class ResolvedSeason:
    season_id: int
    raw: dict[str, Any]
    source: str


def resolve_to_season(api: BiliApi, parsed: ParsedInput) -> ResolvedSeason:
    """按输入类型拿整季原始数据。"""
    match parsed.kind:
        case InputKind.SEASON:
            return _from_season_id(api, int(parsed.value), "ss 号")

        case InputKind.EPISODE:
            return _from_ep_id(api, int(parsed.value), "ep 号")

        case InputKind.SHORT_LINK:
            expanded = api.http.resolve_redirect(parsed.value)
            return resolve_to_season(api, parse_input(expanded))

        case InputKind.AID:
            view = api.bangumi.video_view(aid=int(parsed.value))
            return _from_view(api, view, f"av{parsed.value}")

        case InputKind.BVID:
            view = api.bangumi.video_view(bvid=parsed.value)
            return _from_view(api, view, parsed.value)

        case InputKind.MEDIA:
            raise DirectLinkError(
                "暂不支持 media(md) 链接，请改用「ss…」季链接或「ep…」单集链接。"
            )

    raise DirectLinkError("这条内容既不是季、也不是单集，没法定位。")


# ------------------------------------------------------------------ 内部
def _from_season_id(api: BiliApi, season_id: int, source: str) -> ResolvedSeason:
    raw = api.bangumi.season(season_id=season_id)
    if not raw.get("season_id"):
        raise DirectLinkError(f"没有找到 ss{season_id} 对应的内容。")
    return ResolvedSeason(_int(raw.get("season_id")), raw, source)


def _from_ep_id(api: BiliApi, ep_id: int, source: str) -> ResolvedSeason:
    raw = api.bangumi.season(ep_id=ep_id)
    if not raw.get("season_id"):
        raise DirectLinkError(f"没有找到 ep{ep_id} 对应的内容。")
    return ResolvedSeason(_int(raw.get("season_id")), raw, source)


def _from_view(api: BiliApi, view: dict[str, Any], source: str) -> ResolvedSeason:
    redirect = str(view.get("redirect_url") or "")
    match = _EP_IN_REDIRECT_RE.search(redirect)
    if not match:
        title = view.get("title") or "这条稿件"
        raise DirectLinkError(
            f"《{title}》是普通投稿，不属于番剧 / 国创，请到「UP」分区使用。"
        )
    ep_id = int(match.group(1))
    return _from_ep_id(api, ep_id, f"{source} → ep{ep_id}")


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
