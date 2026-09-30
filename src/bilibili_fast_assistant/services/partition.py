"""顶部三个分区：国创 / 番剧 / UP。

这三个分区的视频组织方式不同，所以搜索入口和详情页也分开：

* 国创、番剧：PGC 季 -> 集，用 ``media_bangumi`` 搜索通道，靠 season_type 区分
* UP：UGC 稿件 / 合集，用 ``video`` 搜索通道
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..api import SEARCH_TYPE_BANGUMI, SEARCH_TYPE_VIDEO


class Partition(StrEnum):
    GUOCHUANG = "guochuang"
    BANGUMI = "bangumi"
    UP = "up"


@dataclass(frozen=True, slots=True)
class PartitionMeta:
    key: Partition
    label: str
    icon: str
    search_type: str
    season_types: tuple[int, ...] | None
    enabled: bool
    hint: str
    empty_text: str


PARTITIONS: tuple[PartitionMeta, ...] = (
    PartitionMeta(
        key=Partition.GUOCHUANG,
        label="国创",
        icon="🎋",
        search_type=SEARCH_TYPE_BANGUMI,
        season_types=(4,),
        enabled=True,
        hint="粘贴 BV / av / ep / ss 链接精准空降，或直接输入国创名字模糊搜索",
        empty_text="试试「凡人修仙传」「伍六七」这种名字，或直接粘贴一集链接",
    ),
    PartitionMeta(
        key=Partition.BANGUMI,
        label="番剧",
        icon="🌸",
        search_type=SEARCH_TYPE_BANGUMI,
        season_types=(1,),
        enabled=False,
        hint="番剧分区开发中",
        empty_text="番剧搜索稍后开放",
    ),
    PartitionMeta(
        key=Partition.UP,
        label="UP",
        icon="📺",
        search_type=SEARCH_TYPE_VIDEO,
        season_types=None,
        enabled=False,
        hint="UP 分区开发中",
        empty_text="UP 投稿搜索稍后开放",
    ),
)

_BY_KEY = {meta.key: meta for meta in PARTITIONS}


def get_meta(partition: Partition) -> PartitionMeta:
    return _BY_KEY[partition]
