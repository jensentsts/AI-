"""
多源论文检索（arXiv / Web of Science / Elsevier-ScienceDirect）
==============================================================

用法：
    python search.py "virtual inertia reinforcement learning" --source arxiv
    python search.py "wind power virtual inertia" --source elsevier --pages 2
    python search.py "SUC frequency constrained wind" --source wos --year-from 2016 --year-to 2025
    python search.py "virtual inertia" --source all --out results.json

输出 JSON 结构（列表，跨源统一格式）：
    [
      {
        "id": "2101.12345v2 | WOS:000xxx | PII",   # 源内唯一 ID
        "source": "arxiv | wos | elsevier",
        "title": "...",
        "url": "...",                              # 详情页
        "authors": [...],
        "year": 2024,
        "snippet": "摘要或页面文本片段",
        "doi": "...",
        "query": "..."
      }, ...
    ]

注意：
    - arxiv 走官方 API，不需要浏览器；wos / elsevier 需要 WebBridge + 已认证浏览器。
    - 浏览器源的结果页为动态渲染，翻页/解析均为启发式，页面改版后需调整 sources/ 内 JS。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import webbridge_client as wb
from sources import PRIMARY, SOURCES

# 需要 WebBridge 的源
_BROWSER_SOURCES = {"wos", "elsevier", "sciencedirect"}


def _resolve_sources(name: str) -> list[str]:
    if name == "all":
        return PRIMARY
    if name not in SOURCES:
        raise SystemExit(f"[ERROR] 未知来源 {name!r}，可选: {', '.join(sorted(SOURCES))} / all")
    return [name]


def main() -> int:
    ap = argparse.ArgumentParser(description="多源论文检索（arXiv / WoS / Elsevier）")
    ap.add_argument("query", help="检索关键词，如 'virtual inertia reinforcement learning'")
    ap.add_argument("--source", default="arxiv",
                    help="检索来源: arxiv / wos / elsevier(sciencedirect) / all（默认 arxiv）")
    ap.add_argument("--pages", type=int, default=1, help="每个源抓取页数（默认 1，每页约 25 条）")
    ap.add_argument("--year-from", type=int, default=None, help="起始年份，如 2016")
    ap.add_argument("--year-to", type=int, default=None, help="截止年份，如 2025")
    ap.add_argument("--out", type=str, default=None,
                    help="结果 JSON 输出路径（默认 search_results_<来源>_<时间戳>.json）")
    ap.add_argument("--delay", type=float, default=None,
                    help="请求/翻页间隔秒数（默认取各源推荐值：arxiv 3s，浏览器源 2-3s）")
    args = ap.parse_args()

    source_names = _resolve_sources(args.source.lower())

    # 浏览器源先统一探测 WebBridge，避免搜到一半才发现链路不通
    if any(s in _BROWSER_SOURCES for s in source_names):
        ready, msg = wb.daemon_status()
        if not ready:
            print(f"[ERROR] {msg}", file=sys.stderr)
            return 1

    all_papers: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for name in source_names:
        mod = SOURCES[name]
        delay = args.delay if args.delay is not None else mod.DEFAULT_DELAY
        print(f"===== 来源: {mod.NAME} =====")
        try:
            papers = mod.search(
                args.query,
                pages=args.pages,
                year_from=args.year_from,
                year_to=args.year_to,
                delay=delay,
            )
        except wb.WebBridgeError as e:
            print(f"[ERROR] {mod.NAME} 检索失败: {e}", file=sys.stderr)
            continue
        for p in papers:
            key = (p["source"], p["id"])
            if key not in seen:
                seen.add(key)
                all_papers.append(p)
        print()

    out_path = Path(args.out) if args.out else Path(
        f"search_results_{args.source}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_path.write_text(
        json.dumps(all_papers, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"共 {len(all_papers)} 条（按 来源+ID 去重），已保存到 {out_path.resolve()}")
    for p in all_papers[:20]:
        print(f"  [{p['source']:>8}] {p['id']:>20}  {p['title'][:60]}")
    if len(all_papers) > 20:
        print(f"  ... 其余 {len(all_papers) - 20} 条见输出文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
