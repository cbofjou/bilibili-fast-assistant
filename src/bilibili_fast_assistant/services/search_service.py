"""统一搜索入口：屏蔽"关键词搜索"和"精准空降"两种方式的差异。"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..api import BiliApi, BiliError
from ..config import SEASON_TYPE_NAMES
from ..models import SearchCard
from .catalog import build_season_detail
from .input_parser import InputKind, parse_input
from .partition import Partition, get_meta
from .resolver import DirectLinkError, resolve_to_season


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    cards: tuple[SearchCard, ...] = field(default_factory=tuple)
    notice: str = ""
    from_direct_link: bool = False
    start_seconds: float | None = None

    @property
    def is_empty(self) -> bool:
        return not self.cards


def search_in_partition(api: BiliApi, partition: Partition, query: str) -> SearchOutcome:
    """在指定分区里搜索。会自动识别输入是关键词还是直达链接。"""
    meta = get_meta(partition)
    parsed = parse_input(query)

    if parsed.kind is InputKind.KEYWORD:
        cards = api.search.bangumi_cards(parsed.value, season_types=meta.season_types)
        notice = "" if cards else f"没有找到匹配的「{meta.label}」内容，换个名字试试？"
        return SearchOutcome(cards=tuple(cards), notice=notice)

    return _search_by_direct_link(api, partition, query, parsed)


def _search_by_direct_link(api, partition: Partition, query: str, parsed) -> SearchOutcome:
    meta = get_meta(partition)
    try:
        resolved = resolve_to_season(api, parsed)
    except DirectLinkError as exc:
        return SearchOutcome(notice=str(exc))
    except BiliError as exc:
        return SearchOutcome(notice=f"解析失败：{exc}")

    detail = build_season_detail(resolved.raw)

    if meta.season_types and detail.season_type not in meta.season_types:
        actual = SEASON_TYPE_NAMES.get(detail.season_type, "其它内容")
        return SearchOutcome(
            notice=f"《{detail.title}》属于「{actual}」，请先切换到「{actual}」分区再搜索。"
        )

    notice = f"已精准定位到《{detail.title}》"
    if parsed.start_seconds is not None:
        notice += f"，起播时间 {parsed.start_seconds_text}"

    return SearchOutcome(
        cards=(SearchCard.from_season(detail),),
        notice=notice,
        from_direct_link=True,
        start_seconds=parsed.start_seconds,
    )
