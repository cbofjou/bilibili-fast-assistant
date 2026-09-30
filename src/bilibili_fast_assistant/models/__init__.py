"""数据模型层：把 B 站返回的原始 JSON 转成结构化的、UI 友好的对象。"""

from .bangumi import (
    ArcGroup,
    Episode,
    EpisodeInteraction,
    SeasonBrief,
    SeasonDetail,
    SeasonSection,
    SeasonStat,
    SearchCard,
    duration_text,
    season_type_name,
)
from .account import Account, QrPollResult, QrSession, QrState, qr_state_from_code

__all__ = [
    "Account",
    "ArcGroup",
    "Episode",
    "EpisodeInteraction",
    "SeasonBrief",
    "SeasonDetail",
    "SeasonSection",
    "SeasonStat",
    "SearchCard",
    "QrPollResult",
    "QrSession",
    "QrState",
    "duration_text",
    "qr_state_from_code",
    "season_type_name",
]
