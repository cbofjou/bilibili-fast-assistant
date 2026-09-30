"""顶部的账号区：扫码登录 / 显示当前账号 / 退出登录。"""

from __future__ import annotations

import asyncio
from typing import Callable

import flet as ft

from ... import theme
from ...api import get_api
from ...models.account import Account, QrSession, QrState
from ...services.credentials import (
    Credentials,
    clear_credentials,
    load_credentials,
    save_credentials,
)
from ..images import DETAIL_THUMB_WIDTH, thumb
from ..qrcode import qr_png

_POLL_INTERVAL = 2.0


class AccountBar:
    def __init__(
        self,
        page: ft.Page,
        *,
        on_change: Callable[[Account | None], None] | None = None,
    ) -> None:
        self._page = page
        self._on_change = on_change
        self._api = get_api()
        self._credentials = load_credentials()
        self._account = self._credentials.account if self._credentials.is_complete else Account()

        # 扫码对话框的状态
        self._stop_poll = True
        self._status = ft.Text("", size=13, color=theme.TEXT_SECONDARY)
        self._qr_image = ft.Image(
            src="",
            width=248,
            height=248,
            semantics_label="登录二维码",
        )
        self._dialog: ft.AlertDialog | None = None

        self._apply_cookies()
        self._root = ft.Container()
        self._render(schedule=False)

    # ------------------------------------------------------------ 对外
    @property
    def control(self) -> ft.Control:
        return self._root

    @property
    def account(self) -> Account:
        return self._account

    @property
    def is_logged_in(self) -> bool:
        return self._credentials.is_complete

    def refresh(self) -> None:
        """后台重新拉一次账号信息（昵称 / 头像 / **硬币余额**）。

        投币会消耗硬币，所以每批三连跑完都要调它一次，否则顶部一直显示旧余额。
        """
        if not self.is_logged_in:
            return
        self._page.run_task(self._refresh_account)

    # ------------------------------------------------------------ 渲染
    def _render(self, *, schedule: bool = True) -> None:
        self._root.content = (
            self._account_row() if self.is_logged_in else self._login_button()
        )
        if schedule:
            self._page.update()

    def _login_button(self) -> ft.Control:
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=7, horizontal=16),
            bgcolor=theme.PINK,
            border_radius=18,
            ink=True,
            on_click=lambda _event: self.open_login_dialog(),
            tooltip="用手机哔哩哔哩扫码登录，不需要输入账号密码",
            content=ft.Row(
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.QR_CODE, size=16, color=ft.Colors.WHITE),
                    ft.Text("扫码登录", size=13, color=ft.Colors.WHITE),
                ],
            ),
        )

    def _account_row(self) -> ft.Control:
        face = thumb(self._account.face, DETAIL_THUMB_WIDTH) if self._account.face else ""
        avatar: ft.Control = (
            ft.Image(src=face, width=28, height=28, fit=ft.BoxFit.COVER)
            if face
            else ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=28, color=theme.PINK)
        )
        subtitle = f"UID {self._account.mid}" if self._account.mid else "已登录"
        return ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=28,
                    height=28,
                    border_radius=14,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    bgcolor=theme.PINK_LIGHT,
                    content=avatar,
                ),
                ft.Column(
                    spacing=0,
                    controls=[
                        ft.Text(
                            self._account.display_name,
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color=theme.TEXT_PRIMARY,
                        ),
                        ft.Text(subtitle, size=10, color=theme.TEXT_TERTIARY),
                    ],
                ),
                ft.TextButton(
                    content="退出",
                    on_click=self._logout,
                    style=ft.ButtonStyle(
                        color=theme.TEXT_TERTIARY,
                        padding=ft.Padding.symmetric(vertical=4, horizontal=8),
                    ),
                ),
            ],
        )

    # ------------------------------------------------------------ 登录
    def open_login_dialog(self) -> None:
        self._stop_poll = True  # 停掉可能还在跑的上一轮
        self._status.value = "正在获取二维码…"
        self._status.color = theme.TEXT_SECONDARY
        self._qr_image.src = ""

        self._dialog = ft.AlertDialog(
            modal=True,
            bgcolor=theme.SURFACE,
            title=ft.Text("扫码登录 B 站", size=16, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                width=280,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=260,
                        height=260,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=theme.COVER_BG,
                        border_radius=theme.RADIUS,
                        content=self._qr_image,
                    ),
                    self._status,
                    ft.Text(
                        "用哔哩哔哩手机客户端扫码，全程不用输入账号密码。\n"
                        "登录凭据只保存在本机，不会上传到任何服务器。",
                        size=11,
                        color=theme.TEXT_TERTIARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
            actions=[
                ft.TextButton(content="刷新二维码", on_click=self._refresh_qr),
                ft.TextButton(content="关闭", on_click=lambda _event: self._close_dialog()),
            ],
        )
        self._page.show_dialog(self._dialog)
        self._page.run_task(self._start_login)

    def _refresh_qr(self, _event: ft.ControlEvent) -> None:
        self._stop_poll = True
        self._page.run_task(self._start_login)

    def _close_dialog(self) -> None:
        self._stop_poll = True
        try:
            self._page.pop_dialog()
        except Exception:
            return
        self._page.update()

    async def _start_login(self) -> None:
        self._stop_poll = False
        try:
            session = await asyncio.to_thread(self._api.auth.create_qr_session)
        except Exception as exc:
            self._set_status(f"获取二维码失败：{exc}", error=True)
            return

        try:
            png = await asyncio.to_thread(qr_png, session.url)
        except Exception as exc:
            self._set_status(f"生成二维码失败：{exc}", error=True)
            return

        self._qr_image.src = png
        self._set_status("请用 B 站手机客户端扫码")
        await self._poll(session)

    async def _poll(self, session: QrSession) -> None:
        while not self._stop_poll:
            await asyncio.sleep(_POLL_INTERVAL)
            if self._stop_poll:
                return
            try:
                result = await asyncio.to_thread(
                    self._api.auth.poll_qr, session.qrcode_key
                )
            except Exception as exc:
                self._set_status(f"状态查询失败：{exc}", error=True)
                return

            if result.state is QrState.CONFIRMED:
                await self._on_confirmed()
                return
            if result.state is QrState.EXPIRED:
                self._set_status("二维码已失效，点「刷新二维码」重试", error=True)
                return
            self._set_status(result.message or "等待扫码…")

    async def _on_confirmed(self) -> None:
        self._stop_poll = True
        self._set_status("登录成功，正在保存…")
        try:
            cookies = await asyncio.to_thread(self._api.auth.ensure_device_cookies)
            account = await asyncio.to_thread(self._api.auth.current_account)
        except Exception as exc:
            self._set_status(f"保存登录状态失败：{exc}", error=True)
            return

        credentials = Credentials.from_cookies(cookies, account=account or Account())
        try:
            save_credentials(credentials)
        except OSError as exc:
            self._set_status(f"写入本地文件失败：{exc}", error=True)
            return

        self._credentials = credentials
        self._account = credentials.account
        self._apply_cookies()
        self._close_dialog()
        self._render()
        self._snack(f"已登录：{self._account.display_name}")
        self._notify()

    # ------------------------------------------------------------ 退出
    def _logout(self, _event: ft.ControlEvent) -> None:
        clear_credentials()
        self._api.http.clear_cookies()
        self._credentials = Credentials()
        self._account = Account()
        self._render()
        self._snack("已退出登录，本地凭据已删除")
        self._notify()

    # ------------------------------------------------------------ 刷新
    async def _refresh_account(self) -> None:
        """用已经保存的 Cookie 拉一次最新账号信息。"""
        try:
            account = await asyncio.to_thread(self._api.auth.current_account)
        except Exception:
            # 网络问题就继续用缓存，不要误判成"登录失效"
            return

        if account is None:
            self._handle_expired()
            return

        self._credentials.account = account
        self._account = account
        try:
            save_credentials(self._credentials)
        except OSError:
            pass
        self._render()
        self._notify()

    def _handle_expired(self) -> None:
        """服务端明确说没登录，才清掉本地凭据。"""
        clear_credentials()
        self._api.http.clear_cookies()
        self._credentials = Credentials()
        self._account = Account()
        self._render()
        self._snack("登录已失效，请重新扫码")
        self._notify()

    # ------------------------------------------------------------ 工具
    def _apply_cookies(self) -> None:
        if self._credentials.is_complete:
            self._api.set_cookies(self._credentials.cookies)

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self._status.value = text
        self._status.color = theme.DANGER if error else theme.TEXT_SECONDARY
        self._page.update()

    def _snack(self, text: str) -> None:
        try:
            self._page.show_dialog(
                ft.SnackBar(
                    content=ft.Text(text, size=13),
                    bgcolor=theme.TEXT_PRIMARY,
                )
            )
        except Exception:
            pass

    def _notify(self) -> None:
        if self._on_change:
            self._on_change(self._account if self.is_logged_in else None)
