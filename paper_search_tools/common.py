"""
通用工具函数
============

PDF 校验、文件名清洗、manifest 读写，供 download.py / extract_text.py 共用。
与 ieee_tools 的规则保持一致，manifest 条目额外记录 source 字段。
"""

from __future__ import annotations

import json
from pathlib import Path

MIN_PDF_BYTES = 50_000  # 小于 50KB 视为无效（可能是 viewer 壳 / 错误页）


def verify_pdf(pdf_path: Path, min_bytes: int = MIN_PDF_BYTES) -> bool:
    """校验：存在、大小足够、以 %PDF- 开头。"""
    if not pdf_path.exists() or pdf_path.stat().st_size < min_bytes:
        return False
    with pdf_path.open("rb") as f:
        return f.read(5) == b"%PDF-"


_FILENAME_BAD = '<>:"/\\|?*'


def sanitize_filename(title: str, max_len: int = 120) -> str:
    """把论文标题转为 Windows 安全文件名：去非法字符、压缩空白、按词边界截断。"""
    name = "".join(" " if c in _FILENAME_BAD else c for c in title)
    name = " ".join(name.split()).strip().rstrip(".")
    if len(name) > max_len:
        cut = name.rfind(" ", 0, max_len)
        name = name[: cut if cut > max_len // 2 else max_len].rstrip()
    return name or "untitled"


def load_manifest(outdir: Path) -> dict:
    """读取 manifest.json（文件名 -> {source, id, title}），不存在或损坏返回 {}。"""
    manifest_path = outdir / "manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def update_manifest(outdir: Path, records: list[dict]) -> None:
    """合并写入 manifest.json。records 项需含 filename / source / id / title。"""
    manifest = load_manifest(outdir)
    for r in records:
        manifest[r["filename"]] = {
            "source": r.get("source", ""),
            "id": r.get("id", ""),
            "title": r.get("title", ""),
        }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
