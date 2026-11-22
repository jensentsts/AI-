"""
Kimi WebBridge 共享客户端
=========================

封装对本地 WebBridge daemon (http://127.0.0.1:10086) 的 HTTP 调用，
供 search.py / download.py 中的浏览器源（Web of Science / Elsevier）共用。
arXiv 源走官方 API，不依赖本模块。

前置条件：
    - Kimi WebBridge daemon 已启动：
        Windows PowerShell:
            & "$env:USERPROFILE\\.kimi-webbridge\\bin\\kimi-webbridge.exe" start
    - 浏览器已通过校园网 / 机构认证，可访问 Web of Science / ScienceDirect 全文。

参考：docs/ieee_xplore_workflow.md（WebBridge 机制与 IEEE 版相同）
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:10086/command"
DEFAULT_SESSION = "paper-search-tools"


class WebBridgeError(RuntimeError):
    """WebBridge 调用失败（daemon 不可达 / 返回错误 / JSON 非法）。"""


def command(
    action: str,
    args: dict | None = None,
    session: str = DEFAULT_SESSION,
    url: str = DEFAULT_URL,
    timeout: float = 180.0,
) -> dict:
    """向 WebBridge daemon 发送一条命令，返回解析后的 JSON 响应。

    响应结构（经验值）::
        {"ok": true, "data": {...}}

    evaluate 的返回值位于 resp["data"]["value"]。
    """
    payload = {"action": action, "args": args or {}, "session": session}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        # daemon 对业务错误也返回 HTTP 5xx（如 no extension connected），
        # 响应体仍是结构化 JSON，照常解析交给上层判断
        body = e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise WebBridgeError(
            f"无法连接 WebBridge daemon ({url}): {e}\n"
            "请先启动 kimi-webbridge 并确认浏览器已打开。"
        ) from e
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise WebBridgeError(f"WebBridge 返回了非法 JSON: {e}; body[:200]={body[:200]!r}") from e


def navigate(page_url: str, new_tab: bool = False, **kw) -> dict:
    """打开一个页面。"""
    resp = command("navigate", {"url": page_url, "newTab": new_tab}, **kw)
    if not resp.get("ok") or not resp.get("data", {}).get("success", True):
        raise WebBridgeError(f"navigate 失败: {page_url} -> {resp}")
    return resp


def evaluate(js_code: str, **kw):
    """在当前页面执行 JS，返回 evaluate 的 value（原始类型）。"""
    resp = command("evaluate", {"code": js_code}, **kw)
    if not resp.get("ok"):
        raise WebBridgeError(f"evaluate 失败: {resp}")
    return resp.get("data", {}).get("value")


def wait(seconds: float) -> None:
    """统一等待（限流保护）。"""
    time.sleep(seconds)


def daemon_status(url: str = DEFAULT_URL, probe_url: str = "https://arxiv.org/") -> tuple[bool, str]:
    """探测 WebBridge 可用性。

    返回 (ready, message)：
      - daemon 不可达     -> (False, 启动提示)
      - 浏览器扩展未连接  -> (False, 打开浏览器提示)
      - 就绪              -> (True, "ok")
    """
    try:
        resp = command("find_tab", {"url": probe_url}, url=url, timeout=10)
    except WebBridgeError as e:
        return False, str(e)
    err = resp.get("error") or {}
    if isinstance(err, dict) and "no extension connected" in str(err.get("message", "")):
        return False, (
            "WebBridge daemon 在线，但没有浏览器扩展连接。\n"
            "请打开装有 Kimi WebBridge 扩展的浏览器（并确认扩展已启用），"
            "然后访问目标站点（WoS / ScienceDirect）完成机构认证。"
        )
    # find_tab 找不到匹配标签页也算就绪（说明链路通）
    return True, "ok"


def check_alive(url: str = DEFAULT_URL) -> bool:
    """简化版探测：链路可用即为 True。"""
    return daemon_status(url)[0]
