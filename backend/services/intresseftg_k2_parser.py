import re
import unicodedata
from collections import defaultdict

# ------------------ utils ------------------
def _norm(s: str) -> str:
    """Normalize names: strip diacritics, lower, keep [a-z0-9 ] only, collapse spaces."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("\u00A0", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _to_float(s: str) -> float:
    return float((s or "0").strip().replace(" ", "").replace(",", "."))

# ---------- discovery step: build dynamic 133x sets ----------
def discover_equity_account_map_for_range_133x(sie_text: str):
    """
    Scan #KONTO/#SRU in 1330–1339 and classify accounts into:
      - ASSET: investment cost accounts (andelar)
      - ACC_IMP: accumulated impairment accounts
      - CONTRIB: aktieägartillskott accounts (company-specific)
    Uses robust name matching and SRU hints (if present).
    """
    lines = sie_text.splitlines()
    konto_re = re.compile(r'^#KONTO\s+(\d{4})\s+"(.*)"')
    sru_re   = re.compile(r'^#SRU\s+(\d{4})\s+(\d+)')
    name_by_acc, sru_by_acc = {}, {}

    for raw in lines:
        t = raw.strip()
        mk = konto_re.match(t)
        if mk:
            acc = int(mk.group(1))
            if 1330 <= acc <= 1339:
                name_by_acc[acc] = mk.group(2)
            continue
        ms = sru_re.match(t)
        if ms:
            acc = int(ms.group(1))
            if 1330 <= acc <= 1339:
                sru_by_acc[acc] = int(ms.group(2))

    # Defaults (BAS)
    default_asset  = {1330, 1331, 1333, 1336}
    default_accimp = {1332, 1334, 1337, 1338}

    # Keywords for contribution accounts (expanded)
    kw_contrib = ("tillsk", "tillskott", "aktieagartillskott", "aktieägartillskott", "aktieagar", "agartillskott", "agartill")
    def is_imp_text(nm: str) -> bool:
        """More precise impairment detection - require 'nedskr' or 'ackum', not bare 'ack'"""
        nm = _norm(nm)
        return ("nedskr" in nm) or ("ackum" in nm) or ("vardened" in nm) or ("v neds" in nm)

    ASSET, ACC_IMP, CONTRIB = set(), set(), set()

    for acc in range(1330, 1340):
        nm = _norm(name_by_acc.get(acc, ""))
        sru = sru_by_acc.get(acc)

        is_contrib = any(k in nm for k in kw_contrib)
        is_imp_txt = is_imp_text(nm)
        # weak hint: 72xx often used around impairment mappings in some charts
        is_imp_sru = (sru is not None and 7200 <= sru < 7300)

        if acc not in name_by_acc:
            # fallback BAS role
            (ACC_IMP if acc in default_accimp else ASSET).add(acc)
            continue

        if is_contrib:
            CONTRIB.add(acc)
        elif is_imp_txt or is_imp_sru or acc in default_accimp:
            ACC_IMP.add(acc)
        else:
            ASSET.add(acc)

    # Ensure contributions never counted as ASSET
    ASSET -= CONTRIB
    return {"ASSET": ASSET, "ACC_IMP": ACC_IMP, "CONTRIB": CONTRIB, "names": name_by_acc, "sru": sru_by_acc}

def _get_balance(lines, kind_flag: str, accounts: set[int]) -> float:
    total = 0.0
    bal_re = re.compile(rf'^#(?:{kind_flag})\s+0\s+(\d+)\s+(-?[0-9][0-9\s.,]*)(?:\s+.*)?$')
    for raw in lines:
        m = bal_re.match(raw.strip())
        if not m: 
            continue
        acct = int(m.group(1))
        if acct in accounts:
            total += _to_float(m.group(2))
    return total

def _parse_vouchers(lines):
    ver_header_re = re.compile(r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"([^"]*)"|.+))?\s*$')
    trans_re = re.compile(
        r'^#(?:BTRANS|RTRANS|TRANS)\s+'
        r'(\d{3,4})'
        r'(?:\s+\{.*?\})?'
        r'\s+(-?(?:\d{1,3}(?:[ \u00A0]?\d{3})*|\d+)(?:[.,]\d+)?)'
        r'(?:\s+\d{8})?'
        r'(?:\s+"(.*?)")?'
        r'\s*$'
    )
    trans_by_ver = defaultdict(list)
    text_by_ver = {}
    cur = None; in_block = False
    for raw in lines:
        t = raw.strip()
        mh = ver_header_re.match(t)
        if mh:
            cur = (mh.group(1), int(mh.group(2)))
            text_by_ver[cur] = (mh.group(4) or "").lower()
            continue
        if t == "{": in_block = True;  continue
        if t == "}": in_block = False; cur = None; continue
        if in_block and cur:
            mt = trans_re.match(t)
            if mt:
                acct = int(mt.group(1))
                amt  = _to_float(mt.group(2))
                trans_by_ver[cur].append((acct, amt))
    return trans_by_ver, text_by_ver

def parse_intresseftg_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    K2 – Andelar i intresseföretag / gemensamt styrda / övriga (1330–1339)
    
    ENHANCED FEATURES:
    1. Dynamic account discovery via #KONTO text analysis
    2. Multiple result share accounts: 8130, 8131, 8132, 8240
    3. HB/KB two-step flow handling with sale P&L validation
    4. Uses actual #UB values from SIE (policy decision)
    5. Separate AAT handling (CONTRIB accounts within 133x range)
    
    ACCOUNT CLASSIFICATION:
    • ASSET: investment cost accounts (andelar) - dynamic + defaults 1330,1331,1333,1336
    • ACC_IMP: accumulated impairment - dynamic + defaults 1332,1334,1337,1338
    • CONTRIB: aktieägartillskott within 133x range (company-specific discovery)
    
    RESULT SHARE ACCOUNTS:
    • 8130, 8131, 8132: Specific associate/joint venture result accounts
    • 8240: General "other companies" result account
    
    SALE P&L ACCOUNTS: 8120, 8121, 8122, 8221
    
    BEHAVIOR:
    • HB/KB cash settlements (K 133x + only bank, no sale P&L) → negative result share
    • Real sales require presence of sale P&L account (812x/8221)
    • AAT flows handled separately from sales
    • Sophisticated impairment detection
    """
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # Discover actual account sets
    m = discover_equity_account_map_for_range_133x(sie_text)
    ASSET_SET   = m["ASSET"]
    CONTRIB_SET = m["CONTRIB"]
    ACC_IMP_SET = m["ACC_IMP"]

    if debug:
        print(f"DEBUG INTRESSEFTG: ASSET={sorted(ASSET_SET)} CONTRIB={sorted(CONTRIB_SET)} ACC_IMP={sorted(ACC_IMP_SET)}")

    # IB / UB (from SIE)
    intresseftg_ib            = _get_balance(lines, 'IB', ASSET_SET | CONTRIB_SET)
    ack_nedskr_intresseftg_ib = _get_balance(lines, 'IB', ACC_IMP_SET)

    # factual UB (USED for final results)
    cost_ub_actual = _get_balance(lines, 'UB', ASSET_SET | CONTRIB_SET)
    ack_ub_actual  = _get_balance(lines, 'UB', ACC_IMP_SET)

    # Accumulators (flows)
    inkop_intresseftg                         = 0.0
    fusion_intresseftg                        = 0.0
    fsg_intresseftg                           = 0.0  # negative
    aktieagartillskott_lamnad_intresseftg     = 0.0
    aktieagartillskott_aterbetald_intresseftg = 0.0
    resultatandel_intresseftg                 = 0.0
    omklass_intresseftg                       = 0.0

    arets_nedskr_intresseftg                  = 0.0
    aterfor_nedskr_intresseftg                = 0.0
    aterfor_nedskr_fsg_intresseftg            = 0.0
    aterfor_nedskr_fusion_intresseftg         = 0.0
    omklass_nedskr_intresseftg                = 0.0

    # --- CONFIG: Result share accounts for associate/joint venture structures ---
    RES_SHARE_SET = {8130, 8131, 8132, 8240}  # Multiple result share accounts
    # 8130, 8131, 8132 = Specific associate/joint venture result accounts
    # 8240 = General "other companies" result account
    
    SALE_PNL_SET = {8120, 8121, 8122, 8221}   # Disposal P&L accounts
    # 8120, 8121, 8122 = Specific disposal P&L for associates/joint ventures
    # 8221 = General disposal P&L
    
    def _is_bank(a: int) -> bool:
        return 1900 <= a <= 1999

    # Parse vouchers
    trans_by_ver, text_by_ver = _parse_vouchers(lines)

    for key, txs in trans_by_ver.items():
        text = (text_by_ver.get(key, "") or "").lower()

        A_D  = sum(amt  for a,amt in txs if a in ASSET_SET   and amt > 0)
        A_K  = sum(-amt for a,amt in txs if a in ASSET_SET   and amt < 0)
        C_D  = sum(amt  for a,amt in txs if a in CONTRIB_SET and amt > 0)
        C_K  = sum(-amt for a,amt in txs if a in CONTRIB_SET and amt < 0)

        IMP_D = sum(amt  for a,amt in txs if a in ACC_IMP_SET and amt > 0)   # reversal
        IMP_K = sum(-amt for a,amt in txs if a in ACC_IMP_SET and amt < 0)   # new impair

        RES_K = sum(-amt for a,amt in txs if a in RES_SHARE_SET and amt < 0) # |K 813x/8240|
        RES_D = sum(amt  for a,amt in txs if a in RES_SHARE_SET and amt > 0) # D 813x/8240

        if debug and (A_D > 0 or A_K > 0 or C_D > 0 or C_K > 0 or RES_K > 0 or RES_D > 0 or IMP_D > 0 or IMP_K > 0):
            print(f"DEBUG INTRESSEFTG {key}: A_D={A_D}, A_K={A_K}, C_D={C_D}, C_K={C_K}, RES_K={RES_K}, RES_D={RES_D}, IMP_D={IMP_D}, IMP_K={IMP_K}, text='{text}'")

        # Resultatandel (signed)
        res_plus  = min(A_D, RES_K) if (A_D > 0 and RES_K > 0) else 0.0
        res_minus = min(A_K, RES_D) if (A_K > 0 and RES_D > 0) else 0.0
        resultatandel_intresseftg += (res_plus - res_minus)

        if debug and (res_plus > 0 or res_minus > 0):
            print(f"DEBUG INTRESSEFTG {key}: resultatandel += {res_plus - res_minus} (res_plus={res_plus}, res_minus={res_minus})")

        # Inköp (remaining D asset after res_plus)
        inc_amount = max(0.0, A_D - res_plus)
        if inc_amount > 0:
            if "fusion" in text:
                fusion_intresseftg += inc_amount
                if debug:
                    print(f"DEBUG INTRESSEFTG {key}: fusion += {inc_amount}")
            else:
                inkop_intresseftg += inc_amount
                if debug:
                    print(f"DEBUG INTRESSEFTG {key}: inkop += {inc_amount}")

        # AAT flows (separate from sales)
        if C_D > 0:
            aktieagartillskott_lamnad_intresseftg += C_D
            if debug:
                print(f"DEBUG INTRESSEFTG {key}: aktieägartillskott_lämnad += {C_D}")
        if C_K > 0:
            aktieagartillskott_aterbetald_intresseftg += C_K
            if debug:
                print(f"DEBUG INTRESSEFTG {key}: aktieägartillskott_återbetald += {C_K}")

        # Försäljning av andelar – HB/KB two-step flow handling
        rem_andel_K = max(0.0, A_K - res_minus)
        if rem_andel_K > 0:
            # Check for sale P&L accounts to distinguish real sales from cash settlements
            has_sale_pnl = any(a in SALE_PNL_SET for a,_ in txs)
            
            # Analyze other accounts (not shares, contrib, impairment, or result share)
            other_accts = {a for a,_ in txs if a not in ASSET_SET and a not in CONTRIB_SET and a not in ACC_IMP_SET and a not in RES_SHARE_SET}
            only_banks  = len(other_accts) > 0 and all(_is_bank(a) for a in other_accts)
            bank_debet  = sum(amt for a,amt in txs if amt > 0 and _is_bank(a))
            
            # Text analysis for transaction type
            kw_sale       = any(k in text for k in ("försälj", "avyttr", "sale"))
            kw_settlement = any(k in text for k in ("utbet", "utbetal", "kap andel", "resultatandel", "kb", "hb", "kommandit", "handelsbolag"))
            
            if has_sale_pnl:
                # ✅ Real sale (requires 812x/8221 P&L account)
                if IMP_D > 0:
                    aterfor_nedskr_fsg_intresseftg += IMP_D
                    IMP_D = 0.0
                    if debug:
                        print(f"DEBUG INTRESSEFTG {key}: aterfor_nedskr_fsg += {IMP_D} (real sale)")
                fsg_intresseftg -= rem_andel_K  # negative by convention
                if debug:
                    print(f"DEBUG INTRESSEFTG {key}: fsg -= {rem_andel_K} (real sale)")
            else:
                # No sale P&L – likely HB/KB cash settlement
                is_payout_prior_share = (
                    RES_D == 0 and RES_K == 0 and IMP_D == 0 and IMP_K == 0
                    and only_banks and abs(bank_debet - rem_andel_K) < 0.5
                    and (kw_settlement or not kw_sale)
                )
                
                if is_payout_prior_share:
                    # Book as negative result share (cash settlement of prior-year partnership share)
                    resultatandel_intresseftg -= rem_andel_K
                    if debug:
                        print(f"DEBUG INTRESSEFTG {key}: resultatandel -= {rem_andel_K} (HB/KB cash settlement)")
                elif kw_sale:
                    # Fallback: text explicitly indicates sale despite missing P&L
                    fsg_intresseftg -= rem_andel_K
                    if debug:
                        print(f"DEBUG INTRESSEFTG {key}: fsg -= {rem_andel_K} (sale by text)")
                else:
                    # Conservative default: treat as cash settlement
                    resultatandel_intresseftg -= rem_andel_K
                    if debug:
                        print(f"DEBUG INTRESSEFTG {key}: resultatandel -= {rem_andel_K} (default: cash settlement)")

        # Nedskrivningar / återföringar (ej försäljning)
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

        # Omklass (assets) – enkel heuristik
        asset_signals = (RES_K > 0 or RES_D > 0 or IMP_D > 0 or IMP_K > 0 or C_D > 0 or C_K > 0)
        if A_D > 0 and A_K > 0 and not asset_signals:
            omklass_intresseftg += (A_D - A_K)
            if debug:
                print(f"DEBUG INTRESSEFTG {key}: omklass += {A_D - A_K}")
        # Omklass ack nedskr (sällsynt)
        if sum(amt for a,amt in txs if a in ACC_IMP_SET and amt > 0) > 0 and \
           sum(-amt for a,amt in txs if a in ACC_IMP_SET and amt < 0) > 0 and \
           not (A_D > 0 or A_K > 0 or RES_K > 0 or RES_D > 0 or C_D > 0 or C_K > 0):
            omklass_nedskr_intresseftg += (IMP_D - IMP_K)
            if debug:
                print(f"DEBUG INTRESSEFTG {key}: omklass_nedskr += {IMP_D - IMP_K}")

    # ---- Final UB from SIE (#UB) as per policy ----
    intresseftg_ub = cost_ub_actual
    ack_nedskr_intresseftg_ub = ack_ub_actual

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
        # Cost roll-forward
        "intresseftg_ib": intresseftg_ib,
        "inkop_intresseftg": inkop_intresseftg,
        "fusion_intresseftg": fusion_intresseftg,
        "fsg_intresseftg": fsg_intresseftg,
        "aktieagartillskott_lamnad_intresseftg": aktieagartillskott_lamnad_intresseftg,
        "aktieagartillskott_aterbetald_intresseftg": aktieagartillskott_aterbetald_intresseftg,
        "resultatandel_intresseftg": resultatandel_intresseftg,
        "omklass_intresseftg": omklass_intresseftg,
        "intresseftg_ub": intresseftg_ub,

        # Impairments
        "ack_nedskr_intresseftg_ib": ack_nedskr_intresseftg_ib,
        "aterfor_nedskr_fsg_intresseftg": aterfor_nedskr_fsg_intresseftg,
        "aterfor_nedskr_fusion_intresseftg": aterfor_nedskr_fusion_intresseftg,
        "aterfor_nedskr_intresseftg": aterfor_nedskr_intresseftg,
        "omklass_nedskr_intresseftg": omklass_nedskr_intresseftg,
        "arets_nedskr_intresseftg": arets_nedskr_intresseftg,
        "ack_nedskr_intresseftg_ub": ack_nedskr_intresseftg_ub,

        # Book value
        "red_varde_intresseftg": red_varde_intresseftg,
    }
