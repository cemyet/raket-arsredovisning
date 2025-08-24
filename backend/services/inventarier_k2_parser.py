import re
from collections import defaultdict

def parse_inventarier_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    INVENTARIER-note (K2) parser.
    
    K2 – Inventarier, verktyg och installationer

    Asset ranges (tillgångskonton):
      • 1220–1227 (inventarier/verktyg m.m.)
      • 1230–1237 (installationer)
      • 1240–1247 (bilar/transport)
      • 1250–1257 (datorer)

    Ackumulerade konton:
      • Ack. avskrivningar: 1229, 1239, 1249, 1259
      • Ack. nedskrivningar: 1228, 1238, 1248, 1258

    Resultat vid avyttring:
      • 3973 (vinst), 7973 (förlust)

    Avskrivningskostnader (för denna not):
      • 7832 (inventarier & verktyg), 7833 (installationer),
        7834 (bilar/transport), 7835 (datorer), 7839 (övriga mask/inv)
      (OBS: 7830/7831 hör till Maskiner-noten enligt vår uppdelning)

    Nedskrivning / återföring:
      • Nedskrivning:  D 7730 + K (1228/1238/1248/1258)
      • Återföring:    K 7780 + D (1228/1238/1248/1258) – om EJ i avyttring
      • Återföring vid avyttring: D på ack. nedskrivning i samma verifikat
    """

    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # --- Parse SRU codes to filter accounts ---
    sru_codes = {}
    sru_re = re.compile(r'^#SRU\s+(\d+)\s+(\d+)\s*$')
    for raw in lines:
        s = raw.strip()
        m = sru_re.match(s)
        if m:
            account = int(m.group(1))
            sru = int(m.group(2))
            sru_codes[account] = sru

    # --- CONFIG (K2 – inventarier) ---
    # Base account ranges for inventarier
    BASE_ASSET_RANGES = [(1220, 1227), (1230, 1237), (1240, 1247), (1250, 1257)]
    BASE_ACC_DEP = {1229, 1239, 1249, 1259}
    BASE_ACC_IMP = {1228, 1238, 1248, 1258}
    
    # Combined logic: Account interval AND SRU code must match
    def belongs_to_inventarier(acct: int) -> bool:
        # Check if account is in inventarier ranges
        in_inventarier_range = any(lo <= acct <= hi for lo, hi in BASE_ASSET_RANGES) or \
                              acct in BASE_ACC_DEP or acct in BASE_ACC_IMP
        
        if not sru_codes:
            # No SRU codes = use original interval logic
            return in_inventarier_range
        
        if acct not in sru_codes:
            # Account has no SRU code = use interval logic
            return in_inventarier_range
        
        account_sru = sru_codes[acct]
        
        # Primary rule: In inventarier range AND SRU = 7215
        if in_inventarier_range and account_sru == 7215:
            return True
        
        # Fallback rule: If in inventarier range but wrong SRU, let SRU decide
        if in_inventarier_range and account_sru != 7215:
            # SRU overrides - this account belongs elsewhere
            return False
        
        # Account not in inventarier range - check if SRU brings it in
        # (This handles cases where accounts outside normal ranges have SRU 7215)
        return account_sru == 7215
    
    # Build filtered account sets
    ASSET_RANGES = []
    for lo, hi in BASE_ASSET_RANGES:
        for acct in range(lo, hi + 1):
            if belongs_to_inventarier(acct):
                ASSET_RANGES.append((acct, acct))
    
    ACC_DEP = {acct for acct in BASE_ACC_DEP if belongs_to_inventarier(acct)}
    ACC_IMP = {acct for acct in BASE_ACC_IMP if belongs_to_inventarier(acct)}
    
    DISPOSAL_PL = {3973, 7973}
    DEPR_COST = {7832, 7833, 7834, 7835, 7839}
    IMPAIR_COST = 7730
    IMPAIR_REV = 7780
    

    # --- Helpers ---
    def in_assets(acct: int) -> bool:
        return any(lo <= acct <= hi for lo, hi in ASSET_RANGES)

    def _to_float(s: str) -> float:
        return float(s.strip().replace(" ", "").replace(",", "."))

    def get_balance(kind_flag: str, accounts):
        total = 0.0
        bal_re = re.compile(rf'^#(?:{kind_flag})\s+0\s+(\d+)\s+(-?[0-9][0-9\s.,]*)(?:\s+.*)?$')
        for raw in lines:
            s = raw.strip()
            m = bal_re.match(s)
            if not m:
                continue
            acct = int(m.group(1))
            amount = _to_float(m.group(2))
            if isinstance(accounts, (set, frozenset)):
                ok = acct in accounts
            else:
                ok = any(lo <= acct <= hi for lo, hi in accounts)
            if ok:
                total += amount
        return total

    # --- Parse vouchers ---
    ver_header_re = re.compile(r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"[^"]*"|.+))?\s*$')
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
    current_ver = None
    in_block = False

    for raw in lines:
        t = raw.strip()
        mh = ver_header_re.match(t)
        if mh:
            current_ver = (mh.group(1), int(mh.group(2)))
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

    # --- IB balances ---
    inventarier_ib = get_balance('IB', ASSET_RANGES)
    ack_avskr_inventarier_ib = get_balance('IB', ACC_DEP)
    ack_nedskr_inventarier_ib = get_balance('IB', ACC_IMP)

    # --- Accumulators ---
    arets_inkop_inventarier = 0.0
    arets_fsg_inventarier = 0.0
    arets_omklass_inventarier = 0.0
    arets_avskr_inventarier = 0.0
    aterfor_avskr_fsg_inventarier = 0.0
    omklass_avskr_inventarier = 0.0
    arets_nedskr_inventarier = 0.0
    aterfor_nedskr_inventarier = 0.0
    aterfor_nedskr_fsg_inventarier = 0.0
    omklass_nedskr_inventarier = 0.0


    # --- Classify vouchers ---
    for key, txs in trans_by_ver.items():
        A_D = sum(amt for a, amt in txs if in_assets(a) and amt > 0)
        A_K = sum(-amt for a, amt in txs if in_assets(a) and amt < 0)
        DEP_D = sum(amt for a, amt in txs if a in ACC_DEP and amt > 0)
        DEP_K = sum(-amt for a, amt in txs if a in ACC_DEP and amt < 0)
        IMP_D = sum(amt for a, amt in txs if a in ACC_IMP and amt > 0)
        IMP_K = sum(-amt for a, amt in txs if a in ACC_IMP and amt < 0)

        has_PL_disposal = any(a in DISPOSAL_PL for a, _ in txs)
        has_depr_cost = any((a in DEPR_COST and amt > 0) for a, amt in txs)
        has_imp_cost = any((a == IMPAIR_COST and amt > 0) for a, amt in txs)
        has_imp_rev = any((a == IMPAIR_REV and amt < 0) for a, amt in txs)

        # Disposal
        is_disposal = (A_K > 0) and (DEP_D > 0 or has_PL_disposal)
        if is_disposal:
            arets_fsg_inventarier += A_K
            aterfor_avskr_fsg_inventarier += DEP_D
            aterfor_nedskr_fsg_inventarier += IMP_D

        # Inköp
        if A_D > 0:
            arets_inkop_inventarier += A_D

        # Depreciations (not in disposal vouchers)
        if DEP_K > 0 and has_depr_cost and not is_disposal:
            arets_avskr_inventarier += DEP_K

        # Impairments
        if has_imp_cost and IMP_K > 0:
            arets_nedskr_inventarier += sum(amt for a, amt in txs if a == IMPAIR_COST and amt > 0)
        if has_imp_rev and IMP_D > 0 and A_K == 0:
            aterfor_nedskr_inventarier += IMP_D

        # Omklass (both D & K asset, no signals)
        signals = (DEP_D + DEP_K + IMP_D + IMP_K) > 0 or has_PL_disposal or has_depr_cost or has_imp_cost or has_imp_rev
        if A_D > 0 and A_K > 0 and not signals:
            arets_omklass_inventarier += (A_D - A_K)

    # --- UB formulas ---
    inventarier_ub = inventarier_ib + arets_inkop_inventarier - arets_fsg_inventarier + arets_omklass_inventarier
    ack_avskr_inventarier_ub = ack_avskr_inventarier_ib + aterfor_avskr_fsg_inventarier - arets_avskr_inventarier
    ack_nedskr_inventarier_ub = ack_nedskr_inventarier_ib + aterfor_nedskr_fsg_inventarier + aterfor_nedskr_inventarier - arets_nedskr_inventarier

    # --- Derived ---
    red_varde_inventarier = inventarier_ub + ack_avskr_inventarier_ub + ack_nedskr_inventarier_ub

    return {
        "inventarier_ib": inventarier_ib,
        "arets_inkop_inventarier": arets_inkop_inventarier,
        "arets_fsg_inventarier": arets_fsg_inventarier,
        "arets_omklass_inventarier": arets_omklass_inventarier,
        "inventarier_ub": inventarier_ub,
        "ack_avskr_inventarier_ib": ack_avskr_inventarier_ib,
        "aterfor_avskr_fsg_inventarier": aterfor_avskr_fsg_inventarier,
        "omklass_avskr_inventarier": omklass_avskr_inventarier,
        "arets_avskr_inventarier": arets_avskr_inventarier,
        "ack_avskr_inventarier_ub": ack_avskr_inventarier_ub,
        "ack_nedskr_inventarier_ib": ack_nedskr_inventarier_ib,
        "arets_nedskr_inventarier": arets_nedskr_inventarier,
        "aterfor_nedskr_inventarier": aterfor_nedskr_inventarier,
        "aterfor_nedskr_fsg_inventarier": aterfor_nedskr_fsg_inventarier,
        "omklass_nedskr_inventarier": omklass_nedskr_inventarier,
        "ack_nedskr_inventarier_ub": ack_nedskr_inventarier_ub,
        "red_varde_inventarier": red_varde_inventarier,
    }
