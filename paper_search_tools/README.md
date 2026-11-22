# paper_search_tools — 多源论文检索 / 下载 / 文本载入脚本组

在 `ieee_tools` 同一套技术方案上扩展的多源版本，支持
**arXiv**、**Web of Science**、**Elsevier（ScienceDirect）** 三个来源，
功能对齐：关键词检索 → 批量下载 PDF → 文本结构化提取。

> 与 `ieee_tools` 完全独立，互不依赖；两个工具可以并存使用。

## 组成

```
paper_search_tools/
├── webbridge_client.py        # WebBridge daemon 共享客户端（浏览器源用）
├── common.py                  # PDF 校验 / 文件名清洗 / manifest 读写
├── search.py                  # 多源检索 CLI
├── download.py                # 多源批量下载 CLI（按来源自动路由）
├── extract_text.py            # PDF 文本提取与结构化（纯本地，多源通用）
└── sources/
    ├── __init__.py            # 源注册表（SOURCES / PRIMARY）
    ├── arxiv_source.py        # arXiv：官方 API，纯 Python，无需浏览器
    ├── wos_source.py          # Web of Science：WebBridge 浏览器自动化
    └── sciencedirect_source.py# Elsevier/ScienceDirect：WebBridge 检索 + 下载
```

## 各源能力矩阵

| 来源 | 检索 | PDF 下载 | 需要浏览器 | 说明 |
|------|------|---------|-----------|------|
| `arxiv` | ✅ 官方 API | ✅ 直连 `arxiv.org/pdf/<id>` | ❌ | 请求间隔 ≥ 3s（官方礼仪） |
| `wos` | ✅ WebBridge | ❌ | ✅ | WoS 是引文索引，**不托管全文**；用结果中的 DOI 交给其他源下载 |
| `elsevier` (= `sciencedirect`) | ✅ WebBridge | ✅ WebBridge 页面内 fetch | ✅ | 需机构认证；非 OA 文章可能下载失败 |

## 前置条件

1. **仅浏览器源（wos / elsevier）需要**：
   - 启动 WebBridge daemon：

     ```powershell
     & "$env:USERPROFILE\.kimi-webbridge\bin\kimi-webbridge.exe" start
     ```

   - 打开装有 Kimi WebBridge 扩展的浏览器，访问 WoS / ScienceDirect 并确认
     校园网 / 机构认证通过（能正常打开论文全文页）。
2. `arxiv` 源与 `extract_text.py` 离线/直连运行，无上述要求。

## 典型流程

```bash
# 1. 检索：--source 指定来源（arxiv / wos / elsevier / all）
python search.py "virtual inertia reinforcement learning" --source arxiv --pages 2
python search.py "wind power virtual inertia" --source elsevier --year-from 2016 --year-to 2025
python search.py "virtual inertia" --source all --out results.json

# 2. 下载：按检索结果中的 source 字段自动路由（混合多源也可以）
python download.py --from-search results.json

#    或指定来源 + ID 列表 / 清单文件
python download.py --source arxiv 2101.12345 2202.00001
python download.py --source elsevier --file piis.txt

# 3. 文本载入：PDF -> 结构化 JSON（../papers_text/）
python extract_text.py                  # 全部
python extract_text.py 2101.12345       # 单篇（文件名需为 <id>.pdf）
python extract_text.py --print 2101.12345
```

## 统一检索记录格式

```json
{
  "id": "2101.12345v2 或 WOS:000xxx 或 PII",
  "source": "arxiv | wos | elsevier",
  "title": "...",
  "url": "详情页 URL",
  "authors": ["..."],
  "year": 2024,
  "snippet": "摘要（arxiv）或页面文本片段（wos/elsevier）",
  "doi": "...",
  "query": "原始检索词"
}
```

## 输出

- 检索：`search_results_<来源>_<时间戳>.json`
- 下载：`../papers/{标题或ID}.pdf`，自动跳过已存在的有效文件，
  逐篇校验 `%PDF-` 头与大小；`manifest.json` 记录 文件名 → {source, id, title}
- 文本：`../papers_text/{文件名}.json` + `index.json`，字段含
  paper_id / source / title / abstract / keywords / sections / references /
  full_text / needs_ocr

## 注意事项

- **WoS 前端是 Angular SPA 且大量使用 shadow DOM**，检索提交与结果提取的 JS
  是启发式的；若提取为空，先确认机构认证，再按 `wos_source.py` 中的诊断输出
  （返回的 inputs 列表）调整选择器。
- ScienceDirect 下载对**非 OA 文章**可能失败（取决于机构订阅范围）；
  批量失败多半是认证过期，在浏览器重新打开 ScienceDirect 主页完成认证后重试。
- arXiv 年份过滤在客户端完成（API 不支持按年范围过滤 relevance 排序结果）；
  WoS / Elsevier 的年份从页面文本片段启发式提取或走 URL 参数，精度有限。
- 超过 12 MB 的 PDF（elsevier 源）自动切换分块回传，避免 evaluate 返回值截断。
- 章节切分是启发式的，双栏排版的标题可能被 pypdf 拆开，sections 仅供参考；
  扫描版 PDF 标记 `needs_ocr=true`，需另走 OCR。
- 各平台页面结构可能变化，检索解析均不依赖动态类名（arXiv 用 API，
  WoS 用 `full-record/WOS:` 链接，ScienceDirect 用 `/science/article/pii/` 链接）。
