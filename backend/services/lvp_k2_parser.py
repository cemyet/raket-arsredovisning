import re
from collections import defaultdict

def parse_lvp_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    LVP-note (K2) parser for Långfristiga värdepapper.

    Handles:
      - #VER with/without quoted titles; extra tokens after date.
      - #TRANS/#BTRANS/#RTRANS with or without "{}", optional date and trailing text.
      - IB/UB numbers with thousand spaces and commas (e.g. "-58 216 440,00").

    K2 business rules for Långfristiga värdepapper (1350-1357):
      • Asset accounts: 1350-1357
      • Accumulated impairment: 1358
      • No depreciation or revaluation for securities
      • Impairment cost: 7730
      • Impairment reversal: 7780
      • UB for impairment read directly from SIE due to reversals

    Returns dict with:
      lang_vardepapper_ib, arets_inkop_lang_vardepapper, arets_fsg_lang_vardepapper, lang_vardepapper_ub,
      ack_nedskr_lang_vardepapper_ib, arets_nedskr_lang_vardepapper, ack_nedskr_lang_vardepapper_ub,
      red_varde_lang_vardepapper
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

    # --- CONFIG (K2 – långfristiga värdepapper) ---
    # Use original base logic - no SRU integration here for LVP
    ASSET_RANGES = [(1350, 1357)]
    ACC_IMP_LVP = {1358}
    
    IMPAIR_COST = 7730
    IMPAIR_REV = 7780
    

    # --- Helpers ---
    def in_lvp_assets(acct: int) -> bool:
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
    lang_vardepapper_ib = get_balance('IB', ASSET_RANGES)
    ack_nedskr_lang_vardepapper_ib = get_balance('IB', ACC_IMP_LVP)

    # --- Accumulators ---
    arets_inkop_lang_vardepapper = 0.0
    arets_fsg_lang_vardepapper = 0.0
    arets_nedskr_lang_vardepapper = 0.0


    # --- Per voucher classification ---
    for key, txs in trans_by_ver.items():
        # Aggregate per voucher
        A_D = sum(amt for a, amt in txs if in_lvp_assets(a) and amt > 0)     # Debet asset (inköp)
        A_K = sum(-amt for a, amt in txs if in_lvp_assets(a) and amt < 0)    # Kredit asset (försäljning)
        IMP_K = sum(-amt for a, amt in txs if a in ACC_IMP_LVP and amt < 0)  # Kredit 1358 (ökar nedskr)
        
        has_imp_cost = any((a == IMPAIR_COST and amt > 0) for a, amt in txs)

        # 1) Inköp (Debet asset accounts)
        if A_D > 0:
            arets_inkop_lang_vardepapper += A_D

        # 2) Försäljning (Kredit asset accounts)
        if A_K > 0:
            arets_fsg_lang_vardepapper += A_K

        # 3) Nedskrivning (D 7730 + K 1358)
        # Only count impairment cost when the voucher actually increases accumulated impairment
        if has_imp_cost and IMP_K > 0:
            arets_nedskr_lang_vardepapper += sum(
                amt for a, amt in txs if a == IMPAIR_COST and amt > 0
            )

    # --- UB formulas ---
    lang_vardepapper_ub = (
        lang_vardepapper_ib
        + arets_inkop_lang_vardepapper
        - arets_fsg_lang_vardepapper
    )

    # Important: Read UB directly from SIE for accumulated impairment
    # This handles reversals (K 7780/D 1358) that don't have separate variables
    ack_nedskr_lang_vardepapper_ub = get_balance('UB', ACC_IMP_LVP)

    # --- Derived calculations ---
    red_varde_lang_vardepapper = lang_vardepapper_ub + ack_nedskr_lang_vardepapper_ub  # Book value

    # --- SRU ADDITION: Handle rare cases of accounts from other ranges with SRU 7214 ---
    # This is a separate addition to the base logic, not integrated into it
    if sru_codes:
        additional_lvp_ib = 0.0
        additional_nedskr_ib = 0.0
        
        for account, sru in sru_codes.items():
            # Check if this account is from the 1200-1299 range with SRU 7214
            in_other_ranges = 1200 <= account <= 1299
            
            if in_other_ranges and sru == 7214:
                # Get the IB balance for this account
                account_ib = get_balance('IB', {account})
                
                # Use account description to determine LVP categorization
                description = account_descriptions.get(account, "").lower()
                
                if "nedskr" in description:  # Contains "nedskr" (nedskrivning, nedskrivningar, etc.)
                    additional_nedskr_ib += account_ib
                else:  # No special keywords - treat as main asset
                    additional_lvp_ib += account_ib
        
        # Add the additional amounts to the results
        if additional_lvp_ib != 0 or additional_nedskr_ib != 0:
            lang_vardepapper_ib += additional_lvp_ib
            ack_nedskr_lang_vardepapper_ib += additional_nedskr_ib
            
            # Recalculate UB values with the additions
            lang_vardepapper_ub = lang_vardepapper_ib + arets_inkop_lang_vardepapper - arets_fsg_lang_vardepapper
            # Note: ack_nedskr_lang_vardepapper_ub is read directly from UB, no recalculation needed
            red_varde_lang_vardepapper = lang_vardepapper_ub + ack_nedskr_lang_vardepapper_ub
            

    return {
        # IB/UB assets
        "lang_vardepapper_ib": lang_vardepapper_ib,
        "arets_inkop_lang_vardepapper": arets_inkop_lang_vardepapper,
        "arets_fsg_lang_vardepapper": arets_fsg_lang_vardepapper,
        "lang_vardepapper_ub": lang_vardepapper_ub,

        # Impairments
        "ack_nedskr_lang_vardepapper_ib": ack_nedskr_lang_vardepapper_ib,
        "arets_nedskr_lang_vardepapper": arets_nedskr_lang_vardepapper,
        "ack_nedskr_lang_vardepapper_ub": ack_nedskr_lang_vardepapper_ub,

        # Derived book value  
        "red_varde_lang_vardepapper": red_varde_lang_vardepapper,
    }
