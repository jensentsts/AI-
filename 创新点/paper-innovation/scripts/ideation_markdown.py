"""Small Markdown readers for the innovation workflow (standard library only)."""

import re

PID = r"P[1-9]\d*(?:[-_.]?v[1-9]\d*|[a-z])?"
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
PLACEHOLDER = re.compile(
    r"\{\{[^{}\n]+\}\}|\b(?:TODO|TBD)\b|"
    r"【(?:填写|例如|例如：|写明|列出|具体|对应|描述|待填|名称与单位|数值|"
    r"P_[xy]|PASS/REVISE/KILL|文献编号|工程代价)[^】\n]*】",
    re.I,
)
INLINE = re.compile(
    r"\\\||(?P<ticks>`+).*?(?P=ticks)|\$\$.*?\$\$|\$(?:\\.|[^$])*?\$|"
    r"\\\(.*?\\\)|\\\[.*?\\\]|(?<!\w)(?:P|Pr|p)\([^()\n]*\|[^()\n]*\)|\|"
)


def placeholders(text):
    return [(n, match.group()) for n, line in enumerate(text.splitlines(), 1)
            for match in PLACEHOLDER.finditer(line)]


def has_value(value):
    if not value or PLACEHOLDER.search(value):
        return False
    plain = re.sub(r"<!--.*?-->", "", value).strip().strip("`*_ \t")
    return plain.lower() not in {
        "", "-", "—", "–", "...", "…", "?", "待填", "待填写", "待补", "待定",
        "待确认", "未填", "未填写", "草稿", "pending", "unknown", "tbd", "n/a",
    }


def section(text, key, fallback_heading_regex):
    """Read an anchored Markdown section, or a matching heading in an older file."""
    lines = text.splitlines()
    headings = [(i, len(m[1]), m[2]) for i, line in enumerate(lines)
                if (m := HEADING.match(line))]
    anchor = re.compile(r"<!--\s*section:" + re.escape(key) + r"\s*-->", re.I)
    marker = next((i for i, line in enumerate(lines) if anchor.search(line)), None)
    if marker is not None:
        heading = next((h for h in reversed(headings) if h[0] <= marker), None)
        start, level = marker + 1, heading[1] if heading else 1
    else:
        if not fallback_heading_regex:
            return ""
        pattern = re.compile(fallback_heading_regex, re.I)
        matches = [h for h in headings if pattern.search(h[2])]
        if not matches:
            return ""
        idx, level, _ = next((h for h in matches if h[1] > 1), matches[0])
        start = idx + 1
    end = next((idx for idx, depth, _ in headings if idx >= start and depth <= level), len(lines))
    return "\n".join(lines[start:end]).strip()


def field(text, key, fallback_label_regex):
    """Read one marked field. A marker is authoritative even if its value is blank."""
    anchor = re.compile(r"<!--\s*field:" + re.escape(key) + r"\s*-->", re.I)
    label = re.compile(fallback_label_regex, re.I) if fallback_label_regex else None
    lines = text.splitlines()
    anchored = [i for i, line in enumerate(lines) if anchor.search(line)]
    for i in anchored or range(len(lines)):
        line = re.sub(r"<!--.*?-->", "", lines[i]).strip()
        line = re.sub(r"^[-*+]\s+", "", line)
        if line.startswith(("#", "|", "[")) or not line:
            continue
        bold = re.match(r"^\*\*(.+?)\*\*\s*[:：]\s*(.*)$", line)
        if bold:
            name, value = bold.groups()
        else:
            parts = re.split(r"\s*[:：]\s*", line, maxsplit=1)
            if len(parts) != 2:
                continue
            name, value = parts
        if not anchored and (label is None or not label.search(name)):
            continue
        if not value.strip():
            continuation = []
            for child in lines[i + 1:]:
                if not child.startswith(("  ", "\t")) or "<!-- field:" in child:
                    break
                continuation.append(child.strip())
            value = "\n".join(continuation)
        return value.strip()
    return ""


def _cells(line):
    # Only unprotected pipes delimit cells; an escaped pipe is literal GFM content.
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith(r"\|"):
        line = line[:-1]
    pieces, start, current = [], 0, []
    for token in INLINE.finditer(line):
        current.append(line[start:token.start()])
        if token.group() == "|":
            pieces.append("".join(current).strip())
            current = []
        else:
            current.append("|" if token.group() == r"\|" else token.group())
        start = token.end()
    current.append(line[start:])
    pieces.append("".join(current).strip())
    return pieces


def table(text):
    """Return (header, rows) of the first GFM table with a real separator."""
    lines = text.splitlines()
    for n in range(1, len(lines)):
        if "|" not in lines[n] or "|" not in lines[n - 1]:
            continue
        separators = _cells(lines[n])
        if not separators or not all(re.fullmatch(r":?-{3,}:?", x) for x in separators):
            continue
        header = _cells(lines[n - 1])
        if len(header) != len(separators):
            continue
        rows = []
        for line in lines[n + 1:]:
            if not line.strip() or "|" not in line or line.lstrip().startswith(("#", "<!--")):
                break
            rows.append(_cells(line))
        return header, rows
    return [], []
