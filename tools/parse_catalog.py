"""
Parse Eugene Investment & Securities' Champion OpenAPI "TRAN서비스IO.pdf" and
"Real서비스IO.pdf" guide documents into machine-readable JSON catalogs.

Both PDFs use one bordered table per TR-code / Real-ID, with a consistent
row layout (제목/설명/Subject/INPUT RECORD/OUTPUT RECORD/.../비고). This
walks every table row on every page as a flat stream and reconstructs each
entry with a small state machine, so the resulting catalogs drive the
FastAPI route generator without hand-maintaining ~200 TR codes by hand.

Usage:
    python parse_catalog.py tran <TRAN서비스IO.pdf> <out_tran_catalog.json>
    python parse_catalog.py real <Real서비스IO.pdf> <out_real_catalog.json>
"""
import json
import re
import sys

import pdfplumber

MIN_TABLE_AREA = 4000  # filters out the tiny page-number footer tables


def compact_row(row):
    """Collapse a pdfplumber table row (lots of None from merged cells) into
    the ordered list of non-empty cell values."""
    out = []
    for cell in row:
        if cell is None:
            continue
        text = cell.strip()
        if text:
            out.append(text)
    return out


def parse_field_row(tokens):
    if len(tokens) >= 4:
        item, name, size, desc = tokens[0], tokens[1], tokens[2], " ".join(tokens[3:])
    elif len(tokens) == 3:
        item, name, size, desc = tokens[0], tokens[1], tokens[2], ""
    elif len(tokens) == 2:
        item, name, size, desc = tokens[0], tokens[1], "", ""
    elif len(tokens) == 1:
        item, name, size, desc = tokens[0], "", "", ""
    else:
        return None
    return {
        "item": item,
        "name": name.replace("\n", " ").strip(),
        "size": size.strip(),
        "description": desc.replace("\n", " ").strip(),
    }


def is_header_row(tokens):
    return bool(tokens) and tokens[0] == "Item" and any(
        t in ("ItemName", "Item name", "Item Name") for t in tokens[1:2]
    )


def iter_compact_rows(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            for table in page.find_tables():
                x0, top, x1, bottom = table.bbox
                area = (x1 - x0) * (bottom - top)
                if area < MIN_TABLE_AREA:
                    continue
                for row in table.extract():
                    tokens = compact_row(row)
                    if tokens:
                        yield page_index + 1, tokens


def new_entry(kind):
    if kind == "tran":
        return {
            "code": None,
            "title": None,
            "description": None,
            "continuable": None,
            "input": [],
            "output_single": [],
            "output_multi": [],
            "remarks": [],
            "page": None,
        }
    return {
        "real_id": None,
        "code": None,
        "title": None,
        "description": None,
        "real_code_desc": [],
        "output": [],
        "remarks": [],
        "page": None,
    }


def parse(pdf_path, kind):
    assert kind in ("tran", "real")
    entries = []
    entry = None
    section = None

    def finalize():
        nonlocal entry
        if entry is not None and (entry.get("code") or entry.get("title")):
            entries.append(entry)
        entry = None

    for page_no, tokens in iter_compact_rows(pdf_path):
        head = tokens[0]

        if head in ("제 목", "제목"):
            finalize()
            entry = new_entry(kind)
            entry["title"] = tokens[1] if len(tokens) > 1 else ""
            entry["page"] = page_no
            section = None
            continue

        if entry is None:
            continue  # cover / table-of-contents noise before the first entry

        if head in ("설 명", "설명"):
            entry["description"] = (tokens[1] if len(tokens) > 1 else "").replace("\n", " ")
            continue

        if head in ("Subject", "RQRP ID"):
            # Most TRAN pages label the TR code "Subject"; a few use "RQRP ID" instead.
            entry["code"] = tokens[1] if len(tokens) > 1 else None
            if kind == "tran":
                entry["continuable"] = tokens[2] if len(tokens) > 2 else None
            continue

        if head == "Real ID":
            entry["real_id"] = tokens[1] if len(tokens) > 1 else None
            if "Subject" in tokens:
                i = tokens.index("Subject")
                if i + 1 < len(tokens):
                    entry["code"] = tokens[i + 1]
            continue

        if head == "Real Code":
            section = "real_code"
            if len(tokens) > 1:
                entry["real_code_desc"].append(tokens[1])
            continue

        if head == "INPUT RECORD":
            section = "input"
            continue

        if head == "OUTPUT RECORD":
            section = "output"
            continue

        if head == "Single RECORD":
            section = "output_single"
            continue

        if head == "Multi RECORD":
            section = "output_multi"
            continue

        if head in ("비 고", "비고"):
            section = "remark"
            continue

        if is_header_row(tokens):
            continue  # "Item / ItemName / Item Size / Description" column header

        if head == "없음":
            continue  # explicit "no fields" marker

        if head == "Record Index":
            continue

        # plain data / continuation row, routed by current section
        if section == "input":
            field = parse_field_row(tokens)
            if field:
                entry["input"].append(field)
        elif section == "output_single":
            field = parse_field_row(tokens)
            if field:
                entry["output_single"].append(field)
        elif section == "output_multi":
            field = parse_field_row(tokens)
            if field:
                entry["output_multi"].append(field)
        elif section == "output":
            field = parse_field_row(tokens)
            if field:
                entry["output"].append(field)
        elif section == "remark":
            entry["remarks"].append(" | ".join(tokens))
        elif section == "real_code":
            entry["real_code_desc"].append(tokens[0])
        # else: stray row before any section marker - ignore

    finalize()
    return entries


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    kind, pdf_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    entries = parse(pdf_path, kind)

    # de-dup by code (a handful of TR codes are cross-referenced twice in the TOC groupings)
    seen = {}
    for e in entries:
        key = e.get("code") or e.get("title")
        seen[key] = e  # last occurrence wins, entries are unique per detail page anyway
    entries = list(seen.values())

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"Parsed {len(entries)} {kind} entries -> {out_path}")
    missing_code = [e for e in entries if not e.get("code")]
    if missing_code:
        print(f"WARNING: {len(missing_code)} entries missing a code:")
        for e in missing_code[:10]:
            print("  page", e.get("page"), repr(e.get("title")))


if __name__ == "__main__":
    main()
