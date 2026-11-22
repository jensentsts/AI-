"""
Elsevier / ScienceDirect 检索源
===============================

通过 Kimi WebBridge 在已认证的浏览器中执行 ScienceDirect 检索与下载。

检索：
    ScienceDirect 检索页支持 GET 参数，直接拼 URL：
        https://www.sciencedirect.com/search?qs=<query>&years=2020,2021&show=25&offset=25
    结果链接为 a[href*="/science/article/pii/"]，从中提取 PII。

下载（与 IEEE 版同一思路）：
    navigate 到文章页建立认证 Cookie 上下文
      -> evaluate 在页面内 fetch pdfft URL 获取 PDF 二进制
      -> FileReader 转 Base64 回传（大文件分块）
      -> Python 端解码保存并校验 %PDF- 头

前置条件：浏览器已通过校园网 / 机构认证，能正常打开 ScienceDirect 全文 PDF。
"""

from __future__ import annotations

import base64
import re
import time
import urllib.parse
from pathlib import Path

import webbridge_client as wb
from common import sanitize_filename, verify_pdf

NAME = "elsevier"
DOWNLOAD_SUPPORTED = True
DEFAULT_DELAY = 2.0

SEARCH_URL = "https://www.sciencedirect.com/search"
ARTICLE_URL = "https://www.sciencedirect.com/science/article/pii/{pii}"
PDF_URL = "https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true"
PER_PAGE = 25

# 分块阈值：evaluate 返回值过大会被截断，超过该大小的 PDF 分块回传
CHUNK_THRESHOLD = 12 * 1024 * 1024  # 12 MB
CHUNK_SIZE = 4 * 1024 * 1024        # 每块 4 MB（base64 字符数）

# 结果提取 JS：遍历指向 /science/article/pii/ 的链接，去重后取标题与容器文本片段
_EXTRACT_JS = r"""
(() => {
    const seen = new Set();
    const out = [];
    document.querySelectorAll('a[href*="/science/article/pii/"]').forEach(a => {
        const href = a.getAttribute('href') || '';
        const m = href.match(/pii\/([A-Za-z0-9]+)/);
        if (!m || seen.has(m[1])) return;
        const title = (a.textContent || '').trim();
        if (!title || title.length < 8) return;
        seen.add(m[1]);
        let container = a.closest('div[class*="result"], li, tr');
        let snippet = '';
        for (let el = container, i = 0; el && i < 6; el = el.parentElement, i++) {
            const t = (el.innerText || '').trim();
            if (t.length > snippet.length && t.length < 2000) snippet = t;
        }
        out.push({ pii: m[1], title: title, snippet: snippet });
    });
    let total = null;
    const tm = (document.body.innerText || '').match(/([\d,]+)\s+results?/i);
    if (tm) total = parseInt(tm[1].replace(/,/g, ''), 10);
    return { papers: out, total: total };
})()
"""

_FETCH_JS = """
(async () => {{
    const resp = await fetch('{pdf_url}');
    if (!resp.ok) return {{ error: 'HTTP ' + resp.status }};
    const blob = await resp.blob();
    if (!blob.type.includes('pdf') && blob.size < 50000)
        return {{ error: 'not a pdf (type=' + blob.type + ', size=' + blob.size + ')' }};
    const reader = new FileReader();
    return new Promise((resolve) => {{
        reader.onloadend = () => resolve({{ data: reader.result }});
        reader.readAsDataURL(blob);
    }});
}})()
"""

_FETCH_CACHE_JS = """
(async () => {{
    const resp = await fetch('{pdf_url}');
    if (!resp.ok) return {{ error: 'HTTP ' + resp.status }};
    const blob = await resp.blob();
    const reader = new FileReader();
    const dataUrl = await new Promise((resolve) => {{
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blob);
    }});
    window.__paperPdfCache = dataUrl;
    return {{ size: dataUrl.length }};
}})()
"""

_FETCH_CHUNK_JS = """
(() => {{
    const s = window.__paperPdfCache || '';
    return {{ chunk: s.slice({start}, {end}), total: s.length }};
}})()
"""


def _decode_data_url(data_url: str) -> bytes | None:
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    try:
        return base64.b64decode(data_url)
    except Exception as e:
        print(f"  [ERROR] Base64 解码失败: {e}")
        return None


def _fetch_pdf_bytes(pii: str, session: str) -> bytes | None:
    """在浏览器上下文中 fetch PDF，返回字节流。大文件自动分块。"""
    pdf_url = PDF_URL.format(pii=pii)

    value = wb.evaluate(_FETCH_JS.format(pdf_url=pdf_url), session=session)
    if isinstance(value, dict) and value.get("error"):
        print(f"  [ERROR] fetch 失败: {value['error']}")
        return None
    data_url = (value or {}).get("data") if isinstance(value, dict) else None

    if data_url and isinstance(data_url, str):
        if len(data_url) <= CHUNK_THRESHOLD * 4 // 3:
            return _decode_data_url(data_url)
        print("  [INFO] PDF 较大，切换为分块回传...")

    cache_val = wb.evaluate(_FETCH_CACHE_JS.format(pdf_url=pdf_url), session=session)
    if not isinstance(cache_val, dict) or "size" not in cache_val:
        print(f"  [ERROR] 分块缓存失败: {cache_val!r}")
        return None
    total = cache_val["size"]
    parts: list[str] = []
    for start in range(0, total, CHUNK_SIZE):
        chunk_val = wb.evaluate(
            _FETCH_CHUNK_JS.format(start=start, end=start + CHUNK_SIZE),
            session=session,
        )
        if not isinstance(chunk_val, dict) or "chunk" not in chunk_val:
            print(f"  [ERROR] 分块 {start} 回传失败: {chunk_val!r}")
            return None
        parts.append(chunk_val["chunk"])
    return _decode_data_url("".join(parts))


def _search_url(query: str, page: int, year_from: int | None, year_to: int | None) -> str:
    params = {"qs": query, "show": str(PER_PAGE)}
    if page > 1:
        params["offset"] = str((page - 1) * PER_PAGE)
    if year_from:
        years = ",".join(str(y) for y in range(year_from, (year_to or year_from) + 1))
        params["years"] = years
    return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"


def search(
    query: str,
    pages: int = 1,
    year_from: int | None = None,
    year_to: int | None = None,
    delay: float = DEFAULT_DELAY,
    session: str = wb.DEFAULT_SESSION,
) -> list[dict]:
    """执行检索，返回按 PII 去重后的论文列表。"""
    results: dict[str, dict] = {}

    for page in range(1, pages + 1):
        url = _search_url(query, page, year_from, year_to)
        print(f"[SEARCH] ScienceDirect 第 {page}/{pages} 页: {url}")
        wb.navigate(url, new_tab=(page == 1), session=session)
        wb.wait(4 if page == 1 else 3)  # 结果页动态渲染

        value = wb.evaluate(_EXTRACT_JS, session=session)
        if not isinstance(value, dict):
            print(f"  [WARN] 第 {page} 页解析失败，返回: {value!r}")
            continue

        papers = value.get("papers") or []
        if page == 1:
            if value.get("total"):
                print(f"  命中总数约 {value['total']} 条")
            if not papers:
                print("  [WARN] 未解析到结果，请确认已通过机构认证且页面结构未变")
        print(f"  本页解析出 {len(papers)} 条")

        for p in papers:
            pii = p["pii"]
            if pii in results:
                continue
            year = None
            ym = re.search(r"\b(19|20)\d{2}\b", p.get("snippet", ""))
            if ym:
                year = int(ym.group(0))
            results[pii] = {
                "id": pii,
                "source": NAME,
                "title": p["title"],
                "url": ARTICLE_URL.format(pii=pii),
                "authors": [],
                "year": year,
                "snippet": p.get("snippet", ""),
                "doi": "",
                "query": query,
            }
        wb.wait(delay)

    return list(results.values())


def download_paper(
    paper_id: str,
    outdir: Path,
    title: str | None = None,
    skip_existing: bool = True,
    delay: float = 1.0,
    session: str = wb.DEFAULT_SESSION,
) -> str | None:
    """下载单篇论文 PDF。成功返回文件名，失败返回 None。"""
    filename = f"{sanitize_filename(title)}.pdf" if title else f"{paper_id}.pdf"
    pdf_path = outdir / filename

    if skip_existing and pdf_path.exists():
        if verify_pdf(pdf_path):
            print(f"[SKIP] {filename} 已存在且有效")
            return filename
        print(f"[RETRY] {filename} 存在但无效，重新下载")

    print(f"[DOWNLOAD] pii={paper_id}" + (f" -> {filename}" if title else ""))

    # Step 1: 打开文章页，建立/刷新 Elsevier 认证 Cookie 上下文
    try:
        wb.navigate(ARTICLE_URL.format(pii=paper_id), new_tab=False, session=session)
    except wb.WebBridgeError as e:
        print(f"  [ERROR] {e}")
        return None
    wb.wait(2.0)

    # Step 2: 页面内 fetch pdfft 链接取 PDF（fetch 自动跟随重定向并携带 Cookie）
    try:
        pdf_bytes = _fetch_pdf_bytes(paper_id, session=session)
    except wb.WebBridgeError as e:
        print(f"  [ERROR] {e}")
        return None
    if pdf_bytes is None:
        return None

    # Step 3: 保存并校验
    outdir.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(pdf_bytes)
    if verify_pdf(pdf_path):
        print(f"  [OK] {pdf_path.name} ({len(pdf_bytes):,} bytes)")
        wb.wait(delay)
        return filename

    print(f"  [FAIL] {pdf_path.name} 校验未通过（可能认证过期、无全文权限或非 OA 文章）")
    pdf_path.unlink(missing_ok=True)
    wb.wait(delay)
    return None
