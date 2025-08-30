from __future__ import annotations
import os, re, unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# ---- Supabase rows loader (official client) ----
# pip install supabase
try:
    from supabase import create_client
except Exception:
    create_client = None  # handled below

# -------------------- Models --------------------

@dataclass
class BrRow:
    row_id: int
    row_title: str
    accounts_included: str = ""
    accounts_included_start: Optional[int] = None
    accounts_included_end: Optional[int] = None
    balance_type: str = "DEBIT"

@dataclass
class AccountInfo:
    account: str
    name: str = ""
    sru: Optional[str] = None
    ub0: float = 0.0; ub_1: float = 0.0
    ib0: float = 0.0; ib_1: float = 0.0
    res0: float = 0.0; res_1: float = 0.0
    used: bool = False
    target_row_id: Optional[int] = None
    target_row_title: Optional[str] = None
    reclass_reason: Optional[str] = None

@dataclass
class PartyAliases:
    koncern: Set[str] = field(default_factory=set)
    intresse: Set[str] = field(default_factory=set)
    ovriga: Set[str] = field(default_factory=set)

@dataclass
class PreclassResult:
    per_account: Dict[str, AccountInfo]
    br_row_totals: Dict[int, Dict[str, float]]  # row_id -> {"row_title", "current", "previous"}
    reclass_log: List[Dict[str, str]]

# ----------------- Text helpers -----------------

def fix_mojibake(text: str) -> str:
    """Normalize å/ä/ö and common SE mojibake, trim quotes/spaces."""
    if not isinstance(text, str):
        return text
    t = unicodedata.normalize("NFKC", text)
    replacements = {
        "Ñ":"ä","Ü":"å","î":"ö","ô":"ö","ï":"ö",
        "Ür":"år", "fîretag":"företag", "koncernfîretag":"koncernföretag",
        "intressefîretag":"intresseföretag",
    }
    for a,b in replacements.items():
        t = t.replace(a,b)
    return re.sub(r"\s+"," ", t).strip().strip('"')

def simplify(s: str) -> str:
    """Lowercase, strip diacritics, keep only [a-z0-9_] to compare names."""
    s = fix_mojibake(s or "").lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^\w]+","", s)

def make_alias_variants(name: str) -> Set[str]:
    name = fix_mojibake(name or "")
    base = re.sub(r"\b(aktiebolaget|ab|kb|hb|ltd|oy|as)\b\.?", "", name, flags=re.I)
    base = re.sub(r"\(.*?\)", "", base).strip()
    variants = {simplify(name), simplify(base), simplify(name.replace(",", " "))}
    return {v for v in variants if v}

# -------------------- SIE parser --------------------

def parse_sie(path: str) -> Dict[str, AccountInfo]:
    """Collect #KONTO, #SRU and UB/IB/RES for year 0 and -1."""
    accs: Dict[str, AccountInfo] = {}
    rx_konto = re.compile(r'^#KONTO\s+(\d{3,4})\s+"?(.*?)"?\s*$', re.I)
    rx_sru   = re.compile(r'^#SRU\s+(\d{3,4})\s+(\d+)\s*$', re.I)
    rx_val   = re.compile(r'^#(UB|IB|RES)\s+(-?1|0)\s+(\d{3,4})\s+([+-]?\d+(?:[.,]\d+)?)\s*$', re.I)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()

            if m := rx_konto.match(line):
                a, nm = m.group(1), fix_mojibake(m.group(2))
                accs.setdefault(a, AccountInfo(account=a)).name = nm
                continue

            if m := rx_sru.match(line):
                a, sru = m.group(1), m.group(2)
                accs.setdefault(a, AccountInfo(account=a)).sru = sru
                continue

            if m := rx_val.match(line):
                tag, year, a, val = m.groups()
                v = float(val.replace(",", "."))
                info = accs.setdefault(a, AccountInfo(account=a))
                if tag.upper() == "UB":
                    if year == "0": info.ub0 = v
                    else: info.ub_1 = v
                elif tag.upper() == "IB":
                    if year == "0": info.ib0 = v
                    else: info.ib_1 = v
                elif tag.upper() == "RES":
                    if year == "0": info.res0 = v
                    else: info.res_1 = v

    for info in accs.values():
        info.used = any(abs(x) > 1e-9 for x in (info.ub0, info.ub_1, info.ib0, info.ib_1, info.res0, info.res_1))
        if not info.name:
            info.name = f"Konto {info.account}"
    return accs

# --------------- BR mapping (Supabase) ---------------

def load_br_mapping_from_supabase(url: str, key: str, table: str = "variable_mapping_br") -> List[BrRow]:
    if create_client is None:
        raise RuntimeError("supabase client not available; install `supabase` and set SUPABASE_URL/KEY.")
    sb = create_client(url, key)
    res = sb.table(table).select(
        "row_id,row_title,accounts_included,accounts_included_start,accounts_included_end,balance_type"
    ).execute()
    rows: List[BrRow] = []
    for r in res.data or []:
        rows.append(BrRow(
            row_id=int(r["row_id"]),
            row_title=str(r["row_title"]),
            accounts_included=(r.get("accounts_included") or "").strip(),
            accounts_included_start=int(r["accounts_included_start"]) if r.get("accounts_included_start") is not None else None,
            accounts_included_end=int(r["accounts_included_end"]) if r.get("accounts_included_end") is not None else None,
            balance_type=(r.get("balance_type") or "DEBIT").upper(),
        ))
    return rows

def account_matches_row(a: int, row: BrRow) -> bool:
    if row.accounts_included_start is not None and row.accounts_included_end is not None:
        if row.accounts_included_start <= a <= row.accounts_included_end:
            return True
    inc = (row.accounts_included or "").replace(",", ";")
    for part in [p.strip() for p in inc.split(";") if p.strip()]:
        if "-" in part:
            lo, hi = part.split("-", 1)
            try:
                if int(lo) <= a <= int(hi): return True
            except: pass
        else:
            try:
                if int(part) == a: return True
            except: pass
    return False

# --------------- Alias extraction ---------------

KONCERN_SYNONYMS  = ["koncern","koncernföretag","koncernbolag","gruppföretag","gruppbolag","dotter","dotterbolag","dotterföretag","moder","moderbolag","moderföretag"]
INTRESSE_SYNONYMS = ["intresseföretag","gemensamt styrda","joint venture","intresse"]
OVRIGA_SYNONYMS   = ["övriga företag","övr.","övr","andra företag","andra ftg"]
AAT_WORDS         = ["aktieägartillskott","aktieagartillskott","villkorat","ovillkorat"]

def extract_aliases(accs: Dict[str, AccountInfo]) -> PartyAliases:
    aliases = PartyAliases()

    def harvest(name: str) -> List[str]:
        parts = [fix_mojibake(name)]
        if "," in name:
            tail = name.split(",", 1)[1].strip()
            if 1 <= len(tail.split()) <= 6:
                parts.append(tail)
        return parts

    for a, info in accs.items():
        nm = info.name.lower()
        # 1310–1329 likely contains subsidiary names
        if re.match(r"^13(10|1[1-9]|20|21)$", a):
            for p in harvest(info.name):
                aliases.koncern |= make_alias_variants(p)
        # 1330–1339/134x likely contains intresseföretag names
        if a.startswith("133") or a.startswith("134"):
            for p in harvest(info.name):
                aliases.intresse |= make_alias_variants(p)
        if any(w in nm for w in INTRESSE_SYNONYMS): aliases.intresse |= make_alias_variants(info.name)
        if any(w in nm for w in KONCERN_SYNONYMS):  aliases.koncern  |= make_alias_variants(info.name)
        if any(w in nm for w in OVRIGA_SYNONYMS):   aliases.ovriga   |= make_alias_variants(info.name)

    def prune(s: Set[str]) -> Set[str]:
        return {x for x in s if len(x) >= 3 and not x.isdigit()}

    aliases.koncern  = prune(aliases.koncern)
    aliases.intresse = prune(aliases.intresse)
    aliases.ovriga   = prune(aliases.ovriga)
    return aliases

def aliases_from_scraper(company_info: dict) -> Tuple[Set[str], Set[str], Set[str]]:
    """Pull alias names from Bolagsfakta scraper output (parent + subsidiaries)."""
    koncern, intresse, ovriga = set(), set(), set()
    if not company_info: 
        print("DEBUG PRECLASS: No company_info provided to aliases_from_scraper")
        return koncern, intresse, ovriga

    print("DEBUG PRECLASS: Processing company aliases from scraper data...")

    # Parent company (treat as koncern alias to catch intercompany items)
    parent = company_info.get("parent_company") or {}
    if parent.get("name"):
        parent_variants = make_alias_variants(parent["name"])
        koncern |= parent_variants
        print(f"DEBUG PRECLASS: Added parent company aliases: {parent_variants}")
    else:
        print("DEBUG PRECLASS: No parent company name found")

    # Subsidiaries
    subsidiaries = company_info.get("subsidiaries") or []
    print(f"DEBUG PRECLASS: Processing {len(subsidiaries)} subsidiaries for aliases...")
    for i, sub in enumerate(subsidiaries):
        nm = sub.get("name") or ""
        if nm: 
            sub_variants = make_alias_variants(nm)
            koncern |= sub_variants
            print(f"DEBUG PRECLASS: Added subsidiary {i+1} aliases from '{nm}': {sub_variants}")

    print(f"DEBUG PRECLASS: Total koncern aliases from scraper: {len(koncern)} variants")
    print(f"DEBUG PRECLASS: Koncern aliases: {sorted(list(koncern))}")

    # If scraper distinguishes interest or others, add here (kept for future)
    return koncern, intresse, ovriga

# --------------- Row picking (by title regex) ---------------

ROW_KEYS = {
    "koncern_shares":       r"andelar\s+i\s+koncern",
    "koncern_fordr_lt":     r"långfristiga.*fordringar.*koncern",
    "koncern_fordr_st":     r"kortfristiga.*fordringar.*koncern",
    "koncern_skulder_lt":   r"långfristiga.*skulder.*koncern",
    "koncern_skulder_st":   r"kortfristiga.*skulder.*koncern",

    "intresse_shares":      r"andelar\s+i\s+intresseföretag|gemensamt styrda",
    "intresse_fordr_lt":    r"långfristiga.*fordringar.*intresse",
    "intresse_fordr_st":    r"kortfristiga.*fordringar.*intresse",
    "intresse_skulder_lt":  r"långfristiga.*skulder.*intresse",
    "intresse_skulder_st":  r"kortfristiga.*skulder.*intresse",
}

def pick_row_id(rows: List[BrRow], key: str) -> Optional[int]:
    rx = re.compile(ROW_KEYS[key], re.I)
    for r in rows:
        if rx.search(r.row_title):
            return r.row_id
    return None

# --------------- SRU hinting ----------------

def sru_hint_group(sru: Optional[str]) -> Optional[str]:
    """Very light SRU grouping signal used to strengthen/conflict checks."""
    if not sru: return None
    try:
        code = int(sru)
    except:
        return None
    # Example: 7214 byggnader vs 7215 inventarier (just a hint)
    if code == 7214: return "byggnader"
    if code == 7215: return "inventarier"
    return None

# --------------- Contextual classification ---------------

def contextual_target(
    a: str,
    info: AccountInfo,
    rows: List[BrRow],
    aliases: PartyAliases,
    extra_koncern: Set[str],
    extra_intresse: Set[str],
    strict: bool = False
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Return (row_id, row_title, reason) or (None, None, None).
    """
    nm = fix_mojibake(info.name)
    nm_low = nm.lower()
    nm_s = simplify(nm)
    a_num = int(a)

    koncern_alias = set(aliases.koncern)  | {simplify(x) for x in extra_koncern}
    intresse_alias= set(aliases.intresse) | {simplify(x) for x in extra_intresse}

    has = lambda toks: any(t in nm_low for t in toks)
    in_any = lambda s, alts: any(tok and tok in s for tok in alts)

    is_k = in_any(nm_s, koncern_alias) or has(KONCERN_SYNONYMS)
    is_i = in_any(nm_s, intresse_alias) or has(INTRESSE_SYNONYMS)

    # If name explicitly says "intresseföretag" but the alias matches a subsidiary, treat as koncern
    if "intresseföretag" in nm_low and is_k:
        is_i = False

    # Aktieägartillskott → shares buckets (proximity to 131x/133x helps)
    if (is_k and (has(AAT_WORDS) or 1310 <= a_num <= 1329)):
        rid = pick_row_id(rows, "koncern_shares")
        if rid: return rid, next(r.row_title for r in rows if r.row_id == rid), "AAT/proximity 131x → Andelar i koncern"

    if (is_i and (has(AAT_WORDS) or 1330 <= a_num <= 1339)):
        rid = pick_row_id(rows, "intresse_shares")
        if rid: return rid, next(r.row_title for r in rows if r.row_id == rid), "AAT/proximity 133x → Andelar i intresse"

    # Koncern receivables (ex: 1681 'Kortfristiga fordringar, RH Property')
    if is_k and ("fordr" in nm_low or a_num in (*range(1320,1330), *range(1680,1690))):
        key = "koncern_fordr_lt" if 1320 <= a_num <= 1329 else "koncern_fordr_st"
        rid = pick_row_id(rows, key)
        if rid: return rid, next(r.row_title for r in rows if r.row_id == rid), f"Koncern fordringar ({'LT' if key.endswith('lt') else 'ST'})"

    # Koncern debts
    if is_k and "skuld" in nm_low:
        key = "koncern_skulder_lt" if 2300 <= a_num <= 2399 else "koncern_skulder_st"
        rid = pick_row_id(rows, key)
        if rid: return rid, next(r.row_title for r in rows if r.row_id == rid), f"Koncern skulder ({'LT' if key.endswith('lt') else 'ST'})"

    # Intresse receivables/debts
    if is_i:
        if "fordr" in nm_low or 1340 <= a_num <= 1349:
            key = "intresse_fordr_lt" if 1340 <= a_num <= 1349 else "intresse_fordr_st"
            rid = pick_row_id(rows, key)
            if rid: return rid, next(r.row_title for r in rows if r.row_id == rid), f"Intresse fordringar ({'LT' if key.endswith('lt') else 'ST'})"
        if "skuld" in nm_low:
            key = "intresse_skulder_lt" if 2300 <= a_num <= 2399 else "intresse_skulder_st"
            rid = pick_row_id(rows, key)
            if rid: return rid, next(r.row_title for r in rows if r.row_id == rid), f"Intresse skulder ({'LT' if key.endswith('lt') else 'ST'})"

    # Label says intresse but alias says koncern → override
    if "intresseföretag" in nm_low and is_k:
        key = ("koncern_skulder_st" if "skuld" in nm_low
               else ("koncern_fordr_lt" if 1320 <= a_num <= 1329 else "koncern_fordr_st"))
        rid = pick_row_id(rows, key)
        if rid: return rid, next(r.row_title for r in rows if r.row_id == rid), "Override intresse→koncern"

    # SRU hint (soft; only used when strict)
    if strict and info.sru:
        hint = sru_hint_group(info.sru)
        if hint == "byggnader" and 7215 in [int(info.sru)]:
            # example pattern place-holder to show how to use SRU for conflicts
            pass

    return None, None, None

# --------------- Public API ---------------

def preclassify_accounts(
    sie_path: str,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
    company_info: Optional[dict] = None,
    extra_koncern_aliases: Optional[List[str]] = None,
    extra_intresse_aliases: Optional[List[str]] = None,
    strict: bool = False,
) -> PreclassResult:
    """
    1) Parse SIE, detect used accounts (IB/UB/RES in year 0 or -1)
    2) Load BR mapping rows from Supabase
    3) Build alias sets (from SIE + Bolagsfakta company_info + extra lists)
    4) Contextually reclassify accounts to BR row IDs
    5) Return per-account mapping, reclass log, and BR totals (UB year0/UB year-1)
    """
    if not supabase_url: supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_key: supabase_key = os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing Supabase config (SUPABASE_URL/SUPABASE_ANON_KEY).")

    accs = parse_sie(sie_path)
    rows = load_br_mapping_from_supabase(supabase_url, supabase_key)

    # Aliases from SIE
    aliases = extract_aliases(accs)

    # Aliases from scraper
    sc_k, sc_i, sc_o = aliases_from_scraper(company_info or {})
    extra_k = set(extra_koncern_aliases or []) | sc_k
    extra_i = set(extra_intresse_aliases or []) | sc_i

    # Default row guess from mapping-table ranges
    default_row: Dict[str, BrRow] = {}
    for a, info in accs.items():
        a_num = int(a)
        for r in rows:
            if account_matches_row(a_num, r):
                default_row[a] = r
                break

    log: List[Dict[str, str]] = []

    total_used = len([a for a in accs.values() if a.used])
    print(f"DEBUG PRECLASS: Starting account classification for {total_used} used accounts")
    
    for a, info in accs.items():
        if not info.used: 
            continue

        drow = default_row.get(a)
        new_id, new_title, reason = contextual_target(
            a, info, rows, aliases,
            extra_k, extra_i, strict=strict
        )

        if new_id:
            info.target_row_id = new_id
            info.target_row_title = new_title
            info.reclass_reason = reason
            if drow and drow.row_id != new_id:
                print(f"DEBUG PRECLASS: RECLASSIFYING Account {a} ({info.name[:30]}{'...' if len(info.name) > 30 else ''})")
                print(f"DEBUG PRECLASS:   FROM: Row {drow.row_id} ({drow.row_title[:30]}{'...' if len(drow.row_title) > 30 else ''})")
                print(f"DEBUG PRECLASS:   TO: Row {new_id} ({new_title[:30]}{'...' if len(new_title) > 30 else ''})")
                print(f"DEBUG PRECLASS:   REASON: {reason}")
                log.append({
                    "account": a,
                    "name": info.name,
                    "from": f"{drow.row_id if drow else 'None'}|{drow.row_title if drow else '-'}",
                    "to": f"{new_id}|{new_title}",
                    "reason": reason or "",
                })
            # Silently keep same classification - no debug spam
        else:
            if drow:
                info.target_row_id = drow.row_id
                info.target_row_title = drow.row_title
            else:
                info.target_row_id = None
                info.target_row_title = None

    # BR totals: sum by row
    totals: Dict[int, Dict[str, float]] = {}
    for info in accs.values():
        if not info.used or info.target_row_id is None:
            continue
        d = totals.setdefault(info.target_row_id, {"row_title": info.target_row_title or "", "current": 0.0, "previous": 0.0})
        d["current"]  += info.ub0
        d["previous"] += info.ub_1

    # Summary
    print(f"DEBUG PRECLASS: SUMMARY - {len(log)} accounts reclassified out of {total_used} total accounts")
    if len(log) == 0:
        print("DEBUG PRECLASS: No reclassifications needed - all accounts using optimal default mappings")

    return PreclassResult(per_account=accs, br_row_totals=totals, reclass_log=log)

# --------------- Integration helpers ---------------

def apply_to_br_parser(raw_postings: List[dict], pre: PreclassResult) -> Dict[int, float]:
    """
    Example shim: group a BR's postings by the *preclassified* row id.
    raw_postings: list of {account:'1681', amount: 123.45, year: 0/-1, side:'D'/'K' ...}
    Returns: {row_id: balance}
    """
    out: Dict[int, float] = {}
    for p in raw_postings:
        acc = str(p["account"])
        info = pre.per_account.get(acc)
        if not info or info.target_row_id is None:
            continue
        amt = float(p.get("amount", 0))
        out[info.target_row_id] = out.get(info.target_row_id, 0.0) + amt
    return out

def apply_to_k2_koncern(note_rows: List[dict], pre: PreclassResult) -> List[dict]:
    """
    Example shim: enrich K2 koncern note lines with preclass data per account.
    note_rows: [{row_id, row_title, amount_current, amount_previous, ...}]
    """
    row_map = {rid: vals for rid, vals in pre.br_row_totals.items()}
    for r in note_rows:
        rid = r.get("row_id")
        if rid in row_map:
            r["amount_current"]  = row_map[rid]["current"]
            r["amount_previous"] = row_map[rid]["previous"]
    return note_rows
