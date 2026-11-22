"""
Web of Science 检索源
=====================

通过 Kimi WebBridge 在已认证的浏览器中操作 WoS 新界面（SPA）：
    navigate 到 basic-search 页 -> JS 填关键词并提交（穿透 shadow DOM）
      -> 等待跳转到 summary 页 -> JS 提取 full-record 链接
      -> 翻页通过改写 summary URL 末尾的 /relevance/N 实现

重要限制：
    WoS 是引文索引库，本身不托管全文 PDF（"Full Text"按钮只是跳转到出版商页面），
    因此 DOWNLOAD_SUPPORTED = False。检索结果中的 DOI 可交给 elsevier / arxiv 源
    或其他渠道下载。

注意：
    WoS 前端是 Angular SPA 且大量使用 shadow DOM，选择器比 IEEE 更脆。
    若提取失败，先用 --debug 查看返回的 inputs/links 诊断信息，
    再按页面实际结构调整本文件中的 JS。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import webbridge_client as wb

NAME = "wos"
DOWNLOAD_SUPPORTED = False  # WoS 不托管全文，见模块 docstring
DEFAULT_DELAY = 3.0

BASE_URL = "https://www.webofscience.com/wos/woscc/basic-search"

# 提交检索：穿透 shadow DOM 找输入框与提交按钮；失败时返回诊断信息
_SUBMIT_JS = r"""
(async () => {
    const q = __QUERY__;
    function deepQuery(root, sel) {
        const hit = root.querySelector(sel);
        if (hit) return hit;
        for (const el of root.querySelectorAll('*')) {
            if (el.shadowRoot) {
                const r = deepQuery(el.shadowRoot, sel);
                if (r) return r;
            }
        }
        return null;
    }
    const input = deepQuery(document, '#search-option')
        || deepQuery(document, 'input[name="search-option"]')
        || deepQuery(document, 'input[type="text"]');
    if (!input) {
        return { error: 'search input not found',
                 inputs: Array.from(document.querySelectorAll('input'))
                     .map(i => i.id || i.name || i.type).slice(0, 20) };
    }
    // 用原生 setter 赋值，兼容 Angular/React 的受控输入
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(input, q);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    const btn = deepQuery(document, 'button[type="submit"]')
        || deepQuery(document, 'button.search-button')
        || Array.from(document.querySelectorAll('button'))
            .find(b => /search/i.test(b.textContent || '') && !b.disabled);
    if (!btn) return { error: 'search button not found' };
    btn.click();
    return { ok: true };
})()
"""

# 结果提取：遍历 full-record 链接，去重后取标题与容器文本片段
_EXTRACT_JS = r"""
(() => {
    const seen = new Set();
    const out = [];
    document.querySelectorAll('a[href*="full-record/WOS:"]').forEach(a => {
        const href = a.getAttribute('href') || '';
        const m = href.match(/full-record\/(WOS:[A-Z0-9]+)/);
        if (!m || seen.has(m[1])) return;
        const title = (a.textContent || '').trim();
        if (!title || title.length < 8) return;
        seen.add(m[1]);
        let container = a.closest('div[class*="record"], app-record, div[class*="result"], li');
        let snippet = '';
        for (let el = container, i = 0; el && i < 6; el = el.parentElement, i++) {
            const t = (el.innerText || '').trim();
            if (t.length > snippet.length && t.length < 2000) snippet = t;
        }
        // DOI 尽力从片段中提取
        const dm = snippet.match(/10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i);
        out.push({ uid: m[1], title: title, snippet: snippet, doi: dm ? dm[0] : '' });
    });
    let total = null;
    const tm = (document.body.innerText || '').match(/([\d,]+)\s+results?/i);
    if (tm) total = parseInt(tm[1].replace(/,/g, ''), 10);
    return { papers: out, total: total, url: location.href };
})()
"""

_LOCATION_JS = "(() => location.href)()"


def _submit_search(query: str, session: str) -> None:
    value = wb.evaluate(_SUBMIT_JS.replace("__QUERY__", json.dumps(query)), session=session)
    if not isinstance(value, dict) or not value.get("ok"):
        raise wb.WebBridgeError(
            f"WoS 检索提交失败: {value}\n"
            "可能页面结构已变化，或尚未通过机构认证。"
        )


def _page_url(current_url: str, page: int) -> str | None:
    """把 summary URL 的 /relevance/1 改成 /relevance/N。不匹配则返回 None。"""
    new_url, n = re.subn(r"/relevance/\d+", f"/relevance/{page}", current_url)
    return new_url if n else None


def search(
    query: str,
    pages: int = 1,
    year_from: int | None = None,
    year_to: int | None = None,
    delay: float = DEFAULT_DELAY,
    session: str = wb.DEFAULT_SESSION,
) -> list[dict]:
    """执行检索，返回按 UID 去重后的论文列表。年份过滤在客户端完成。"""
    results: dict[str, dict] = {}

    print(f"[SEARCH] WoS: {BASE_URL}")
    wb.navigate(BASE_URL, new_tab=True, session=session)
    wb.wait(5)  # SPA 首屏加载较慢
    _submit_search(query, session)
    wb.wait(5)  # 等待跳转 summary 页并渲染结果

    for page in range(1, pages + 1):
        if page > 1:
            current = wb.evaluate(_LOCATION_JS, session=session)
            next_url = _page_url(current or "", page)
            if not next_url:
                print(f"  [WARN] 无法构造第 {page} 页 URL（当前: {current}），停止翻页")
                break
            print(f"[SEARCH] WoS 第 {page}/{pages} 页: {next_url}")
            wb.navigate(next_url, new_tab=False, session=session)
            wb.wait(4)

        value = wb.evaluate(_EXTRACT_JS, session=session)
        if not isinstance(value, dict):
            print(f"  [WARN] 第 {page} 页解析失败，返回: {value!r}")
            continue

        papers = value.get("papers") or []
        if page == 1:
            if value.get("total"):
                print(f"  命中总数约 {value['total']} 条")
            if not papers:
                print("  [WARN] 未解析到结果，请确认 WoS 已通过机构认证且页面结构未变")
        print(f"  本页解析出 {len(papers)} 条")

        for p in papers:
            uid = p["uid"]
            if uid in results:
                continue
            year = None
            ym = re.search(r"\b(19|20)\d{2}\b", p.get("snippet", ""))
            if ym:
                year = int(ym.group(0))
            if year_from and (year is None or year < year_from):
                continue
            if year_to and (year is None or year > year_to):
                continue
            results[uid] = {
                "id": uid,
                "source": NAME,
                "title": p["title"],
                "url": f"https://www.webofscience.com/wos/woscc/full-record/{uid}",
                "authors": [],
                "year": year,
                "snippet": p.get("snippet", ""),
                "doi": p.get("doi", ""),
                "query": query,
            }
        wb.wait(delay)

    return list(results.values())


def download_paper(paper_id: str, outdir: Path, **kw) -> None:
    """WoS 不托管全文 PDF，直接给出指引。"""
    print(
        f"[SKIP] WoS 记录 {paper_id} 不支持直接下载（WoS 是引文索引，不托管全文）。\n"
        "       请用检索结果中的 DOI 交给 --source elsevier / arxiv 下载，"
        "或在浏览器中点击 'Full Text at Publisher'。"
    )
    return None
