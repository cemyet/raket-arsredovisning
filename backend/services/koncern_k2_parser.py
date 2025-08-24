import re
import unicodedata
from collections import defaultdict

# ---- Regex patterns for precise matching ----
ACK_IMP_PAT = re.compile(r'\b(?:ack(?:[.\s]*nedskr\w*)|ackum\w*|nedskriv\w*)\b', re.IGNORECASE)
FORDR_PAT   = re.compile(r'\b(fordran|fordringar|lan|lån|ranta|ränta|amort|avbetal)\b', re.IGNORECASE)

# ---- Sale P&L accounts for distinguishing real sales from cash settlements ----
SALE_PNL = tuple(range(8220, 8230))  # resultat vid försäljning av andelar (BAS 822x)

def parse_koncern_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    KONCERN-note (K2) parser — enhanced with dynamic account classification and HB/KB flow handling.

    ENHANCEMENTS:
    1. Dynamic account classification via account text (#KONTO):
       • Capture custom AAT/Share accounts within 1310–1318
       • Rescue misplaced AAT/Shares within 1320–1329 (without receivables keywords)
       • EXCLUDE all receivables completely from parser

    2. HB/KB two-step flow handling:
       • Distinguishes real sales (with 822x P&L accounts) from cash settlements
       • Prevents false "sales" for partnership result share payouts
       • Handles common pattern: D 1930 / K 1311 (payout) + D 1311 / K 8030|8240 (year-end share)
       • Supports both 8030 (dotterföretag) and 8240 (other companies) result accounts

    Key principles:
      - IB/UB for 'koncern_ib', 'koncern_ub' includes both Share and AAT accounts (as acquisition value)
      - Purchase/Sale calculations only from Share accounts (not AAT)
      - AAT given/repaid calculated only from AAT accounts (not via text signal)
      - Sales require 822x P&L accounts OR explicit sale keywords
      - Cash settlements (K 131x + only banks, no 822x) treated as negative resultatandel
      - Result shares handled via 8030 (dotterföretag) or 8240 (other companies)
      - Accumulated impairment of shares (1318 and possibly other 131x with acc/impair text) included
      - 132x used ONLY if account text clearly indicates Shares or AAT AND lacks receivables keywords

    Unchanged keys:
      koncern_ib, inkop_koncern, fusion_koncern, aktieagartillskott_lamnad_koncern,
      fsg_koncern, resultatandel_koncern, omklass_koncern, koncern_ub,
      ack_nedskr_koncern_ib, arets_nedskr_koncern, aterfor_nedskr_koncern,
      aterfor_nedskr_fsg_koncern, aterfor_nedskr_fusion_koncern, omklass_nedskr_koncern,
      ack_nedskr_koncern_ub, red_varde_koncern

    New key (non-breaking):
      aktieagartillskott_aterbetald_koncern
    """

    # ---------- Utils ----------
    def _normalize(s: str) -> str:
        if not s:
            return ""
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = s.lower().replace("\u00a0", " ").replace("\t", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _to_float(s: str) -> float:
        # tolerant for "123 456,78" and "123,456.78"
        return float(s.strip().replace(" ", "").replace(",", "."))

    def _has(text: str, *subs) -> bool:
        return any(sub in text for sub in subs)

    # ---------- Pre-normalize SIE text ----------
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # ---------- Read #KONTO (account names) & #SRU ----------
    konto_name = {}   # acct -> normalized name
    sru_codes = {}    # acct -> sru

    konto_re = re.compile(r'^#KONTO\s+(\d+)\s+"([^"]*)"\s*$')
    sru_re   = re.compile(r'^#SRU\s+(\d+)\s+(\d+)\s*$')

    for raw in lines:
        s = raw.strip()
        mk = konto_re.match(s)
        if mk:
            acct = int(mk.group(1))
            name = _normalize(mk.group(2))
            konto_name[acct] = name
            continue
        ms = sru_re.match(s)
        if ms:
            account = int(ms.group(1))
            sru = int(ms.group(2))
            sru_codes[account] = sru

    # ---------- Classify accounts (dynamic sets) ----------
    # Scope: 1310–1318 primarily; 1320–1329 only if text says Shares/AAT and not receivables
    def is_fordrings_text(t: str) -> bool:
        return bool(FORDR_PAT.search(t))

    def is_aat_text(t: str) -> bool:
        return any(w in t for w in ("aktieagartillskott", "aktieägartillskott", "villkorat", "ovillkorat"))

    def is_andelar_koncern_text(t: str) -> bool:
        # kräver både koncern/dotter OCH andel/aktie
        return (any(w in t for w in ("koncern", "koncernforetag", "koncernföretag", "dotter", "subsidiary"))
                and any(w in t for w in ("andel", "andelar", "aktie", "aktier")))

    def is_ack_ned_andelar_text(t: str) -> bool:
        # Viktigt: träffar INTE på "Holtback" längre
        return bool(ACK_IMP_PAT.search(t))

    # Start with fixed intervals
    base_andel_range = set(a for a in range(1310, 1318+1))
    base_imp_set = {1318}

    andel_set = set()    # accounts representing shares in koncern
    aat_set   = set()    # accounts representing AAT in koncern
    imp_set   = set()    # acc impairment shares (primarily 1318, possibly others with clear text)

    # 1) 1310–1318
    for acct in range(1310, 1318+1):
        t = konto_name.get(acct, "")
        if acct == 1318:
            imp_set.add(acct)
            continue
        # Exclude if text seems to describe receivables (edge case)
        if t and is_fordrings_text(t):
            continue
        if t and is_aat_text(t):
            aat_set.add(acct)
        else:
            andel_set.add(acct)

    # 2) 1320–1329 (only with clear shares/AAT text and NOT receivables)
    for acct in range(1320, 1329+1):
        t = konto_name.get(acct, "")
        if not t:
            continue
        if is_fordrings_text(t):
            continue
        if is_aat_text(t):
            aat_set.add(acct)
        elif is_andelar_koncern_text(t):
            andel_set.add(acct)
        # acc-impair in 132x interpreted as receivables-related — left out

    # 3) Capture possibly misplaced acc impairment shares in 131x via text
    for acct in range(1310, 1317+1):
        if acct == 1318:
            continue
        t = konto_name.get(acct, "")
        if t and is_ack_ned_andelar_text(t):
            imp_set.add(acct)       # endast om NEDSKR/ACKUM finns i texten

    # Asset universe used in resultatandel/omklass heuristics etc.
    asset_all_set = andel_set | aat_set

    # ---------- Helpers with dynamic sets ----------
    def get_balance(kind_flag: str, accounts) -> float:
        """Sum #IB or #UB for the given account set/ranges (current year '0' rows)."""
        if not accounts:
            return 0.0
        acct_set = set(accounts)
        total = 0.0
        bal_re = re.compile(rf'^#(?:{kind_flag})\s+0\s+(\d+)\s+(-?[0-9][0-9\s.,]*)(?:\s+.*)?$')
        for raw in lines:
            s = raw.strip()
            m = bal_re.match(s)
            if not m:
                continue
            acct = int(m.group(1))
            if acct in acct_set:
                amount = _to_float(m.group(2))
                total += amount
        return total

    # --- Parse vouchers with text extraction (original) ---
    ver_header_re = re.compile(
        r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"([^"]*)"|(.+)))?\s*$'
    )
    trans_re = re.compile(
        r'^#(?:BTRANS|RTRANS|TRANS)\s+'
        r'(\d{3,4})'
        r'(?:\s+\{.*?\})?'
        r'\s+(-?(?:\d{1,3}(?:[ \u00A0]?\d{3})*|\d+)(?:[.,]\d+)?)'
        r'(?:\s+\d{8})?'
        r'(?:\s+".*?")?'
        r'\s*$'
    )

    trans_by_ver = defaultdict(list)
    text_by_ver = {}
    current_ver = None
    in_block = False

    for raw in lines:
        t = raw.strip()
        mh = ver_header_re.match(t)
        if mh:
            current_ver = (mh.group(1), int(mh.group(2)))
            voucher_text = mh.group(4) or mh.group(5) or ""
            text_by_ver[current_ver] = _normalize(voucher_text)
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
                amt = _to_float(mt.group(2))
                trans_by_ver[current_ver].append((acct, amt))

    # ---------- IB balances (dynamic sets) ----------
    koncern_ib = get_balance('IB', asset_all_set)
    ack_nedskr_koncern_ib = get_balance('IB', imp_set)

    # Debug output for impairment account classification
    if debug:
        debug_imp_ib = {}
        for raw in lines:
            m = re.match(r'^#IB\s+0\s+(\d+)\s+(-?[0-9][0-9\s.,]*)', raw.strip())
            if m:
                acct = int(m.group(1))
                if acct in imp_set:
                    val = float(m.group(2).replace(" ", "").replace(",", "."))
                    debug_imp_ib[acct] = val
        print(f"DEBUG KONCERN: Impairment accounts (imp_set): {sorted(imp_set)}")
        print(f"DEBUG KONCERN: IB values for impairment accounts: {debug_imp_ib}")
        print(f"DEBUG KONCERN: Total ack_nedskr_koncern_ib: {ack_nedskr_koncern_ib}")

    # ---------- Accumulators ----------
    resultatandel_koncern = 0.0
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

    # --- CONFIG: Result share accounts for different ownership structures ---
    STRICT_GROUP_RESULT = False  # True => require 8030 only (pure group companies)
    RES_SHARE_SET = {8030, 8240} if not STRICT_GROUP_RESULT else {8030}
    # 8030 = Dotterföretag (group-owned HB/KB)
    # 8240 = Other companies (external partnerships)

    # ---------- per voucher classification ----------
    for key, txs in trans_by_ver.items():
        text = text_by_ver.get(key, "")

        # Set sums per class
        A_ANDEL_D = sum(amt  for a,amt in txs if a in andel_set     and amt > 0)
        A_ANDEL_K = sum(-amt for a,amt in txs if a in andel_set     and amt < 0)
        A_AAT_D   = sum(amt  for a,amt in txs if a in aat_set       and amt > 0)
        A_AAT_K   = sum(-amt for a,amt in txs if a in aat_set       and amt < 0)
        A_D_total = A_ANDEL_D + A_AAT_D
        A_K_total = A_ANDEL_K + A_AAT_K

        IMP_D = sum(amt  for a,amt in txs if a in imp_set and amt > 0)    # D1318 (+ possibly other 131x w. acc/impair)
        IMP_K = sum(-amt for a,amt in txs if a in imp_set and amt < 0)    # |K1318|

        RES_K = sum(-amt for a,amt in txs if a in RES_SHARE_SET and amt < 0)  # |K 8030/8240|
        RES_D = sum(amt  for a,amt in txs if a in RES_SHARE_SET and amt > 0)  # D 8030/8240

        # 1) Resultatandel, first consume on Share side, then AAT if needed
        res_plus  = min(A_D_total, RES_K) if RES_K > 0 and A_D_total > 0 else 0.0
        res_minus = min(A_K_total, RES_D) if RES_D > 0 and A_K_total > 0 else 0.0
        resultatandel_koncern += (res_plus - res_minus)

        # Allocate res_plus against D sides in priority order: Share -> AAT
        res_plus_left = res_plus
        consume_andel_D = min(A_ANDEL_D, res_plus_left);  res_plus_left -= consume_andel_D
        consume_aat_D   = min(A_AAT_D,   res_plus_left);  res_plus_left -= consume_aat_D

        # Allocate res_minus against K sides in priority order: Share -> AAT
        res_minus_left = res_minus
        consume_andel_K = min(A_ANDEL_K, res_minus_left); res_minus_left -= consume_andel_K
        consume_aat_K   = min(A_AAT_K,   res_minus_left); res_minus_left -= consume_aat_K

        # 2) Purchase/Fusion = remaining D on SHARE accounts (AAT-D goes to AAT given)
        rem_andel_D = max(0.0, A_ANDEL_D - consume_andel_D)
        rem_aat_D   = max(0.0, A_AAT_D   - consume_aat_D)

        if rem_andel_D > 0:
            if "fusion" in text:
                fusion_koncern += rem_andel_D
            else:
                inkop_koncern += rem_andel_D

        if rem_aat_D > 0:
            # ONLY AAT accounts count as AAT given
            aktieagartillskott_lamnad_koncern += rem_aat_D

        # 3) Sale/AAT-repayment = remaining K on respective class
        rem_andel_K = max(0.0, A_ANDEL_K - consume_andel_K)
        rem_aat_K   = max(0.0, A_AAT_K   - consume_aat_K)

        if rem_andel_K > 0:
            # Check for sale P&L accounts to distinguish real sales from cash settlements
            has_sale_pnl = any(a in SALE_PNL for a,_ in txs)
            
            # Analyze other accounts (not shares, AAT, impairment, or result share)
            other_accts = {a for a,_ in txs if a not in andel_set and a not in aat_set and a not in imp_set and a not in RES_SHARE_SET}
            only_banks  = len(other_accts) > 0 and all(1900 <= a <= 1999 for a in other_accts)
            bank_debet  = sum(amt for a,amt in txs if amt > 0 and 1900 <= a <= 1999)
            
            # Text analysis for transaction type
            kw_sale      = any(k in text for k in ("försälj", "avyttr", "sale"))
            kw_settlement= any(k in text for k in ("utbet", "utbetal", "kap andel", "resultatandel", "kb", "hb", "kommandit", "handelsbolag"))
            
            if has_sale_pnl:
                # ✅ Real sale (requires 822x P&L account)
                if IMP_D > 0:
                    aterfor_nedskr_fsg_koncern += IMP_D
                    IMP_D = 0.0
                fsg_koncern += rem_andel_K
            else:
                # No 822x – likely cash settlement of prior year result share
                is_payout_prior_share = (
                    RES_D == 0 and RES_K == 0 and IMP_D == 0 and IMP_K == 0
                    and only_banks and abs(bank_debet - rem_andel_K) < 0.5
                    and (kw_settlement or not kw_sale)
                )
                if is_payout_prior_share:
                    # Book as negative result share instead of sale
                    resultatandel_koncern -= rem_andel_K
                elif kw_sale:
                    # Optional fallback: text says sale despite missing 822x
                    fsg_koncern += rem_andel_K
                else:
                    # Default: treat as cash settlement (same as above)
                    resultatandel_koncern -= rem_andel_K

        if rem_aat_K > 0:
            # ONLY AAT accounts count as AAT repaid
            aktieagartillskott_aterbetald_koncern += rem_aat_K

        # 4) Reversal/Impairment (not bound to sale)
        if IMP_D > 0:
            if "fusion" in text:
                aterfor_nedskr_fusion_koncern += IMP_D
            else:
                aterfor_nedskr_koncern += IMP_D
        if IMP_K > 0:
            arets_nedskr_koncern += IMP_K

        # 5) Reclassification (asset and acc impairment) without signals — now with dynamic asset_all_set
        asset_signals = (RES_K > 0 or RES_D > 0 or IMP_D > 0 or IMP_K > 0)
        if A_D_total > 0 and A_K_total > 0 and not asset_signals:
            omklass_koncern += (A_D_total - A_K_total)

        # Reclassification for impairment separate
        imp_d_orig = sum(amt  for a,amt in txs if a in imp_set and amt > 0)
        imp_k_orig = sum(-amt for a,amt in txs if a in imp_set and amt < 0)
        if imp_d_orig > 0 and imp_k_orig > 0 and not (A_D_total > 0 or A_K_total > 0 or RES_K > 0 or RES_D > 0):
            omklass_nedskr_koncern += (imp_d_orig - imp_k_orig)

    # ---------- UB formulas (updated for AAT repayment) ----------
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

    red_varde_koncern = koncern_ub + ack_nedskr_koncern_ub

    # ---------- Return (same + 1 key) ----------
    return {
        # Asset movements
        "koncern_ib": koncern_ib,
        "inkop_koncern": inkop_koncern,
        "fusion_koncern": fusion_koncern,
        "aktieagartillskott_lamnad_koncern": aktieagartillskott_lamnad_koncern,
        "aktieagartillskott_aterbetald_koncern": aktieagartillskott_aterbetald_koncern,  # NEW (non-breaking)
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
