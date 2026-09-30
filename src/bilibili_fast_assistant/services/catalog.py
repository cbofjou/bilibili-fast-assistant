"""把 B 站的原始 season JSON 组装成 ``SeasonDetail``。

这里解决两个 B 站数据结构上的坑（见 docs 第 9 节）：

1. ``episodes[]`` 里混着"每集预告"（``section_type == 1``），必须过滤；
2. 长番的"篇章"（如"星海飞驰"）在 B 站没有结构化字段，只能靠
   ``long_title`` 的"名字 + 序号"前缀还原。
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

from ..models import (
    ArcGroup,
    Episode,
    SeasonBrief,
    SeasonDetail,
    SeasonSection,
    SeasonStat,
    season_type_name,
)

# "魔道争锋1" / "凡人风起天南1重制版" / "星海飞驰28"
_ARC_RE = re.compile(r"^(?P<name>.+?)(?P<num>\d+)(?:\s*重制版)?$")
# "第12话 海陆之间" 这种前缀先剥掉
_EP_PREFIX_RE = re.compile(r"^第\s*\d+\s*[话集回]\s*")

# 至少这么大比例的单集能解析出"名字+序号"，才认为这一季分了篇章
_ARC_MIN_RATIO = 0.9


def split_arc_label(long_title: str) -> tuple[str, int] | None:
    """``"魔道争锋1"`` -> ``("魔道争锋", 1)``；解析不出返回 None。"""
    text = _EP_PREFIX_RE.sub("", (long_title or "").strip())
    if not text:
        return None
    match = _ARC_RE.match(text)
    if not match:
        return None
    name = match.group("name").strip(" -_·")
    if len(name) < 2:
        return None
    return name, int(match.group("num"))


def group_arcs(
    episodes: Sequence[Episode],
    *,
    min_ratio: float = _ARC_MIN_RATIO,
) -> tuple[ArcGroup, ...]:
    """按 ``long_title`` 前缀把单集切成篇章。

    切不动（比如副标题式命名）时返回一个 ``name=""`` 的平铺分组。
    """
    if not episodes:
        return ()

    labels = [split_arc_label(episode.long_title) for episode in episodes]
    parsed = [label for label in labels if label]
    distinct = {name for name, _ in parsed}

    if len(parsed) < len(episodes) * min_ratio or len(distinct) < 2:
        return (ArcGroup(name="", episodes=tuple(episodes)),)

    groups: list[ArcGroup] = []
    current_name = ""
    bucket: list[Episode] = []
    for episode, label in zip(episodes, labels):
        name = label[0] if label else ""
        if bucket and name != current_name:
            groups.append(ArcGroup(name=current_name, episodes=tuple(bucket)))
            bucket = []
        current_name = name
        bucket.append(episode)
    if bucket:
        groups.append(ArcGroup(name=current_name, episodes=tuple(bucket)))

    return tuple(groups)


def build_season_detail(raw: Mapping[str, Any]) -> SeasonDetail:
    """把 ``pgc/view/web/season`` 的 ``result`` 转成 ``SeasonDetail``。"""
    season_id = _int(raw.get("season_id"))
    main_episodes = build_episodes(raw.get("episodes"))

    sections = tuple(
        SeasonSection(
            section_id=_int(item.get("id")),
            title=str(item.get("title") or ""),
            section_type=_int(item.get("type")),
            episodes=tuple(Episode.from_raw(ep) for ep in (item.get("episodes") or [])),
        )
        for item in (raw.get("section") or [])
    )

    seasons = tuple(
        SeasonBrief.from_raw(item, current_id=season_id)
        for item in (raw.get("seasons") or [])
    )

    rating = raw.get("rating") or {}
    publish = raw.get("publish") or {}
    season_type = _int(raw.get("type"))
    title = str(raw.get("season_title") or raw.get("title") or "")

    detail = SeasonDetail(
        season_id=season_id,
        media_id=_int(raw.get("media_id")),
        series_id=_int((raw.get("series") or {}).get("series_id")),
        title=title,
        type_name=season_type_name(season_type),
        season_type=season_type,
        cover=str(raw.get("cover") or "").replace("http://", "https://"),
        index_show=_index_show(main_episodes, publish),
        areas=_join_labels(raw.get("areas")),
        styles=_join_labels(raw.get("styles")),
        evaluate=str(raw.get("evaluate") or ""),
        score=_float(rating.get("score")),
        score_count=_int(rating.get("count")),
        publish_text=str(publish.get("pub_time_show") or ""),
        episodes=tuple(main_episodes),
        arcs=group_arcs(main_episodes),
        sections=sections,
        seasons=seasons,
        stat=SeasonStat.from_raw(raw.get("stat") or {}),
    )
    return _ensure_current_season(detail)


def build_episodes(raw_episodes: Any) -> list[Episode]:
    """过滤掉"每集预告"，并按集数排好序。

    长番的 ``episodes[]`` 同时混着正片（``section_type == 0``）和每集预告
    （``section_type == 1``），而且数组顺序不等于集数顺序，两个坑都要处理。
    """
    episodes = [
        Episode.from_raw(item)
        for item in (raw_episodes or [])
        if _int(item.get("section_type")) == 0
    ]
    episodes.sort(key=lambda ep: (ep.number, ep.ep_id))
    return episodes


def _ensure_current_season(detail: SeasonDetail) -> SeasonDetail:
    """``seasons[]`` 有时不含当前季，补上，保证"所有季"列表完整。"""
    if any(item.is_current for item in detail.seasons):
        return detail
    from dataclasses import replace

    current = SeasonBrief(
        season_id=detail.season_id,
        title=detail.title,
        cover=detail.cover,
        index_show=detail.index_show,
        is_current=True,
    )
    return replace(detail, seasons=(current, *detail.seasons))


def _index_show(episodes: Sequence[Episode], publish: Mapping[str, Any]) -> str:
    if not episodes:
        return "暂无剧集"
    finished = _int(publish.get("is_finish")) == 1
    last = episodes[-1].number
    if finished:
        return f"全{len(episodes)}话"
    return f"更新至第{last}话 · 共 {len(episodes)} 话"


def _join_labels(value: Any) -> str:
    """``areas`` 是 ``[{"name": "中国大陆"}]``，``styles`` 是 ``["玄幻", ...]``。"""
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable):
        parts: list[str] = []
        for item in value:
            if isinstance(item, Mapping):
                parts.append(str(item.get("name") or item.get("title") or ""))
            else:
                parts.append(str(item))
        return "/".join(part for part in parts if part)
    return str(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
