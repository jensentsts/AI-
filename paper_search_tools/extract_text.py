"""
论文 PDF 文本载入（多源通用版）
===============================

将 papers/ 中已下载的 PDF（arXiv / Elsevier / IEEE 均可）提取为结构化文本 JSON，
供后续摘要提取、方法对比、主题聚类等分析使用。

提取策略：
    1. 首选 pypdf 提取文本层
    2. 若文本为空（扫描版），尝试 pdfplumber；仍为空则标记 needs_ocr
    3. 用正则粗略切分 abstract / keywords / 章节（启发式，仅供参考）

与 ieee_tools/extract_text.py 的差异：
    - ID 反查支持新 manifest 格式 {source, id, title}，同时兼容旧的 {arnumber, title}
    - 输出记录用 paper_id + source 字段（arnumber 是 IEEE 专有概念）

用法：
    python extract_text.py                          # 处理 ../papers 下全部 PDF
    python extract_text.py 2101.12345               # 只处理指定 ID（文件名需为 <id>.pdf）
    python extract_text.py --indir ..\\papers --outdir ..\\papers_text
    python extract_text.py --print 2101.12345       # 终端预览提取结果

输出（每篇一个 JSON，另加汇总 index.json）：
    {
      "paper_id": "2101.12345v2",
      "source": "arxiv",
      "pdf_file": "....pdf",
      "metadata": {"pages": 11, "pdf_size_bytes": 1986989, "extractor": "pypdf"},
      "title": "...",            # 从首页启发式提取，可能不准
      "abstract": "...",
      "keywords": ["..."],
      "sections": {"I. INTRODUCTION": "...", ...},
      "references": ["...", ...],
      "full_text": "...",
      "needs_ocr": false
    }
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import load_manifest

DEFAULT_INDIR = Path(__file__).parent.parent / "papers"
DEFAULT_OUTDIR = Path(__file__).parent.parent / "papers_text"

# 章节标题：IEEE 风格 "I. INTRODUCTION"（全大写罗马/数字编号）
#           + 一般期刊风格 "1. Introduction"（数字编号、首字母大写混排）
_SECTION_RE = re.compile(
    r"^\s*((?:[IVXLC]+|[0-9]+)\.\s+[A-Z][A-Z \-,&/()]{3,60}"
    r"|[0-9]+\.\s+[A-Z][A-Za-z][A-Za-z0-9 \-,&/()]{2,60})\s*$", re.M
)
# Abstract 分隔符兼容 IEEE 破折号与期刊句号/无分隔符写法；
# 终止于 Keywords 或第一个章节标题（含 "1. Introduction" 混排）
_ABSTRACT_RE = re.compile(
    r"Abstract\s*[—\-–:.]?\s*(.+?)(?=Index Terms|Keywords?\s*[—\-–:]|\n\s*(?:[IVXLC]+|1)\s*\.\s*[A-Z])",
    re.S | re.I,
)
_KEYWORDS_RE = re.compile(
    r"(?:Index Terms|Keywords?)[—\-–:]\s*(.+?)(?=\n\s*(?:[IVXLC]+|1)\s*\.|\n\s*\n|$)",
    re.S | re.I,
)
_REFERENCES_RE = re.compile(
    r"^\s*(?:R\s*E\s*FERENCES|References)\s*$", re.M
)


def extract_raw_text(pdf_path: Path) -> tuple[str, int, str]:
    """提取原始文本。返回 (text, page_count, extractor_name)。"""
    # 方法1: pypdf
    try:
        import pypdf

        reader = pypdf.PdfReader(str(pdf_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages)
        if text.strip():
            return text, len(reader.pages), "pypdf"
        page_count = len(reader.pages)
    except Exception as e:
        print(f"  [WARN] pypdf 失败: {e}")
        page_count = 0

    # 方法2: pdfplumber（对复杂排版更鲁棒）
    try:
        import pdfplumber

        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages)
            return text, len(pdf.pages), "pdfplumber"
    except Exception as e:
        print(f"  [WARN] pdfplumber 失败: {e}")

    return "", page_count, "none"


def guess_title(first_page_text: str) -> str:
    """从首页前几行猜测标题（跳过页眉行，取较长行）。"""
    lines = [l.strip() for l in first_page_text.splitlines() if l.strip()]
    candidates = []
    for line in lines[:12]:
        if re.match(r"^\d{4}\s", line):  # 年份页眉
            continue
        if ("IEEE" in line or "Elsevier" in line or "ScienceDirect" in line) and len(line) < 60:
            continue
        if re.match(r"^(arXiv:|Available at|www\.)", line, re.I):
            continue
        if len(line) > 25:
            candidates.append(line)
    return " ".join(candidates[:2])[:200] if candidates else ""


def parse_structure(full_text: str) -> dict:
    """从全文中粗略切分 abstract / keywords / sections / references。"""
    result: dict = {"abstract": "", "keywords": [], "sections": {}, "references": []}

    m = _ABSTRACT_RE.search(full_text[:6000])
    if m:
        result["abstract"] = re.sub(r"\s+", " ", m.group(1)).strip()

    m = _KEYWORDS_RE.search(full_text[:8000])
    if m:
        kw_text = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".")
        result["keywords"] = [k.strip() for k in kw_text.split(",") if k.strip()]

    ref_m = _REFERENCES_RE.search(full_text)
    body = full_text[: ref_m.start()] if ref_m else full_text

    matches = list(_SECTION_RE.finditer(body))
    for i, sm in enumerate(matches):
        start = sm.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        title = re.sub(r"\s+", " ", sm.group(1)).strip()
        result["sections"][title] = body[start:end].strip()

    if ref_m:
        ref_text = full_text[ref_m.end() :]
        refs = re.split(r"\n\s*\[\d+\]\s*", ref_text)
        result["references"] = [
            re.sub(r"\s+", " ", r).strip() for r in refs if len(r.strip()) > 20
        ][:200]

    return result


def _lookup_paper(pdf_path: Path) -> tuple[str, str]:
    """从同目录 manifest.json 或文件名确定 (paper_id, source)。"""
    entry = load_manifest(pdf_path.parent).get(pdf_path.name)
    if entry:
        # 兼容 ieee_tools 旧格式 {arnumber, title}
        pid = str(entry.get("id") or entry.get("arnumber") or "")
        return pid, str(entry.get("source") or "")
    # 无 manifest：文件名直接当 ID（适用于 --name-by-id 下载的论文）
    stem = pdf_path.stem
    if re.fullmatch(r"[\d.]+(v\d+)?", stem):
        return stem, "arxiv" if "." in stem else ""
    if re.fullmatch(r"[A-Za-z0-9]{10,}", stem):
        return stem, "elsevier"
    return "", ""


def process_pdf(pdf_path: Path, outdir: Path) -> dict:
    """处理单个 PDF，返回结构化 dict 并写盘。"""
    paper_id, source = _lookup_paper(pdf_path)
    print(f"[EXTRACT] {pdf_path.name}" + (f" ({source}:{paper_id})" if paper_id else ""))

    full_text, pages, extractor = extract_raw_text(pdf_path)
    needs_ocr = not full_text.strip()
    if needs_ocr:
        print("  [WARN] 未提取到文本层（可能是扫描版），标记 needs_ocr=true")
    else:
        print(f"  {pages} 页, {len(full_text):,} 字符 (via {extractor})")

    structure = parse_structure(full_text) if full_text.strip() else {
        "abstract": "", "keywords": [], "sections": {}, "references": [],
    }

    record = {
        "paper_id": paper_id,
        "source": source,
        "pdf_file": pdf_path.name,
        "metadata": {
            "pages": pages,
            "pdf_size_bytes": pdf_path.stat().st_size,
            "extractor": extractor,
        },
        "title": guess_title(full_text[:3000]) if full_text else "",
        **structure,
        "full_text": full_text,
        "needs_ocr": needs_ocr,
    }

    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"{pdf_path.stem}.json"  # JSON 与 PDF 同名（标题命名时即标题）
    out_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [OK] -> {out_path}")
    return record


def print_preview(record: dict) -> None:
    print(f"paper_id : {record['paper_id']}  (source: {record.get('source') or '?'})")
    print(f"title    : {record['title']}")
    print(f"pages    : {record['metadata']['pages']}, extractor: {record['metadata']['extractor']}")
    print(f"abstract : {record['abstract'][:300]}{'...' if len(record['abstract']) > 300 else ''}")
    print(f"keywords : {', '.join(record['keywords'][:10])}")
    print(f"sections : {', '.join(record['sections'].keys())}")
    print(f"refs     : {len(record['references'])} 条")
    print(f"full_text: {len(record['full_text']):,} 字符, needs_ocr={record['needs_ocr']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="论文 PDF 文本载入与结构化（多源通用）")
    ap.add_argument("ids", nargs="*", help="只处理指定 ID（默认全部；对应 <id>.pdf 文件名）")
    ap.add_argument("--indir", type=str, default=str(DEFAULT_INDIR))
    ap.add_argument("--outdir", type=str, default=str(DEFAULT_OUTDIR))
    ap.add_argument("--print", dest="preview", type=str, default=None,
                    help="打印已提取 JSON 的摘要（不重新提取）")
    args = ap.parse_args()

    indir, outdir = Path(args.indir), Path(args.outdir)

    if args.preview:
        p = outdir / f"{args.preview}.json"
        if not p.exists():
            print(f"[ERROR] 未找到 {p}", file=sys.stderr)
            return 1
        print_preview(json.loads(p.read_text(encoding="utf-8")))
        return 0

    if args.ids:
        pdfs = [indir / f"{a}.pdf" for a in args.ids]
        missing = [str(p) for p in pdfs if not p.exists()]
        if missing:
            print(f"[ERROR] 文件不存在: {missing}", file=sys.stderr)
            return 1
    else:
        pdfs = sorted(indir.glob("*.pdf"))

    if not pdfs:
        print(f"[ERROR] {indir} 下没有 PDF 文件", file=sys.stderr)
        return 1

    print(f"输入目录: {indir.resolve()}  ({len(pdfs)} 个 PDF)")
    print(f"输出目录: {outdir.resolve()}\n")

    index = []
    failed = 0
    for pdf in pdfs:
        try:
            rec = process_pdf(pdf, outdir)
            index.append({
                "paper_id": rec["paper_id"],
                "source": rec["source"],
                "title": rec["title"],
                "pages": rec["metadata"]["pages"],
                "needs_ocr": rec["needs_ocr"],
                "json": f"{pdf.stem}.json",
            })
        except Exception as e:
            print(f"  [FAIL] {pdf.name}: {e}")
            failed += 1
        print()

    outdir.mkdir(parents=True, exist_ok=True)
    index_path = outdir / "index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"完成: {len(index)}/{len(pdfs)} 成功，索引 -> {index_path}")
    if any(r["needs_ocr"] for r in index):
        print("提示: 存在扫描版 PDF（needs_ocr=true），如需全文请走 OCR 方案"
              "（pdf2image + tesseract，见 docs/ieee_xplore_workflow.md 4.3 方法2）。")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
