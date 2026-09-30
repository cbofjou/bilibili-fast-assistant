"""接口层异常。"""

from __future__ import annotations


class BiliError(RuntimeError):
    """本项目的接口异常基类。"""


class BiliNetworkError(BiliError):
    """网络层面失败：超时、DNS、连接被拒等。"""


class BiliApiError(BiliError):
    """B 站返回了非 0 的业务错误码。"""

    def __init__(self, code: int, message: str, *, url: str = "") -> None:
        self.code = code
        self.message = message
        self.url = url
        super().__init__(f"[{code}] {message}")

    def __str__(self) -> str:
        return f"接口返回错误 {self.code}：{self.message}"


class BiliRiskError(BiliApiError):
    """被风控 / 限流拦下。

    两种情况都归到这里：

    * 业务码：B 站返回 HTTP 200，但 body 里的 ``code`` 是风控码；
    * HTTP 码：直接被 WAF 挡在门外（最常见的是 412 / 429），
      这时压根没有 JSON body 可以解析。

    执行器只认这一种异常来降速和熔断，所以两条路径必须都归到这儿。
    """


# 常见的风控 / 限流业务码
#
# -403 要特别说明：它的文案有两种。一种是普通的"权限不足"（比如内容不可用），
# 另一种是「账号异常,操作失败」——后者是 B 站对账号做的临时限制，属于风控。
# 两种用同一个码，没法从码上区分，所以这里统一按风控处理：
# 代价是前者会白等两次退避，收益是真的被限制时立刻降速。
RISK_CODES = frozenset({-352, -403, -412, -509, -799})

# HTTP 层的拦截面具：没有 body，只有状态码
RISK_HTTP_STATUS = frozenset({412, 429})


def is_risk_error(exc: BaseException) -> bool:
    if isinstance(exc, BiliRiskError):
        return True
    return isinstance(exc, BiliApiError) and exc.code in RISK_CODES


RISK_HINT = "疑似触发风控，建议降低频率或过几小时再试"
