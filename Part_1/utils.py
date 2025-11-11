import json
from math import fsum
from typing import List, Tuple, Optional, Dict, Any
from collections import OrderedDict

# Hebrew label → Canonical target key mapping
# Values can be a string (top-level field) or a tuple ('parent','child') for nested.
HEB2CANON = {
    # personal
    "שם משפחה": "lastName",
    "שם פרטי": "firstName",
    "מספר זהות": "idNumber",
    "ת.ז": "idNumber",
    "ז.ת": "idNumber",
    "מין": "gender",
    "תאריך לידה": "dateOfBirth",
    "כתובת": "address",
    "רחוב": ("address","street"),
    "מספר בית": ("address","houseNumber"),
    "כניסה": ("address","entrance"),
    "דירה": ("address","apartment"),
    "ישוב": ("address","city"),
    "מיקוד": ("address","postalCode"),
    "תא דואר": ("address","poBox"),
    "טלפון קווי": "landlinePhone",
    "טלפון נייד": "mobilePhone",
    "סוג העבודה": "jobType",
    # accident
    "תאריך הפגיעה": "dateOfInjury",
    "שעת הפגיעה": "timeOfInjury",
    "מקום התאונה": "accidentLocation",
    "כתובת מקום התאונה": "accidentAddress",
    "תיאור התאונה": "accidentDescription",
    "תאור התאונה": "accidentDescription",
    "האיבר שנפגע": "injuredBodyPart",
    "חתימה": "signature",
    # dates bottom
    "תאריך מילוי הטופס": "formFillingDate",
    "תאריך קבלת הטופס בקופה": "formReceiptDateAtClinic",
    # medical institution fields
    "למילוי ע\"י המוסד הרפואי": "medicalInstitutionFields",
    "חבר בקופת חולים": ("medicalInstitutionFields","healthFundMember"),
    "מהות התאונה": ("medicalInstitutionFields","natureOfAccident"),
    "אבחנות רפואיות": ("medicalInstitutionFields","medicalDiagnoses"),
}

# ------------------------------------------------------
# Helpers
# ------------------------------------------------------
def _gather_text_lines(result) -> List[str]:
    """Flatten all page lines to a simple list of strings (preserving page order)."""
    lines: List[str] = []
    for p in (result.pages or []):
        for ln in (p.lines or []):
            if getattr(ln, "content", None):
                lines.append(ln.content.strip())
    return lines

def _gather_labeled_checkboxes(result) -> dict[str, object]:
    """Return {label: state} for selection marks using 'nearest-left-line' heuristic."""
    labeled_checks: Dict[str, Dict[str, object]] = {}
    for page in (result.pages or []):
        for sm in (page.selection_marks or []):
            cx, cy = _center(sm.polygon)
            label = _nearest_left_line_label(page, cx, cy)
            if not label:
                label = f"@{cx:.2f},{cy:.2f}"
            labeled_checks[label] = {
                "state": sm.state,
                "center": {"x": round(cx, 3), "y": round(cy, 3)}
            }
    return {k: v["state"] for k, v in labeled_checks.items()}


def _build_system_prompt(hebrew_keys: bool) -> str:
    """System instruction for AOAI to produce strict JSON with canonical (or Hebrew) keys."""
    return (
        "You are a precise information extraction assistant. "
        "You receive raw text lines from a Hebrew form and a map of checkbox labels to states. "
        "Your task: output a STRICT JSON object that follows the expected schema.\n\n"
        "Rules:\n"
        "1) If a value is missing, leave it as an empty string (\"\").\n"
        "2) Trim spaces and punctuation from labels and values.\n"
        "3) For all the dates, output a nested object like:\n"
        "   \"dateOfBirth\": {\"day\": \"\", \"month\": \"\", \"year\": \"\"}.\n or יום חודש שנה if Hebrew is required"
        "4) Make phone numbers start with '05' (no country codes).\n"
        "5) For checkboxes: true if selected, false otherwise.\n"
        "6) Hebrew text may appear right-to-left; infer meaning from common Hebrew labels.\n"
        f"7) Emit keys in {'Hebrew' if hebrew_keys else 'English canonical'} as requested.\n"
        "8) For the 'medicalInstitutionFields' group, always output keys in this exact order:\n"
        "   \"healthFundMember\", \"natureOfAccident\", \"medicalDiagnoses\".\n"
        "   - If one of the checkboxes 'כללית', 'מאוחדת', 'מכבי', or 'לאומית' is selected, set healthFundMember to the selected one.\n"
        "   - If the checkbox 'מהות התאונה:' is selected, take the text on the next line as 'natureOfAccident' else leave it empty.\n"
        "The same for 'medicalDiagnoses' - 'אבחנות רפואיות'.\n"
    )


def _build_user_prompt(
    lines: List[str],
    checks: Dict[str, str],
    hebrew_keys: bool,
) -> str:
    """User content containing raw evidence and exact schema expectation, preserving HEB2CANON order."""

    # Build schema description preserving insertion order
    ordered_keys = OrderedDict()
    nested_paths = []
    for heb, canon in HEB2CANON.items():
        if isinstance(canon, str):
            ordered_keys[canon] = None
        elif isinstance(canon, tuple):
            # store nested paths as joined strings
            nested_paths.append("/".join(canon))
            if canon[0] not in ordered_keys:
                ordered_keys[canon[0]] = None

    schema_desc = OrderedDict([
        ("top_level_english_keys", list(ordered_keys.keys())),
        ("nested_english_paths", sorted(set(nested_paths))),
        ("hebrew_label_examples", list(HEB2CANON.keys())[:30]),
    ])

    requested_key_language = "Hebrew" if hebrew_keys else "English"

    payload = OrderedDict([
        ("instruction", OrderedDict([
            ("requested_key_language", requested_key_language),
            ("notes", [
                "Map Hebrew labels to the appropriate canonical field.",
                "If multiple values found for a field, pick the most confident; else join with a single space.",
                "If a nested group exists (e.g., address/*), output an object there."
            ]),
            ("schema_hint", schema_desc),
        ])),
        ("evidence", OrderedDict([
            ("raw_lines", lines),
            ("checkboxes", checks),
        ])),
    ])

    # ensure_ascii=False to keep Hebrew characters intact
    return json.dumps(payload, ensure_ascii=False, indent=None, separators=(",", ":"))

def _ensure_json(obj: Any) -> Any:
    """Small guard to ensure we end up with a JSON-serializable dict."""
    if isinstance(obj, (dict, list, str, int, float)) or obj is None:
        return obj
    # If Azure OpenAI returned a string, try to parse it.
    try:
        return json.loads(str(obj))
    except Exception:
        return obj


def _center(poly: List[float]) -> Tuple[float, float]:
    xs = poly[0::2]; ys = poly[1::2]
    return (fsum(xs)/len(xs), fsum(ys)/len(ys))

def _bbox(poly: List[float]) -> Tuple[float, float, float, float]:
    xs = poly[0::2]; ys = poly[1::2]
    return (min(xs), min(ys), max(xs), max(ys))

def _line_bbox(line) -> Tuple[float,float,float,float]:
    return _bbox(line.polygon) if getattr(line, "polygon", None) else (0,0,0,0)

def _y_overlap(a: Tuple[float,float,float,float], b: Tuple[float,float,float,float]) -> float:
    _, ay1, _, ay2 = a
    _, by1, _, by2 = b
    return max(0.0, min(ay2, by2) - max(ay1, by1))

def _nearest_left_line_label(page, cx: float, cy: float,
                             min_y_overlap: float = 0.06,
                             max_dx: float = 2.0) -> Optional[str]:
    """
    Find the line with the largest right-edge (x2) that is still < cx,
    has enough vertical overlap with the checkbox center band,
    and is within max_dx horizontally.
    """
    best = None
    best_key = None
    band = (cx, cy - 0.10, cx, cy + 0.10)  # ~0.2" vertical band around center

    for ln in page.lines or []:
        x1, y1, x2, y2 = _line_bbox(ln)
        if x2 >= cx:  # must be strictly to the left
            continue
        yov = _y_overlap(band, (x1, y1, x2, y2))
        if yov < min_y_overlap:
            continue
        dx = cx - x2  # horizontal distance from line's right edge to checkbox center
        if dx <= max_dx:
            # choose the line whose right edge is closest to the checkbox
            key = (dx, -yov)  # prefer smaller dx; if tie, prefer larger y-overlap
            if best is None or key < best:
                best = key
                best_key = ln.content

    if best_key:
        return best_key.strip(" :•.-").replace("  ", " ")
    return None

