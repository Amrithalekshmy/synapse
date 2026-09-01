import re
from datetime import date, timedelta
from dateutil import parser as dateutil_parser
from typing import Optional


STATUS_MAP: dict[str, str] = {
    "completed": "completed",
    "complete": "completed",
    "done": "completed",
    "finished": "completed",
    "fully completed": "completed",
    "fully complete": "completed",
    "installed": "completed",
    "started": "started",
    "begun": "started",
    "commenced": "started",
    "in progress": "in_progress",
    "in-progress": "in_progress",
    "ongoing": "in_progress",
    "underway": "in_progress",
    "continuing": "in_progress",
    "pending": "not_started",
    "awaiting": "not_started",
    "waiting": "not_started",
    "not started": "not_started",
    "not yet received": "not_started",
    "not received": "not_started",
    "delayed": "delayed",
    "behind schedule": "delayed",
    "blocked": "blocked",
    "held up": "blocked",
    "could not be done": "blocked",
    "cannot be done": "blocked",
    "found faulty": "blocked",
}

ACTIVITY_TYPE_MAP: dict[str, str] = {
    "erect": "erection",
    "erected": "erection",
    "erection": "erection",
    "erecting": "erection",
    "weld": "welding",
    "welded": "welding",
    "welding": "welding",
    "install": "installation",
    "installed": "installation",
    "installing": "installation",
    "installation": "installation",
    "test": "testing",
    "tested": "testing",
    "testing": "testing",
    "commission": "commissioning",
    "commissioned": "commissioning",
    "commissioning": "commissioning",
    "excavate": "excavation",
    "excavated": "excavation",
    "excavation": "excavation",
    "concrete": "concreting",
    "concreting": "concreting",
    "pour": "concreting",
    "poured": "concreting",
    "pouring": "concreting",
    "backfill": "backfilling",
    "backfilled": "backfilling",
    "backfilling": "backfilling",
    "insulate": "insulation",
    "insulated": "insulation",
    "insulation": "insulation",
    "hydrotest": "hydrotest",
    "hydrotesting": "hydrotest",
    "hydrotested": "hydrotest",
    "pull": "cable_pulling",
    "pulled": "cable_pulling",
    "pulling": "cable_pulling",
    "terminate": "termination",
    "terminated": "termination",
    "termination": "termination",
    "align": "alignment",
    "aligned": "alignment",
    "alignment": "alignment",
    "fabricate": "fabrication",
    "fabricated": "fabrication",
    "fabrication": "fabrication",
    "inspect": "inspection",
    "inspected": "inspection",
    "inspection": "inspection",
    "loop check": "loop_check",
    "calibrate": "calibration",
    "calibrated": "calibration",
    "calibration": "calibration",
    "paint": "painting",
    "painted": "painting",
    "painting": "painting",
    "curing": "curing",
    "glanding": "glanding",
    "set": "equipment_setting",
    "setting": "equipment_setting",
    "connect": "piping_connection",
    "connected": "piping_connection",
    "connection": "piping_connection",
}

DISCIPLINE_KEYWORDS: dict[str, list[str]] = {
    "piping": ["pipe", "piping", "spool", "valve", "line ", "hydrotest", "insulation", "insulate"],
    "electrical": ["cable", "electrical", "panel", "mcc", "power cable", "cable tray", "termination"],
    "civil": ["concrete", "excavation", "backfill", "foundation", "civil", "curing", "sleeper", "road", "hardstanding"],
    "instrumentation": ["instrument", "transmitter", "gauge", "control valve", "loop check", "calibration", "FT-", "PG-", "CV-"],
    "mechanical": ["pump", "compressor", "mechanical", "alignment", "equipment", "motor", "driver", "rotating", "commissioning"],
}

_ASSET_PATTERNS = [
    (r'\b[Ll]ine\s+(\d+(?:-[A-Z0-9]+)?)\b', lambda m: f"Line {m.group(1)}"),
    (r'\bL-?(\d+(?:-[A-Z0-9]+)?)\b', lambda m: f"Line {m.group(1)}"),
    (r'\b(\d+)-XX\b', lambda m: f"Line {m.group(1)}-XX"),
    (r'\b(V-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(P-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(K-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(F-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(CT-[A-Z0-9]+)\b', lambda m: m.group(1).upper()),
    (r'\b(PC-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(IC-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(FT-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(PG-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(CV-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(M-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(PS-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
    (r'\b(S-\d+[A-Z]?)\b', lambda m: m.group(1).upper()),
]

_LOCATION_PATTERNS = [
    (r'\b[Uu]nit\s+(\d+)\b', lambda m: f"Unit {m.group(1)}"),
    (r'\b[Aa]rea\s+([A-Z0-9]+)\b', lambda m: f"Area {m.group(1)}"),
    (r'\b[Ss]ubstation\b', lambda _: "Substation"),
    (r'\b[Ff]abrication\s+[Yy]ard\b', lambda _: "Fabrication Yard"),
    (r'\b[Pp]ipe\s+[Rr]ack(?:\s+([A-Z]))?\b', lambda m: f"Pipe Rack {m.group(1)}" if m.group(1) else "Pipe Rack"),
]

_QUANTITY_PATTERNS = [
    (r'(\d+(?:\.\d+)?)\s*(?:metres|meters|m)\b', "metres"),
    (r'(\d+(?:\.\d+)?)\s*spools?\b', "spools"),
    (r'(\d+(?:\.\d+)?)\s*joints?\b', "joints"),
    (r'(\d+(?:\.\d+)?)\s*(?:percent|%)', "%"),
    (r'(\d+)\s+of\s+(\d+)', None),
]


def normalize_status(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    for phrase, normalized in sorted(STATUS_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower:
            return normalized
    return None


def normalize_activity_type(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    if "loop check" in text_lower:
        return "loop_check"
    words = re.findall(r'\b\w+\b', text_lower)
    for word in words:
        if word in ACTIVITY_TYPE_MAP:
            return ACTIVITY_TYPE_MAP[word]
    return None


EQUIPMENT_ASSET_DISCIPLINE: dict[str, str] = {
    "K-": "mechanical",
    "P-": "mechanical",
    "FT-": "instrumentation",
    "PG-": "instrumentation",
    "CV-": "instrumentation",
    "CT-": "electrical",
    "PC-": "electrical",
    "IC-": "electrical",
    "M-": "electrical",
    "V-": "piping",
    "F-": "civil",
    "PS-": "civil",
}


def infer_discipline(text: str) -> Optional[str]:
    text_lower = text.lower()

    for prefix, discipline in EQUIPMENT_ASSET_DISCIPLINE.items():
        if prefix.lower() in text_lower or prefix in text:
            if prefix == "P-" and "pump" not in text_lower:
                continue
            if prefix == "M-" and "mcc" not in text_lower and "panel" not in text_lower:
                continue
            return discipline

    PRIMARY_EQUIPMENT = {
        "mechanical": ["pump", "compressor", "motor", "driver", "turbine"],
        "instrumentation": ["transmitter", "gauge", "control valve", "calibration"],
        "electrical": ["cable", "panel", "mcc"],
        "piping": ["spool", "valve", "pipe", "piping"],
    }
    for discipline, equip_words in PRIMARY_EQUIPMENT.items():
        for ew in equip_words:
            if ew in text_lower:
                return discipline

    scores: dict[str, int] = {}
    for discipline, keywords in DISCIPLINE_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw.lower() in text_lower:
                score += 2 if len(kw) > 4 else 1
        if score > 0:
            scores[discipline] = score
    if not scores:
        return None
    return max(scores, key=scores.get)


def extract_assets(text: str) -> list[str]:
    assets = []
    for pattern, formatter in _ASSET_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            asset = formatter(match)
            if asset not in assets:
                assets.append(asset)
    return assets


def extract_location(text: str) -> Optional[str]:
    for pattern, formatter in _LOCATION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return formatter(match)
    return None


def _is_asset_number(text: str, match: re.Match) -> bool:
    start = match.start()
    prefix = text[:start].rstrip()
    return bool(re.search(r'(?:[Ll]ine|[Ll]-?|[Ll]ine-)\s*$', prefix))


def extract_quantity(text: str) -> tuple[Optional[float], Optional[str]]:
    fraction_pattern = r'(\d+)\s+of\s+(\d+)'
    fraction_match = re.search(fraction_pattern, text, re.IGNORECASE)
    if fraction_match and not _is_asset_number(text, fraction_match):
        numerator = float(fraction_match.group(1))
        denominator = float(fraction_match.group(2))
        return numerator, f"of {int(denominator)}"

    for pattern, unit_label in _QUANTITY_PATTERNS:
        if unit_label is None:
            continue
        match = re.search(pattern, text, re.IGNORECASE)
        if match and not _is_asset_number(text, match):
            return float(match.group(1)), unit_label
    return None, None


def normalize_date(text: str, reference_date: Optional[date] = None) -> Optional[str]:
    if reference_date is None:
        reference_date = date.today()

    text_lower = text.lower().strip()

    relative_map = {
        "today": timedelta(days=0),
        "yesterday": timedelta(days=-1),
        "tomorrow": timedelta(days=1),
        "this morning": timedelta(days=0),
        "this afternoon": timedelta(days=0),
        "this evening": timedelta(days=0),
        "last night": timedelta(days=-1),
    }

    for phrase, delta in relative_map.items():
        if phrase in text_lower:
            resolved = reference_date + delta
            return resolved.isoformat()

    date_patterns = [
        r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
        r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})',
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})',
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                parsed = dateutil_parser.parse(match.group(0), dayfirst=True)
                return parsed.date().isoformat()
            except (ValueError, OverflowError):
                continue

    month_day = re.search(
        r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*',
        text_lower,
    )
    if month_day:
        try:
            parsed = dateutil_parser.parse(month_day.group(0), dayfirst=True)
            if parsed.year == 1900:
                parsed = parsed.replace(year=reference_date.year)
            return parsed.date().isoformat()
        except (ValueError, OverflowError):
            pass

    month_only = re.search(
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\b',
        text_lower,
    )
    if month_only:
        try:
            parsed = dateutil_parser.parse(month_only.group(0))
            if parsed.year == 1900:
                parsed = parsed.replace(year=reference_date.year)
            return parsed.date().isoformat()
        except (ValueError, OverflowError):
            pass

    return None


def normalize_asset_identifier(raw: str) -> str:
    cleaned = raw.strip()
    match = re.match(r'^L-?(\d+.*)$', cleaned, re.IGNORECASE)
    if match:
        return f"Line {match.group(1)}"
    return cleaned
