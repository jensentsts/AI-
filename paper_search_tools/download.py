"""
多源论文 PDF 批量下载
=====================

按来源自动路由：
    - arxiv      纯 Python 直连 https://arxiv.org/pdf/<id>，无需浏览器
    - elsevier   经 WebBridge 在已认证浏览器内 fetch pdfft 链接
    - wos        不支持（WoS 不托管全文），会打印指引并跳过

用法：
    python download.py --source arxiv 2101.12345 2202.00001
    python download.py --source arxiv --file arxiv_ids.txt      # 每行一个 ID
    python download.py --from-search results.json               # 按记录里的 source 自动路由（可混合多源）
    python download.py --from-search results.json --source elsevier   # 只下其中 elsevier 的记录

前置条件：
    - 仅 elsevier 源需要 WebBridge daemon 在线 + 浏览器机构认证
    - arxiv 源遵守 3 秒间隔（--delay 可调，不建议低于 3）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import webbridge_client as wb
from common import update_manifest
from sources import SOURCES

_BROWSER_SOURCES = {"elsevier", "sciencedirect"}


def _collect_targets(args: argparse.Namespace) -> list[dict]:
    """收集下载目标 [{source, id, title}]。"""
    targets: dict[tuple[str, str], dict] = {}

    if args.from_search:
        data = json.loads(Path(args.from_search).read_text(encoding="utf-8"))
        for p in data:
            pid = str(p.get("id") or p.get("arnumber") or "").strip()  # 兼容 ieee_tools 结果
            source = (p.get("source") or args.source or "").lower()
            if not pid or not source:
                continue
            if args.source and source != args.source.lower():
                # --from-search 与 --source 同用时，只取匹配来源的记录
                if not (args.source.lower() == "elsevier" and source == "sciencedirect"):
                    continue
            targets.setdefault((source, pid), {
                "source": source,
                "id": pid,
                "title": (p.get("title") or "").strip() or None,
            })

    if args.file or args.ids:
        if not args.source:
            ap_error("位置参数 ID / --file 需要配合 --source 指明来源")
        source = args.source.lower()
        if args.file:
            for line in Path(args.file).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    targets.setdefault((source, line), {"source": source, "id": line, "title": None})
        for pid in args.ids:
            targets.setdefault((source, pid), {"source": source, "id": pid, "title": None})

    return list(targets.values())


def ap_error(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    ap = argparse.ArgumentParser(description="多源论文 PDF 批量下载（arXiv 直连 / Elsevier 经 WebBridge）")
    ap.add_argument("ids", nargs="*", help="要下载的论文 ID 列表（需 --source）")
    ap.add_argument("--source", type=str, default=None,
                    help="来源: arxiv / elsevier(sciencedirect)（wos 不支持下载）")
    ap.add_argument("--file", type=str, default=None, help="ID 清单文件，每行一个（需 --source）")
    ap.add_argument("--from-search", type=str, default=None,
                    help="search.py 输出的 JSON；按记录 source 自动路由，可混合多源")
    ap.add_argument("--outdir", type=str, default=str(Path(__file__).parent.parent / "papers"))
    ap.add_argument("--name-by-id", action="store_true",
                    help="用论文 ID 命名（默认：有标题时用论文标题命名）")
    ap.add_argument("--no-skip", action="store_true", help="不跳过已存在的有效 PDF")
    ap.add_argument("--delay", type=float, default=None,
                    help="每篇间隔秒数（默认取各源推荐值：arxiv 3s / elsevier 1s）")
    args = ap.parse_args()

    targets = _collect_targets(args)
    if not targets:
        ap.error("请提供下载目标（位置参数 ID / --file / --from-search 至少一种）")

    unknown = sorted({t["source"] for t in targets if t["source"] not in SOURCES})
    if unknown:
        ap.error(f"未知来源: {', '.join(unknown)}（可选: {', '.join(sorted(SOURCES))}）")

    # 有浏览器源目标时先探测 WebBridge
    if any(t["source"] in _BROWSER_SOURCES for t in targets):
        ready, msg = wb.daemon_status()
        if not ready:
            print(f"[ERROR] {msg}", file=sys.stderr)
            return 1

    outdir = Path(args.outdir)
    print(f"输出目录: {outdir.resolve()}")
    print(f"共 {len(targets)} 篇待处理\n")

    ok, failed, saved = 0, [], []
    for t in targets:
        mod = SOURCES[t["source"]]
        if not mod.DOWNLOAD_SUPPORTED:
            mod.download_paper(t["id"], outdir)  # 打印指引
            failed.append(t["id"])
            print()
            continue
        title = None if args.name_by_id else t["title"]
        delay = args.delay if args.delay is not None else (1.0 if t["source"] in _BROWSER_SOURCES else mod.DEFAULT_DELAY)
        fname = mod.download_paper(
            t["id"], outdir, title=title,
            skip_existing=not args.no_skip, delay=delay,
        )
        if fname:
            ok += 1
            saved.append({"filename": fname, "source": t["source"],
                          "id": t["id"], "title": t["title"] or t["id"]})
        else:
            failed.append(t["id"])
        print()

    if saved:
        update_manifest(outdir, saved)
    print(f"完成: {ok}/{len(targets)} 成功")
    if failed:
        print(f"失败/跳过: {', '.join(failed)}")
        print("提示: elsevier 批量失败多半是认证过期——请在浏览器重新打开 ScienceDirect 主页完成认证后重试。")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
