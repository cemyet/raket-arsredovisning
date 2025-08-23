import re
from collections import defaultdict

def parse_bygg_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    BYGG-note (K2) parser.

    Handles:
      - #VER with/without quoted titles; extra tokens after date.
      - #TRANS/#BTRANS/#RTRANS with or without "{}", optional date and trailing text.
      - IB/UB numbers with thousand spaces and commas (e.g. "-58 216 440,00").

    K2 business rules:
      • Uppskrivning (revaluation):          D building asset + K 2085
      • Depreciation on revaluation:         K 1119/1159 + D 2085
      • Ordinary depreciation:               K 1119/1159 + D 7820/7821/7824/7829 (and no D 2085)
      • Disposal:                            K building asset AND (D 1119/1159 OR 3972/7972 OR D 2085)
      • Nedskrivning (impairment):           D 7720 + K 1158
        Återföring (no disposal):            K 7770 + D 1158
        Återföring at disposal:              D 1158 within a disposal voucher
      • Inköp vs uppskrivning split per voucher:
            uppskr_del  = min(D asset, K 2085)
            inköp_del   = max(0, D asset - uppskr_del)

    Returns dict with:
      bygg_ib, arets_inkop_bygg, arets_fsg_bygg, arets_omklass_bygg, bygg_ub,
      ack_avskr_bygg_ib, aterfor_avskr_fsg_bygg, arets_avskr_bygg, ack_avskr_bygg_ub,
      ack_uppskr_bygg_ib, arets_uppskr_bygg, arets_avskr_uppskr_bygg, aterfor_uppskr_fsg_bygg, ack_uppskr_bygg_ub,
      ack_nedskr_bygg_ib, arets_nedskr_bygg, aterfor_nedskr_bygg, aterfor_nedskr_fsg_bygg, ack_nedskr_bygg_ub
    """
    # Normalize whitespace and NBSP so numbers like "58 216 440,00" parse
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # --- Parse SRU codes to include additional accounts ---
    sru_codes = {}
    sru_re = re.compile(r'^#SRU\s+(\d+)\s+(\d+)\s*$')
    for raw in lines:
        s = raw.strip()
        m = sru_re.match(s)
        if m:
            account = int(m.group(1))
            sru = int(m.group(2))
            sru_codes[account] = sru
            if debug:
                print(f"DEBUG BYGG: Found SRU {account} -> {sru}")

    # --- CONFIG (K2 – bygg/mark) ---
    # Base building asset ranges
    BASE_BUILDING_ASSET_RANGES = [(1110,1117),(1130,1139),(1140,1149),(1150,1157),(1180,1189)]
    BASE_ACC_DEP_BYGG = {1119, 1159}
    BASE_ACC_IMP_BYGG = {1158}
    
    # Combined logic: Account interval AND SRU code must match, OR SRU overrides
    def belongs_to_bygg(acct: int) -> bool:
        # Check if account is in standard bygg ranges
        in_bygg_range = any(lo <= acct <= hi for lo, hi in BASE_BUILDING_ASSET_RANGES) or \
                       acct in BASE_ACC_DEP_BYGG or acct in BASE_ACC_IMP_BYGG
        
        if not sru_codes:
            # No SRU codes = use original interval logic
            return in_bygg_range
        
        if acct not in sru_codes:
            # Account has no SRU code = use interval logic
            return in_bygg_range
        
        account_sru = sru_codes[acct]
        
        # Primary rule: In bygg range AND SRU = 7214
        if in_bygg_range and account_sru == 7214:
            return True
        
        # Fallback rule: If in bygg range but wrong SRU, let SRU decide
        if in_bygg_range and account_sru != 7214:
            # SRU overrides - this account belongs elsewhere (shouldn't happen for standard bygg accounts)
            return False
        
        # Account not in bygg range - check if SRU brings it in
        # This handles cases like 1222 (byggnadsinventarier) with SRU 7214
        return account_sru == 7214
    
    # Build account sets with combined logic
    BUILDING_ASSET_RANGES = list(BASE_BUILDING_ASSET_RANGES)  # Start with base ranges
    ACC_DEP_BYGG = set(BASE_ACC_DEP_BYGG)  # Start with base depreciation accounts
    ACC_IMP_BYGG = set(BASE_ACC_IMP_BYGG)  # Start with base impairment accounts
    
    # Add accounts that belong to bygg based on combined logic
    if sru_codes:
        for account, sru in sru_codes.items():
            if belongs_to_bygg(account) and account not in [acct for lo, hi in BASE_BUILDING_ASSET_RANGES for acct in range(lo, hi+1)] and \
               account not in BASE_ACC_DEP_BYGG and account not in BASE_ACC_IMP_BYGG:
                # This is an additional account brought in by SRU
                account_str = str(account)
                last_digit = int(account_str[-1])
                
                if last_digit == 8:  # Pattern: xxx8 = Ack nedskrivningar
                    ACC_IMP_BYGG.add(account)
                    if debug:
                        print(f"DEBUG BYGG: Adding SRU 7214 account {account} as impairment account")
                elif last_digit == 9:  # Pattern: xxx9 = Ack avskrivningar  
                    ACC_DEP_BYGG.add(account)
                    if debug:
                        print(f"DEBUG BYGG: Adding SRU 7214 account {account} as depreciation account")
                elif last_digit == 4:  # Pattern: xxx4 = Ack avskrivningar (like 1224)
                    ACC_DEP_BYGG.add(account)
                    if debug:
                        print(f"DEBUG BYGG: Adding SRU 7214 account {account} as depreciation account")
                else:  # Asset account
                    BUILDING_ASSET_RANGES.append((account, account))
                    if debug:
                        print(f"DEBUG BYGG: Adding SRU 7214 account {account} as building asset")
    
    UPSKR_FOND = 2085
    DISPOSAL_PL = {3972, 7972}
    DEPR_COST = {7820, 7821, 7824, 7829}
    IMPAIR_COST = 7720
    IMPAIR_REV  = 7770
    
    if debug:
        print(f"DEBUG BYGG: Final building asset ranges: {BUILDING_ASSET_RANGES}")
        print(f"DEBUG BYGG: Final depreciation accounts: {ACC_DEP_BYGG}")
        print(f"DEBUG BYGG: Final impairment accounts: {ACC_IMP_BYGG}")

    # --- Helpers ---
    def in_building_assets(acct: int) -> bool:
        return any(lo <= acct <= hi for lo,hi in BUILDING_ASSET_RANGES)

    def _to_float(s: str) -> float:
        # tolerant for "123 456,78" and "123,456.78"
        return float(s.strip().replace(" ", "").replace(",", "."))

    def get_balance(kind_flag: str, accounts):
        """Sum #IB or #UB for the given account set/ranges (current year '0' rows)."""
        total = 0.0
        # allow thousand spaces; allow optional trailing text after number
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
                ok = any(lo <= acct <= hi for lo,hi in accounts)
            if ok:
                total += amount
        return total

    # --- Parse vouchers ---
    ver_header_re = re.compile(
        r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"[^"]*"|.+))?\s*$'
    )
    trans_re = re.compile(
        r'^#(?:BTRANS|RTRANS|TRANS)\s+'
        r'(\d{3,4})'                            
        r'(?:\s+\{.*?\})?'                      
        r'\s+(-?(?:\d{1,3}(?:[ \u00A0]?\d{3})*|\d+)(?:[.,]\d+)?)'  # amount only
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
    bygg_ib               = get_balance('IB', BUILDING_ASSET_RANGES)  # asset (incl. uppskrivning since posted on asset)
    ack_avskr_bygg_ib     = get_balance('IB', ACC_DEP_BYGG)
    ack_nedskr_bygg_ib    = get_balance('IB', ACC_IMP_BYGG)
    ack_uppskr_bygg_ib    = get_balance('IB', {UPSKR_FOND})           # IB on 2085 (can be negative/credit)

    # --- Accumulators ---
    arets_inkop_bygg           = 0.0
    arets_fsg_bygg             = 0.0
    arets_omklass_bygg         = 0.0

    arets_avskr_bygg           = 0.0
    aterfor_avskr_fsg_bygg     = 0.0

    arets_uppskr_bygg          = 0.0
    arets_avskr_uppskr_bygg    = 0.0
    aterfor_uppskr_fsg_bygg    = 0.0

    arets_nedskr_bygg          = 0.0
    aterfor_nedskr_bygg        = 0.0
    aterfor_nedskr_fsg_bygg    = 0.0

    if debug:
        print(f"DEBUG K2: vouchers parsed = {len(trans_by_ver)} (sample: {list(trans_by_ver)[:5]})")
        # Debug: Look for the specific voucher A 312
        if ('A', 312) in trans_by_ver:
            print(f"DEBUG K2: Found voucher A 312: {trans_by_ver[('A', 312)]}")
        else:
            print(f"DEBUG K2: Voucher A 312 not found. Available vouchers: {list(trans_by_ver.keys())[:5]}...")

    # --- Per voucher classification ---
    for key, txs in trans_by_ver.items():
        # Debug depreciation vouchers
        if debug and (any(a in ACC_DEP_BYGG for a,_ in txs) or any(a in DEPR_COST for a,_ in txs)):
            print(f"DEBUG K2: Checking voucher {key} with transactions: {txs}")
        # Aggregate per voucher
        A_D  = sum(amt for a,amt in txs if in_building_assets(a) and amt > 0)     # Debet asset
        A_K  = sum(-amt for a,amt in txs if in_building_assets(a) and amt < 0)    # Kredit asset (abs)
        F2085_D = sum(amt for a,amt in txs if a == UPSKR_FOND and amt > 0)        # Debet 2085
        F2085_K = sum(-amt for a,amt in txs if a == UPSKR_FOND and amt < 0)       # Kredit 2085
        DEP_D = sum(amt for a,amt in txs if a in ACC_DEP_BYGG and amt > 0)        # Debet 1119/1159
        DEP_K = sum(-amt for a,amt in txs if a in ACC_DEP_BYGG and amt < 0)       # Kredit 1119/1159
        IMP_D = sum(amt for a,amt in txs if a in ACC_IMP_BYGG and amt > 0)        # Debet 1158
        IMP_K = sum(-amt for a,amt in txs if a in ACC_IMP_BYGG and amt < 0)       # Kredit 1158
        has_PL_disposal = any(a in DISPOSAL_PL for a,_ in txs)
        has_depr_cost = any((a in DEPR_COST and amt > 0) for a,amt in txs)
        has_imp_cost  = any((a == IMPAIR_COST and amt > 0) for a,amt in txs)
        has_imp_rev   = any((a == IMPAIR_REV  and amt < 0) for a,amt in txs)

        # 1) Disposal
        is_disposal = (A_K > 0) and (DEP_D > 0 or has_PL_disposal or F2085_D > 0)
        if is_disposal:
            arets_fsg_bygg         += A_K
            aterfor_avskr_fsg_bygg += DEP_D
            aterfor_uppskr_fsg_bygg+= F2085_D
            aterfor_nedskr_fsg_bygg+= IMP_D

        # 2) Split D asset into uppskrivning vs inköp
        uppskr_amount = min(A_D, F2085_K)  # part of D asset backed by K 2085
        if uppskr_amount > 0:
            arets_uppskr_bygg += uppskr_amount

        inkop_amount = max(0.0, A_D - uppskr_amount)
        if inkop_amount > 0:
            arets_inkop_bygg += inkop_amount

        # 3) Depreciations
        #    a) Depreciation on revaluation (K 1119/1159 + D 2085)
        if DEP_K > 0 and F2085_D > 0:
            inc = min(DEP_K, F2085_D)
            arets_avskr_uppskr_bygg += inc
            if debug:
                print(f"DEBUG {key}: avskr uppskr += {inc} (DEP_K={DEP_K}, F2085_D={F2085_D})")

        #    b) Ordinary depreciation (K 1119/1159 + D 78xx, but no D 2085)
        if DEP_K > 0 and has_depr_cost and F2085_D == 0:
            arets_avskr_bygg += DEP_K
            if debug:
                print(f"DEBUG {key}: avskr ord += {DEP_K}")

        # 4) Impairments (non-disposal)
        if has_imp_cost and IMP_K > 0:
            arets_nedskr_bygg += sum(amt for a,amt in txs if a == IMPAIR_COST and amt > 0)
        if has_imp_rev and IMP_D > 0 and A_K == 0:
            aterfor_nedskr_bygg += IMP_D

        # 5) Omklass (both D & K asset, no signals)
        signals = (F2085_D+F2085_K+DEP_D+DEP_K+IMP_D+IMP_K) > 0 or has_PL_disposal or has_depr_cost or has_imp_cost or has_imp_rev
        if A_D > 0 and A_K > 0 and not signals:
            arets_omklass_bygg += (A_D - A_K)

    # --- UB formulas ---
    bygg_ub = bygg_ib + arets_inkop_bygg - arets_fsg_bygg + arets_omklass_bygg

    ack_avskr_bygg_ub = (
        ack_avskr_bygg_ib
      + aterfor_avskr_fsg_bygg
      - arets_avskr_bygg
    )

    ack_uppskr_bygg_ub = (
        ack_uppskr_bygg_ib       # IB on 2085 (credit balance shows as negative)
      + arets_uppskr_bygg
      - arets_avskr_uppskr_bygg
      - aterfor_uppskr_fsg_bygg
    )

    ack_nedskr_bygg_ub = (
        ack_nedskr_bygg_ib
      + aterfor_nedskr_fsg_bygg
      + aterfor_nedskr_bygg
      - arets_nedskr_bygg
    )

    # --- Derived calculations ---
    red_varde_bygg = bygg_ub + ack_avskr_bygg_ub + ack_nedskr_bygg_ub + ack_uppskr_bygg_ub  # Book value

    return {
        # IB/UB assets
        "bygg_ib": bygg_ib,
        "arets_inkop_bygg": arets_inkop_bygg,
        "arets_fsg_bygg": arets_fsg_bygg,
        "arets_omklass_bygg": arets_omklass_bygg,
        "bygg_ub": bygg_ub,

        # Depreciations (historical cost)
        "ack_avskr_bygg_ib": ack_avskr_bygg_ib,
        "aterfor_avskr_fsg_bygg": aterfor_avskr_fsg_bygg,
        "arets_avskr_bygg": arets_avskr_bygg,
        "ack_avskr_bygg_ub": ack_avskr_bygg_ub,

        # Revaluations (via 2085)
        "ack_uppskr_bygg_ib": ack_uppskr_bygg_ib,
        "arets_uppskr_bygg": arets_uppskr_bygg,
        "arets_avskr_uppskr_bygg": arets_avskr_uppskr_bygg,
        "aterfor_uppskr_fsg_bygg": aterfor_uppskr_fsg_bygg,
        "ack_uppskr_bygg_ub": ack_uppskr_bygg_ub,

        # Impairments
        "ack_nedskr_bygg_ib": ack_nedskr_bygg_ib,
        "arets_nedskr_bygg": arets_nedskr_bygg,
        "aterfor_nedskr_bygg": aterfor_nedskr_bygg,
        "aterfor_nedskr_fsg_bygg": aterfor_nedskr_fsg_bygg,
        "ack_nedskr_bygg_ub": ack_nedskr_bygg_ub,

        # Derived book value
        "red_varde_bygg": red_varde_bygg,
    }
