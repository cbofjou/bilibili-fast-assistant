"""扫码登录相关的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


def parse_coin_balance(value: Any) -> int | None:
    """硬币余额收敛成整数；接口偶尔给字符串或浮点（如 ``"88.0"``）。"""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class Account:
    """登录后的账号摘要。"""

    mid: int = 0
    name: str = ""
    face: str = ""
    level: int = 0
    coin_balance: int | None = None

    @property
    def display_name(self) -> str:
        return self.name or (f"UID {self.mid}" if self.mid else "已登录")

    def to_dict(self) -> dict[str, Any]:
        return {
            "mid": self.mid,
            "name": self.name,
            "face": self.face,
            "level": self.level,
            "coin_balance": self.coin_balance,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "Account":
        raw = raw or {}
        return cls(
            mid=int(raw.get("mid") or 0),
            name=str(raw.get("name") or ""),
            face=str(raw.get("face") or ""),
            level=int(raw.get("level") or 0),
            coin_balance=parse_coin_balance(raw.get("coin_balance")),
        )


class QrState(StrEnum):
    PENDING = "pending"        # 86101 还没扫
    SCANNED = "scanned"        # 86090 扫了但没点确认
    CONFIRMED = "confirmed"    # 0 登录成功
    EXPIRED = "expired"        # 86038 二维码过期
    UNKNOWN = "unknown"


# B 站扫码轮询的状态码
_STATE_BY_CODE: dict[int, QrState] = {
    0: QrState.CONFIRMED,
    86038: QrState.EXPIRED,
    86090: QrState.SCANNED,
    86101: QrState.PENDING,
}


def qr_state_from_code(code: int) -> QrState:
    return _STATE_BY_CODE.get(code, QrState.UNKNOWN)


@dataclass(frozen=True, slots=True)
class QrSession:
    """一次扫码登录会话。``url`` 会被画成二维码给用户扫。"""

    qrcode_key: str
    url: str


@dataclass(frozen=True, slots=True)
class QrPollResult:
    state: QrState
    message: str = ""
    cookies: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_done(self) -> bool:
        """成功或失败，都不需要继续轮询了。"""
        return self.state in (QrState.CONFIRMED, QrState.EXPIRED)
