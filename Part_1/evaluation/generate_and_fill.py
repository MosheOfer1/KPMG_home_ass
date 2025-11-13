#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_and_fill_local.py
--------------------------
Use local random JSON to fill an AcroForm PDF (placeholders + checkboxes)
and flatten it into static content.
"""

from __future__ import annotations
import json
from pathlib import Path
from pdfrw import PdfDict, PdfName, PdfReader, PdfWriter

from fill_pdf import Rules, PLACEHOLDER_MAP, raw_value, apply_rules, flatten_into_page_content, \
    set_need_appearances


# -------------------------------------------------------------
# Local random JSON
# -------------------------------------------------------------
import random
from datetime import datetime, timedelta

def _local_random_json() -> dict:
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
        """Return a random date between given years."""
        year = random.randint(start_year, end_year)
        month = random.randint(1, 12)
        day = random.randint(1, 28)  # keep simple
        return {"day": day, "month": month, "year": year}

    def _recent_date(days_back: int = 180) -> dict:
        """Random recent date within X days back from today."""
        today = datetime.now()
        rand_date = today - timedelta(days=random.randint(0, days_back))
        return {"day": rand_date.day, "month": rand_date.month, "year": rand_date.year}

    def phone():
        return "05" + "".join(random.choice("0123456789") for _ in range(8))

    gender = random.choice(["זכר", "נקבה"])
    hf = random.choice(health_funds)
    nature = random.choice(accident_natures)
    accident_loc = random.choice(accident_locations)

    # Random but sensible temporal ordering
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

# -------------------------------------------------------------
# PDF filling + checkboxes + flatten (like your style)
# -------------------------------------------------------------
def fill_pdf_with_checkboxes(in_pdf: Path, out_pdf: Path, data: dict):
    """Directly update widgets on the original PDF (like your script)."""
    rules = Rules.load(None)
    pdf = PdfReader(str(in_pdf))

    # Precompute field values
    values = {}
    for placeholder, canonical in PLACEHOLDER_MAP.items():
        raw = raw_value(canonical, data)
        val = apply_rules(canonical=canonical, placeholder=placeholder, raw=raw, data=data, rules=rules)
        values[placeholder] = val

    # Checkbox logic
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

    # Walk through fields like your original script
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
                    annot.update(PdfDict(V=(PdfName.Yes if checked else PdfName.Off),
                                         AS=(PdfName.Yes if checked else PdfName.Off)))
            elif name in values:
                val = values[name]
                annot.update(PdfDict(V=val, DV=val, AP=None))

    # Flatten into static content
    flatten_into_page_content(pdf)
    PdfWriter().write(str(out_pdf), pdf)

# -------------------------------------------------------------
# Main
# -------------------------------------------------------------
def main():
    import argparse
    p = argparse.ArgumentParser(description="Generate random JSON → fill & flatten PDF.")
    p.add_argument("--in", dest="in_pdf", required=True, help="Template input PDF")
    p.add_argument("--out", dest="out_pdf", required=True, help="Output filled PDF")
    args = p.parse_args()

    data = _local_random_json()
    out_pdf = Path(args.out_pdf)
    out_json = out_pdf.with_suffix(".json")

    fill_pdf_with_checkboxes(Path(args.in_pdf), out_pdf, data)
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Created {out_pdf}")
    print(f"✅ JSON saved as {out_json}")

if __name__ == "__main__":
    main()
