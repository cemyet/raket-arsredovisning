# koncern_k2_parser.py
# -*- coding: utf-8 -*-
"""
K2 KONCERN note parser — restored & hardened

- Always computes from SIE (#IB/#UB/#RES/#VER/#TRANS), never from BR row totals.
- Accepts optional preclass account_sets to seed classification. No totals consumed.
- Restores voucher-scoped logic for sale vs. payout; fusion, AAT, omklass, impairment.
- Optional company-name hints (from scraper) to improve 132x rescue inside 1310–1339.
"""

from __future__ import annotations
import re
import unicodedata
from collections import defaultdict
from typing import Iterable, List, Dict, Optional, Set, Tuple

# ---- Regex patterns ----
ACK_IMP_PAT = re.compile(r'\b(?:ack(?:[.\s]*nedskr\w*)|ackum\w*|nedskriv\w*)\b', re.IGNORECASE)
FORDR_PAT   = re.compile(r'\b(fordran|fordringar|lan|lån|ranta|ränta|amort|avbetal)\b', re.IGNORECASE)

# ---- Sale P&L accounts (BAS 822x) ----
SALE_PNL = tuple(range(8220, 8230))

# ---- Utils ----
def _norm_text(s: str) -> str:
    """ASCII-fold + lower + collapse spaces."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("\u00a0", " ").replace("\t", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _f(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))

def _name_variants(name: str) -> Set[str]:
    """Generate a few robust variants for company-name matching in kontotext."""
    n = _norm_text(name)
    # strip common affixes, punctuation, duplicate spaces
    n = re.sub(r"[^a-z0-9 åäö]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    # simple variants
    v = {n}
    # remove legal suffix spacing variants (ab, kb, hb)
    for suf in [" ab", " kb", " hb", " kommanditbolag", " aktiebolag"]:
        if n.endswith(suf):
            v.add(n[: -len(suf)].strip())
    return v

# ---- Core parser ----
def parse_koncern_k2_from_sie_text(
    sie_text: str,
    preclass_result=None,                 # expects optional .account_sets
    debug: bool = False,
    scraper_companies: Optional[Iterable[str]] = None  # optional names from scraper
) -> Dict[str, float]:
    """
    Returns dict with the standard K2 KONCERN note keys.
    """

    # -------- Pre-normalize SIE + read #KONTO, #IB/#UB/#RES --------
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    konto_name: Dict[int, str] = {}
    ib: Dict[int, float] = {}
    ub: Dict[int, float] = {}
    res: Dict[int, float] = {}

    rx_konto = re.compile(r'^#KONTO\s+(\d{3,4})\s+"([^"]*)"', re.I)
    rx_bal   = re.compile(r'^#(IB|UB|RES)\s+(-?1|0)\s+(\d{3,4})\s+(-?[0-9][0-9\s.,]*)', re.I)

    for raw in lines:
        s = raw.strip()
        mk = rx_konto.match(s)
        if mk:
            konto_name[int(mk.group(1))] = _norm_text(mk.group(2))
            continue
        mb = rx_bal.match(s)
        if not mb:
            continue
        tag, yr, acc, val = mb.group(1), int(mb.group(2)), int(mb.group(3)), _f(mb.group(4))
        if yr != 0:
            continue
        if tag == "IB":
            ib[acc] = val
        elif tag == "UB":
            ub[acc] = val
        elif tag == "RES":
            res[acc] = res.get(acc, 0.0) + val

    # -------- Company-name hints (optional) --------
    # Restrict use to 1310–1339 konton to help "rescue" 132x that are really shares/AAT
    name_tokens: Set[str] = set()
    if scraper_companies:
        for nm in scraper_companies:
            for variant in _name_variants(nm or ""):
                if variant:
                    name_tokens.add(variant)

    # -------- Dynamic account classification --------
    def is_receivable(nm: str) -> bool:
        return bool(FORDR_PAT.search(nm))

    def is_aat(nm: str) -> bool:
        return any(w in nm for w in ("aktieagartillskott", "aktieägartillskott", "villkorat", "ovillkorat", "tillskott", "aat"))

    def is_share_koncern(nm: str) -> bool:
        base = (("koncern" in nm or "koncernföretag" in nm or "koncernforetag" in nm or "dotter" in nm)
                and ("andel" in nm or "andelar" in nm or "aktie" in nm or "aktier" in nm))
        # If kontotext includes any known company name token, bias towards "share"
        has_name = any(tok and tok in nm for tok in name_tokens) if name_tokens else False
        return base or has_name

    def is_imp_text(nm: str) -> bool:
        return bool(ACK_IMP_PAT.search(nm))

    andel_set: Set[int] = set()
    aat_set: Set[int]   = set()
    imp_set: Set[int]   = set()

    # Seed from preclass sets (if provided)
    if preclass_result is not None and hasattr(preclass_result, "account_sets"):
        andel_set |= set(preclass_result.account_sets.get("koncern_share_accounts", []))
        aat_set   |= set(preclass_result.account_sets.get("aat_accounts", []))
        imp_set   |= set(preclass_result.account_sets.get("impairment_accounts", []))

    # Heuristic classification to fill any gaps

    # 1310–1318 (1318 impairment)
    for a in range(1310, 1319):
        nm = konto_name.get(a, "")
        if a == 1318 or is_imp_text(nm):
            imp_set.add(a)
            continue
        if not is_receivable(nm):
            (aat_set if is_aat(nm) else andel_set).add(a)

    # 1320–1329 rescue: look like shares/AAT, not receivables; allow company-name hint
    for a in range(1320, 1330):
        nm = konto_name.get(a, "")
        if not nm or is_receivable(nm):
            continue
        if is_aat(nm):
            aat_set.add(a)
        elif is_share_koncern(nm):
            andel_set.add(a)

    # (Optional) allow name hint bias also on 1330–1339 for "misplaced" shares
    for a in range(1330, 1340):
        nm = konto_name.get(a, "")
        if nm and not is_receivable(nm) and any(tok in nm for tok in name_tokens):
            # do not guess AAT in 133x; only add to shares if strongly hinted
            andel_set.add(a)

    asset_all: Set[int] = andel_set | aat_set

    if debug:
        print("KONCERN account sets:")
        print("  andel_set:", sorted(andel_set))
        print("  aat_set  :", sorted(aat_set))
        print("  imp_set  :", sorted(imp_set))

    # -------- Base note values from balances & RES --------
    koncern_ib  = sum(ib.get(a, 0.0) for a in asset_all)
    koncern_ub  = sum(ub.get(a, 0.0) for a in asset_all)
    ack_nedskr_koncern_ib = sum(ib.get(a, 0.0) for a in imp_set)
    ack_nedskr_koncern_ub = sum(ub.get(a, 0.0) for a in imp_set)

    # Årets resultatandel: RES 8030/8240 (income on RES is negative; invert)
    resultatandel_koncern = -(res.get(8030, 0.0) + res.get(8240, 0.0))

    # -------- Voucher parsing for movements (sale vs payout, AAT, fusion, omklass, impairment) --------
    ver_header_re = re.compile(r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"([^"]*)"|(.+)))?$', re.I)
    trans_re = re.compile(
        r'^#(?:BTRANS|RTRANS|TRANS)\s+'
        r'(\d{3,4})'                     # account
        r'(?:\s+\{.*?\})?'               # optional object
        r'\s+(-?(?:\d{1,3}(?:[ \u00A0]?\d{3})*|\d+)(?:[.,]\d+)?)'  # amount
        r'(?:\s+\d{8})?'                 # optional date
        r'(?:\s+".*?")?'                 # optional text
        r'\s*$', re.I
    )

    trans_by_ver: Dict[Tuple[str, int], List[Tuple[int, float]]] = defaultdict(list)
    text_by_ver: Dict[Tuple[str, int], str] = {}
    current_ver: Optional[Tuple[str, int]] = None
    in_block = False

    for raw in lines:
        t = raw.strip()
        mh = ver_header_re.match(t)
        if mh:
            current_ver = (mh.group(1), int(mh.group(2)))
            header_text = (mh.group(4) or mh.group(5) or "")
            text_by_ver[current_ver] = _norm_text(header_text)
            continue
        if t == "{":
            in_block = True
            continue
        if t == "}":
            in_block = False
            current_ver = None
            continue
        if in_block and current_ver:
            mt = trans_re.match(t)
            if mt:
                acct = int(mt.group(1))
                amt = _f(mt.group(2))
                trans_by_ver[current_ver].append((acct, amt))

    # Accumulators
    inkop_koncern = 0.0
    fusion_koncern = 0.0
    aktieagartillskott_lamnad_koncern = 0.0
    aktieagartillskott_aterbetald_koncern = 0.0
    fsg_koncern = 0.0
    omklass_koncern = 0.0

    arets_nedskr_koncern = 0.0
    aterfor_nedskr_koncern = 0.0
    aterfor_nedskr_fsg_koncern = 0.0
    aterfor_nedskr_fusion_koncern = 0.0
    omklass_nedskr_koncern = 0.0

    RES_SHARE_SET = {8030, 8240}

    for key, txs in trans_by_ver.items():
        text = text_by_ver.get(key, "")

        A_ANDEL_D = sum(amt  for a, amt in txs if a in andel_set and amt > 0)
        A_ANDEL_K = sum(-amt for a, amt in txs if a in andel_set and amt < 0)
        A_AAT_D   = sum(amt  for a, amt in txs if a in aat_set   and amt > 0)
        A_AAT_K   = sum(-amt for a, amt in txs if a in aat_set   and amt < 0)
        A_D_total = A_ANDEL_D + A_AAT_D
        A_K_total = A_ANDEL_K + A_AAT_K

        IMP_D = sum(amt  for a, amt in txs if a in imp_set and amt > 0)
        IMP_K = sum(-amt for a, amt in txs if a in imp_set and amt < 0)

        RES_K = sum(-amt for a, amt in txs if a in RES_SHARE_SET and amt < 0)  # |K 8030/8240|
        RES_D = sum(amt  for a, amt in txs if a in RES_SHARE_SET and amt > 0)  # D 8030/8240

        # 1) Result share consumption (priority: share -> AAT)
        res_plus  = min(A_D_total, RES_K) if RES_K > 0 and A_D_total > 0 else 0.0
        res_minus = min(A_K_total, RES_D) if RES_D > 0 and A_K_total > 0 else 0.0
        resultatandel_koncern += (res_plus - res_minus)

        res_plus_left = res_plus
        consume_andel_D = min(A_ANDEL_D, res_plus_left);  res_plus_left -= consume_andel_D
        consume_aat_D   = min(A_AAT_D,   res_plus_left);  res_plus_left -= consume_aat_D

        res_minus_left = res_minus
        consume_andel_K = min(A_ANDEL_K, res_minus_left); res_minus_left -= consume_andel_K
        consume_aat_K   = min(A_AAT_K,   res_minus_left); res_minus_left -= consume_aat_K

        # 2) Purchases/Fusion (residual D on shares); AAT given (residual D on AAT)
        rem_andel_D = max(0.0, A_ANDEL_D - consume_andel_D)
        rem_aat_D   = max(0.0, A_AAT_D   - consume_aat_D)
        if rem_andel_D > 0:
            if "fusion" in text:
                fusion_koncern += rem_andel_D
            else:
                inkop_koncern += rem_andel_D
        if rem_aat_D > 0:
            aktieagartillskott_lamnad_koncern += rem_aat_D

        # 3) Sales vs. payout; AAT repaid
        rem_andel_K = max(0.0, A_ANDEL_K - consume_andel_K)
        rem_aat_K   = max(0.0, A_AAT_K   - consume_aat_K)

        if rem_andel_K > 0:
            # Sale only if THIS voucher has any 822x
            has_sale_pnl = any(a in SALE_PNL for a, _ in txs)

            other_accts = {a for a, _ in txs if a not in andel_set | aat_set | imp_set | RES_SHARE_SET}
            only_banks  = len(other_accts) > 0 and all(1900 <= a <= 1999 for a in other_accts)
            bank_debet  = sum(amt for a, amt in txs if amt > 0 and 1900 <= a <= 1999)

            kw_sale       = any(k in text for k in ("försälj", "avyttr", "sale"))
            kw_settlement = any(k in text for k in ("utbet", "utbetal", "kap andel", "resultatandel", "kb", "hb", "kommandit", "handelsbolag"))

            if has_sale_pnl:
                # Real sale
                if IMP_D > 0:
                    aterfor_nedskr_fsg_koncern += IMP_D
                    IMP_D = 0.0
                fsg_koncern += rem_andel_K
            else:
                is_payout_prior_share = (
                    RES_D == 0 and RES_K == 0 and IMP_D == 0 and IMP_K == 0
                    and only_banks and abs(bank_debet - rem_andel_K) < 0.5
                    and (kw_settlement or not kw_sale)
                )
                if is_payout_prior_share:
                    resultatandel_koncern -= rem_andel_K
                elif kw_sale:
                    fsg_koncern += rem_andel_K
                else:
                    resultatandel_koncern -= rem_andel_K

        if rem_aat_K > 0:
            aktieagartillskott_aterbetald_koncern += rem_aat_K

        # 4) Impairment & reversals (outside sale)
        if IMP_D > 0:
            if "fusion" in text:
                aterfor_nedskr_fusion_koncern += IMP_D
            else:
                aterfor_nedskr_koncern += IMP_D
        if IMP_K > 0:
            arets_nedskr_koncern += IMP_K

        # 5) Omklass (assets & impairment) when no signals
        asset_signals = (RES_K > 0 or RES_D > 0 or IMP_D > 0 or IMP_K > 0)
        if A_D_total > 0 and A_K_total > 0 and not asset_signals:
            omklass_koncern += (A_D_total - A_K_total)

        imp_d_orig = sum(amt  for a, amt in txs if a in imp_set and amt > 0)
        imp_k_orig = sum(-amt for a, amt in txs if a in imp_set and amt < 0)
        if imp_d_orig > 0 and imp_k_orig > 0 and not (A_D_total > 0 or A_K_total > 0 or RES_K > 0 or RES_D > 0):
            omklass_nedskr_koncern += (imp_d_orig - imp_k_orig)

    # -------- UB/Redov värde (signs) --------
    koncern_ub = (
        koncern_ib
        + inkop_koncern
        + fusion_koncern
        + aktieagartillskott_lamnad_koncern
        - fsg_koncern
        - aktieagartillskott_aterbetald_koncern
        + resultatandel_koncern
        + omklass_koncern
    )

    ack_nedskr_koncern_ub = (
        ack_nedskr_koncern_ib
        - arets_nedskr_koncern
        + aterfor_nedskr_koncern
        + aterfor_nedskr_fsg_koncern
        + aterfor_nedskr_fusion_koncern
        + omklass_nedskr_koncern
    )

    # In SIE, ack nedskr is (typically) negative; redovisat värde = UB + ack_nedskr
    red_varde_koncern = koncern_ub + ack_nedskr_koncern_ub

    if debug:
        print("KONCERN NOTE SUMMARY")
        print("  koncern_ib:", koncern_ib)
        print("  koncern_ub:", koncern_ub)
        print("  resultatandel_koncern:", resultatandel_koncern)
        print("  fsg_koncern:", fsg_koncern)
        print("  aat (given/rep):", aktieagartillskott_lamnad_koncern, aktieagartillskott_aterbetald_koncern)
        print("  ack_nedskr (IB/UB):", ack_nedskr_koncern_ib, ack_nedskr_koncern_ub)
        print("  red_varde_koncern:", red_varde_koncern)

    return {
        # Asset movements
        "koncern_ib": koncern_ib,
        "inkop_koncern": inkop_koncern,
        "fusion_koncern": fusion_koncern,
        "aktieagartillskott_lamnad_koncern": aktieagartillskott_lamnad_koncern,
        "aktieagartillskott_aterbetald_koncern": aktieagartillskott_aterbetald_koncern,  # keep as non-breaking
        "fsg_koncern": fsg_koncern,
        "resultatandel_koncern": resultatandel_koncern,
        "omklass_koncern": omklass_koncern,
        "koncern_ub": koncern_ub,

        # Impairment movements
        "ack_nedskr_koncern_ib": ack_nedskr_koncern_ib,
        "arets_nedskr_koncern": arets_nedskr_koncern,
        "aterfor_nedskr_koncern": aterfor_nedskr_koncern,
        "aterfor_nedskr_fsg_koncern": aterfor_nedskr_fsg_koncern,
        "aterfor_nedskr_fusion_koncern": aterfor_nedskr_fusion_koncern,
        "omklass_nedskr_koncern": omklass_nedskr_koncern,
        "ack_nedskr_koncern_ub": ack_nedskr_koncern_ub,

        # Derived
        "red_varde_koncern": red_varde_koncern,
    }