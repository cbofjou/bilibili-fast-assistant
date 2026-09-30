"""把用户粘贴的各种东西解析成统一的输入类型。

支持的形态（详见 docs/bilibili-api-research.md 第 8.6 / 8.7 节）：

* ``https://www.bilibili.com/bangumi/play/ss29308``      -> 季
* ``https://www.bilibili.com/bangumi/play/ep308426``      -> 集
* ``https://www.bilibili.com/bangumi/media/md28223043``   -> media
* ``https://www.bilibili.com/video/BV1GJ41157f6``         -> BV 号
* ``https://www.bilibili.com/video/av117325252529597?t=356.8`` -> av 号（精准空降）
* ``BV1GJ41157f6`` / ``av117325252529597`` / ``117325252529597`` -> 同上
* ``https://b23.tv/xxxx``                                  -> 短链，需要联网展开
* 其它文本                                                 -> 关键词

``?t=`` 是起播秒数（可带小数），和三连无关，主要用于提示用户。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qs, urlparse


class InputKind(StrEnum):
    SEASON = "season"       # ss 号
    EPISODE = "episode"     # ep 号
    MEDIA = "media"         # md 号
    AID = "aid"             # av 号 / 纯数字
    BVID = "bvid"           # BV 号
    SHORT_LINK = "short"    # b23.tv 短链，需要联网展开
    KEYWORD = "keyword"     # 文字模糊搜索


@dataclass(frozen=True, slots=True)
class ParsedInput:
    kind: InputKind
    value: str
    raw: str
    start_seconds: float | None = None
    page: int | None = None

    @property
    def is_direct_link(self) -> bool:
        """True 表示"精准空降"这类直达输入，只会命中一个结果。"""
        return self.kind is not InputKind.KEYWORD

    @property
    def start_seconds_text(self) -> str:
        if self.start_seconds is None:
            return ""
        minutes, seconds = divmod(int(self.start_seconds), 60)
        return f"{minutes}:{seconds:02d}"


_BVID_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_AVID_RE = re.compile(r"\bav(\d+)\b", re.IGNORECASE)
_SEASON_RE = re.compile(r"\bss(\d+)\b", re.IGNORECASE)
_EPISODE_RE = re.compile(r"\bep(\d+)\b", re.IGNORECASE)
_MEDIA_RE = re.compile(r"\bmd(\d+)\b", re.IGNORECASE)
_DIGITS_RE = re.compile(r"^\d+$")
_SHORT_HOSTS = ("b23.tv", "bili2233.cn")


def parse_input(text: str) -> ParsedInput:
    raw = (text or "").strip()
    if not raw:
        return ParsedInput(InputKind.KEYWORD, "", raw)

    start_seconds = _extract_start_seconds(raw)
    page = _extract_page(raw)

    lowered = raw.lower()
    if any(host in lowered for host in _SHORT_HOSTS):
        return ParsedInput(
            InputKind.SHORT_LINK, raw, raw, start_seconds=start_seconds, page=page
        )

    # 顺序很重要：BV 要先于 av 判断，避免误伤
    if match := _BVID_RE.search(raw):
        return ParsedInput(
            InputKind.BVID, match.group(1), raw, start_seconds=start_seconds, page=page
        )
    if match := _AVID_RE.search(raw):
        return ParsedInput(
            InputKind.AID, match.group(1), raw, start_seconds=start_seconds, page=page
        )
    if match := _SEASON_RE.search(raw):
        return ParsedInput(
            InputKind.SEASON, match.group(1), raw, start_seconds=start_seconds, page=page
        )
    if match := _EPISODE_RE.search(raw):
        return ParsedInput(
            InputKind.EPISODE, match.group(1), raw, start_seconds=start_seconds, page=page
        )
    if match := _MEDIA_RE.search(raw):
        return ParsedInput(
            InputKind.MEDIA, match.group(1), raw, start_seconds=start_seconds, page=page
        )
    if _DIGITS_RE.match(raw):
        # 纯数字当作 av 号处理
        return ParsedInput(
            InputKind.AID, raw, raw, start_seconds=start_seconds, page=page
        )

    return ParsedInput(InputKind.KEYWORD, raw, raw)


def _extract_start_seconds(raw: str) -> float | None:
    query = parse_qs(urlparse(raw).query)
    values = query.get("t")
    if not values:
        return None
    try:
        return float(values[0])
    except ValueError:
        return None


def _extract_page(raw: str) -> int | None:
    query = parse_qs(urlparse(raw).query)
    values = query.get("p")
    if not values:
        return None
    try:
        return int(values[0])
    except ValueError:
        return None
