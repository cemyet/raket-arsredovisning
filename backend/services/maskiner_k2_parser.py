import re
from collections import defaultdict

def parse_maskiner_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    MASKINER-note (K2) parser.

    • Ingen uppskrivningslogik (2085 används ej).
    • Tillgångskonton: 1210–1217
    • Avskrivningskostnader: 7830, 7831 (exkludera 7833 och 7839)
    • Nedskrivning:        D7730 + K1218
      Återföring:          K7780 + D1218 (ej disposal)
      Återföring disposal: D1218 i avyttringsverifikat
    """

    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # --- CONFIG (K2 – maskiner) ---
    ASSET_RANGES = [(1210, 1217)]
    ACC_DEP_MASK = {1219}
    ACC_IMP_MASK = {1218}
    DISPOSAL_PL = {3973, 7973}
    DEPR_COST = {7830, 7831}     # exkluderar 7833 och 7839
    IMPAIR_COST = 7730
    IMPAIR_REV  = 7780

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
    maskiner_ib            = get_balance('IB', ASSET_RANGES)
    ack_avskr_maskiner_ib  = get_balance('IB', ACC_DEP_MASK)
    ack_nedskr_maskiner_ib = get_balance('IB', ACC_IMP_MASK)

    # --- Accumulators ---
    arets_inkop_maskiner        = 0.0
    arets_fsg_maskiner          = 0.0
    arets_omklass_maskiner      = 0.0
    arets_avskr_maskiner        = 0.0
    aterfor_avskr_fsg_maskiner  = 0.0
    arets_nedskr_maskiner       = 0.0
    aterfor_nedskr_maskiner     = 0.0
    aterfor_nedskr_fsg_maskiner = 0.0

    if debug:
        print(f"DEBUG MASKINER K2: vouchers parsed = {len(trans_by_ver)} (sample: {list(trans_by_ver)[:5]})")

    # --- Classify vouchers ---
    for key, txs in trans_by_ver.items():
        # Debug maskiner vouchers
        if debug and (any(a in ACC_DEP_MASK for a,_ in txs) or any(a in DEPR_COST for a,_ in txs) or any(in_assets(a) for a,_ in txs)):
            print(f"DEBUG MASKINER K2: Checking voucher {key} with transactions: {txs}")
            
        A_D  = sum(amt for a, amt in txs if in_assets(a) and amt > 0)
        A_K  = sum(-amt for a, amt in txs if in_assets(a) and amt < 0)
        DEP_D = sum(amt for a, amt in txs if a in ACC_DEP_MASK and amt > 0)
        DEP_K = sum(-amt for a, amt in txs if a in ACC_DEP_MASK and amt < 0)
        IMP_D = sum(amt for a, amt in txs if a in ACC_IMP_MASK and amt > 0)
        IMP_K = sum(-amt for a, amt in txs if a in ACC_IMP_MASK and amt < 0)
        has_PL_disposal = any(a in DISPOSAL_PL for a, _ in txs)
        has_depr_cost = any((a in DEPR_COST and amt > 0) for a, amt in txs)
        has_imp_cost  = any((a == IMPAIR_COST and amt > 0) for a, amt in txs)
        has_imp_rev   = any((a == IMPAIR_REV  and amt < 0) for a, amt in txs)

        # Disposal
        if (A_K > 0) and (DEP_D > 0 or has_PL_disposal):
            arets_fsg_maskiner         += A_K
            aterfor_avskr_fsg_maskiner += DEP_D
            aterfor_nedskr_fsg_maskiner+= IMP_D
            if debug:
                print(f"DEBUG MASKINER {key}: disposal - fsg += {A_K}, aterfor_avskr += {DEP_D}, aterfor_nedskr += {IMP_D}")

        # Inköp
        if A_D > 0:
            arets_inkop_maskiner += A_D
            if debug:
                print(f"DEBUG MASKINER {key}: inkop += {A_D}")

        # Depreciations
        if DEP_K > 0 and has_depr_cost:
            arets_avskr_maskiner += DEP_K
            if debug:
                print(f"DEBUG MASKINER {key}: avskr += {DEP_K}")

        # Impairments
        if has_imp_cost and IMP_K > 0:
            arets_nedskr_maskiner += sum(amt for a, amt in txs if a == IMPAIR_COST and amt > 0)
            if debug:
                print(f"DEBUG MASKINER {key}: nedskr += {sum(amt for a, amt in txs if a == IMPAIR_COST and amt > 0)}")
        if has_imp_rev and IMP_D > 0 and A_K == 0:
            aterfor_nedskr_maskiner += IMP_D
            if debug:
                print(f"DEBUG MASKINER {key}: aterfor_nedskr += {IMP_D}")

        # Omklass
        signals = (DEP_D+DEP_K+IMP_D+IMP_K) > 0 or has_PL_disposal or has_depr_cost or has_imp_cost or has_imp_rev
        if A_D > 0 and A_K > 0 and not signals:
            arets_omklass_maskiner += (A_D - A_K)
            if debug:
                print(f"DEBUG MASKINER {key}: omklass += {A_D - A_K}")

    # --- UB formulas ---
    maskiner_ub = maskiner_ib + arets_inkop_maskiner - arets_fsg_maskiner + arets_omklass_maskiner
    ack_avskr_maskiner_ub = ack_avskr_maskiner_ib + aterfor_avskr_fsg_maskiner - arets_avskr_maskiner
    ack_nedskr_maskiner_ub = ack_nedskr_maskiner_ib + aterfor_nedskr_fsg_maskiner + aterfor_nedskr_maskiner - arets_nedskr_maskiner

    # --- Derived ---
    red_varde_maskiner = maskiner_ub + ack_avskr_maskiner_ub + ack_nedskr_maskiner_ub

    if debug:
        print(f"DEBUG MASKINER K2: Final results:")
        print(f"  maskiner_ib: {maskiner_ib}")
        print(f"  arets_inkop_maskiner: {arets_inkop_maskiner}")
        print(f"  arets_fsg_maskiner: {arets_fsg_maskiner}")
        print(f"  arets_omklass_maskiner: {arets_omklass_maskiner}")
        print(f"  maskiner_ub: {maskiner_ub}")
        print(f"  ack_avskr_maskiner_ib: {ack_avskr_maskiner_ib}")
        print(f"  aterfor_avskr_fsg_maskiner: {aterfor_avskr_fsg_maskiner}")
        print(f"  arets_avskr_maskiner: {arets_avskr_maskiner}")
        print(f"  ack_avskr_maskiner_ub: {ack_avskr_maskiner_ub}")
        print(f"  ack_nedskr_maskiner_ib: {ack_nedskr_maskiner_ib}")
        print(f"  arets_nedskr_maskiner: {arets_nedskr_maskiner}")
        print(f"  aterfor_nedskr_maskiner: {aterfor_nedskr_maskiner}")
        print(f"  aterfor_nedskr_fsg_maskiner: {aterfor_nedskr_fsg_maskiner}")
        print(f"  ack_nedskr_maskiner_ub: {ack_nedskr_maskiner_ub}")
        print(f"  red_varde_maskiner: {red_varde_maskiner}")

    return {
        "maskiner_ib": maskiner_ib,
        "arets_inkop_maskiner": arets_inkop_maskiner,
        "arets_fsg_maskiner": arets_fsg_maskiner,
        "arets_omklass_maskiner": arets_omklass_maskiner,
        "maskiner_ub": maskiner_ub,
        "ack_avskr_maskiner_ib": ack_avskr_maskiner_ib,
        "aterfor_avskr_fsg_maskiner": aterfor_avskr_fsg_maskiner,
        "arets_avskr_maskiner": arets_avskr_maskiner,
        "ack_avskr_maskiner_ub": ack_avskr_maskiner_ub,
        "ack_nedskr_maskiner_ib": ack_nedskr_maskiner_ib,
        "arets_nedskr_maskiner": arets_nedskr_maskiner,
        "aterfor_nedskr_maskiner": aterfor_nedskr_maskiner,
        "aterfor_nedskr_fsg_maskiner": aterfor_nedskr_fsg_maskiner,
        "ack_nedskr_maskiner_ub": ack_nedskr_maskiner_ub,
        "red_varde_maskiner": red_varde_maskiner,
    }
