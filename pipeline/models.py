"""Record model shared by every connector. One Program == one row in `program` plus its junction rows."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict

Level = Literal["federal", "state", "county", "city", "utility"]
FundingType = Literal[
    "grant", "cooperative_agreement", "rebate", "loan", "tax_credit",
    "forgivable_loan", "formula", "voucher", "other",
]
FundingSource = Literal["direct", "pass_through"]
Status = Literal["open", "forecasted", "closed", "paused", "exhausted", "unknown"]
ApplicantType = Literal[
    "municipality", "county", "state", "tribe", "special_district", "school", "higher_ed",
    "housing_authority", "nonprofit", "business", "household", "individual", "utility",
]
Category = Literal[
    "infrastructure", "housing", "energy", "water", "transportation", "broadband",
    "public_safety", "parks", "health", "workforce", "other",
]

ALL_APPLICANT_TYPES: tuple[str, ...] = get_args(ApplicantType)
ALL_CATEGORIES: tuple[str, ...] = get_args(Category)


class ApplicantTag(BaseModel):
    """A normalized applicant type plus the raw source code it was mapped from."""
    model_config = ConfigDict(frozen=True)
    value: ApplicantType
    source_code: str = ""


class CategoryTag(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: Category
    source_code: str = ""


class RawRecord(BaseModel):
    """What a connector's fetch() returns. payload is stored verbatim in raw_record."""
    source_connector: str
    source_id: str
    payload: dict[str, Any]


# Columns of `program` that the connector owns. Everything else on the row
# (id, slug, parent_program_id, record_hash, timestamps) is managed by the pipeline.
PROGRAM_FIELDS: tuple[str, ...] = (
    "source_connector", "source_id", "source_url", "external_number", "name", "level",
    "jurisdiction", "administering_agency", "agency_code", "funding_type", "funding_source",
    "amount_min", "amount_max", "match_required", "match_pct", "status", "opens_at",
    "closes_at", "closes_at_text", "rolling", "summary", "eligibility_text",
    "eligibility_structured",
)
LIST_FIELDS: tuple[str, ...] = ("applicant_types", "categories", "alns")


class Program(BaseModel):
    source_connector: str
    source_id: str
    source_url: str
    external_number: str | None = None
    name: str
    level: Level
    jurisdiction: str
    administering_agency: str | None = None
    agency_code: str | None = None
    funding_type: FundingType | None = None
    funding_source: FundingSource
    amount_min: int | None = None
    amount_max: int | None = None
    match_required: bool | None = None
    match_pct: float | None = None
    status: Status
    opens_at: date | None = None
    closes_at: date | None = None
    closes_at_text: str | None = None
    rolling: bool | None = None
    summary: str | None = None
    eligibility_text: str | None = None
    eligibility_structured: dict[str, Any] | None = None
    applicant_types: list[ApplicantTag] = []
    categories: list[CategoryTag] = []
    alns: list[str] = []

    @property
    def slug(self) -> str:
        return f"{slugify(self.name)[:80]}-{self.source_connector.replace('_', '-')}-{self.source_id}"

    def row(self) -> dict[str, Any]:
        """Column values for the `program` table, SQLite-typed (bools -> 0/1, dates -> ISO, json -> text)."""
        out: dict[str, Any] = {}
        for f in PROGRAM_FIELDS:
            v = getattr(self, f)
            if isinstance(v, bool):
                v = int(v)
            elif isinstance(v, date):
                v = v.isoformat()
            elif isinstance(v, dict):
                v = json.dumps(v, sort_keys=True, separators=(",", ":"))
            out[f] = v
        return out

    def applicant_pairs(self) -> list[tuple[str, str]]:
        return sorted({(t.value, t.source_code) for t in self.applicant_types})

    def category_pairs(self) -> list[tuple[str, str]]:
        return sorted({(t.value, t.source_code) for t in self.categories})

    def aln_list(self) -> list[str]:
        return sorted(set(self.alns))

    def canonical(self) -> dict[str, Any]:
        """Everything that counts as 'the record' for change detection."""
        data = self.row()
        data["applicant_types"] = self.applicant_pairs()
        data["categories"] = self.category_pairs()
        data["alns"] = self.aln_list()
        return data

    @property
    def record_hash(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Program:
        """Rebuild a Program from a `program` row dict that also carries the three list fields
        (as produced by pipeline.upsert.load_existing)."""
        data = {f: row.get(f) for f in PROGRAM_FIELDS}
        for b in ("match_required", "rolling"):
            if data[b] is not None:
                data[b] = bool(data[b])
        if isinstance(data.get("eligibility_structured"), str):
            data["eligibility_structured"] = json.loads(data["eligibility_structured"])
        data["applicant_types"] = [ApplicantTag(value=v, source_code=c) for v, c in row.get("applicant_types", [])]
        data["categories"] = [CategoryTag(value=v, source_code=c) for v, c in row.get("categories", [])]
        data["alns"] = list(row.get("alns", []))
        return cls(**data)


_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _slug_re.sub("-", text.lower()).strip("-") or "program"
