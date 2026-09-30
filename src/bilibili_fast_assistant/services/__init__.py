"""业务逻辑层：输入解析、分区规则、数据组装、统一搜索入口。"""

from .catalog import build_episodes, build_season_detail, group_arcs, split_arc_label
from .credentials import (
    Credentials,
    clear_credentials,
    config_dir,
    credentials_path,
    load_credentials,
    save_credentials,
)
from .input_parser import InputKind, ParsedInput, parse_input
from .partition import PARTITIONS, Partition, PartitionMeta, get_meta
from .resolver import resolve_to_season
from .search_service import SearchOutcome, search_in_partition

__all__ = [
    "InputKind",
    "PARTITIONS",
    "ParsedInput",
    "Partition",
    "PartitionMeta",
    "SearchOutcome",
    "build_season_detail",
    "build_episodes",
    "Credentials",
    "clear_credentials",
    "config_dir",
    "credentials_path",
    "load_credentials",
    "save_credentials",
    "get_meta",
    "group_arcs",
    "parse_input",
    "resolve_to_season",
    "search_in_partition",
    "split_arc_label",
]
