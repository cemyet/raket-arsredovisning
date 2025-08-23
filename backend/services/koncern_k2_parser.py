import re
from collections import defaultdict

def parse_koncern_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    KONCERN-note (K2) parser.
    
    Handles "Andelar i koncernföretag" (shares in group companies) with complex logic:
    • Resultatandel signerad (signed result share): based on min(D asset, K 8240) or min(K asset, D 8240)
    • Inköp (purchases): remaining D asset after resultatandel, classified by voucher text
    • Försäljning (sales): remaining K asset after resultatandel
    • Återföring/nedskrivning (reversal/impairment): D/K 1318 logic
    • Omklassificering (reclassification): transactions without signals
    
    Assets: 1310-1317
    Impairment acc: 1318  
    Result share acc: 8240
    """
    # Normalize whitespace and NBSP so numbers like "58 216 440,00" parse
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # --- Parse SRU codes (if present) ---
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
                print(f"DEBUG KONCERN: Found SRU {account} -> {sru}")

    # --- CONFIG (K2 – koncern) ---
    ASSET_RANGES = [(1310, 1317)]
    ACC_IMP = {1318}  # Impairment account
    RES_SHARE = 8240  # Result share account
    
    if debug:
        print(f"DEBUG KONCERN: Asset ranges: {ASSET_RANGES}")
        print(f"DEBUG KONCERN: Impairment account: {ACC_IMP}")
        print(f"DEBUG KONCERN: Result share account: {RES_SHARE}")

    # --- Helpers ---
    def in_assets(acct: int) -> bool:
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

    # --- Parse vouchers with text extraction ---
    ver_header_re = re.compile(
        r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"([^"]*)"|(.+)))?\s*$'
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
    text_by_ver = {}  # Store voucher text
    current_ver = None
    in_block = False

    for raw in lines:
        t = raw.strip()
        mh = ver_header_re.match(t)
        if mh:
            current_ver = (mh.group(1), int(mh.group(2)))
            # Extract voucher text (quoted or unquoted)
            voucher_text = mh.group(4) or mh.group(5) or ""
            text_by_ver[current_ver] = voucher_text
            if debug and voucher_text:
                print(f"DEBUG KONCERN: Voucher {current_ver} text: '{voucher_text}'")
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
    koncern_ib = get_balance('IB', ASSET_RANGES)
    ack_nedskr_koncern_ib = get_balance('IB', ACC_IMP)

    # --- Accumulators ---
    resultatandel_koncern = 0.0
    inkop_koncern = 0.0
    fusion_koncern = 0.0
    aktieagartillskott_lamnad_koncern = 0.0
    fsg_koncern = 0.0
    omklass_koncern = 0.0
    
    # Impairment accumulators
    arets_nedskr_koncern = 0.0
    aterfor_nedskr_koncern = 0.0
    aterfor_nedskr_fsg_koncern = 0.0
    aterfor_nedskr_fusion_koncern = 0.0
    omklass_nedskr_koncern = 0.0

    if debug:
        print(f"DEBUG KONCERN K2: vouchers parsed = {len(trans_by_ver)}")
        for key, txs in list(trans_by_ver.items())[:3]:  # Show first 3 vouchers
            print(f"DEBUG KONCERN K2: Voucher {key}: {txs}, text: '{text_by_ver.get(key, '')}'")

    # --- per voucher classification (SIGNED RESULTATANDEL) ---
    for key, txs in trans_by_ver.items():
        text = text_by_ver.get(key, "").lower()

        A_D  = sum(amt  for a,amt in txs if in_assets(a) and amt > 0)     # D 1310–1317
        A_K  = sum(-amt for a,amt in txs if in_assets(a) and amt < 0)     # |K 1310–1317|

        IMP_D = sum(amt  for a,amt in txs if a in ACC_IMP and amt > 0)    # D1318
        IMP_K = sum(-amt for a,amt in txs if a in ACC_IMP and amt < 0)    # |K1318|

        RES_K = sum(-amt for a,amt in txs if a == RES_SHARE and amt < 0)  # |K8240|
        RES_D = sum(amt  for a,amt in txs if a == RES_SHARE and amt > 0)  # D8240

        if debug and (A_D > 0 or A_K > 0 or RES_K > 0 or RES_D > 0 or IMP_D > 0 or IMP_K > 0):
            print(f"DEBUG KONCERN {key}: A_D={A_D}, A_K={A_K}, RES_K={RES_K}, RES_D={RES_D}, IMP_D={IMP_D}, IMP_K={IMP_K}, text='{text}'")

        # 1) Resultatandel (signerad):
        #   +  D tillgång + K8240
        #   -  K tillgång + D8240
        res_plus  = min(A_D, RES_K) if RES_K > 0 and A_D > 0 else 0.0
        res_minus = min(A_K, RES_D) if RES_D > 0 and A_K > 0 else 0.0
        resultatandel_koncern += (res_plus - res_minus)

        if debug and (res_plus > 0 or res_minus > 0):
            print(f"DEBUG KONCERN {key}: resultatandel += {res_plus - res_minus} (res_plus={res_plus}, res_minus={res_minus})")

        # 2) Inköp = resterande D på tillgång efter resultatandel (+delen)
        inkop_amount = max(0.0, A_D - res_plus)
        if inkop_amount > 0:
            if "fusion" in text:
                fusion_koncern += inkop_amount
                if debug:
                    print(f"DEBUG KONCERN {key}: fusion += {inkop_amount}")
            elif "aktieägartillskott" in text:
                aktieagartillskott_lamnad_koncern += inkop_amount
                if debug:
                    print(f"DEBUG KONCERN {key}: aktieägartillskott += {inkop_amount}")
            else:
                inkop_koncern += inkop_amount
                if debug:
                    print(f"DEBUG KONCERN {key}: inkop += {inkop_amount}")

        # 3) Försäljning = resterande K på tillgång efter resultatandel (-delen)
        sale_amount = max(0.0, A_K - res_minus)
        if sale_amount > 0:
            # allokera återföring av nedskrivning till försäljning om den förekommer
            if IMP_D > 0:
                aterfor_nedskr_fsg_koncern += IMP_D
                IMP_D = 0.0  # consumed
                if debug:
                    print(f"DEBUG KONCERN {key}: aterfor_nedskr_fsg += {IMP_D}")
            fsg_koncern += sale_amount
            if debug:
                print(f"DEBUG KONCERN {key}: fsg += {sale_amount}")

        # 4) Återföring/nedskrivning som inte redan bundits till försäljning
        if IMP_D > 0:
            if "fusion" in text:
                aterfor_nedskr_fusion_koncern += IMP_D
                if debug:
                    print(f"DEBUG KONCERN {key}: aterfor_nedskr_fusion += {IMP_D}")
            else:
                aterfor_nedskr_koncern += IMP_D
                if debug:
                    print(f"DEBUG KONCERN {key}: aterfor_nedskr += {IMP_D}")
        if IMP_K > 0:
            arets_nedskr_koncern += IMP_K
            if debug:
                print(f"DEBUG KONCERN {key}: arets_nedskr += {IMP_K}")

        # 5) Omklass (tillgång resp. ack nedskr) utan signaler
        asset_signals = (RES_K > 0 or RES_D > 0 or IMP_D > 0 or IMP_K > 0)
        if A_D > 0 and A_K > 0 and not asset_signals:
            omklass_koncern += (A_D - A_K)
            if debug:
                print(f"DEBUG KONCERN {key}: omklass += {A_D - A_K}")
        
        # Omklass for nedskrivning accounts separately
        imp_d_orig = sum(amt for a,amt in txs if a in ACC_IMP and amt > 0)
        imp_k_orig = sum(-amt for a,amt in txs if a in ACC_IMP and amt < 0)
        if imp_d_orig > 0 and imp_k_orig > 0 and \
           not (A_D > 0 or A_K > 0 or RES_K > 0 or RES_D > 0):
            omklass_nedskr_koncern += (imp_d_orig - imp_k_orig)
            if debug:
                print(f"DEBUG KONCERN {key}: omklass_nedskr += {imp_d_orig - imp_k_orig}")

    # --- UB formulas ---
    koncern_ub = koncern_ib + inkop_koncern + fusion_koncern + aktieagartillskott_lamnad_koncern - fsg_koncern + resultatandel_koncern + omklass_koncern
    
    ack_nedskr_koncern_ub = (
        ack_nedskr_koncern_ib
        - arets_nedskr_koncern
        + aterfor_nedskr_koncern
        + aterfor_nedskr_fsg_koncern
        + aterfor_nedskr_fusion_koncern
        + omklass_nedskr_koncern
    )

    # --- Derived calculations ---
    red_varde_koncern = koncern_ub - ack_nedskr_koncern_ub

    if debug:
        print(f"DEBUG KONCERN K2: Final results:")
        print(f"  koncern_ib: {koncern_ib}")
        print(f"  inkop_koncern: {inkop_koncern}")
        print(f"  fusion_koncern: {fusion_koncern}")
        print(f"  aktieagartillskott_lamnad_koncern: {aktieagartillskott_lamnad_koncern}")
        print(f"  fsg_koncern: {fsg_koncern}")
        print(f"  resultatandel_koncern: {resultatandel_koncern}")
        print(f"  omklass_koncern: {omklass_koncern}")
        print(f"  koncern_ub: {koncern_ub}")
        print(f"  ack_nedskr_koncern_ib: {ack_nedskr_koncern_ib}")
        print(f"  arets_nedskr_koncern: {arets_nedskr_koncern}")
        print(f"  aterfor_nedskr_koncern: {aterfor_nedskr_koncern}")
        print(f"  aterfor_nedskr_fsg_koncern: {aterfor_nedskr_fsg_koncern}")
        print(f"  aterfor_nedskr_fusion_koncern: {aterfor_nedskr_fusion_koncern}")
        print(f"  omklass_nedskr_koncern: {omklass_nedskr_koncern}")
        print(f"  ack_nedskr_koncern_ub: {ack_nedskr_koncern_ub}")
        print(f"  red_varde_koncern: {red_varde_koncern}")

    return {
        # Asset movements
        "koncern_ib": koncern_ib,
        "inkop_koncern": inkop_koncern,
        "fusion_koncern": fusion_koncern,
        "aktieagartillskott_lamnad_koncern": aktieagartillskott_lamnad_koncern,
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
