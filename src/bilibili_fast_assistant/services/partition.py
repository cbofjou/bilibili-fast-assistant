"""顶部分区：国创 / 番剧。

两个分区都是 PGC「季 -> 集」的结构，走同一个 ``media_bangumi`` 搜索通道，
只靠 ``season_type`` 区分（国创 = 4，番剧 = 1），所以搜索、详情、批量三连
的代码完全共用。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..api import SEARCH_TYPE_BANGUMI


class Partition(StrEnum):
    GUOCHUANG = "guochuang"
    BANGUMI = "bangumi"


@dataclass(frozen=True, slots=True)
class PartitionMeta:
    key: Partition
    label: str
    icon: str
    search_type: str
    season_types: tuple[int, ...]
    hint: str
    empty_text: str


PARTITIONS: tuple[PartitionMeta, ...] = (
    PartitionMeta(
        key=Partition.GUOCHUANG,
        label="国创",
        icon="🎋",
        search_type=SEARCH_TYPE_BANGUMI,
        season_types=(4,),
        hint="粘贴 BV / av / ep / ss 链接精准空降，或直接输入国创名字模糊搜索",
        empty_text="试试「凡人修仙传」「伍六七」这种名字，或直接粘贴一集链接",
    ),
    PartitionMeta(
        key=Partition.BANGUMI,
        label="番剧",
        icon="🌸",
        search_type=SEARCH_TYPE_BANGUMI,
        season_types=(1,),
        hint="粘贴 BV / av / ep / ss 链接精准空降，或直接输入番剧名字模糊搜索",
        empty_text="试试「葬送的芙莉莲」「间谍过家家」这种名字，或直接粘贴一集链接",
    ),
)

_BY_KEY = {meta.key: meta for meta in PARTITIONS}


def get_meta(partition: Partition) -> PartitionMeta:
    return _BY_KEY[partition]
