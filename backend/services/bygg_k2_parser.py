import re
from collections import defaultdict

def parse_bygg_k2_from_sie_text(sie_text: str):
    """
    Parser för BYGG-not (K2).
    Identifierar inköp, uppskrivningar (via 2085), avyttringar, avskrivningar, nedskrivningar
    och beräknar UB enligt hårdkodade formler.
    """
    lines = sie_text.splitlines()

    # --- KONFIG (K2 – bygg/mark) ---
    BUILDING_ASSET_RANGES = [(1110,1117),(1130,1139),(1140,1149),(1150,1157),(1180,1189)]
    ACC_DEP_BYGG = {1119, 1159}
    ACC_IMP_BYGG = {1158}
    UPSKR_FOND = 2085
    DISPOSAL_PL = {3972, 7972}
    DEPR_COST = {7820, 7821, 7824, 7829}
    IMPAIR_COST = 7720
    IMPAIR_REV  = 7770

    # --- Hjälpare ---
    def in_building_assets(acct: int) -> bool:
        return any(lo <= acct <= hi for lo,hi in BUILDING_ASSET_RANGES)

    def get_balance(kind_flag: str, accounts):
        """Summera #IB eller #UB för angivet kontoset/range-lista."""
        total = 0.0
        for s in lines:
            m = re.match(rf'#({kind_flag})\s+0\s+(\d+)\s+(-?[0-9.,]+)', s.strip())
            if not m: 
                continue
            _, acct, amount = m.groups()
            acct = int(acct)
            amount = float(amount.replace(",", "."))
            ok = False
            if isinstance(accounts, (set, frozenset)):
                ok = acct in accounts
            else:  # list of ranges
                ok = any(lo <= acct <= hi for lo,hi in accounts)
            if ok:
                total += amount
        return total

    # --- Läs verifikationer ---
    ver_header_re = re.compile(r'#VER\s+([A-ZÅÄÖ])\s+(\d+)\s+(\d{8})\s+"[^"]*"')
    trans_re = re.compile(r'#(?:BTRANS|RTRANS|TRANS)\s+(\d{3,4})\s+\{\}?\s+(-?[0-9.,]+)')

    trans_by_ver = defaultdict(list)
    current_ver = None
    in_block = False
    for s in lines:
        t = s.strip()
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
                amt = float(mt.group(2).replace(",", "."))
                trans_by_ver[current_ver].append((acct, amt))

    # --- IB från SIE ---
    bygg_ib               = get_balance('IB', BUILDING_ASSET_RANGES)
    ack_avskr_bygg_ib     = get_balance('IB', ACC_DEP_BYGG)
    ack_nedskr_bygg_ib    = get_balance('IB', ACC_IMP_BYGG)
    ack_uppskr_bygg_ib    = get_balance('IB', {UPSKR_FOND})

    # --- Init totals ---
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

    # --- Per verifikat ---
    for key, txs in trans_by_ver.items():
        A_D  = sum(amt for a,amt in txs if in_building_assets(a) and amt > 0)
        A_K  = sum(-amt for a,amt in txs if in_building_assets(a) and amt < 0)
        F2085_D = sum(amt for a,amt in txs if a == UPSKR_FOND and amt > 0)
        F2085_K = sum(-amt for a,amt in txs if a == UPSKR_FOND and amt < 0)
        DEP_D = sum(amt for a,amt in txs if a in ACC_DEP_BYGG and amt > 0)
        DEP_K = sum(-amt for a,amt in txs if a in ACC_DEP_BYGG and amt < 0)
        IMP_D = sum(amt for a,amt in txs if a in ACC_IMP_BYGG and amt > 0)
        IMP_K = sum(-amt for a,amt in txs if a in ACC_IMP_BYGG and amt < 0)
        has_PL_disposal = any(a in DISPOSAL_PL for a,_ in txs)
        has_depr_cost = any((a in DEPR_COST and amt > 0) for a,amt in txs)
        has_imp_cost  = any((a == IMPAIR_COST and amt > 0) for a,amt in txs)
        has_imp_rev   = any((a == IMPAIR_REV  and amt < 0) for a,amt in txs)

        # 1) AVYTTRING
        is_disposal = (A_K > 0) and (DEP_D > 0 or has_PL_disposal or F2085_D > 0)
        if is_disposal:
            arets_fsg_bygg         += A_K
            aterfor_avskr_fsg_bygg += DEP_D
            aterfor_uppskr_fsg_bygg+= F2085_D
            aterfor_nedskr_fsg_bygg+= IMP_D

        # 2) UPPDELNING av Debet byggnad
        uppskr_amount = min(A_D, F2085_K)
        if uppskr_amount > 0:
            arets_uppskr_bygg += uppskr_amount

        inkop_amount = max(0.0, A_D - uppskr_amount)
        if inkop_amount > 0:
            arets_inkop_bygg += inkop_amount

        # 3) ÅRETS AVSKRIVNINGAR
        if DEP_K > 0 and F2085_D > 0:
            arets_avskr_uppskr_bygg += min(DEP_K, F2085_D)

        if DEP_K > 0 and has_depr_cost and F2085_D == 0:
            arets_avskr_bygg += DEP_K

        # 4) NEDSKRIVNINGAR
        if has_imp_cost and IMP_K > 0:
            arets_nedskr_bygg += sum(amt for a,amt in txs if a == IMPAIR_COST and amt > 0)

        if has_imp_rev and IMP_D > 0 and A_K == 0:
            aterfor_nedskr_bygg += IMP_D

        # 5) OMKLASS
        signals = (F2085_D+F2085_K+DEP_D+DEP_K+IMP_D+IMP_K) > 0 or has_PL_disposal or has_depr_cost or has_imp_cost or has_imp_rev
        if A_D > 0 and A_K > 0 and not signals:
            arets_omklass_bygg += (A_D - A_K)

    # --- UB-formler ---
    bygg_ub = bygg_ib + arets_inkop_bygg - arets_fsg_bygg + arets_omklass_bygg
    ack_avskr_bygg_ub = ack_avskr_bygg_ib + aterfor_avskr_fsg_bygg - arets_avskr_bygg
    ack_uppskr_bygg_ub = ack_uppskr_bygg_ib + arets_uppskr_bygg - arets_avskr_uppskr_bygg - aterfor_uppskr_fsg_bygg
    ack_nedskr_bygg_ub = ack_nedskr_bygg_ib + aterfor_nedskr_fsg_bygg + aterfor_nedskr_bygg - arets_nedskr_bygg

    return {
        "bygg_ib": bygg_ib,
        "arets_inkop_bygg": arets_inkop_bygg,
        "arets_fsg_bygg": arets_fsg_bygg,
        "arets_omklass_bygg": arets_omklass_bygg,
        "bygg_ub": bygg_ub,
        "ack_avskr_bygg_ib": ack_avskr_bygg_ib,
        "aterfor_avskr_fsg_bygg": aterfor_avskr_fsg_bygg,
        "arets_avskr_bygg": arets_avskr_bygg,
        "ack_avskr_bygg_ub": ack_avskr_bygg_ub,
        "ack_uppskr_bygg_ib": ack_uppskr_bygg_ib,
        "arets_uppskr_bygg": arets_uppskr_bygg,
        "arets_avskr_uppskr_bygg": arets_avskr_uppskr_bygg,
        "aterfor_uppskr_fsg_bygg": aterfor_uppskr_fsg_bygg,
        "ack_uppskr_bygg_ub": ack_uppskr_bygg_ub,
        "ack_nedskr_bygg_ib": ack_nedskr_bygg_ib,
        "arets_nedskr_bygg": arets_nedskr_bygg,
        "aterfor_nedskr_bygg": aterfor_nedskr_bygg,
        "aterfor_nedskr_fsg_bygg": aterfor_nedskr_fsg_bygg,
        "ack_nedskr_bygg_ub": ack_nedskr_bygg_ub,
    }
