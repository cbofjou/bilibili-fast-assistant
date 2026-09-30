"""把执行过程中的失败原因写进文件。

文件放在和凭据同一个配置目录下，方便出问题之后回头查。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import APP_TITLE
from .credentials import config_dir

LOG_NAME = "failures.log"


def failure_log_path() -> Path:
    return config_dir() / LOG_NAME


def record_run_start(total_episodes: int, actions: str) -> Path:
    """每批开跑前写一行抬头，方便把不同批次分开。"""
    line = (
        f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} "
        f"{APP_TITLE} 执行 {total_episodes} 集 · {actions} =====\n"
    )
    return _append(line)


def record_failure(
    *,
    ep_id: int,
    title: str,
    action: str,
    message: str,
) -> Path:
    line = (
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ep{ep_id} 《{title}》 "
        f"{action} 失败：{message}\n"
    )
    return _append(line)


def _append(text: str) -> Path:
    path = failure_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    return path
