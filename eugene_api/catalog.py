"""
Loads the JSON catalogs produced by tools/parse_catalog.py (parsed from
Eugene's TRAN서비스IO.pdf / Real서비스IO.pdf) into typed, sanitized specs
that the route generator turns into FastAPI endpoints.

The source PDFs are mostly-consistent bordered tables, but a handful of
entries embed long multi-line "code = meaning" legends inside a Description
cell; a naive table walk misreads a few of those lines as bogus extra
fields. Rather than trust every parsed field blindly (which would either
crash pydantic model creation on duplicate/invalid names, or send garbage
item names to the real OCX call), every field list is sanitized here:
invalid identifiers and duplicates are dropped, and the drop counts are
recorded so the load-time report tells you exactly which TR/Real codes are
worth double-checking against the original PDF.
"""
from __future__ import annotations

import json
import keyword
import pathlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

CATALOG_DIR = pathlib.Path(__file__).resolve().parent.parent / "catalog"
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_ITEM_LEN = 40


@dataclass
class FieldSpec:
    item: str
    name: str
    size: str
    description: str


@dataclass
class SanitizeResult:
    clean: List[FieldSpec]
    dropped: List[str]


def _sanitize(raw_fields: List[dict]) -> SanitizeResult:
    clean: List[FieldSpec] = []
    dropped: List[str] = []
    seen = set()
    for raw in raw_fields:
        item = raw.get("item", "")
        valid = (
            bool(_IDENT_RE.match(item))
            and not keyword.iskeyword(item)
            and len(item) <= _MAX_ITEM_LEN
        )
        if not valid or item in seen:
            dropped.append(item[:60])
            continue
        seen.add(item)
        clean.append(FieldSpec(item=item, name=raw.get("name", ""), size=raw.get("size", ""),
                                description=raw.get("description", "")))
    return SanitizeResult(clean=clean, dropped=dropped)


@dataclass
class TranSpec:
    code: str
    title: str
    description: str
    continuable: Optional[str]
    input: List[FieldSpec]
    output_single: List[FieldSpec]
    output_multi: List[FieldSpec]
    remarks: List[str] = field(default_factory=list)
    dropped_fields: List[str] = field(default_factory=list)

    @property
    def is_mutating(self) -> bool:
        """TR codes ending in U are order/cancel/amend ("처리") calls; Q is query ("조회")."""
        return self.code.upper().endswith("U")

    @property
    def has_usable_schema(self) -> bool:
        return bool(self.output_single or self.output_multi)


@dataclass
class RealSpec:
    real_id: str
    code: str
    title: str
    description: str
    real_code_desc: List[str]
    output: List[FieldSpec]
    remarks: List[str] = field(default_factory=list)
    dropped_fields: List[str] = field(default_factory=list)


def _load_raw(path: pathlib.Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tran_catalog(path: Optional[pathlib.Path] = None) -> Dict[str, TranSpec]:
    path = path or CATALOG_DIR / "tran_catalog.json"
    specs: Dict[str, TranSpec] = {}
    for e in _load_raw(path):
        code = e.get("code")
        if not code:
            continue
        inp = _sanitize(e.get("input", []))
        single = _sanitize(e.get("output_single", []))
        multi = _sanitize(e.get("output_multi", []))
        specs[code] = TranSpec(
            code=code,
            title=(e.get("title") or code).strip(),
            description=(e.get("description") or "").strip(),
            continuable=e.get("continuable"),
            input=inp.clean,
            output_single=single.clean,
            output_multi=multi.clean,
            remarks=e.get("remarks", []),
            dropped_fields=inp.dropped + single.dropped + multi.dropped,
        )
    return specs


def load_real_catalog(path: Optional[pathlib.Path] = None) -> Dict[str, RealSpec]:
    path = path or CATALOG_DIR / "real_catalog.json"
    specs: Dict[str, RealSpec] = {}
    for e in _load_raw(path):
        real_id = e.get("real_id")
        if not real_id:
            continue
        out = _sanitize(e.get("output", []))
        specs[real_id] = RealSpec(
            real_id=real_id,
            code=(e.get("code") or real_id).strip(),
            title=(e.get("title") or real_id).strip(),
            description=(e.get("description") or "").strip(),
            real_code_desc=e.get("real_code_desc", []),
            output=out.clean,
            remarks=e.get("remarks", []),
            dropped_fields=out.dropped,
        )
    return specs


def build_quality_report(tran: Dict[str, TranSpec], real: Dict[str, RealSpec]) -> dict:
    return {
        "tran": {code: spec.dropped_fields for code, spec in tran.items() if spec.dropped_fields},
        "real": {rid: spec.dropped_fields for rid, spec in real.items() if spec.dropped_fields},
    }
