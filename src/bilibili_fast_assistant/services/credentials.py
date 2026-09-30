"""登录凭据（Cookie）的本地存储。

设计原则：

* **只存本机**。文件放在用户配置目录（Linux 是 ``~/.config/...``），
  权限设成 600，不上传、不外发。
* **文件里不放任何账号密码**，只放 B 站下发的 Cookie。
* 也缓存一份昵称 / 头像，这样启动时不用联网就能显示"当前登录的是谁"。

``BFA_CONFIG_DIR`` 环境变量可以改配置目录，测试和便携模式都用得上。

跨平台说明：

===========  ==========================================  ==========================
平台          配置目录                                     文件保护
===========  ==========================================  ==========================
Windows       ``%APPDATA%\\bilibili-fast-assistant``       仅靠系统账户隔离
macOS         ``~/Library/Application Support/...``       ``chmod 600``
Linux/其它    ``$XDG_CONFIG_HOME`` 或 ``~/.config/...``   ``chmod 600``
===========  ==========================================  ==========================

Windows 上 ``chmod`` 没有实际意义（ACL 才管用），所以那里只是把文件放在
用户自己的 ``%APPDATA%`` 下，靠系统账户隔离。要更强的保护需要额外接
DPAPI / 系统钥匙串，目前没有做。

**为什么刻意不做加密**（别再"好心"加上）：

凭据本身就是 B 站下发的 Cookie，和浏览器里的登录态是同一个东西。
能读到这个文件的程序，同样能读到浏览器的 Cookie 存储；反过来说，
拿不到本机文件的攻击者也不会因为这个文件是明文就多出什么机会。
也就是说本地加密并不缩小实际攻击面，反而会引入"密钥存哪"的新问题。

真正的泄露途径是**用户把文件或截图发出去**，所以这里的选择是：

* 文件只放在用户自己的配置目录里，且退出登录立刻删除；
* 任何对外展示（界面、日志、错误信息）一律走 :meth:`Credentials.masked_sessdata`；
* 不做加密，也不假装做了加密。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..config import COOKIE_KEYS
from ..models.account import Account

CONFIG_ENV_VAR = "BFA_CONFIG_DIR"
APP_DIR_NAME = "bilibili-fast-assistant"
FILE_NAME = "credentials.json"


def config_dir() -> Path:
    """按平台返回配置目录；``BFA_CONFIG_DIR`` 优先级最高。"""
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return _platform_config_root() / APP_DIR_NAME


def _platform_config_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return Path(base) if base else Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg) if xdg else Path.home() / ".config"


def credentials_path() -> Path:
    return config_dir() / FILE_NAME


@dataclass(slots=True)
class Credentials:
    cookies: dict[str, str] = field(default_factory=dict)
    account: Account = field(default_factory=Account)
    saved_at: str = ""

    # ------------------------------------------------------------ 判定
    @property
    def sessdata(self) -> str:
        return self.cookies.get("SESSDATA", "")

    @property
    def csrf(self) -> str:
        """写操作要用的 csrf，就是 ``bili_jct``。"""
        return self.cookies.get("bili_jct", "")

    @property
    def is_complete(self) -> bool:
        """登录票据和 csrf 都在，才认为凭据可用。"""
        return bool(self.sessdata and self.csrf)

    def masked_sessdata(self) -> str:
        """给界面显示用的脱敏串。"""
        value = self.sessdata
        if not value:
            return ""
        if len(value) <= 10:
            return "*" * len(value)
        return f"{value[:4]}…{value[-4:]}"

    # ------------------------------------------------------------ 序列化
    def to_dict(self) -> dict[str, Any]:
        return {
            "cookies": self.cookies,
            "account": self.account.to_dict(),
            "saved_at": self.saved_at,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Credentials":
        cookies = {
            str(key): str(value)
            for key, value in (raw.get("cookies") or {}).items()
            if value
        }
        return cls(
            cookies=cookies,
            account=Account.from_dict(raw.get("account")),
            saved_at=str(raw.get("saved_at") or ""),
        )

    @classmethod
    def from_cookies(
        cls,
        cookies: Mapping[str, str],
        *,
        account: Account | None = None,
    ) -> "Credentials":
        picked = {key: str(cookies[key]) for key in COOKIE_KEYS if cookies.get(key)}
        return cls(
            cookies=picked,
            account=account or Account(),
            saved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )


# ------------------------------------------------------------------ 读写
def load_credentials() -> Credentials:
    try:
        path = credentials_path()
        if not path.is_file():
            return Credentials()
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # 文件坏了 / 目录不存在 / 拿不到 home 目录，都不该影响启动
        return Credentials()
    if not isinstance(raw, dict):
        return Credentials()
    return Credentials.from_dict(raw)


def save_credentials(credentials: Credentials) -> Path:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    _harden(directory, 0o700)

    path = credentials_path()
    payload = json.dumps(credentials.to_dict(), ensure_ascii=False, indent=2)

    # 先写临时文件再原子替换：中途崩掉也不会留下半个坏文件
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    _harden(temporary, 0o600)
    os.replace(temporary, path)
    _harden(path, 0o600)
    return path


def clear_credentials() -> bool:
    path = credentials_path()
    if not path.is_file():
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def _harden(path: Path, mode: int) -> None:
    """把权限收紧；Windows 上 chmod 基本无效，忽略即可。"""
    if sys.platform == "win32":
        return
    try:
        path.chmod(mode)
    except OSError:
        pass
