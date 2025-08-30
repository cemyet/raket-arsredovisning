# -*- coding: utf-8 -*-
"""
preclass_reclassifier.py — one drop-in module

What it does
------------
1) Parse SIE (#KONTO, #SRU, #IB/#UB/#RES).
2) Harvest company names from 1310–1339 account texts.
3) Optionally merge external scraper results (Ratsit/Allabolag/Bolagsfakta).
4) Build robust matchers (handles å/ä/ö, AB/HB/KB variants, acronyms).
5) Reclassify any account by:
   • which company name it mentions (koncern/intresse/övriga),
   • whether it's Andelar/Fordringar/Skulder,
   • short vs long (text + range heuristics).
6) Produce:
   • used_accounts_df (per account balances for year 0 & −1 + BR hint),
   • br_row_totals (aggregated current/previous totals by BR hint),
   • account_sets for K2 (shares, AAT, impairment).

Wire-up
-------
- Call run_preclass(sie_text, external_group_info=None) right after reading SIE.
- Pass its return to BR/K2 parsers.
- Resolve "BR Hint" -> BR row id via Supabase (hook provided below).
"""

from __future__ import annotations
import re, unicodedata, html
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Iterable
import pandas as pd

# ---------------- Normalization ----------------

def _soft(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()

def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("\u00A0", " ")
    return _soft(s)

# ---------------- SIE parsing ----------------

_BAL_RE = re.compile(r'^#(IB|UB|RES)\s+(-?1|0)\s+(\d{3,4})\s+(-?[0-9][0-9\s.,]*)')
_KONTO_RE = re.compile(r'^#KONTO\s+(\d{3,4})\s+"([^"]*)"\s*$')
_SRU_RE = re.compile(r'^#SRU\s+(\d{3,4})\s+(\d+)\s*$')

def _to_float(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))

def parse_sie(sie_text: str):
    lines = (sie_text or "").replace("\t", " ").replace("\u00A0", " ").splitlines()
    konto_name: Dict[int, str] = {}
    sru_codes: Dict[int, int] = {}
    balances: Dict[Tuple[int,int], Dict[str,float]] = {}

    for raw in lines:
        s = raw.strip()
        mk = _KONTO_RE.match(s)
        if mk:
            acct = int(mk.group(1)); name = mk.group(2)
            konto_name[acct] = name
            continue
        ms = _SRU_RE.match(s)
        if ms:
            acct = int(ms.group(1)); sru = int(ms.group(2))
            sru_codes[acct] = sru
            continue
        mb = _BAL_RE.match(s)
        if mb:
            tag, year, acct, amount = mb.group(1), int(mb.group(2)), int(mb.group(3)), _to_float(mb.group(4))
            key = (acct, year)
            if key not in balances:
                balances[key] = {"IB": 0.0, "UB": 0.0, "RES": 0.0}
            balances[key][tag] = amount

    return konto_name, sru_codes, balances

# ---------------- Company harvesting (1310–1339) ----------------

LEGAL_SUFFIX_RE = re.compile(r"\b(?:ab|ab \(publ\)|hb|kb|kommanditbolag)\b\.?", re.I)
GENERIC_STOP = {
    "andel","andelar","aktie","aktier","aktiebolag","aktiebolaget",
    "koncern","koncernföretag","koncernforetag","dotterbolag",
    "intresseföretag","intresseforetag","gemensamt","styrda","företag","foretag",
    "fordran","fordringar","långfristiga","langfristiga","kortfristiga","övriga","ovriga",
    "hos","i","till","mm","mfl",
}

def _company_like_spans(text: str) -> List[str]:
    # strip common preambles
    t = re.sub(r'^(andelar|fordringar)\s+(i|hos)\s+', '', text or '', flags=re.I)
    t = re.sub(r'^(långfristiga|langfristiga|kortfristiga|övriga|ovriga)\s+', '', t, flags=re.I).strip()
    out: List[str] = []

    # explicit "… Name AB/HB/KB …"
    for m in re.finditer(r'([A-ZÅÄÖ][A-Za-zÅÄÖåäö0-9&.,\- ]{1,80}\s+(?:AB(?:\s*\(publ\))?|HB|KB|Kommanditbolag)\b)', t):
        out.append(m.group(1).strip())

    # fallback: 2–6 capitalized tokens
    if not out:
        for m in re.finditer(r'(([A-ZÅÄÖ][A-Za-zÅÄÖåäö0-9\-]{2,}\s+){1,5}[A-ZÅÄÖ][A-Za-zÅÄÖåäö0-9\-]{2,})', t):
            cand = m.group(1).strip()
            fold = _fold(cand)
            toks = [x for x in re.split(r'[\s\-.,&/]+', fold) if x]
            if sum(tok not in GENERIC_STOP for tok in toks) >= 1:
                out.append(cand)

    # dedupe
    seen = set(); uniq = []
    for nm in out:
        key = _soft(nm)
        if key not in seen:
            seen.add(key); uniq.append(nm)
    return uniq

def _alias_pack(full_name: str):
    full_soft = _soft(full_name)
    base_soft = _soft(LEGAL_SUFFIX_RE.sub("", full_name)).strip()
    base_fold = _fold(base_soft)
    toks_soft = [t for t in re.split(r'[\s,&./\-]+', base_soft) if t]
    toks_fold = [t for t in re.split(r'[\s,&./\-]+', base_fold) if t]
    sig_soft = [t for t in toks_soft if t not in GENERIC_STOP and len(t) >= 3]
    sig_fold = [t for t in toks_fold if t not in GENERIC_STOP and len(t) >= 3]
    acro = "".join(w[0] for w in toks_soft if w and w[0].isalpha())

    aliases = set([full_soft, base_soft, base_fold])
    aliases.update(sig_soft[:3])
    if len(sig_soft) >= 2:
        aliases.add(" ".join(sig_soft[:2]))
    if acro and len(acro) >= 2:
        aliases.add(acro.lower())

    rx_tokens = [re.escape(t) for t in (sig_fold or [base_fold])]
    core = r"(?:\W+)?".join(rx_tokens)
    rx_suffix = r"(?:\W+(?:ab(?:\W*\(publ\))?|hb|kb|kommanditbolag))?"
    rx = re.compile(rf"\b{core}{rx_suffix}\b", re.I)

    return {"full": {full_soft}, "regex": {rx}}

def harvest_company_names_from_1310_1339(konto_name: Dict[int,str]):
    buckets = {
        "koncern": {"full": set(), "regex": set()},
        "intresse": {"full": set(), "regex": set()},
        "ovriga": {"full": set(), "regex": set()},
    }
    for acct, txt in (konto_name or {}).items():
        if not (1310 <= acct <= 1339): 
            continue
        for nm in _company_like_spans(txt or ""):
            pack = _alias_pack(nm)
            if 1310 <= acct <= 1319:
                b = "koncern"
            elif 1330 <= acct <= 1335:
                b = "intresse"
            else:
                b = "ovriga"
            buckets[b]["full"]  |= pack["full"]
            buckets[b]["regex"] |= pack["regex"]

    def unify(regexes: Iterable[re.Pattern]) -> re.Pattern:
        pat = "|".join(sorted({r.pattern for r in regexes})) or r"(?!x)"
        return re.compile(pat, re.I)

    return {
        "koncern":  {"full": buckets["koncern"]["full"],  "regex": {unify(buckets["koncern"]["regex"])}},
        "intresse": {"full": buckets["intresse"]["full"], "regex": {unify(buckets["intresse"]["regex"])}},
        "ovriga":   {"full": buckets["ovriga"]["full"],   "regex": {unify(buckets["ovriga"]["regex"])}},
    }

# ---------------- External scraper adapter (Ratsit / Bolagsfakta) ----------------

def normalize_external_group_info(scraper_data: dict):
    """
    Accepts output like RatsitGroupScraper.get_group_info():
      {"parent_company": {...} | None, "subsidiaries": [{"name": ...}, ...], ...}
    or your Bolagsfakta scraper (same essential keys).
    Returns sets of names per bucket.
    """
    out = {"koncern": set(), "intresse": set(), "ovriga": set()}
    if not isinstance(scraper_data, dict):
        return out
    for sub in scraper_data.get("subsidiaries") or []:
        nm = (sub or {}).get("name") or ""
        if nm:
            out["koncern"].add(nm)
    # (If you later add explicit associates/others, extend here.)
    return out

def merge_company_sources(harvested, external_names):
    merged = {
        "koncern":  {"full": set(harvested["koncern"]["full"]),  "regex": set(harvested["koncern"]["regex"])},
        "intresse": {"full": set(harvested["intresse"]["full"]), "regex": set(harvested["intresse"]["regex"])},
        "ovriga":   {"full": set(harvested["ovriga"]["full"]),   "regex": set(harvested["ovriga"]["regex"])},
    }
    for g in ("koncern","intresse","ovriga"):
        for nm in external_names.get(g, []):
            pack = _alias_pack(nm)
            merged[g]["full"] |= pack["full"]
            pats = {r.pattern for r in merged[g]["regex"]}
            pats |= {r.pattern for r in pack["regex"]}
            merged[g]["regex"] = {re.compile("|".join(sorted(pats)) or r"(?!x)", re.I)}
    return merged

def match_group(text: str, matchers) -> Optional[str]:
    hay = f"{_soft(text)} || {_fold(text)}"
    for g in ("koncern", "intresse", "ovriga"):
        for rx in matchers[g]["regex"]:
            if rx.search(hay):
                return g
    return None

# ---------------- BR row hinting ----------------

FORDR_PAT = re.compile(r'\b(fordran|fordringar)\b', re.I)
SKULD_PAT = re.compile(r'\b(skuld|skulder)\b', re.I)
KORT_PAT  = re.compile(r'\b(kortfrist|kort frist)\w*', re.I)
LANG_PAT  = re.compile(r'\b(långfrist|langfrist)\w*', re.I)
ANDEL_PAT = re.compile(r'\b(andel|andelar|aktie|aktier)\b', re.I)
AAT_PAT   = re.compile(r'\b(aktieägartillskott|aktieagartillskott|villkorat|ovillkorat)\b', re.I)
IMP_PAT   = re.compile(r'\b(?:ack(?:[.\s]*nedskr\w*)|ackum\w*|nedskriv\w*)\b', re.I)

def br_hint_for_account(acct: int, name: str, group: Optional[str]) -> Optional[str]:
    nm = name or ""
    is_andel = bool(ANDEL_PAT.search(nm)) or (1310 <= acct <= 1319 or 1330 <= acct <= 1339)
    is_fordr = bool(FORDR_PAT.search(nm)) or (1600 <= acct <= 1799)
    is_skuld = bool(SKULD_PAT.search(nm)) or (2800 <= acct <= 2999)
    is_kort  = bool(KORT_PAT.search(nm))  or (1500 <= acct <= 1999 or 2800 <= acct <= 2999)
    is_lang  = bool(LANG_PAT.search(nm))  or (1300 <= acct <= 1499 or 2300 <= acct <= 2799)

    if group == "koncern":
        if is_andel or (1310 <= acct <= 1319):
            return "Andelar i koncernföretag"
        if is_fordr:
            return "Fordringar hos koncernföretag (kortfristiga)" if is_kort else "Långfristiga fordringar hos koncernföretag"
        if is_skuld:
            return "Kortfristiga skulder till koncernföretag" if is_kort else "Långfristiga skulder till koncernföretag"

    if group == "intresse":
        if is_andel or (1330 <= acct <= 1335):
            return "Andelar i intresseföretag och gemensamt styrda företag"
        if is_fordr:
            return "Kortfristiga fordringar hos intresseföretag och gemensamt styrda företag" if is_kort else "Långfristiga fordringar hos intresseföretag och gemensamt styrda företag"
        if is_skuld:
            return "Kortfristiga skulder till intresseföretag och gemensamt styrda företag" if is_kort else "Långfristiga skulder till intresseföretag och gemensamt styrda företag"

    if group == "ovriga":
        if is_andel or (1336 <= acct <= 1339):
            return "Ägarintressen i övriga företag"
        if is_fordr:
            return "Kortfristiga fordringar hos övriga företag som det finns ett ägarintresse i" if is_kort else "Långfristiga fordringar hos övriga företag som det finns ett ägarintresse i"
        if is_skuld:
            return "Kortfristiga skulder till övriga företag som det finns ett ägarintresse i" if is_kort else "Långfristiga skulder till övriga företag som det finns ett ägarintresse i"

    # Fallbacks when group not detected but range is indicative
    if 1310 <= acct <= 1319:
        return "Andelar i koncernföretag"
    if 1330 <= acct <= 1335:
        return "Andelar i intresseföretag och gemensamt styrda företag"
    if 1336 <= acct <= 1339:
        return "Ägarintressen i övriga företag"

    return None

# ---------------- Output structure ----------------

@dataclass
class PreclassResult:
    used_accounts_df: pd.DataFrame         # per-account balances + group & BR hint
    br_row_totals: Dict[str, Dict[str,float]]  # {br_hint: {current, previous}}
    account_sets: Dict[str, set]           # for K2 integration (shares, AAT, impairment)
    company_matchers: Dict[str, dict]      # the compiled matchers (koncern/intresse/ovriga)

# ---------------- Supabase bridge (placeholder) ----------------

def resolve_br_hint_to_row_id_via_supabase(br_hint: str) -> Optional[str]:
    """
    Placeholder: in production, query Supabase 'br_rows' to resolve a hint string to the exact row id.
    Keep this function name/signature; Cursor will implement with Supabase client.
    """
    return None  # not used in this drop-in

# ---------------- Main entrypoint ----------------

def run_preclass(sie_text: str, external_group_info: Optional[dict] = None) -> PreclassResult:
    konto_name, sru_codes, balances = parse_sie(sie_text)

    # 1) company names from SIE 1310–1339
    harvested = harvest_company_names_from_1310_1339(konto_name)

    # 2) merge external (Ratsit/Bolagsfakta) if given
    ext_names = normalize_external_group_info(external_group_info or {})
    matchers = merge_company_sources(harvested, ext_names)

    # 3) build used accounts table (year 0 & −1)
    def nz(x): return abs(x) > 1e-9
    used: Dict[int, dict] = {}
    for (acct, yr), bal in balances.items():
        if yr not in (0, -1): 
            continue
        if not any(nz(v) for v in bal.values()):
            continue
        row = used.setdefault(acct, {
            "Account": acct, "Name": konto_name.get(acct, ""),
            "SRU": sru_codes.get(acct),
            "IB (0)": 0.0, "UB (0)": 0.0, "RES (0)": 0.0,
            "IB (-1)": 0.0, "UB (-1)": 0.0, "RES (-1)": 0.0
        })
        row[f"IB ({yr})"]  = bal.get("IB",  row[f"IB ({yr})"])
        row[f"UB ({yr})"]  = bal.get("UB",  row[f"UB ({yr})"])
        row[f"RES ({yr})"] = bal.get("RES", row[f"RES ({yr})"])

    rows = []
    for acct, r in used.items():
        name = r["Name"] or ""
        # PRIORITY: if text matches koncern, that overrides "intresse" even if the word 'intresseföretag' appears (2863 case)
        grp = match_group(name, matchers)
        hint = br_hint_for_account(acct, name, grp)
        rows.append({**r, "GroupMatch": grp or "", "BR Hint": hint or ""})

    used_df = pd.DataFrame(rows).sort_values(["BR Hint","Account"]).reset_index(drop=True)

    # 4) aggregate by BR hint (current = UB(0), previous = UB(-1) by convention)
    totals: Dict[str, Dict[str,float]] = {}
    for _, r in used_df.iterrows():
        br = r["BR Hint"] or "(Unmapped)"
        cur = float(r["UB (0)"] or 0.0)
        prv = float(r["UB (-1)"] or 0.0)
        d = totals.setdefault(br, {"current":0.0, "previous":0.0})
        d["current"]  += cur
        d["previous"] += prv

    # 5) account sets for K2:
    account_sets = {
        # Shares in group companies
        "koncern_share_accounts": {int(a) for a in used_df.loc[
            used_df["BR Hint"]=="Andelar i koncernföretag","Account"
        ].tolist()},
        # AAT accounts (by text)
        "aat_accounts": {int(a) for a, nm in konto_name.items()
                         if 1310 <= a <= 1339 and AAT_PAT.search(nm or "")},
        # Impairment accounts (1318 + any 131x with ack/ned patterns)
        "impairment_accounts": {a for a in konto_name
                                if (a == 1318) or (1310 <= a <= 1319 and IMP_PAT.search(konto_name[a] or ""))}
    }

    return PreclassResult(
        used_accounts_df=used_df,
        br_row_totals=totals,
        account_sets=account_sets,
        company_matchers=matchers
    )
