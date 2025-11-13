#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_pdf.py
Elegant filler for AcroForm PDFs whose field names are placeholders.
- Canonical-field extraction from JSON
- Composable preprocessing transforms (including Hebrew RTL & spaced digits)
- Optional rules JSON for overrides
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence

from pdfrw import PdfDict, PdfName, PdfObject, PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

PLACEHOLDER_MAP: Dict[str, str] = {
    "formFillingDate": "formFillingDate",
    "formReceiptDateAtClinic": "formReceiptDateAtClinic",
    "dateOfInjury": "dateOfInjury",
    "lastName": "lastName",
    "firstName": "firstName",
    "idNumber": "idNumber",
    "dateOfBirth": "dateOfBirth",
    "street": "street",
    "houseNumber": "houseNumber",
    "entrance": "entrance",
    "apartment": "apartment",
    "city": "city",
    "postalCode": "postalCode",
    "landlinePhone": "landlinePhone",
    "mobilePhone": "mobilePhone",
    "timeOfInjury": "timeOfInjury",
    "accidentLocation": "accidentLocation",
    "accidentDescription": "accidentDescription",
    "accidentAddress": "accidentAddress",
    "injuredBodyPart": "injuredBodyPart",
    "signature": "signature",
}

DATE_FIELDS = {"dateOfBirth", "dateOfInjury", "formFillingDate", "formReceiptDateAtClinic"}

DEFAULT_RULES: Dict[str, List[str]] = {
    # Hebrew-ish fields: reverse for LTR AcroForm viewers, then trim
    "firstName": ["reverse_hebrew", "strip"],
    "lastName": ["reverse_hebrew", "strip"],
    "city": ["reverse_hebrew", "strip"],
    "street": ["reverse_hebrew", "strip"],
    "entrance": ["reverse_hebrew", "strip"],
    "accidentLocation": ["reverse_hebrew", "strip"],
    "accidentAddress": ["reverse_hebrew", "strip"],
    "accidentDescription": ["reverse_hebrew", "strip"],
    "injuredBodyPart": ["reverse_hebrew", "strip"],

    # Documents & phones
    "idNumber": ["digits_only", "as_spaced_date:4"],
    "mobilePhone": ["digits_only", "as_spaced_date:3"],
    "landlinePhone": ["digits_only", "as_spaced_date:3"],

    # Dates default to boxed-digits style with 3 spaces
    "dateOfBirth": ["as_spaced_date:3"],
    "dateOfInjury": ["as_spaced_date:3"],

    "formFillingDate": ["as_spaced_date:3"],
    "formReceiptDateAtClinic": ["as_spaced_date:3"],

    # Time as-is
    "timeOfInjury": ["strip"],
    "signature": ["reverse_hebrew", "strip"],
}

DEFAULT_RULES_BY_PLACEHOLDER: Dict[str, List[str]] = {}


# ---------------------------------------------------------------------
# Tiny utilities
# ---------------------------------------------------------------------

def _z2(x: str | int | None) -> str:
    s = "" if x in (None, "") else str(x)
    return s.zfill(2) if s else ""

def fmt_date_dotted(obj: Optional[Mapping[str, object]]) -> str:
    if not obj:
        return ""
    d, m, y = _z2(obj.get("day")), _z2(obj.get("month")), str(obj.get("year") or "")
    return f"{d}.{m}.{y}" if d and m and y else ""

def fmt_date_spaced_digits(obj: Optional[Mapping[str, object]], spaces: int = 3) -> str:
    if not obj:
        return ""
    d, m, y = _z2(obj.get("day")), _z2(obj.get("month")), str(obj.get("year") or "")
    if not (d and m and y):
        return ""
    s = f"{d}{m}{y}"
    gap = " " * spaces
    extra_gap = " " * (spaces + 1)  # one more space after 4th digit
    return gap.join(s[:4]) + extra_gap + gap.join(s[4:])


def pick(data: Mapping[str, object], key: str) -> str:
    v = data.get(key, "")
    return "" if v is None else str(v)

def addr(data: Mapping[str, object], key: str) -> str:
    a = (data.get("address") or {})  # type: ignore[assignment]
    if not isinstance(a, Mapping):
        return ""
    v = a.get(key, "")
    return "" if v is None else str(v)


# ---------------------------------------------------------------------
# Extraction (raw, before transforms)
# ---------------------------------------------------------------------

def raw_value(canonical: str, data: Mapping[str, object]) -> str:
    if canonical in {
        "lastName","firstName","idNumber","landlinePhone","mobilePhone",
        "accidentLocation","accidentAddress","accidentDescription","injuredBodyPart",
        "timeOfInjury", "signature"
    }:
        return pick(data, canonical)

    if canonical in {"street","houseNumber","entrance","apartment","city","postalCode"}:
        return addr(data, canonical)

    if canonical in DATE_FIELDS:
        return fmt_date_dotted(data.get(canonical))  # the dotted baseline

    return ""


# ---------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------

Transform = Callable[[str], str]
_HEB = re.compile(r"[\u0590-\u05FF]")

def reverse_hebrew(s: str) -> str:
    return s[::-1] if s and _HEB.search(s) else s

def digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def ensure_prefix(prefix: str) -> Transform:
    def _f(s: str) -> str:
        if not s:
            return s
        stripped = digits_only(s)
        return stripped if stripped.startswith(prefix) else prefix + stripped
    return _f

def strip(s: str) -> str:
    return (s or "").strip()

def space_only_between_digits(n: int = 4) -> Transform:
    gap = " " * n
    def _f(s: str) -> str:
        if not s:
            return s
        out: List[str] = []
        for i, ch in enumerate(s):
            out.append(ch)
            if ch.isdigit() and i + 1 < len(s) and s[i + 1].isdigit():
                out.append(gap)
        return "".join(out)
    return _f

# Registry with lightweight argument parsing "name:arg"
def _parse_rule(r: str) -> tuple[str, Optional[str]]:
    if ":" in r:
        k, v = r.split(":", 1)
        return k.strip(), v.strip()
    return r.strip(), None

REGISTRY: Dict[str, Callable[[Optional[str]], Transform]] = {
    "reverse_hebrew": lambda _: reverse_hebrew,
    "digits_only":    lambda _: digits_only,
    "strip":          lambda _: strip,
    "space_only_between_digits": lambda a: space_only_between_digits(int(a or "3")),
    "ensure_prefix":  lambda a: ensure_prefix(a or ""),
    # "as_spaced_date" handled specially
}

def build_pipeline(rules: Sequence[str]) -> List[Transform]:
    return [REGISTRY[name](arg) for name, arg in map(_parse_rule, rules) if name != "as_spaced_date"]


# ---------------------------------------------------------------------
# Rules loading & application
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class Rules:
    by_canonical: Mapping[str, Sequence[str]]
    by_placeholder: Mapping[str, Sequence[str]]

    @staticmethod
    def load(path: Optional[Path]) -> "Rules":
        if not path:
            return Rules(DEFAULT_RULES, DEFAULT_RULES_BY_PLACEHOLDER)
        with path.open("r", encoding="utf-8") as f:
            obj = json.load(f) or {}
        bc = {**DEFAULT_RULES, **obj.get("byCanonical", {})}
        bp = {**DEFAULT_RULES_BY_PLACEHOLDER, **obj.get("byPlaceholder", {})}
        return Rules(bc, bp)

    def of(self, *, canonical: str, placeholder: str) -> Sequence[str]:
        return self.by_placeholder.get(placeholder) or self.by_canonical.get(canonical) or ()


def apply_rules(
    *,
    canonical: str,
    placeholder: str,
    raw: str,
    data: Mapping[str, object],
    rules: Rules
) -> str:
    rs = list(rules.of(canonical=canonical, placeholder=placeholder))

    # Extract "as_spaced_date:N" if present
    spaced = next((r for r in rs if r.startswith("as_spaced_date")), None)
    n_spaces = None
    if spaced:
        _, arg = _parse_rule(spaced)
        n_spaces = int(arg or "3")

    # For date fields: regenerate from JSON (DDMMYYYY with N spaces)
    if spaced and canonical in DATE_FIELDS:
        val = fmt_date_spaced_digits(data.get(canonical), spaces=n_spaces or 3)
    else:
        # For non-date fields: start from raw, then pipeline first
        val = raw

    # Build pipeline excluding the special as_spaced_date
    pipe = build_pipeline(rs)
    for t in pipe:
        val = t(val)

    # If this is a non-date field and as_spaced_date was requested,
    # apply spacing between consecutive digits at the very end
    if spaced and canonical not in DATE_FIELDS and n_spaces is not None:
        val = space_only_between_digits(n_spaces)(val)

    return val



# ---------------------------------------------------------------------
# PDF I/O
# ---------------------------------------------------------------------

def set_need_appearances(pdf) -> None:
    if not hasattr(pdf, "Root") or pdf.Root is None:
        return
    acro = getattr(pdf.Root, "AcroForm", None)
    if acro is None:
        pdf.Root.AcroForm = PdfDict(NeedAppearances=PdfObject("true"))
    else:
        acro.update(PdfDict(NeedAppearances=PdfObject("true")))

def fill_pdf(
    in_pdf: Path,
    out_pdf: Path,
    data: Mapping[str, object],
    rules: Rules,
    flatten: bool = False,
) -> None:
    pdf = PdfReader(str(in_pdf))
    set_need_appearances(pdf)

    # Precompute values
    values: Dict[str, str] = {}
    for placeholder, canonical in PLACEHOLDER_MAP.items():
        rv = raw_value(canonical, data)
        values[placeholder] = apply_rules(
            canonical=canonical, placeholder=placeholder, raw=rv, data=data, rules=rules
        )

    # Fill
    for page in pdf.pages:
        annots = getattr(page, "Annots", None)
        if not annots:
            continue
        for annot in annots:
            if getattr(annot, "Subtype", None) != PdfName.Widget:
                continue
            field_obj = getattr(annot, "T", None)
            if not field_obj:
                continue
            name = str(field_obj).strip("()")
            if name not in values:
                continue
            val = values[name]
            annot.update(PdfDict(V=val, DV=val, AP=None))

    if flatten:
        flatten_into_page_content(pdf)

    PdfWriter().write(str(out_pdf), pdf)


from io import BytesIO
from reportlab.pdfgen import canvas
from pdfrw import PageMerge

# (Optional) register a Unicode font for Hebrew glyphs; adjust TTF path as needed.
pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
DEFAULT_FONT = "DejaVu"
# DEFAULT_FONT = "Helvetica"  # switch to "DejaVu" if you register above

def _draw_overlay(page, stamps):
    buf = BytesIO()
    # Page size doesn't matter; we overlay absolutely in page units
    c = canvas.Canvas(buf)
    c.setFont(DEFAULT_FONT, 14)
    for s in stamps:
        x, y, w, h, text, align, fs = (
            s["x"], s["y"], s["w"], s["h"], s["text"], s.get("align","left"), s.get("fontsize",14)
        )
        if not text:
            continue
        c.setFont(DEFAULT_FONT, fs)
        pad_x = 0
        pad_y = max(0, (h - fs) / 2.5)
        if align == "right":
            c.drawRightString(x + w - pad_x, y + pad_y, text)
        elif align == "center":
            c.drawCentredString(x + w / 2, y + pad_y, text)
        else:
            c.drawString(x + pad_x, y + pad_y, text)
    c.showPage()
    c.save()
    buf.seek(0)
    overlay = PdfReader(buf)
    PageMerge(page).add(overlay.pages[0]).render()

def _is_checked(annot) -> bool:
    # Handle common checkbox states
    v = getattr(annot, "V", None)
    as_ = getattr(annot, "AS", None)
    on_names = {PdfName.Yes, PdfName.On, "Yes", "On", True}
    return (v in on_names) or (as_ in on_names)
import re
_HEB = re.compile(r"[\u0590-\u05FF]")

def _is_numberlike(s: str) -> bool:
    """Return True if the string is primarily numeric or punctuation."""
    return bool(re.fullmatch(r"[\d\s\-\./]+", s.strip()))

def flatten_into_page_content(pdf):
    for page in pdf.pages:
        annots = getattr(page, "Annots", None)
        if not annots:
            continue
        stamps = []
        for annot in list(annots):
            if getattr(annot, "Subtype", None) != PdfName.Widget:
                continue
            rect = getattr(annot, "Rect", None)
            if not rect or len(rect) != 4:
                continue
            llx, lly, urx, ury = map(float, rect)
            w, h = (urx - llx), (ury - lly)

            ft = getattr(annot, "FT", None)  # field type
            txt = ""
            align = "right"  # default (Hebrew-friendly)

            if ft == PdfName.Btn:
                txt = "✓" if _is_checked(annot) else ""
                align = "center"
            else:
                v = getattr(annot, "V", None)
                if v is not None:
                    txt = str(v).strip("()")

            if not txt:
                continue

            # ---- alignment logic ----
            if _is_numberlike(txt):
                align = "left"
            elif _HEB.search(txt):
                align = "right"
            else:
                align = "left"

            stamps.append({
                "x": llx, "y": lly, "w": w, "h": h,
                "text": txt, "align": align, "fontsize": 10
            })

        if stamps:
            _draw_overlay(page, stamps)

        page.Annots = []

    if getattr(pdf.Root, "AcroForm", None):
        pdf.Root.AcroForm = PdfDict()


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    in_pdf: Path
    json_path: Path
    out_pdf: Path
    rules_json: Optional[Path]
    flatten: bool

# def parse_args(argv: Optional[Sequence[str]] = None) -> Config:
#     p = argparse.ArgumentParser(description="Fill a fillable AcroForm PDF by placeholder names with preprocessing.")
#     p.add_argument("--in", dest="in_pdf", required=True, help="Input PDF")
#     p.add_argument("--json", dest="json_path", required=True, help="Path to JSON data")
#     p.add_argument("--out", dest="out_pdf", required=True, help="Output PDF")
#     p.add_argument("--rules", dest="rules_json", default=None, help="Optional rules JSON")
#     p.add_argument("--flatten", action="store_true", help="Flatten form fields into static content")
#     a = p.parse_args(argv)
#     return Config(
#         in_pdf=Path(a.in_pdf),
#         json_path=Path(a.json_path),
#         out_pdf=Path(a.out_pdf),
#         rules_json=Path(a.rules_json) if a.rules_json else None,
#         flatten=a.flatten,
#     )
#
# def main(argv: Optional[Sequence[str]] = None) -> None:
#     cfg = parse_args(argv)
#     data = json.loads(cfg.json_path.read_text(encoding="utf-8"))
#     rules = Rules.load(cfg.rules_json)
#     fill_pdf(cfg.in_pdf, cfg.out_pdf, data, rules, flatten=cfg.flatten)
#     print(f"Filled PDF written to: {cfg.out_pdf}")
#
# if __name__ == "__main__":
#     main()
