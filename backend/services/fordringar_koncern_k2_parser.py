import re
import unicodedata
from collections import defaultdict

def parse_fordringar_koncern_k2_from_sie_text(sie_text: str, debug: bool = False) -> dict:
    """
    FORDRINGAR KONCERN-note (K2) parser — Långfristiga fordringar hos koncernföretag
    
    Handles long-term receivables from group companies with the following business rules:
    
    Inclusion filter:
      • Include ONLY accounts in 1320–1327 WITH SRU = 7232
      • EXCLUDE from assets if account name contains both an 'ack*' token AND a 'ned*' token
        (e.g., 'Ack nedskrivningar ...').
    
    Impairment accounts:
      • 1328 (primary impairment account)
      • Any 132x whose name clearly says 'nedskr' or 'ackum'
    
    AAT/andelar misposts in 132x are excluded from this parser.
    
    Returns dict with cost roll-forward, impairment movements, and book value calculations.
    """
    
    # ---------- Helper functions ----------
    def _normalize(s: str) -> str:
        """Normalize string for text matching"""
        if not s:
            return ""
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = s.lower().replace("\u00a0", " ").replace("\t", " ")
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _to_float(s: str) -> float:
        """Convert string to float, handling spaces and commas"""
        return float((s or "0").replace(" ", "").replace(",", "."))

    def _parse_accounts_and_sru(sie_text: str):
        """Parse account names and SRU codes from SIE text"""
        names, sru = {}, {}
        rx_konto = re.compile(r'^#KONTO\s+(\d{4})\s+"(.*)"\s*$')
        rx_sru   = re.compile(r'^#SRU\s+(\d{4})\s+(\d+)\s*$')
        
        for raw in sie_text.splitlines():
            t = raw.strip()
            mk = rx_konto.match(t)
            if mk:
                names[int(mk.group(1))] = _normalize(mk.group(2))
                continue
            ms = rx_sru.match(t)
            if ms:
                sru[int(ms.group(1))] = int(ms.group(2))
        return names, sru

    def _get_balance(lines, kind_flag: str, accounts: set) -> float:
        """Get IB or UB balance for specified accounts"""
        if not accounts: 
            return 0.0
        rx = re.compile(rf'^#(?:{kind_flag})\s+0\s+(\d+)\s+(-?[0-9][0-9\s.,]*)')
        acct_set = set(accounts)
        tot = 0.0
        for raw in lines:
            m = rx.match(raw.strip())
            if not m: 
                continue
            a = int(m.group(1))
            if a in acct_set:
                tot += _to_float(m.group(2))
        return tot

    def _parse_vouchers(lines):
        """Parse vouchers from SIE lines"""
        rx_ver = re.compile(r'^#VER\s+(\S+)\s+(\d+)\s+(\d{8})(?:\s+(?:"([^"]*)"|.+))?\s*$')
        rx_tx  = re.compile(
            r'^#(?:BTRANS|RTRANS|TRANS)\s+'
            r'(\d{3,4})(?:\s+\{.*?\})?\s+'
            r'(-?(?:\d{1,3}(?:[ \u00A0]?\d{3})*|\d+)(?:[.,]\d+)?)'
            r'(?:\s+\d{8})?(?:\s+".*?")?\s*$'
        )
        trans_by_ver = defaultdict(list)
        text_by_ver = {}
        cur = None
        in_block = False
        
        for raw in lines:
            t = raw.strip()
            mh = rx_ver.match(t)
            if mh:
                cur = (mh.group(1), int(mh.group(2)))
                text_by_ver[cur] = _normalize(mh.group(4) or "")
                continue
            if t == "{": 
                in_block = True
                continue
            if t == "}": 
                in_block = False
                cur = None
                continue
            if in_block and cur:
                mt = rx_tx.match(t)
                if mt:
                    trans_by_ver[cur].append((int(mt.group(1)), _to_float(mt.group(2))))
        return trans_by_ver, text_by_ver

    # ---------- Main parsing logic ----------
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # Parse accounts and SRU codes
    names, sru = _parse_accounts_and_sru(sie_text)

    # Name detectors (on normalized text)
    ACK_TOK = re.compile(r'\b(?:ack\w*|ackum\w*)\b')
    NED_TOK = re.compile(r'\b(?:nedskr\w*|vardened\w*)\b')
    
    def has_ack_and_ned(nm: str) -> bool:
        return bool(ACK_TOK.search(nm)) and bool(NED_TOK.search(nm))

    def is_aat_name(nm: str) -> bool:
        return any(k in nm for k in ("aktieagartillskott", "aktieagar", "agartillskott", "villkorat", "ovillkorat"))
    
    def is_share_name(nm: str) -> bool:
        return ("koncern" in nm or "dotter" in nm) and any(k in nm for k in ("andel", "aktie"))
    
    def is_imp_name(nm: str) -> bool:
        return ("nedskr" in nm) or ("ackum" in nm)

    # Asset set: 1320–1327 with SRU 7232, excluding AAT/andelar and names with *both* ack+ned tokens
    ASSET_SET = set()
    for a in range(1320, 1328):  # 1320–1327 inclusive
        if sru.get(a) == 7232:
            nm = names.get(a, "")
            if not is_aat_name(nm) and not is_share_name(nm) and not has_ack_and_ned(nm):
                ASSET_SET.add(a)

    # Impairment set: 1328 + any 132x with nedskr/ackum in name
    IMP_SET = {1328}
    for a, nm in names.items():
        if 1320 <= a <= 1329 and a != 1328 and is_imp_name(nm):
            IMP_SET.add(a)

    if debug:
        print(f"[FORDRKONC] ASSET_SET={sorted(ASSET_SET)} IMP_SET={sorted(IMP_SET)} (SRU=7232; excluding ack+ned names)")

    # Get IB/UB factual balances
    fordr_koncern_ib = _get_balance(lines, "IB", ASSET_SET)
    ack_nedskr_fordr_koncern_ib = _get_balance(lines, "IB", IMP_SET)
    fordr_koncern_ub_actual = _get_balance(lines, "UB", ASSET_SET)
    ack_nedskr_fordr_koncern_ub_act = _get_balance(lines, "UB", IMP_SET)

    # Initialize flow accumulators
    nya_fordr_koncern = 0.0
    fusion_fordr_koncern = 0.0
    reglerade_fordr_koncern = 0.0
    bortskrivna_fordr_koncern = 0.0
    omklass_fordr_koncern = 0.0

    aterfor_nedskr_reglerade_fordr_koncern = 0.0
    aterfor_nedskr_fusion_fordr_koncern = 0.0
    aterfor_nedskr_bortskrivna_fordr_koncern = 0.0
    aterfor_nedskr_fordr_koncern = 0.0  # General reversal bucket
    omklass_nedskr_fordr_koncern = 0.0
    arets_nedskr_fordr_koncern = 0.0

    # Classification helpers
    def _is_bank(a: int) -> bool:    
        return 1900 <= a <= 1999
    
    def _is_st_ic(a: int) -> bool:   
        return 1680 <= a <= 1689   # kortfristiga fordr hos koncern
    
    def _is_expense(a: int) -> bool: 
        return 6000 <= a <= 8999 and not (8120 <= a <= 8139 or a in (8240,))

    # Parse vouchers
    trans_by_ver, text_by_ver = _parse_vouchers(lines)

    # Classify each voucher
    for key, txs in trans_by_ver.items():
        text = text_by_ver.get(key, "")

        R_D = sum(amt  for a, amt in txs if a in ASSET_SET and amt > 0)
        R_K = sum(-amt for a, amt in txs if a in ASSET_SET and amt < 0)

        IMP_D = sum(amt  for a, amt in txs if a in IMP_SET and amt > 0)   # reversal
        IMP_K = sum(-amt for a, amt in txs if a in IMP_SET and amt < 0)   # new impairment

        other = {a for a, _ in txs if a not in ASSET_SET and a not in IMP_SET}
        only_bank_or_stic = len(other) > 0 and all(_is_bank(a) or _is_st_ic(a) for a in other)
        any_expense = any(_is_expense(a) for a, _ in txs)
        is_fusion = ("fusion" in text)
        is_writeoff = any(k in text for k in ("bortskriv", "avskriv", "efterskank")) or any_expense

        # 1) New receivables / fusion (debet)
        if R_D > 0:
            if is_fusion:
                fusion_fordr_koncern += R_D
            else:
                nya_fordr_koncern += R_D

        # 2) Credits on receivables → classify
        if R_K > 0:
            if is_writeoff:
                bortskrivna_fordr_koncern += R_K
                if IMP_D > 0:
                    aterfor_nedskr_bortskrivna_fordr_koncern += IMP_D
                    IMP_D = 0.0
            elif is_fusion:
                reglerade_fordr_koncern += R_K  # fusion outflow counts as regulated
                if IMP_D > 0:
                    aterfor_nedskr_fusion_fordr_koncern += IMP_D
                    IMP_D = 0.0
            elif only_bank_or_stic:
                reglerade_fordr_koncern += R_K
                if IMP_D > 0:
                    aterfor_nedskr_reglerade_fordr_koncern += IMP_D
                    IMP_D = 0.0
            else:
                # No clear signal → treat as reclassification
                if R_D > 0:
                    omklass_fordr_koncern += (R_D - R_K)
                else:
                    omklass_fordr_koncern -= R_K

        # 3) Remaining impairment not tied above
        if IMP_D > 0:
            # generic reversal not linked to settlement / fusion / write-off
            aterfor_nedskr_fordr_koncern += IMP_D
            IMP_D = 0.0
        if IMP_K > 0:
            arets_nedskr_fordr_koncern += IMP_K

        # 4) Omklass av ack nedskr (båda sidor på 1328/IMP_SET i samma verifikat utan asset-signal)
        imp_d_orig = sum(amt  for a, amt in txs if a in IMP_SET and amt > 0)
        imp_k_orig = sum(-amt for a, amt in txs if a in IMP_SET and amt < 0)
        if imp_d_orig > 0 and imp_k_orig > 0 and R_D == 0 and R_K == 0:
            omklass_nedskr_fordr_koncern += (imp_d_orig - imp_k_orig)

    # Calculate UB/Book value (prefer factual UB from SIE)
    fordr_koncern_ub = fordr_koncern_ub_actual
    ack_nedskr_fordr_koncern_ub = (
        ack_nedskr_fordr_koncern_ib
        - arets_nedskr_fordr_koncern
        + aterfor_nedskr_reglerade_fordr_koncern
        + aterfor_nedskr_fusion_fordr_koncern
        + aterfor_nedskr_bortskrivna_fordr_koncern
        + aterfor_nedskr_fordr_koncern
        + omklass_nedskr_fordr_koncern
    )
    
    # If SIE has UB on 1328, prefer factual UB value
    if ack_nedskr_fordr_koncern_ub_act or ack_nedskr_fordr_koncern_ub_act == 0.0:
        ack_nedskr_fordr_koncern_ub = ack_nedskr_fordr_koncern_ub_act

    red_varde_fordr_koncern = fordr_koncern_ub + ack_nedskr_fordr_koncern_ub

    if debug:
        print(f"[FORDRKONC] IB={fordr_koncern_ib} UB={fordr_koncern_ub} AIB={ack_nedskr_fordr_koncern_ib} AUB={ack_nedskr_fordr_koncern_ub}")
        print(f"[FORDRKONC] +nya={nya_fordr_koncern} +fusion={fusion_fordr_koncern} -reglerade={reglerade_fordr_koncern} -bortskr={bortskrivna_fordr_koncern} ±omklass={omklass_fordr_koncern}")
        print(f"[FORDRKONC] nedskr: år={arets_nedskr_fordr_koncern} återf(reg)={aterfor_nedskr_reglerade_fordr_koncern} återf(fusion)={aterfor_nedskr_fusion_fordr_koncern} återf(bortskr)={aterfor_nedskr_bortskrivna_fordr_koncern} återf(övrigt)={aterfor_nedskr_fordr_koncern} omklass={omklass_nedskr_fordr_koncern}")
        print(f"[FORDRKONC] red_värde={red_varde_fordr_koncern}")

    return {
        # Cost roll-forward
        "fordr_koncern_ib": fordr_koncern_ib,
        "nya_fordr_koncern": nya_fordr_koncern,
        "fusion_fordr_koncern": fusion_fordr_koncern,
        "reglerade_fordr_koncern": reglerade_fordr_koncern,
        "bortskrivna_fordr_koncern": bortskrivna_fordr_koncern,
        "omklass_fordr_koncern": omklass_fordr_koncern,
        "fordr_koncern_ub": fordr_koncern_ub,

        # Impairments
        "ack_nedskr_fordr_koncern_ib": ack_nedskr_fordr_koncern_ib,
        "aterfor_nedskr_reglerade_fordr_koncern": aterfor_nedskr_reglerade_fordr_koncern,
        "aterfor_nedskr_fusion_fordr_koncern": aterfor_nedskr_fusion_fordr_koncern,
        "aterfor_nedskr_bortskrivna_fordr_koncern": aterfor_nedskr_bortskrivna_fordr_koncern,
        "aterfor_nedskr_fordr_koncern": aterfor_nedskr_fordr_koncern,
        "omklass_nedskr_fordr_koncern": omklass_nedskr_fordr_koncern,
        "arets_nedskr_fordr_koncern": arets_nedskr_fordr_koncern,
        "ack_nedskr_fordr_koncern_ub": ack_nedskr_fordr_koncern_ub,

        # Book value
        "red_varde_fordr_koncern": red_varde_fordr_koncern,
    }
