import hashlib
import re
from urllib.parse import quote

from .config import REPOSITORY, SOURCE_PREFIX
from .models import Document, Evidence


def stable_id(*parts):
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]


def source_url(commit, path, start=None, end=None):
    base = f"https://github.com/{REPOSITORY}/blob/{commit}/{quote(path)}"
    return base if start is None else f"{base}#L{start}-L{end}"


def document(path, text, commit):
    title = path.removeprefix(SOURCE_PREFIX).rsplit(".", 1)[0].replace("/", "／")
    return Document(
        id=stable_id(REPOSITORY, path),
        title=title,
        source_path=path,
        source_commit=commit,
        source_url=source_url(commit, path),
    )


def safe_lines(text):
    """Keep original coordinates. Exclude whole unsafe lines rather than invent quotes."""
    # Split on LF only: retain CR bytes so evidence remains a literal substring
    # of CRLF originals, including multi-line paragraphs.
    lines = text.split("\n")
    frontmatter = bool(lines and lines[0].strip() == "---")
    fence = None
    comment = False
    script = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if frontmatter:
            if i > 1 and s == "---":
                frontmatter = False
            yield i, None
            continue
        marker = re.match(r"^(`{3,}|~{3,})", s)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            yield i, None
            continue
        if fence:
            yield i, None
            continue
        unsafe = comment or script or "<!--" in line or bool(re.search(r"<script\b", line, re.I))
        if "<!--" in line:
            comment = True
        if "-->" in line:
            comment = False
        if re.search(r"<script\b", line, re.I):
            script = True
        if re.search(r"</script\s*>", line, re.I):
            script = False
        if unsafe or s.startswith(("import ", "export ")) or re.match(r"^!\[.*\]\(.*\)\s*$", s):
            yield i, None
        else:
            yield i, line


def campus_for(path, text):
    # Mixed-campus passages must never inherit the directory's campus.
    shahe = bool(re.search("沙河|雁南|雁北|雁西", text))
    haidian = bool(re.search("海淀|西土城|本部", text))
    if shahe and haidian:
        return "unknown"
    if shahe:
        return "shahe"
    if haidian:
        return "haidian"
    if "/沙河校区/" in path:
        return "shahe"
    if "/海淀校区/" in path:
        return "haidian"
    # Explicitly curated general-topic directories; arbitrary paths are NOT shared.
    if any(f"/{d}/" in path for d in ("学习生活", "新生入学", "学生组织")) or path.endswith("/行话辞典.md"):
        return "shared"
    return "unknown"


def chunks(path, text, token_length, max_tokens=400):
    result, heading, block = [], [], []

    def flush():
        if not block:
            return
        start, end = block[0][0], block[-1][0]
        raw = "\n".join(x[1] for x in block)
        if raw.strip():
            title = " / ".join(title for _, title in heading)
            result.append(
                {
                    "key": stable_id(path, str(start), str(end), raw),
                    "text": raw,
                    "heading": title,
                    "line_start": start,
                    "line_end": end,
                    "campus": campus_for(path, title + "\n" + raw),
                }
            )
        block.clear()

    for line_no, line in safe_lines(text):
        if line is None or not line.strip():
            flush()
            continue
        h = re.match(r"^(#{1,6})\s+(.+)", line)
        if h:
            flush()
            heading = [(level, title) for level, title in heading if level < len(h[1])] + [
                (len(h[1]), h[2].rstrip("\r"))
            ]
            continue
        # Split an unusually long original line into exact substrings. Evidence still
        # references that original line; no cleaning changes quote coordinates.
        pieces = [line]
        while any(token_length(p) > max_tokens for p in pieces):
            split = []
            for p in pieces:
                if token_length(p) > max_tokens and len(p) > 1:
                    split.extend([p[: len(p) // 2], p[len(p) // 2 :]])
                else:
                    split.append(p)
            pieces = split
        for piece in pieces:
            if block and token_length("\n".join(x[1] for x in block) + "\n" + piece) > max_tokens:
                flush()
            if len(pieces) > 1:
                flush()
            block.append((line_no, piece))
            if len(pieces) > 1:
                flush()
    flush()
    return result


def evidence_for(doc, chunk):
    return Evidence(
        id=stable_id(doc.id, doc.source_commit, chunk["key"]),
        doc_id=doc.id,
        source_commit=doc.source_commit,
        source_path=doc.source_path,
        heading=chunk["heading"],
        line_start=chunk["line_start"],
        line_end=chunk["line_end"],
        quote=chunk["text"],
        source_url=source_url(doc.source_commit, doc.source_path, chunk["line_start"], chunk["line_end"]),
    )
