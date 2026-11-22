"""
检索源注册表
============

每个源模块约定暴露：
    NAME               源名称
    DOWNLOAD_SUPPORTED 是否支持 download_paper
    DEFAULT_DELAY      该源的推荐请求间隔（秒）
    search(query, pages, year_from, year_to, delay, session) -> list[dict]
    download_paper(paper_id, outdir, title, skip_existing, delay, session) -> str | None

统一检索记录格式：
    {
      "id": "...",          # 源内唯一 ID（arxiv id / WOS UID / Elsevier PII）
      "source": "arxiv|wos|elsevier",
      "title": "...",
      "url": "...",         # 详情页
      "authors": [...],
      "year": 2024 或 None,
      "snippet": "...",     # 页面文本片段或摘要
      "doi": "...",         # 能拿到就填
      "query": "..."
    }
"""

from . import arxiv_source, sciencedirect_source, wos_source

SOURCES = {
    "arxiv": arxiv_source,
    "wos": wos_source,
    # Elsevier 检索落地在 ScienceDirect，两个名字都接受
    "elsevier": sciencedirect_source,
    "sciencedirect": sciencedirect_source,
}

# --source all 时去重后的遍历顺序
PRIMARY = ["arxiv", "wos", "elsevier"]
