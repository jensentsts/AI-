"""
arXiv 检索源
============

走 arXiv 官方公共 API（https://export.arxiv.org/api/query），
纯 Python HTTP，不需要浏览器、不需要认证。

- 检索：Atom XML 解析，按 relevance 排序，客户端侧做年份过滤
- 下载：直接 GET https://arxiv.org/pdf/<id>，校验 %PDF- 头

注意 arXiv API 礼仪：请求间隔 >= 3 秒（DEFAULT_DELAY=3.0），
批量下载同样遵守，避免被封 IP。
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from common import sanitize_filename, verify_pdf

NAME = "arxiv"
DOWNLOAD_SUPPORTED = True
DEFAULT_DELAY = 3.0  # arXiv 官方要求请求间隔 >= 3s

API_URL = "https://export.arxiv.org/api/query"
MAX_PER_PAGE = 25

_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

_UA = {"User-Agent": "paper-search-tools/1.0 (local research script)"}


def _build_query(query: str) -> str:
    """构造 arXiv search_query：多词按 AND 逐词组合（all:a AND all:b）。
    注意布尔运算符与词之间必须是真实空格，由 urlencode 编码成 +；
    预先写死 '+' 会被编码成 %2B，arXiv 服务端不按空格处理，会命中 0 条。
    用户显式带引号时按短语处理。"""
    q = query.strip()
    if q.startswith('"') and q.endswith('"'):
        return f"all:{q}"
    terms = [t for t in q.split() if t]
    return " AND ".join(f"all:{t}" for t in terms) if terms else "all:*"


def _fetch(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_feed(xml_bytes: bytes, query: str) -> tuple[list[dict], int | None]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  [WARN] Atom XML 解析失败: {e}")
        return [], None

    total = None
    total_el = root.find("opensearch:totalResults", _NS)
    if total_el is not None and (total_el.text or "").strip().isdigit():
        total = int(total_el.text.strip())

    papers: list[dict] = []
    for entry in root.findall("a:entry", _NS):
        raw_id = (entry.findtext("a:id", default="", namespaces=_NS) or "").strip()
        arxiv_id = raw_id.rsplit("/abs/", 1)[-1]
        if not arxiv_id:
            continue
        title = " ".join((entry.findtext("a:title", default="", namespaces=_NS) or "").split())
        abstract = " ".join((entry.findtext("a:summary", default="", namespaces=_NS) or "").split())
        published = entry.findtext("a:published", default="", namespaces=_NS) or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        authors = [
            (a.findtext("a:name", default="", namespaces=_NS) or "").strip()
            for a in entry.findall("a:author", _NS)
        ]
        doi_el = entry.find("arxiv:doi", _NS)
        doi = (doi_el.text or "").strip() if doi_el is not None and doi_el.text else ""
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        for link in entry.findall("a:link", _NS):
            if link.get("title") == "pdf" and link.get("href"):
                pdf_url = link.get("href")
        cats = [c.get("term", "") for c in entry.findall("a:category", _NS) if c.get("term")]

        papers.append({
            "id": arxiv_id,
            "source": NAME,
            "title": title,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": pdf_url,
            "authors": authors,
            "year": year,
            "snippet": abstract,
            "doi": doi,
            "categories": cats,
            "query": query,
        })
    return papers, total


def search(
    query: str,
    pages: int = 1,
    year_from: int | None = None,
    year_to: int | None = None,
    delay: float = DEFAULT_DELAY,
    session: str | None = None,  # 兼容浏览器源签名，arXiv 用不到
) -> list[dict]:
    """执行检索，返回去重后的论文列表（年份过滤在客户端完成）。"""
    results: dict[str, dict] = {}

    for page in range(pages):
        params = {
            "search_query": _build_query(query),
            "start": page * MAX_PER_PAGE,
            "max_results": MAX_PER_PAGE,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        url = f"{API_URL}?{urllib.parse.urlencode(params)}"
        print(f"[SEARCH] arXiv 第 {page + 1}/{pages} 页: {url}")

        try:
            xml_bytes = _fetch(url)
        except urllib.error.URLError as e:
            print(f"  [ERROR] 请求失败: {e}")
            break

        papers, total = _parse_feed(xml_bytes, query)
        if page == 0 and total is not None:
            print(f"  命中总数约 {total} 条")
        print(f"  本页解析出 {len(papers)} 条")

        for p in papers:
            if year_from and (p["year"] is None or p["year"] < year_from):
                continue
            if year_to and (p["year"] is None or p["year"] > year_to):
                continue
            if p["id"] not in results:
                results[p["id"]] = p

        if len(papers) < MAX_PER_PAGE:
            break  # 没有更多结果
        if page + 1 < pages:
            time.sleep(delay)

    return list(results.values())


def download_paper(
    paper_id: str,
    outdir: Path,
    title: str | None = None,
    skip_existing: bool = True,
    delay: float = DEFAULT_DELAY,
    session: str | None = None,  # 兼容签名，arXiv 用不到
) -> str | None:
    """下载单篇 PDF。成功返回文件名，失败返回 None。"""
    filename = f"{sanitize_filename(title)}.pdf" if title else f"{paper_id}.pdf"
    pdf_path = outdir / filename

    if skip_existing and pdf_path.exists():
        if verify_pdf(pdf_path):
            print(f"[SKIP] {filename} 已存在且有效")
            return filename
        print(f"[RETRY] {filename} 存在但无效，重新下载")

    url = f"https://arxiv.org/pdf/{paper_id}"
    print(f"[DOWNLOAD] arxiv={paper_id}" + (f" -> {filename}" if title else ""))

    try:
        data = _fetch(url, timeout=180.0)
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] HTTP {e.code}（论文可能已撤稿或 ID 有误）: {url}")
        return None
    except urllib.error.URLError as e:
        print(f"  [ERROR] 请求失败: {e}")
        return None

    outdir.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(data)
    if verify_pdf(pdf_path):
        print(f"  [OK] {pdf_path.name} ({len(data):,} bytes)")
        time.sleep(delay)
        return filename

    print(f"  [FAIL] {pdf_path.name} 校验未通过（返回的可能不是 PDF）")
    pdf_path.unlink(missing_ok=True)
    time.sleep(delay)
    return None
