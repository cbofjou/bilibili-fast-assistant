"""全局配置：请求参数、接口地址、超时等常量。

这里只放"不会随 UI 变化"的东西。样式相关的常量在 ``theme`` 里。
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "bilibili-fast-assistant"
APP_TITLE = "B站快捷助手"

# ---------------------------------------------------------------- 接口地址
API_BASE = "https://api.bilibili.com"
BANGUMI_API_BASE = "https://bangumi.bilibili.com"
WEB_BASE = "https://www.bilibili.com"

# ---------------------------------------------------------------- 请求伪装
# B 站对 UA / Referer 有校验，缺失时容易触发风控（HTTP 412）。
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REFERER = f"{WEB_BASE}/"
ORIGIN = WEB_BASE

REQUEST_TIMEOUT = 10.0

# ------------------------------------------------------- 三连执行节奏
# 写操作比查询敏感得多：宁可慢，也别触发风控。
#
# 执行是**严格串行**的（单线程，一集做完才做下一集），这里再加两道闸：
# 一是任意两次写请求之间的最小间隔，避免一集的三条请求挤在一起形成突发；
# 二是每集之后的额外停顿。两者相加大约是每集 3 秒。
ACTION_REQUEST_GAP = 0.7     # 任意两次写请求之间的最小间隔（秒）
ACTION_EPISODE_PAUSE = 0.8   # 每集做完之后的额外停顿（秒）
ACTION_JITTER = 0.4          # 叠加的随机抖动，避免节奏过于规律

# 保险丝：连续这么多集"所有操作都被拦"就整批停下，别把账号往更深的限流里推
ACTION_RISK_STREAK_LIMIT = 3
# 自适应降速的上限：每撞一次风控，写请求间隔翻倍，最多到这个值
ACTION_MAX_REQUEST_GAP = 5.0


def dry_run_enabled() -> bool:
    """演练模式：只走一遍流程，不真的发请求。

    用环境变量 ``BFA_DRY_RUN=1`` 打开。给自己或用户一个"先看看会发生什么"
    的入口，尤其是投币这种不可撤销的操作。
    """
    return os.environ.get("BFA_DRY_RUN", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

# ---------------------------------------------------------------- 业务常量
# 番剧 / 影视的分类枚举，见 docs/bilibili-api-research.md 第 8 节
SEASON_TYPE_NAMES: dict[int, str] = {
    1: "番剧",
    2: "电影",
    3: "纪录片",
    4: "国创",
    5: "电视剧",
    7: "综艺",
}

# 收藏资源的类型：番剧 / 影视单集是 42
FAV_TYPE_PGC = 42

# 登录后真正用得上的 Cookie：
# SESSDATA 是登录票据，bili_jct 是写操作要用的 csrf，
# buvid3/buvid4 是设备指纹（带上能降低触发风控的概率）。
COOKIE_KEYS = (
    "SESSDATA",
    "bili_jct",
    "DedeUserID",
    "DedeUserID__ckMd5",
    "sid",
    "buvid3",
    "buvid4",
)

ASSETS_DIR = Path(__file__).parent / "assets"
