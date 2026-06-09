#!/usr/bin/env python3
"""HTML rendering for the PayComp client vista page and dashboard."""

import html
import os
import re
from datetime import datetime, timedelta

NAVY = "#16306b"
BLUE = "#2b6cb0"
ORANGE = "#f5821f"


def esc(v):
    return html.escape(str(v)) if v else ""


def dash(v):
    return esc(v) if v else '<span class="muted">&mdash;</span>'


def initials(name):
    parts = [p for p in (name or "").split() if p[:1].isalpha()]
    return ("".join(p[0] for p in parts[:2]) or "C").upper()


# --------------------------------------------------------------------------- #
#  Shared style
# --------------------------------------------------------------------------- #
STYLE = f"""
:root{{--navy:{NAVY};--blue:{BLUE};--orange:{ORANGE};--bg:#f4f6fb;--card:#fff;
--line:#e3e8f0;--text:#1f2a44;--muted:#8a93a8;}}
*{{box-sizing:border-box;}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--text);line-height:1.5;}}
a{{color:var(--blue);text-decoration:none;}}
.muted{{color:var(--muted);}}
.wrap{{max-width:1040px;margin:0 auto;padding:0 24px 56px;}}
.topbar{{background:var(--navy);color:#fff;padding:14px 24px;display:flex;align-items:center;gap:10px;}}
.logo{{font-weight:800;font-size:20px;letter-spacing:-.5px;}}
.logo .o{{color:var(--orange);}}
.tag{{font-size:12px;color:#acc1e6;margin-left:4px;}}
.hero{{background:linear-gradient(135deg,var(--navy),var(--blue));color:#fff;
padding:30px 24px;}}
.hero .wrap{{padding-bottom:0;display:flex;align-items:center;gap:20px;}}
.avatar{{width:62px;height:62px;border-radius:14px;background:rgba(255,255,255,.15);
display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:800;
border:1px solid rgba(255,255,255,.25);}}
.hero h1{{margin:0;font-size:26px;}}
.hero .sub{{color:#cfe0f7;font-size:14px;margin-top:3px;}}
.badge{{display:inline-block;background:var(--orange);color:#fff;font-size:11px;
font-weight:700;padding:3px 9px;border-radius:20px;text-transform:uppercase;letter-spacing:.5px;}}
.flags{{margin-left:auto;text-align:right;}}
.flag{{display:inline-block;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);
font-size:11px;padding:3px 9px;border-radius:6px;margin:2px 0 2px 6px;}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:-26px 0 26px;}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;
box-shadow:0 6px 18px rgba(20,40,90,.06);}}
.kpi .k{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;}}
.kpi .v{{font-size:17px;font-weight:700;margin-top:4px;word-break:break-word;}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;
box-shadow:0 4px 14px rgba(20,40,90,.05);overflow:hidden;}}
.card h2{{margin:0;font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:var(--navy);
padding:14px 18px;border-bottom:1px solid var(--line);background:#fafbfe;
display:flex;align-items:center;gap:8px;}}
.card h2 .dot{{width:8px;height:8px;border-radius:50%;background:var(--orange);}}
.card .body{{padding:6px 18px 14px;}}
.row{{display:flex;padding:8px 0;border-bottom:1px solid #f0f3f9;gap:12px;}}
.row:last-child{{border-bottom:none;}}
.row .l{{flex:0 0 42%;color:var(--muted);font-size:13px;}}
.row .r{{flex:1;font-weight:600;font-size:14px;word-break:break-word;}}
.full{{grid-column:1 / -1;}}
table{{width:100%;border-collapse:collapse;font-size:14px;}}
th{{background:var(--navy);color:#fff;text-align:left;padding:9px 12px;font-size:12px;
text-transform:uppercase;letter-spacing:.5px;}}
td{{padding:9px 12px;border-bottom:1px solid var(--line);}}
.foot{{margin-top:34px;color:var(--muted);font-size:12px;text-align:center;}}
.back{{color:#cfe0f7;font-size:13px;}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr;}}.kpis{{grid-template-columns:1fr 1fr;}}
.hero .wrap{{flex-wrap:wrap;}}.flags{{margin-left:0;text-align:left;}}}}
"""


def row(label, value):
    return f'<div class="row"><div class="l">{esc(label)}</div><div class="r">{dash(value)}</div></div>'


def card(title, rows_html, full=False):
    cls = "card full" if full else "card"
    return (f'<section class="{cls}"><h2><span class="dot"></span>{esc(title)}</h2>'
            f'<div class="body">{rows_html}</div></section>')


# --------------------------------------------------------------------------- #
#  Client vista page
# --------------------------------------------------------------------------- #
def vista_html(d):
    name = d.get("legal_business_name") or "Unnamed Client"
    dba = d.get("dba")
    freq = d.get("payroll_frequency", "")
    day = d.get("payroll_day", "")
    freq_disp = (freq + (f" ({day})" if day and freq in ("Weekly", "Bi-Weekly") else
                         (f" ({day})" if day else ""))) if freq else ""

    flags = []
    if d.get("multiple_locations"): flags.append("Multiple Locations")
    if d.get("multiple_feins"): flags.append("Multiple FEINs")
    if d.get("multiple_payroll_providers"): flags.append("Multiple Payroll Providers")
    flags_html = "".join(f'<span class="flag">&#9888; {esc(f)}</span>' for f in flags)

    addr = ", ".join(x for x in [d.get("business_address"),
                                 " ".join(y for y in [d.get("city"), d.get("state"), d.get("zip")] if y)] if x)

    business = card("Business &amp; Policy", "".join([
        row("Legal name", name),
        row("DBA", dba),
        row("FEIN", d.get("fein")),
        row("Address", addr),
    ]))

    contact = card("Primary Contact", "".join([
        row("Name", d.get("contact_name")),
        row("Email", d.get("contact_email")),
        row("Phone", d.get("contact_phone")),
    ]))

    policy = card("Workers&rsquo; Comp Policy", "".join([
        row("Carrier", d.get("wc_carrier")),
        row("Policy number", d.get("policy_number")),
        row("Effective date", d.get("policy_effective_date")),
    ]))

    schedule = card("Payroll Schedule", "".join([
        row("Frequency", freq_disp),
        row("Next check date", d.get("next_check_date")),
        row("Processed by", d.get("payroll_processor")),
    ]))

    agency = card("Agency", "".join([
        row("Agency name", d.get("agency_name")),
        row("Producer", d.get("producer_name")),
        row("Email", d.get("agency_email")),
        row("Phone", d.get("agency_phone")),
    ]))

    provider = card("Payroll Provider", "".join([
        row("Provider", d.get("provider_name")),
        row("Contact", d.get("provider_contact")),
        row("Email", d.get("provider_email")),
        row("Phone", d.get("provider_phone")),
    ]))

    # Wholesaler (only if present)
    wh_rows = "".join([
        row("Name", d.get("wholesaler_name")),
        row("Contact", d.get("wholesaler_contact")),
        row("Email", d.get("wholesaler_email")),
        row("Phone", d.get("wholesaler_phone")),
    ])
    wholesaler = card("Wholesaler / MGA", wh_rows) if any(
        d.get(k) for k in ("wholesaler_name", "wholesaler_contact", "wholesaler_email", "wholesaler_phone")
    ) else ""

    sched_contact = card("Scheduling &amp; Onboarding", "".join([
        row("Best contact", d.get("sched_contact")),
        row("Phone", d.get("sched_phone")),
        row("Email", d.get("sched_email")),
        row("Best times", d.get("sched_times")),
        row("Integration assistance ack.", "Yes" if d.get("integration_ack") else "No"),
    ]))

    auth = card("Authorization", "".join([
        row("Authorized signature", d.get("authorized_signature")),
        row("Printed name", d.get("printed_name")),
        row("Title", d.get("title")),
        row("Date", d.get("signature_date")),
        row("Authority confirmed", "Yes" if d.get("authority_confirmed") else "No"),
    ]))

    # Excluded employees table
    excl = d.get("excluded_employees") or []
    if d.get("no_excluded_employees"):
        excl_body = '<p class="muted">No excluded employees.</p>'
    elif excl:
        trs = "".join(
            f'<tr><td>{esc(e.get("name"))}</td><td>{esc(e.get("employee_id"))}</td>'
            f'<td>{esc(e.get("reason"))}</td></tr>' for e in excl)
        excl_body = (f'<table><tr><th>Name</th><th>Employee ID</th><th>Reason for exclusion</th></tr>'
                     f'{trs}</table>')
    else:
        excl_body = '<p class="muted">None listed.</p>'
    excluded = (f'<section class="card full"><h2><span class="dot"></span>'
                f'Excluded Employees / Officers</h2><div class="body">{excl_body}</div></section>')

    cards = [business, contact, policy, schedule, agency, provider]
    if wholesaler:
        cards.append(wholesaler)
    cards += [sched_contact, auth]

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(name)} &middot; PayComp Client Vista</title>
<style>{STYLE}</style></head><body>
<div class="topbar"><span class="logo">Pay<span class="o">Comp</span></span>
<span class="tag">Client Vista</span>
<a class="back" href="../../index.html" style="margin-left:auto;">&larr; All clients</a></div>
<div class="hero"><div class="wrap">
  <div class="avatar">{initials(name)}</div>
  <div>
    <span class="badge">Active Client</span>
    <h1>{esc(name)}</h1>
    <div class="sub">{esc(dba + " &bull; " if dba else "")}FEIN {esc(d.get('fein') or '—')}</div>
  </div>
  <div class="flags">{flags_html}</div>
</div></div>
<div class="wrap">
  <div class="kpis">
    <div class="kpi"><div class="k">Payroll Frequency</div><div class="v">{dash(freq_disp)}</div></div>
    <div class="kpi"><div class="k">Next Check Date</div><div class="v">{dash(d.get('next_check_date'))}</div></div>
    <div class="kpi"><div class="k">Payroll Provider</div><div class="v">{dash(d.get('provider_name'))}</div></div>
    <div class="kpi"><div class="k">WC Carrier</div><div class="v">{dash(d.get('wc_carrier'))}</div></div>
  </div>
  <div class="grid">
    {''.join(cards)}
    {excluded}
  </div>
  <div class="foot">Generated by PayComp intake parser from
    <strong>{esc(d.get('_source_pdf') or 'intake form')}</strong> &middot;
    {datetime.now().strftime('%b %d, %Y %I:%M %p')}</div>
</div></body></html>"""


# --------------------------------------------------------------------------- #
#  Dashboard
# --------------------------------------------------------------------------- #
def dashboard_html(clients):
    clients = sorted(clients, key=lambda c: (c.get("legal_business_name") or "").lower())
    cards = []
    for c in clients:
        name = c.get("legal_business_name") or "Unnamed Client"
        slug = c.get("_slug")
        freq = c.get("payroll_frequency", "")
        sub = " &bull; ".join(x for x in [c.get("city") and f"{esc(c.get('city'))}, {esc(c.get('state'))}",
                                          esc(c.get("provider_name"))] if x)
        cards.append(f"""
        <a class="ccard" href="clients/{esc(slug)}/index.html">
          <div class="cav">{initials(name)}</div>
          <div class="cinfo">
            <div class="cname">{esc(name)}</div>
            <div class="csub">{sub or '<span class=muted>—</span>'}</div>
          </div>
          <div class="cmeta"><span class="chip">{esc(freq) or '—'}</span>
            <span class="next">{esc(c.get('next_check_date') or '')}</span></div>
        </a>""")
    body = "".join(cards) if cards else '<p class="muted">No clients yet. Drop an intake PDF in Dropbox/ and run <code>python3 paycomp.py</code>.</p>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PayComp &middot; Clients</title>
<style>{STYLE}
.ccard{{display:flex;align-items:center;gap:16px;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:16px 18px;margin-bottom:12px;box-shadow:0 4px 14px rgba(20,40,90,.05);
transition:transform .08s,box-shadow .08s;}}
.ccard:hover{{transform:translateY(-1px);box-shadow:0 8px 22px rgba(20,40,90,.12);}}
.cav{{width:48px;height:48px;border-radius:11px;background:linear-gradient(135deg,var(--navy),var(--blue));
color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px;}}
.cinfo{{flex:1;}} .cname{{font-weight:700;font-size:16px;color:var(--navy);}}
.csub{{font-size:13px;color:var(--muted);margin-top:2px;}}
.cmeta{{text-align:right;}} .chip{{display:inline-block;background:#eef3fb;color:var(--blue);
font-size:12px;font-weight:600;padding:3px 10px;border-radius:20px;}}
.next{{display:block;font-size:12px;color:var(--muted);margin-top:5px;}}
.count{{color:var(--muted);font-size:14px;margin:0 0 18px;}}
</style></head><body>
<div class="topbar"><span class="logo">Pay<span class="o">Comp</span></span>
<span class="tag">Client Directory</span></div>
<div class="hero"><div class="wrap"><div>
  <h1>Clients</h1><div class="sub">Generated from intake forms dropped in your Dropbox folder</div>
</div></div></div>
<div class="wrap" style="padding-top:28px;">
  <p class="count">{len(clients)} client{'s' if len(clients)!=1 else ''}</p>
  {body}
  <div class="foot">PayComp intake parser &middot; updated {datetime.now().strftime('%b %d, %Y %I:%M %p')}</div>
</div></body></html>"""


# --------------------------------------------------------------------------- #
#  Atlas client portal  (live template built from portal_template.html)
#
#  The mockup in portal_template.html is treated as a fixed design. We inject
#  the real intake data from client.json into the spots that map to it, and
#  flag the sections the intake form does NOT provide (premium history,
#  reconciliation, class codes, audit trail) with a "Sample data" badge.
#
#  The carrier-setup wizard (page-carrier + the CARRIERS JS object) is a
#  generic how-to-connect helper that lists several carriers as templates,
#  so it is shielded from the carrier-name substitution below.
# --------------------------------------------------------------------------- #
TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "portal_template.html")

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _parse_date(s):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
        try:
            return datetime.strptime((s or "").strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def _client_id(d):
    inits = initials(d.get("legal_business_name"))
    slug = d.get("_slug") or ""
    m = re.search(r"(\d{3,})$", slug)
    if m:
        suffix = m.group(1)
    else:
        digits = re.sub(r"\D", "", d.get("fein", "") or "")
        suffix = (digits or "0001")[-4:]
    return f"{inits}-{suffix}"


def _user_short(name):
    parts = [p for p in (name or "").split() if p[:1].isalpha()]
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}"
    return name or "Client"


def _sample_badge():
    return ('<span style="display:inline-block;margin-left:8px;background:#FEF0E4;'
            'color:#F07C20;font-size:10px;font-weight:800;letter-spacing:.4px;'
            'text-transform:uppercase;padding:2px 8px;border-radius:10px;'
            'vertical-align:middle">Sample data</span>')


def _protect(text, start_marker, end_marker, sentinel):
    """Replace text[start..end) with a sentinel; return (text, original_block)."""
    i = text.find(start_marker)
    if i == -1:
        return text, None
    j = text.find(end_marker, i + len(start_marker))
    if j == -1:
        return text, None
    block = text[i:j]
    return text[:i] + sentinel + text[j:], block


def portal_html(d):
    """Render the Atlas client portal for one client, populated from client.json."""
    with open(TEMPLATE_PATH, encoding="utf-8") as fh:
        t = fh.read()

    company = d.get("legal_business_name") or "Client"
    inits = initials(company)
    cid = _client_id(d)
    email = d.get("contact_email") or "client@example.com"
    user_short = _user_short(d.get("contact_name"))
    carrier = d.get("wc_carrier") or "Your carrier"
    policy = d.get("policy_number") or "—"
    provider = (d.get("provider_name") or d.get("payroll_processor")
                or "Your payroll provider")

    eff = _parse_date(d.get("policy_effective_date"))
    if eff:
        end = eff.replace(year=eff.year + 1) - timedelta(days=1)
        term_html = (f"{_MONTHS[eff.month - 1]}&nbsp;{eff.year}&ndash;"
                     f"{_MONTHS[end.month - 1]}&nbsp;{end.year}")
        term_txt = (f"{_MONTHS[eff.month - 1]} {eff.year}–"
                    f"{_MONTHS[end.month - 1]} {end.year}")
        renews = f"Renews {(end + timedelta(days=1)).strftime('%d %b %Y')}"
    else:
        term_html = term_txt = "&mdash;"
        renews = "Renews —"

    # Shield the generic carrier-setup wizard from the carrier-name swap.
    t, carriers_js = _protect(t, "var CARRIERS={", "var STATE={};", "@@CARRIERS_JS@@")
    t, carrier_pg = _protect(t, '<div class="page" id="page-carrier">',
                             '<div class="page" id="page-relationship">', "@@CARRIER_PG@@")

    # Context-specific replacements (the two "Acme Payroll, Inc." spots mean
    # different things, so they are anchored separately).
    t = t.replace('<div class="av">AC</div>', f'<div class="av">{esc(inits)}</div>')
    t = t.replace('font-size:12.5px">Acme Payroll, Inc.</div>',
                  f'font-size:12.5px">{esc(company)}</div>')          # sidebar identity
    t = t.replace('<div class="n">Acme Payroll, Inc.</div>',
                  f'<div class="n">{esc(provider)}</div>')            # payroll provider node
    t = t.replace('Client ID &middot; AC-20413', f'Client ID &middot; {esc(cid)}')
    t = t.replace('S. Johnson (You)', f'{esc(user_short)} (You)')
    t = t.replace('Jan&ndash;Dec 2026', term_html)
    t = t.replace('Term: Jan–Dec 2026', f'Term: {term_txt}')
    t = t.replace('Renews 01 Jan 2027', renews)

    # Rebuild the excluded-members table body from the real intake data.
    # Columns the intake form does not supply (class code, effective date,
    # annual wages) are shown as em-dashes rather than invented numbers.
    exc = d.get("excluded_employees") or []
    ei = t.find("Excluded members</h3>")
    if ei != -1:
        tb = t.find("<tbody>", ei)
        tbe = t.find("</tbody>", tb)
        if tb != -1 and tbe != -1:
            if exc:
                rows = []
                for e in exc:
                    name = esc(e.get("name") or "Excluded member")
                    reason = e.get("reason") or ""
                    rl = reason.lower()
                    role = ("Owner / Officer" if "owner" in rl or "officer" in rl
                            else "LLC member" if "llc" in rl
                            else "Excluded member")
                    rows.append(
                        f"<tr><td><b>{name}</b></td><td>{role}</td>"
                        f"<td>{esc(reason) or 'Owner/officer exclusion'}</td>"
                        "<td class=\"mono\">&mdash;</td><td>&mdash;</td>"
                        "<td class=\"mono\">&mdash;</td>"
                        "<td><span class=\"pill amber\">&#8854; Excluded</span></td></tr>")
                new_tb = "<tbody>" + "".join(rows)
            else:
                new_tb = ("<tbody><tr><td colspan=\"7\" style=\"text-align:center;"
                          "color:#6B7280;padding:18px\">No excluded members on this "
                          "account.</td></tr>")
            t = t[:tb] + new_tb + t[tbe:]
    t = t.replace('<div class="lbl">Excluded Members</div><div class="val">3</div>',
                  f'<div class="lbl">Excluded Members</div>'
                  f'<div class="val">{len(exc)}</div>')

    # Global swaps (wizard already shielded).
    t = t.replace('sarah.johnson@acme-payroll.com', esc(email))
    t = t.replace('TRV-WC-884102', esc(policy))
    t = t.replace('Travelers', esc(carrier))

    # Flag the sections the intake form does not provide.
    for head in ['Recent activity</h3>', 'Premium history</h3>',
                 'Reconciliation by payroll run</h3>', "What you're billed</h3>",
                 'Audit trail &mdash; up to the minute</h3>']:
        t = t.replace(head, head[:-5] + _sample_badge() + '</h3>', 1)

    # Restore shielded regions.
    if carriers_js:
        t = t.replace("@@CARRIERS_JS@@", carriers_js)
    if carrier_pg:
        t = t.replace("@@CARRIER_PG@@", carrier_pg)

    t = t.replace('<title>Atlas Client Portal — PayComp (Mockup)</title>',
                  f'<title>{esc(company)} · Atlas Client Portal — PayComp</title>')
    t = t.replace(
        "ATLAS CLIENT PORTAL · WORKERS' COMP — interactive mockup with sample data (not live)",
        f"ATLAS CLIENT PORTAL · {esc(company)} — live intake data; "
        "flagged sections show sample data")
    return t
