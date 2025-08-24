import re
from collections import defaultdict

def parse_ovriga_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    ÖVRIGA-note (K2) parser for Övriga materiella anläggningstillgångar.

    Handles:
      - #VER with/without quoted titles; extra tokens after date.
      - #TRANS/#BTRANS/#RTRANS with or without "{}", optional date and trailing text.
      - IB/UB numbers with thousand spaces and commas (e.g. "-58 216 440,00").

    K2 business rules for Övriga materiella anläggningstillgångar (1290–1297):
      • Asset accounts: 1290-1297
      • Accumulated depreciation: 1299
      • Accumulated impairment: 1298
      • Depreciation cost: 7839
      • Disposal P&L: 3973/7973
      • Impairment cost: 7730
      • Impairment reversal: 7780

    Returns dict with:
      ovriga_ib, arets_inkop_ovriga, arets_fsg_ovriga, arets_omklass_ovriga, ovriga_ub,
      ack_avskr_ovriga_ib, aterfor_avskr_fsg_ovriga, arets_avskr_ovriga, ack_avskr_ovriga_ub,
      ack_nedskr_ovriga_ib, arets_nedskr_ovriga, aterfor_nedskr_ovriga, aterfor_nedskr_fsg_ovriga, ack_nedskr_ovriga_ub,
      red_varde_ovriga
    """
    # Normalize whitespace and NBSP so numbers like "58 216 440,00" parse
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # --- Parse SRU codes and account descriptions ---
    sru_codes = {}
    account_descriptions = {}
    
    sru_re = re.compile(r'^#SRU\s+(\d+)\s+(\d+)\s*$')
    konto_re = re.compile(r'^#KONTO\s+(\d+)\s+"([^"]*)"')
    
    for raw in lines:
        s = raw.strip()
        # Parse SRU codes
        m = sru_re.match(s)
        if m:
            account = int(m.group(1))
            sru = int(m.group(2))
            sru_codes[account] = sru
        
        # Parse account descriptions
        m = konto_re.match(s)
        if m:
            account = int(m.group(1))
            description = m.group(2)
            account_descriptions[account] = description

    # --- CONFIG (K2 – övriga materiella anläggningstillgångar) ---
    # Use original base logic - no SRU integration here
    ASSET_RANGES = [(1290, 1297)]
    ACC_DEP_OVRIGA = {1299}
    ACC_IMP_OVRIGA = {1298}
    
    DISPOSAL_PL = {3973, 7973}
    DEPR_COST = {7839}
    IMPAIR_COST = 7730
    IMPAIR_REV = 7780
    

    # --- Helpers ---
    def in_ovriga_assets(acct: int) -> bool:
        return any(lo <= acct <= hi for lo, hi in ASSET_RANGES)

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
                ok = any(lo <= acct <= hi for lo, hi in accounts)
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
    ovriga_ib = get_balance('IB', ASSET_RANGES)
    ack_avskr_ovriga_ib = get_balance('IB', ACC_DEP_OVRIGA)
    ack_nedskr_ovriga_ib = get_balance('IB', ACC_IMP_OVRIGA)

    # --- Accumulators ---
    arets_inkop_ovriga = 0.0
    arets_fsg_ovriga = 0.0
    arets_omklass_ovriga = 0.0

    arets_avskr_ovriga = 0.0
    aterfor_avskr_fsg_ovriga = 0.0

    arets_nedskr_ovriga = 0.0
    aterfor_nedskr_fsg_ovriga = 0.0
    aterfor_nedskr_ovriga = 0.0


    # --- Per voucher classification ---
    for key, txs in trans_by_ver.items():
        # Aggregate per voucher
        A_D = sum(amt for a, amt in txs if in_ovriga_assets(a) and amt > 0)     # Debet asset
        A_K = sum(-amt for a, amt in txs if in_ovriga_assets(a) and amt < 0)    # Kredit asset (abs)
        DEP_D = sum(amt for a, amt in txs if a in ACC_DEP_OVRIGA and amt > 0)   # Debet 1299
        DEP_K = sum(-amt for a, amt in txs if a in ACC_DEP_OVRIGA and amt < 0)  # Kredit 1299
        IMP_D = sum(amt for a, amt in txs if a in ACC_IMP_OVRIGA and amt > 0)   # Debet 1298
        IMP_K = sum(-amt for a, amt in txs if a in ACC_IMP_OVRIGA and amt < 0)  # Kredit 1298
        
        has_PL_disposal = any(a in DISPOSAL_PL for a, _ in txs)
        has_depr_cost = any((a in DEPR_COST and amt > 0) for a, amt in txs)
        has_imp_cost = any((a == IMPAIR_COST and amt > 0) for a, amt in txs)
        has_imp_rev = any((a == IMPAIR_REV and amt < 0) for a, amt in txs)

        # 1) Omklass (both D & K asset, no signals)
        signals = (DEP_D + DEP_K + IMP_D + IMP_K) > 0 or has_PL_disposal or has_depr_cost or has_imp_cost or has_imp_rev
        if A_D > 0 and A_K > 0 and not signals:
            arets_omklass_ovriga += (A_D - A_K)
            continue

        # 2) Disposal
        is_disposal = (A_K > 0) and (DEP_D > 0 or has_PL_disposal)
        if is_disposal:
            arets_fsg_ovriga += A_K
            aterfor_avskr_fsg_ovriga += DEP_D
            aterfor_nedskr_fsg_ovriga += IMP_D

        # 3) Inköp
        if A_D > 0:
            arets_inkop_ovriga += A_D

        # 4) Depreciations (ordinary depreciation, not disposal)
        if DEP_K > 0 and has_depr_cost and not is_disposal:
            arets_avskr_ovriga += DEP_K

        # 5) Impairments (non-disposal)
        if has_imp_cost and IMP_K > 0:
            arets_nedskr_ovriga += sum(amt for a, amt in txs if a == IMPAIR_COST and amt > 0)
        if has_imp_rev and IMP_D > 0 and A_K == 0:
            aterfor_nedskr_ovriga += IMP_D

    # --- UB formulas ---
    ovriga_ub = ovriga_ib + arets_inkop_ovriga - arets_fsg_ovriga + arets_omklass_ovriga

    ack_avskr_ovriga_ub = (
        ack_avskr_ovriga_ib
        + aterfor_avskr_fsg_ovriga
        - arets_avskr_ovriga
    )

    ack_nedskr_ovriga_ub = (
        ack_nedskr_ovriga_ib
        + aterfor_nedskr_fsg_ovriga
        + aterfor_nedskr_ovriga
        - arets_nedskr_ovriga
    )

    # --- Derived calculations ---
    red_varde_ovrmat = ovriga_ub + ack_avskr_ovriga_ub + ack_nedskr_ovriga_ub  # Book value

    # --- SRU ADDITION: Handle rare cases of accounts from other ranges with SRU 7214 ---
    # This is a separate addition to the base logic, not integrated into it
    if sru_codes:
        additional_ovriga_ib = 0.0
        additional_avskr_ib = 0.0
        additional_nedskr_ib = 0.0
        
        for account, sru in sru_codes.items():
            # Check if this account is from the 1200-1299 range with SRU 7214
            in_other_ranges = 1200 <= account <= 1299
            
            if in_other_ranges and sru == 7214:
                # Get the IB balance for this account
                account_ib = get_balance('IB', {account})
                
                # Use account description to determine ÖVRIGA categorization
                description = account_descriptions.get(account, "").lower()
                
                if "avskr" in description:  # Contains "avskr" (avskrivning, avskrivningar, etc.)
                    additional_avskr_ib += account_ib
                elif "nedskr" in description:  # Contains "nedskr" (nedskrivning, nedskrivningar, etc.)
                    additional_nedskr_ib += account_ib
                else:  # No special keywords or "uppskr" - treat as main asset
                    additional_ovriga_ib += account_ib
        
        # Add the additional amounts to the results
        if additional_ovriga_ib != 0 or additional_avskr_ib != 0 or additional_nedskr_ib != 0:
            ovriga_ib += additional_ovriga_ib
            ack_avskr_ovriga_ib += additional_avskr_ib
            ack_nedskr_ovriga_ib += additional_nedskr_ib
            
            # Recalculate UB values with the additions
            ovriga_ub = ovriga_ib + arets_inkop_ovriga - arets_fsg_ovriga + arets_omklass_ovriga
            ack_avskr_ovriga_ub = ack_avskr_ovriga_ib + aterfor_avskr_fsg_ovriga - arets_avskr_ovriga
            ack_nedskr_ovriga_ub = ack_nedskr_ovriga_ib + aterfor_nedskr_fsg_ovriga + aterfor_nedskr_ovriga - arets_nedskr_ovriga
            red_varde_ovrmat = ovriga_ub + ack_avskr_ovriga_ub + ack_nedskr_ovriga_ub
            

    return {
        # IB/UB assets
        "ovriga_ib": ovriga_ib,
        "arets_inkop_ovriga": arets_inkop_ovriga,
        "arets_fsg_ovriga": arets_fsg_ovriga,
        "arets_omklass_ovriga": arets_omklass_ovriga,
        "ovriga_ub": ovriga_ub,

        # Depreciations
        "ack_avskr_ovriga_ib": ack_avskr_ovriga_ib,
        "aterfor_avskr_fsg_ovriga": aterfor_avskr_fsg_ovriga,
        "arets_avskr_ovriga": arets_avskr_ovriga,
        "ack_avskr_ovriga_ub": ack_avskr_ovriga_ub,

        # Impairments
        "ack_nedskr_ovriga_ib": ack_nedskr_ovriga_ib,
        "arets_nedskr_ovriga": arets_nedskr_ovriga,
        "aterfor_nedskr_ovriga": aterfor_nedskr_ovriga,
        "aterfor_nedskr_fsg_ovriga": aterfor_nedskr_fsg_ovriga,
        "ack_nedskr_ovriga_ub": ack_nedskr_ovriga_ub,

        # Derived book value
        "red_varde_ovrmat": red_varde_ovrmat,
    }
