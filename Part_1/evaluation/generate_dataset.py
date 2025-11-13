"""
generate_dataset.py
-------------------
Create a dataset folder with N filled & flattened PDFs and matching golden JSONs,
using ONLY the local random JSON generator and your fill_pdf pipeline.

Usage:
  python generate_dataset.py --in template.pdf --outdir dataset --n 100 --prefix ex_
"""

from __future__ import annotations
import argparse
import json
import os
import random
from pathlib import Path

from pdfrw import PdfReader  # sanity check that PDF opens

# Your fill pipeline pieces (exactly as in your script)
from fill_pdf import (
    Rules, PLACEHOLDER_MAP, raw_value, apply_rules,
    flatten_into_page_content, set_need_appearances
)
from pdfrw import PdfDict, PdfName, PdfWriter

# ---------------------------------------------------------------------
# Local random JSON (unchanged except for being embedded here)
# ---------------------------------------------------------------------
def _local_random_json() -> dict:
    import random
    from datetime import datetime, timedelta

    first_names = ["דוד", "יוסי", "טל", "מיכל", "נעמה", "הילה", "רועי", "אורי", "שירה", "אדם", "נעם", "עומר", "נועה", "ליאן", "אלון"]
    last_names = ["כהן", "לוי", "מזרחי", "חדד", "יעקב", "ברדוגו", "פרץ", "אליהו", "בן דוד", "שלום", "דנינו", "אוחנה", "סבן", "גולן"]
    streets = ["הרצל", "אלנבי", "אבן גבירול", "דיזנגוף", "ז'בוטינסקי", "ויצמן", "יהודה הלוי", "בן גוריון", "החשמונאים", "שדרות חן"]
    cities = ["תל אביב", "ירושלים", "חיפה", "ראשון לציון", "פתח תקווה", "אשדוד", "נתניה", "באר שבע", "הרצליה", "רעננה"]

    accident_locations = [
        "מקום העבודה", "בבית", "בדרך לעבודה", "בדרך הביתה", "במדרגות הבניין",
        "בכביש", "במגרש הספורט", "בגן הציבורי", "בחוף הים", "בבית הספר"
    ]

    accident_natures = [
        "תאונת דרכים קלה", "החלקה בבית", "פגיעה במהלך ספורט", "נפילה ממדרגות",
        "התחשמלות קלה", "חתך ביד", "חבלה בגב", "נפילה מאופניים", "מכה בראש", "פציעה בעבודה"
    ]

    body_parts = [
        "יד ימין", "יד שמאל", "רגל ימין", "רגל שמאל", "קרסול שמאל", "גב תחתון",
        "צוואר", "ברך ימין", "מרפק שמאל", "שכם ימין"
    ]

    health_funds = ["כללית", "מאוחדת", "מכבי", "לאומית", "פרטי", "ללא"]

    signatures = [
        "חתימת נבדק", "חתימה רפואית", "חתימת מטופל", "חתימה אלקטרונית",
        "חתימה ידנית", "נחתם על ידי נציג", "חתימה ממוחשבת"
    ]

    def _rand_date_between(start_year: int, end_year: int) -> dict:
        year = random.randint(start_year, end_year)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        return {"day": day, "month": month, "year": year}

    def _recent_date(days_back: int = 180) -> dict:
        today = datetime.now()
        rand_date = today - timedelta(days=random.randint(0, days_back))
        return {"day": rand_date.day, "month": rand_date.month, "year": rand_date.year}

    def phone():
        return "05" + "".join(random.choice("0123456789") for _ in range(8))

    gender = random.choice(["זכר", "נקבה"])
    hf = random.choice(health_funds)
    nature = random.choice(accident_natures)
    accident_loc = random.choice(accident_locations)

    date_of_birth = _rand_date_between(1970, 2002)
    date_of_injury = _recent_date(90)
    form_filling_date = _recent_date(30)
    form_receipt_date = _recent_date(15)

    return {
        "lastName": random.choice(last_names),
        "firstName": random.choice(first_names),
        "idNumber": "".join(random.choice("0123456789") for _ in range(9)),
        "dateOfBirth": date_of_birth,
        "address": {
            "street": random.choice(streets),
            "houseNumber": random.randint(1, 120),
            "entrance": random.choice(["", "א", "ב", "ג", "ד"]),
            "apartment": random.randint(1, 60),
            "city": random.choice(cities),
            "postalCode": "".join(random.choice("0123456789") for _ in range(7)),
        },
        "landlinePhone": phone(),
        "mobilePhone": phone(),
        "dateOfInjury": date_of_injury,
        "timeOfInjury": f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}",
        "accidentLocation": accident_loc,
        "accidentDescription": f"{nature} {random.choice(['במהלך עבודה', 'בעת ירידה במדרגות', 'במהלך פעילות יומיומית', ''])}".strip(),
        "accidentAddress": f"רח' {random.choice(streets)} {random.randint(1, 200)}, {random.choice(cities)}",
        "injuredBodyPart": random.choice(body_parts),
        "signature": random.choice(signatures),
        "formFillingDate": form_filling_date,
        "formReceiptDateAtClinic": form_receipt_date,
        "gender": gender,
        "healthFundMember": hf,
        "natureOfAccident": nature,
    }

# ---------------------------------------------------------------------
# PDF fill (your style) – unchanged logic
# ---------------------------------------------------------------------
def fill_pdf_with_checkboxes(in_pdf: Path, out_pdf: Path, data: dict):
    rules = Rules.load(None)
    pdf = PdfReader(str(in_pdf))

    # compute values for placeholders
    values = {}
    for placeholder, canonical in PLACEHOLDER_MAP.items():
        rv = raw_value(canonical, data)
        val = apply_rules(canonical=canonical, placeholder=placeholder, raw=rv, data=data, rules=rules)
        values[placeholder] = val

    # checkboxes
    gender = data.get("gender", "")
    hf = data.get("healthFundMember", "")
    nature = bool(data.get("natureOfAccident", ""))

    checkbox_state = {
        "male": gender == "זכר",
        "female": gender == "נקבה",
        "Clalit": hf == "כללית",
        "Muhedet": hf == "מאוחדת",
        "Macabi": hf == "מכבי",
        "Leumit": hf == "לאומית",
        "None": hf == "ללא",
        "natureOfAccident": nature,
    }

    set_need_appearances(pdf)

    for page in pdf.pages:
        annots = getattr(page, "Annots", None)
        if not annots:
            continue
        for annot in annots:
            if getattr(annot, "Subtype", None) != PdfName.Widget:
                continue
            name = str(getattr(annot, "T", "")).strip("()")
            if not name:
                continue

            ft = getattr(annot, "FT", None)
            if ft == PdfName.Btn:
                if name in checkbox_state:
                    checked = checkbox_state[name]
                    annot.update(PdfDict(
                        V=(PdfName.Yes if checked else PdfName.Off),
                        AS=(PdfName.Yes if checked else PdfName.Off)
                    ))
            elif name in values:
                val = values[name]
                annot.update(PdfDict(V=val, DV=val, AP=None))

    # flatten
    flatten_into_page_content(pdf)
    PdfWriter().write(str(out_pdf), pdf)

# ---------------------------------------------------------------------
# Batch gen
# ---------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Build a dataset of filled PDFs + golden JSONs.")
    ap.add_argument("--in", dest="in_pdf", required=True, help="Template input PDF (AcroForm).")
    ap.add_argument("--outdir", required=True, help="Output directory for dataset (will be created).")
    ap.add_argument("--n", type=int, default=100, help="How many examples to generate (default: 100).")
    ap.add_argument("--prefix", default="ex_", help="Filename prefix (default: ex_).")
    args = ap.parse_args()

    in_pdf = Path(args.in_pdf)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Quick sanity check: template opens
    _ = PdfReader(str(in_pdf))

    for i in range(1, args.n + 1):
        # Make runs nicely non-deterministic but distinct
        random.seed(os.urandom(16) + i.to_bytes(4, "little"))

        stem = f"{args.prefix}{i:03d}"
        pdf_path = outdir / f"{stem}.pdf"
        json_path = outdir / f"{stem}.golden.json"

        data = _local_random_json()
        fill_pdf_with_checkboxes(in_pdf, pdf_path, data)
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"✓ {stem}: wrote {pdf_path.name} and {json_path.name}")

    print(f"\n✅ Done. Dataset at: {outdir.resolve()}")

if __name__ == "__main__":
    main()
