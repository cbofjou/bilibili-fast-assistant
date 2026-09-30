"""Flet 应用入口。

* ``flet run`` 会调用 :func:`main`
* 命令行脚本 ``bilibili-fast-assistant`` 会调用 :func:`run`

注意：``flet run`` 是把本文件当**独立脚本**执行的，此时它不属于任何包，
相对导入（``from .ui.app import ...``）会直接报
``attempted relative import with no known parent package``。
所以这里必须用绝对导入。
"""

from __future__ import annotations

import flet as ft

from bilibili_fast_assistant.ui.app import BiliAssistantApp


def main(page: ft.Page) -> None:
    BiliAssistantApp(page).mount()


def run() -> None:
    ft.run(main)


if __name__ == "__main__":
    run()
