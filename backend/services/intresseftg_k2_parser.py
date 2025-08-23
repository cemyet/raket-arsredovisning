import re
from collections import defaultdict

def parse_intresseftg_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    INTRESSEFTG-note (K2) parser.
    
    Handles "Andelar i intresseföretag, gemensamt styrda företag och övriga företag":
    • Asset accounts: 1330, 1331, 1333, 1336
    • Accumulated impairment: 1332, 1334, 1337, 1338
    • Result share via 8240 (signed)
    • Purchase classification by voucher text (fusion, aktieägartillskott)
    • Sales with impairment reversal allocation
    • Reclassification without signals
    • Aktieägartillskott återbetalt (repaid shareholder contributions)
    """
    # Normalize whitespace and NBSP so numbers like "58 216 440,00" parse
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # --- CONFIG (K2 – intresseftg) ---
    ASSET_SET = {1330, 1331, 1333, 1336}
    ACC_IMP_SET = {1332, 1334, 1337, 1338}
    RES_SHARE = 8240  # Result share account
    
    if debug:
        print(f"DEBUG INTRESSEFTG: Asset accounts: {ASSET_SET}")
        print(f"DEBUG INTRESSEFTG: Impairment accounts: {ACC_IMP_SET}")
        print(f"DEBUG INTRESSEFTG: Result share account: {RES_SHARE}")

    # --- Helpers ---
    def _to_float(s: str) -> float:
        # tolerant for "123 456,78" and "123,456.78"
        return float(s.strip().replace(" ", "").replace(",", "."))

    def get_balance(kind_flag: str, accounts):
        """Sum #IB or #UB for the given account set (current year '0' rows)."""
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
            if acct in accounts:
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
            text_by_ver[current_ver] = voucher_text.lower()
            if debug and voucher_text:
                print(f"DEBUG INTRESSEFTG: Voucher {current_ver} text: '{voucher_text}'")
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
    intresseftg_ib = get_balance('IB', ASSET_SET)
    ack_nedskr_intresseftg_ib = get_balance('IB', ACC_IMP_SET)

    # --- Accumulators ---
    inkop_intresseftg = 0.0
    fsg_intresseftg = 0.0
    fusion_intresseftg = 0.0
    aktieagartillskott_lamnad_intresseftg = 0.0
    aktieagartillskott_aterbetald_intresseftg = 0.0
    resultatandel_intresseftg = 0.0
    omklass_intresseftg = 0.0
    
    # Impairment accumulators
    arets_nedskr_intresseftg = 0.0
    aterfor_nedskr_intresseftg = 0.0
    aterfor_nedskr_fsg_intresseftg = 0.0
    aterfor_nedskr_fusion_intresseftg = 0.0
    omklass_nedskr_intresseftg = 0.0

    if debug:
        print(f"DEBUG INTRESSEFTG K2: vouchers parsed = {len(trans_by_ver)}")
        for key, txs in list(trans_by_ver.items())[:3]:  # Show first 3 vouchers
            print(f"DEBUG INTRESSEFTG K2: Voucher {key}: {txs}, text: '{text_by_ver.get(key, '')}'")

    # --- per voucher classification (SIGNED RESULTATANDEL) ---
    for key, txs in trans_by_ver.items():
        text = text_by_ver.get(key, "")

        A_D = sum(amt for a, amt in txs if a in ASSET_SET and amt > 0)     # D asset
        A_K = sum(-amt for a, amt in txs if a in ASSET_SET and amt < 0)    # |K asset|

        IMP_D = sum(amt for a, amt in txs if a in ACC_IMP_SET and amt > 0)    # D impairment (reversal)
        IMP_K = sum(-amt for a, amt in txs if a in ACC_IMP_SET and amt < 0)   # |K impairment| (new impairment)

        RES_K = sum(-amt for a, amt in txs if a == RES_SHARE and amt < 0)  # |K8240|
        RES_D = sum(amt for a, amt in txs if a == RES_SHARE and amt > 0)   # D8240

        if debug and (A_D > 0 or A_K > 0 or RES_K > 0 or RES_D > 0 or IMP_D > 0 or IMP_K > 0):
            print(f"DEBUG INTRESSEFTG {key}: A_D={A_D}, A_K={A_K}, RES_K={RES_K}, RES_D={RES_D}, IMP_D={IMP_D}, IMP_K={IMP_K}, text='{text}'")

        # 1) Resultatandel (signerad):
        #   +  D tillgång + K8240
        #   -  K tillgång + D8240
        res_plus = min(A_D, RES_K) if (A_D > 0 and RES_K > 0) else 0.0
        res_minus = min(A_K, RES_D) if (A_K > 0 and RES_D > 0) else 0.0
        resultatandel_intresseftg += (res_plus - res_minus)

        if debug and (res_plus > 0 or res_minus > 0):
            print(f"DEBUG INTRESSEFTG {key}: resultatandel += {res_plus - res_minus} (res_plus={res_plus}, res_minus={res_minus})")

        # 2) Inköp = resterande D på tillgång efter resultatandel (+delen)
        inc_amount = max(0.0, A_D - res_plus)
        if inc_amount > 0:
            if "fusion" in text:
                fusion_intresseftg += inc_amount
                if debug:
                    print(f"DEBUG INTRESSEFTG {key}: fusion += {inc_amount}")
            elif "aktieägartillskott" in text or "aktieagartillskott" in text:
                aktieagartillskott_lamnad_intresseftg += inc_amount
                if debug:
                    print(f"DEBUG INTRESSEFTG {key}: aktieägartillskott_lämnad += {inc_amount}")
            else:
                inkop_intresseftg += inc_amount
                if debug:
                    print(f"DEBUG INTRESSEFTG {key}: inkop += {inc_amount}")

        # 3) Försäljning = resterande K på tillgång efter resultatandel (-delen)
        sale_amount = max(0.0, A_K - res_minus)
        if sale_amount > 0:
            # allokera återföring av nedskrivning till försäljning om den förekommer
            if IMP_D > 0:
                aterfor_nedskr_fsg_intresseftg += IMP_D
                IMP_D = 0.0  # consumed
                if debug:
                    print(f"DEBUG INTRESSEFTG {key}: aterfor_nedskr_fsg += {IMP_D}")
            fsg_intresseftg += sale_amount
            if debug:
                print(f"DEBUG INTRESSEFTG {key}: fsg += {sale_amount}")

        # 4) Återföring/nedskrivning som inte redan bundits till försäljning
        if IMP_D > 0:
            if "fusion" in text:
                aterfor_nedskr_fusion_intresseftg += IMP_D
                if debug:
                    print(f"DEBUG INTRESSEFTG {key}: aterfor_nedskr_fusion += {IMP_D}")
            else:
                aterfor_nedskr_intresseftg += IMP_D
                if debug:
                    print(f"DEBUG INTRESSEFTG {key}: aterfor_nedskr += {IMP_D}")
        if IMP_K > 0:
            arets_nedskr_intresseftg += IMP_K
            if debug:
                print(f"DEBUG INTRESSEFTG {key}: arets_nedskr += {IMP_K}")

        # 5) Omklass (tillgång resp. ack nedskr) utan signaler
        asset_signals = (RES_K > 0 or RES_D > 0 or IMP_D > 0 or IMP_K > 0)
        if A_D > 0 and A_K > 0 and not asset_signals:
            omklass_intresseftg += (A_D - A_K)
            if debug:
                print(f"DEBUG INTRESSEFTG {key}: omklass += {A_D - A_K}")
        
        # Omklass for nedskrivning accounts separately
        imp_d_orig = sum(amt for a, amt in txs if a in ACC_IMP_SET and amt > 0)
        imp_k_orig = sum(-amt for a, amt in txs if a in ACC_IMP_SET and amt < 0)
        if imp_d_orig > 0 and imp_k_orig > 0 and \
           not (A_D > 0 or A_K > 0 or RES_K > 0 or RES_D > 0):
            omklass_nedskr_intresseftg += (imp_d_orig - imp_k_orig)
            if debug:
                print(f"DEBUG INTRESSEFTG {key}: omklass_nedskr += {imp_d_orig - imp_k_orig}")

        # 6) Aktieägartillskott återbetalt – text + K-tillgång
        if ("aktieägartillskott" in text or "aktieagartillskott" in text) and A_K > 0:
            aktieagartillskott_aterbetald_intresseftg += A_K
            if debug:
                print(f"DEBUG INTRESSEFTG {key}: aktieägartillskott_återbetald += {A_K}")

    # --- UB formulas ---
    intresseftg_ub = (
        intresseftg_ib
        + inkop_intresseftg
        + fusion_intresseftg
        - fsg_intresseftg  # Note: fsg is subtracted in UB calculation
        + aktieagartillskott_lamnad_intresseftg
        - aktieagartillskott_aterbetald_intresseftg  # Note: repaid is subtracted
        + resultatandel_intresseftg
        + omklass_intresseftg
    )
    
    ack_nedskr_intresseftg_ub = (
        ack_nedskr_intresseftg_ib
        - arets_nedskr_intresseftg
        + aterfor_nedskr_intresseftg
        + aterfor_nedskr_fsg_intresseftg
        + aterfor_nedskr_fusion_intresseftg
        + omklass_nedskr_intresseftg
    )

    # --- Derived calculations ---
    red_varde_intresseftg = intresseftg_ub + ack_nedskr_intresseftg_ub

    if debug:
        print(f"DEBUG INTRESSEFTG K2: Final results:")
        print(f"  intresseftg_ib: {intresseftg_ib}")
        print(f"  inkop_intresseftg: {inkop_intresseftg}")
        print(f"  fusion_intresseftg: {fusion_intresseftg}")
        print(f"  fsg_intresseftg: {fsg_intresseftg}")
        print(f"  aktieagartillskott_lamnad_intresseftg: {aktieagartillskott_lamnad_intresseftg}")
        print(f"  aktieagartillskott_aterbetald_intresseftg: {aktieagartillskott_aterbetald_intresseftg}")
        print(f"  resultatandel_intresseftg: {resultatandel_intresseftg}")
        print(f"  omklass_intresseftg: {omklass_intresseftg}")
        print(f"  intresseftg_ub: {intresseftg_ub}")
        print(f"  ack_nedskr_intresseftg_ib: {ack_nedskr_intresseftg_ib}")
        print(f"  arets_nedskr_intresseftg: {arets_nedskr_intresseftg}")
        print(f"  aterfor_nedskr_intresseftg: {aterfor_nedskr_intresseftg}")
        print(f"  aterfor_nedskr_fsg_intresseftg: {aterfor_nedskr_fsg_intresseftg}")
        print(f"  aterfor_nedskr_fusion_intresseftg: {aterfor_nedskr_fusion_intresseftg}")
        print(f"  omklass_nedskr_intresseftg: {omklass_nedskr_intresseftg}")
        print(f"  ack_nedskr_intresseftg_ub: {ack_nedskr_intresseftg_ub}")
        print(f"  red_varde_intresseftg: {red_varde_intresseftg}")

    return {
        # Asset movements
        "intresseftg_ib": intresseftg_ib,
        "inkop_intresseftg": inkop_intresseftg,
        "fusion_intresseftg": fusion_intresseftg,
        "fsg_intresseftg": fsg_intresseftg,
        "aktieagartillskott_lamnad_intresseftg": aktieagartillskott_lamnad_intresseftg,
        "aktieagartillskott_aterbetald_intresseftg": aktieagartillskott_aterbetald_intresseftg,
        "resultatandel_intresseftg": resultatandel_intresseftg,
        "omklass_intresseftg": omklass_intresseftg,
        "intresseftg_ub": intresseftg_ub,
        
        # Impairment movements
        "ack_nedskr_intresseftg_ib": ack_nedskr_intresseftg_ib,
        "arets_nedskr_intresseftg": arets_nedskr_intresseftg,
        "aterfor_nedskr_intresseftg": aterfor_nedskr_intresseftg,
        "aterfor_nedskr_fsg_intresseftg": aterfor_nedskr_fsg_intresseftg,
        "aterfor_nedskr_fusion_intresseftg": aterfor_nedskr_fusion_intresseftg,
        "omklass_nedskr_intresseftg": omklass_nedskr_intresseftg,
        "ack_nedskr_intresseftg_ub": ack_nedskr_intresseftg_ub,
        
        # Derived
        "red_varde_intresseftg": red_varde_intresseftg,
    }
