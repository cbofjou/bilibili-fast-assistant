"""番剧 / 影视（PGC）相关的数据结构。

字段含义见 docs/bilibili-api-research.md。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import SEASON_TYPE_NAMES


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def season_type_name(season_type: int) -> str:
    return SEASON_TYPE_NAMES.get(season_type, "影视")


def duration_text(milliseconds: int) -> str:
    """把毫秒时长格式化成 ``24:02`` 这种形式。"""
    total_seconds = max(0, milliseconds // 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


# ------------------------------------------------------------------ 搜索卡片
@dataclass(frozen=True, slots=True)
class SearchCard:
    """搜索结果卡片。既用于关键词搜索，也用于"精准空降"解析出来的单条结果。"""

    season_id: int
    media_id: int
    title: str
    index_show: str
    cover: str
    season_type: int
    season_type_name: str
    areas: str = ""
    styles: str = ""
    desc: str = ""
    score: float = 0.0
    score_count: int = 0
    url: str = ""
    badge: str = ""

    @property
    def meta_line(self) -> str:
        """卡片上那行小字：``中国大陆 · 小说改/玄幻``。"""
        parts = [p for p in (self.areas, self.styles) if p]
        return " · ".join(parts)

    @property
    def score_text(self) -> str:
        if self.score <= 0:
            return "暂无评分"
        return f"{self.score:.1f} 分"

    @classmethod
    def from_search_result(cls, raw: dict[str, Any], *, title: str) -> "SearchCard":
        badges = raw.get("badges") or []
        badge = _as_str(badges[0].get("text")) if badges else ""
        media_score = raw.get("media_score") or {}
        return cls(
            season_id=_as_int(raw.get("season_id")),
            media_id=_as_int(raw.get("media_id")),
            title=title,
            index_show=_as_str(raw.get("index_show")),
            cover=_as_str(raw.get("cover")).replace("http://", "https://"),
            season_type=_as_int(raw.get("season_type")),
            season_type_name=_as_str(
                raw.get("season_type_name"), season_type_name(_as_int(raw.get("season_type")))
            ),
            areas=_as_str(raw.get("areas")),
            styles=_as_str(raw.get("styles")),
            desc=_as_str(raw.get("desc")),
            score=_as_float(media_score.get("score")),
            score_count=_as_int(media_score.get("user_count")),
            url=_as_str(raw.get("url")),
            badge=badge,
        )

    @classmethod
    def from_season(cls, season: "SeasonDetail") -> "SearchCard":
        """把详情页的季信息压缩成一张卡片（精准空降用）。"""
        return cls(
            season_id=season.season_id,
            media_id=season.media_id,
            title=season.title,
            index_show=season.index_show,
            cover=season.cover,
            season_type=season.season_type,
            season_type_name=season.type_name,
            areas=season.areas,
            styles=season.styles,
            desc=season.evaluate,
            score=season.score,
            score_count=season.score_count,
            url=f"https://www.bilibili.com/bangumi/play/ss{season.season_id}",
        )


# ------------------------------------------------------------------ 单集
@dataclass(frozen=True, slots=True)
class Episode:
    """一集。``aid`` 是三连接口真正需要的字段。"""

    ep_id: int
    aid: int
    bvid: str
    cid: int
    title: str
    long_title: str
    show_title: str
    duration_ms: int
    section_type: int

    @property
    def is_main(self) -> bool:
        """``section_type == 0`` 才是正片，1 是"每集预告"。"""
        return self.section_type == 0

    @property
    def duration_text(self) -> str:
        return duration_text(self.duration_ms)

    @property
    def display_title(self) -> str:
        return self.long_title or self.show_title or f"第{self.title}话"

    @property
    def number(self) -> int:
        """集数序号，用于排序；解析不出来时退化为 0。"""
        try:
            return int(self.title)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "Episode":
        return cls(
            ep_id=_as_int(raw.get("ep_id") or raw.get("id")),
            aid=_as_int(raw.get("aid")),
            bvid=_as_str(raw.get("bvid")),
            cid=_as_int(raw.get("cid")),
            title=_as_str(raw.get("title")),
            long_title=_as_str(raw.get("long_title")),
            show_title=_as_str(raw.get("show_title")),
            duration_ms=_as_int(raw.get("duration")),
            section_type=_as_int(raw.get("section_type")),
        )


@dataclass(frozen=True, slots=True)
class EpisodeInteraction:
    """当前登录用户对某一集的互动状态（来自 ``user_community``）。"""

    liked: bool = False
    coin: int = 0
    favorited: bool = False

    @property
    def has_any(self) -> bool:
        return self.liked or self.coin > 0 or self.favorited

    @classmethod
    def from_raw(cls, raw: "dict[str, Any] | None") -> "EpisodeInteraction":
        raw = raw or {}
        return cls(
            liked=_as_int(raw.get("like")) == 1,
            coin=_as_int(raw.get("coin_number")),
            favorited=_as_int(raw.get("favorite")) == 1,
        )


# ------------------------------------------------------------------ 篇章
@dataclass(frozen=True, slots=True)
class ArcGroup:
    """篇章（如"星海飞驰"）。B 站没有这个实体，是我们按 ``long_title`` 前缀还原的。

    ``name`` 为空表示这一季不划分篇章，按平铺列表展示。
    """

    name: str
    episodes: tuple[Episode, ...]

    @property
    def is_flat(self) -> bool:
        return not self.name

    @property
    def episode_range(self) -> str:
        if not self.episodes:
            return ""
        first, last = self.episodes[0], self.episodes[-1]
        if first.number == last.number:
            return f"第{first.number}话"
        return f"第{first.number}-{last.number}话 · 共 {len(self.episodes)} 话"


# ------------------------------------------------------------------ 季
@dataclass(frozen=True, slots=True)
class SeasonSection:
    """花絮 / 预告 / PV 等非正片分区。"""

    section_id: int
    title: str
    section_type: int
    episodes: tuple[Episode, ...]


@dataclass(frozen=True, slots=True)
class SeasonBrief:
    """``seasons[]`` 里的条目：同系列的其它季。"""

    season_id: int
    title: str
    cover: str
    index_show: str
    is_current: bool = False

    @classmethod
    def from_raw(cls, raw: dict[str, Any], *, current_id: int) -> "SeasonBrief":
        new_ep = raw.get("new_ep") or {}
        season_id = _as_int(raw.get("season_id"))
        return cls(
            season_id=season_id,
            title=_as_str(raw.get("season_title") or raw.get("title")),
            cover=_as_str(raw.get("cover")).replace("http://", "https://"),
            index_show=_as_str(new_ep.get("index_show")),
            is_current=season_id == current_id,
        )


@dataclass(frozen=True, slots=True)
class SeasonStat:
    views: int = 0
    danmakus: int = 0
    coins: int = 0
    favorites: int = 0
    likes: int = 0
    follow_text: str = ""

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "SeasonStat":
        return cls(
            views=_as_int(raw.get("views")),
            danmakus=_as_int(raw.get("danmakus")),
            coins=_as_int(raw.get("coins")),
            favorites=_as_int(raw.get("favorites")),
            likes=_as_int(raw.get("likes")),
            follow_text=_as_str(raw.get("follow_text")),
        )


@dataclass(frozen=True, slots=True)
class SeasonDetail:
    """一季的完整信息：包含所有正片、篇章切分、花絮分区和同系列其它季。"""

    season_id: int
    media_id: int
    series_id: int
    title: str
    type_name: str
    season_type: int
    cover: str
    index_show: str
    areas: str = ""
    styles: str = ""
    evaluate: str = ""
    score: float = 0.0
    score_count: int = 0
    publish_text: str = ""
    episodes: tuple[Episode, ...] = ()
    arcs: tuple[ArcGroup, ...] = field(default_factory=tuple)
    sections: tuple[SeasonSection, ...] = ()
    seasons: tuple[SeasonBrief, ...] = ()
    stat: SeasonStat = field(default_factory=SeasonStat)

    @property
    def episode_count(self) -> int:
        return len(self.episodes)

    @property
    def total_episodes(self) -> int:
        """整季正片数量。注意不能用接口的 ``total`` 字段（长番会返回 0 或 -1）。"""
        return len(self.episodes)
