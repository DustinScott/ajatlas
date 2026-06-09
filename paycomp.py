#!/usr/bin/env python3
"""
PayComp Intake -> Client pipeline.

Drop a filled "PayComp Client Intake Form" PDF into the Dropbox/ folder, then run:

    python3 paycomp.py

For each new PDF it will:
  1. Parse the intake form into structured client data
  2. Generate a branded "client vista" page  (clients/<slug>/index.html)
  3. Save the raw data                        (clients/<slug>/client.json)
  4. Move the PDF into Dropbox/processed/
  5. Rebuild the dashboard                     (index.html)

Extraction approach
-------------------
The intake template is a fixed PDF.  The blank template uses CodecPro / CanvaSans
fonts; the *typed-in answers* are overlaid in Helvetica (and rendered twice).
So we keep only Helvetica characters, de-duplicate the overlapping doubles, group
them into lines by vertical position, and read each field by its location on the
page.  Checkbox selections are detected from the position of "X" marks.

If PayComp ever redesigns the form, the coordinate map in FIELD bands / CHECKBOXES
below is the only thing that needs updating.
"""

import json
import re
import shutil
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("Missing dependency. Run:  pip install pdfplumber --break-system-packages")

ROOT = Path(__file__).resolve().parent
DROPBOX = ROOT / "Dropbox"
PROCESSED = DROPBOX / "processed"
CLIENTS = ROOT / "clients"


# --------------------------------------------------------------------------- #
#  Low-level extraction
# --------------------------------------------------------------------------- #
def value_chars(page):
    """Helvetica chars (the typed answers), de-duplicated from the doubled render."""
    chars = [c for c in page.chars if "Helvetica" in c["fontname"]]
    seen, uniq = set(), []
    for c in sorted(chars, key=lambda c: (round(c["top"]), c["x0"])):
        key = (round(c["x0"]), round(c["top"]), c["text"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return uniq


def group_lines(chars, y_tol=3.0):
    """Group chars into lines by vertical proximity. Returns list of line dicts."""
    lines = []
    for c in sorted(chars, key=lambda c: (c["top"], c["x0"])):
        placed = False
        for ln in lines:
            if abs(ln["top"] - c["top"]) <= y_tol:
                ln["chars"].append(c)
                ln["top"] = (ln["top"] * ln["n"] + c["top"]) / (ln["n"] + 1)
                ln["n"] += 1
                placed = True
                break
        if not placed:
            lines.append({"top": c["top"], "n": 1, "chars": [c]})
    for ln in lines:
        ln["chars"].sort(key=lambda c: c["x0"])
    return lines


def render(chars, gap=2.2):
    """Turn a sorted list of chars into a string, inserting spaces across gaps."""
    out, prev = "", None
    for c in sorted(chars, key=lambda c: c["x0"]):
        if prev is not None and c["x0"] - prev > gap:
            out += " "
        out += c["text"]
        prev = c["x1"]
    return out.strip()


def band(lines, lo, hi, x0=0, x1=10000):
    """Concatenate all value text whose line-top is in [lo,hi] and x in [x0,x1)."""
    picked = []
    for ln in lines:
        if lo <= ln["top"] < hi:
            picked.extend(c for c in ln["chars"] if x0 <= c["x0"] < x1)
    return render(picked)


def checkmarks(chars):
    """Return (x0, top) for every 'X' answer mark."""
    return [(c["x0"], c["top"]) for c in chars if c["text"].strip().upper() == "X"]


def has_x(marks, x_lo, x_hi, y_lo, y_hi):
    return any(x_lo <= x <= x_hi and y_lo <= y <= y_hi for x, y in marks)


def columns(line_chars, gap=14):
    """Split a single line's chars into column strings on large horizontal gaps."""
    cols, cur, prev = [], [], None
    for c in sorted(line_chars, key=lambda c: c["x0"]):
        if prev is not None and c["x0"] - prev > gap:
            cols.append(render(cur))
            cur = []
        cur.append(c)
        prev = c["x1"]
    if cur:
        cols.append(render(cur))
    return [c for c in cols if c]


def clean(v):
    if not v:
        return ""
    v = v.strip()
    return "" if v.upper() in ("N/A", "NA", "") else v


# --------------------------------------------------------------------------- #
#  Field map  (coordinates tuned to PayComp Client Intake Form template v1)
# --------------------------------------------------------------------------- #
def parse(pdf_path):
    pdf = pdfplumber.open(pdf_path)
    p1, p2 = pdf.pages[0], pdf.pages[1]

    c1, c2 = value_chars(p1), value_chars(p2)
    L1, L2 = group_lines(c1), group_lines(c2)
    X1, X2 = checkmarks(c1), checkmarks(c2)

    d = {}

    # --- Business & policy ---
    d["legal_business_name"] = band(L1, 103, 110, x0=140)
    d["dba"] = band(L1, 116, 123, x0=140)
    d["fein"] = band(L1, 130, 137, x0=95)
    d["business_address"] = band(L1, 174, 184, x0=150)
    csz = band(L1, 188, 195, x0=95)
    d["city"], d["state"], d["zip"] = split_csz(csz)
    d["contact_name"] = band(L1, 202, 209, x0=150)
    ep = band(L1, 217, 224, x0=80)
    d["contact_email"] = band(L1, 217, 224, x0=80, x1=265)
    d["contact_phone"] = band(L1, 217, 224, x0=265)

    # --- Workers' comp policy ---
    d["wc_carrier"] = band(L1, 257, 264, x0=140)
    d["policy_number"] = band(L1, 271, 278, x0=140)
    d["policy_effective_date"] = band(L1, 285, 292, x0=140)

    # --- Additional business structures (checkboxes) ---
    d["multiple_locations"] = has_x(X1, 70, 95, 317, 327)
    d["multiple_feins"] = has_x(X1, 215, 245, 317, 327)
    d["multiple_payroll_providers"] = has_x(X1, 70, 95, 335, 345)

    # --- Agency information ---
    d["agency_name"] = band(L1, 417, 424, x0=140, x1=300)
    d["producer_name"] = band(L1, 430, 437, x0=140, x1=300)
    d["agency_email"] = band(L1, 445, 452, x0=95, x1=300)
    d["agency_phone"] = band(L1, 459, 465, x0=80, x1=300)

    # --- Wholesaler / MGA (right column) ---
    d["wholesaler_name"] = clean(band(L1, 417, 424, x0=300))
    d["wholesaler_contact"] = clean(band(L1, 430, 437, x0=300))
    d["wholesaler_email"] = clean(band(L1, 459, 465, x0=300, x1=470))
    d["wholesaler_phone"] = clean(band(L1, 459, 465, x0=470))

    # --- Who processes payroll (checkboxes) ---
    if has_x(X1, 405, 420, 508, 516):
        d["payroll_processor"] = "Payroll Company"
    elif has_x(X1, 405, 420, 523, 531):
        d["payroll_processor"] = "CPA/Bookkeeper"
    elif has_x(X1, 405, 420, 538, 546):
        d["payroll_processor"] = "In-House Payroll"
    elif has_x(X1, 405, 420, 553, 561):
        d["payroll_processor"] = "Other"
    else:
        d["payroll_processor"] = ""

    # --- Payroll provider ---
    d["provider_name"] = band(L1, 505, 512, x0=180, x1=400)
    d["provider_contact"] = band(L1, 519, 526, x0=180)
    d["provider_email"] = band(L1, 533, 540, x0=95)
    d["provider_phone"] = band(L1, 547, 554, x0=95)

    # --- Payroll schedule (frequency + day from checkbox position) ---
    d["payroll_frequency"], d["payroll_day"] = parse_frequency(X1, L1)
    d["next_check_date"] = band(L1, 720, 728, x0=75, x1=200)

    # --- Page 2: excluded employees ---
    d["no_excluded_employees"] = has_x(X2, 115, 132, 112, 122)
    d["excluded_employees"] = parse_excluded(L2)

    # --- Integration assistance ack ---
    d["integration_ack"] = has_x(X2, 70, 90, 315, 325)

    # --- Scheduling contact ---
    d["sched_contact"] = band(L2, 368, 375, x0=200)
    d["sched_phone"] = band(L2, 383, 390, x0=110, x1=250)
    d["sched_email"] = band(L2, 383, 390, x0=250)
    d["sched_times"] = band(L2, 396, 403, x0=200)

    # --- Authorization ---
    d["authorized_signature"] = band(L2, 676, 683, x0=140, x1=350)
    d["printed_name"] = band(L2, 676, 683, x0=400)
    d["title"] = band(L2, 690, 697, x0=95, x1=340)
    d["signature_date"] = band(L2, 690, 697, x0=340)
    d["authority_confirmed"] = has_x(X2, 75, 92, 722, 732)

    pdf.close()
    return d


def split_csz(text):
    """'Charlotte NC 28208' -> ('Charlotte', 'NC', '28208')."""
    if not text:
        return "", "", ""
    zip_m = re.search(r"(\d{5}(?:-\d{4})?)\s*$", text)
    zipc = zip_m.group(1) if zip_m else ""
    rest = text[: zip_m.start()].strip() if zip_m else text
    state_m = re.search(r"\b([A-Z]{2})\s*$", rest)
    state = state_m.group(1) if state_m else ""
    city = rest[: state_m.start()].strip() if state_m else rest
    return city, state, zipc


def parse_frequency(marks, lines):
    """Frequency + weekday from the schedule checkbox grid."""
    # columns: weekly x~185, bi-weekly x~277 ; rows: Mon659 Tue672 Wed686 Thu699 Fri713
    days = [("Monday", 659), ("Tuesday", 672), ("Wednesday", 686),
            ("Thursday", 699), ("Friday", 713)]
    for x, y in marks:
        if 640 <= y <= 735:
            col = None
            if 170 <= x <= 210:
                col = "Weekly"
            elif 265 <= x <= 305:
                col = "Bi-Weekly"
            if col:
                day = min(days, key=lambda dz: abs(dz[1] - y))
                return col, day[0] if abs(day[1] - y) < 14 else ""
    # semi-monthly / monthly have fill-in blanks rather than day checkboxes
    semi = band(lines, 655, 700, x0=360, x1=470)
    monthly = band(lines, 655, 700, x0=480)
    if semi:
        return "Semi-Monthly", semi
    if monthly:
        return "Monthly", monthly
    return "", ""


def parse_excluded(lines):
    """Rows of the excluded-employees table -> list of {name, employee_id, reason}."""
    rows = []
    for ln in lines:
        if 150 <= ln["top"] <= 300:
            cells = columns([c for c in ln["chars"] if c["x0"] < 560], gap=16)
            if not cells:
                continue
            row = {
                "name": cells[0] if len(cells) > 0 else "",
                "employee_id": cells[1] if len(cells) > 1 else "",
                "reason": " ".join(cells[2:]) if len(cells) > 2 else "",
            }
            if row["name"]:
                rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
#  Pipeline
# --------------------------------------------------------------------------- #
def slugify(data):
    base = data.get("legal_business_name") or "client"
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    fein = re.sub(r"\D", "", data.get("fein", ""))
    return f"{slug}-{fein[-4:]}" if fein else slug


def process_dropbox():
    import generate  # local module for HTML rendering
    for p in (DROPBOX, PROCESSED, CLIENTS):
        p.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(q for q in DROPBOX.glob("*.pdf"))
    if not pdfs:
        print("No new PDFs in Dropbox/. Drop an intake form there and run again.")
    new_clients = []
    for pdf_path in pdfs:
        print(f"Parsing {pdf_path.name} ...")
        data = parse(pdf_path)
        slug = slugify(data)
        data["_slug"] = slug
        data["_source_pdf"] = pdf_path.name
        cdir = CLIENTS / slug
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "client.json").write_text(json.dumps(data, indent=2))
        (cdir / "index.html").write_text(generate.portal_html(data))
        shutil.move(str(pdf_path), str(PROCESSED / pdf_path.name))
        new_clients.append((slug, data))
        print(f"  -> created client '{data['legal_business_name']}'  (clients/{slug}/index.html)")

    # rebuild dashboard from all clients on disk
    all_clients = []
    for cj in sorted(CLIENTS.glob("*/client.json")):
        all_clients.append(json.loads(cj.read_text()))
    (ROOT / "index.html").write_text(generate.dashboard_html(all_clients))
    print(f"Dashboard rebuilt with {len(all_clients)} client(s): index.html")
    return new_clients


if __name__ == "__main__":
    process_dropbox()
