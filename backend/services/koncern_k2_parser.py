import re
import unicodedata
from collections import defaultdict

ACK_IMP_PAT = re.compile(r'\b(?:ack(?:[.\s]*nedskr\w*)|ackum\w*|nedskriv\w*)\b', re.IGNORECASE)

def parse_koncern_k2_from_sie_text(sie_text: str, preclass_result=None, debug: bool=False, scraper_companies=None) -> dict:
    """
    K2 Koncern note (131x) with correct AV/impairment split, RR share-of-result, and cash payout detection.

    Returns keys compatible with the old note:
      koncern_ib, koncern_ub  (ACQUISITION VALUES ONLY, excludes 1318)
      ack_nedskr_koncern_ib, ack_nedskr_koncern_ub
      arets_nedskr_koncern, aterfor_nedskr_koncern
      arets_resultatandel_koncern  (alias of resultatandel_koncern)
      resultatandel_koncern
      utbetalning_resultatandel_koncern  (cash payout of prior result share via 19xx/131x voucher without 822x/8030/8240)
      red_varde_koncern  (= koncern_ub - abs(ack_nedskr_koncern_ub))
    """
    def _norm(s: str) -> str:
        s = unicodedata.normalize('NFKD', s or '')
        s = ''.join(c for c in s if not unicodedata.combining(c))
        return s.lower().strip()

    def _f(x: str) -> float:
        return float(x.replace(' ', '').replace(',', '.'))

    sie_text = sie_text.replace('\u00A0',' ').replace('\t',' ')
    lines = sie_text.splitlines()

    # Account name map (for impairment text match)
    konto_name = {}
    for ln in lines:
        t = ln.strip()
        if t.startswith("#KONTO"):
            parts = t.split(None, 2)
            if len(parts) >= 3:
                konto_name[parts[1]] = _norm(parts[2].strip('"'))

    def is_impairment_account(acct: str) -> bool:
        if acct == '1318':
            return True
        nm = konto_name.get(acct, '')
        return bool(ACK_IMP_PAT.search(nm))

    def is_share_account(acct: str) -> bool:
        # True for 1310–1319 EXCEPT impairment (1318 / text).
        return acct.startswith('131') and not is_impairment_account(acct)

    # --- balances (IB/UB) ---
    balances = defaultdict(lambda: {'ib': 0.0, 'ub': 0.0})
    for ln in lines:
        t = ln.strip()
        if t.startswith(("#IB", "#UB")):
            parts = t.split()
            if len(parts) >= 4:
                tag, year, acct, amount = parts[0], parts[1], parts[2], _f(parts[3])
                if year in ('0','-1') and (is_share_account(acct) or is_impairment_account(acct)):
                    if tag == "#IB":
                        balances[acct]['ib'] = amount
                    else:
                        balances[acct]['ub'] = amount

    # Acquisition values (exclude impairment)
    koncern_ib = sum(v['ib'] for a,v in balances.items() if is_share_account(a))
    koncern_ub = sum(v['ub'] for a,v in balances.items() if is_share_account(a))

    # Accumulated impairment (1318 etc)
    ack_nedskr_koncern_ib = sum(v['ib'] for a,v in balances.items() if is_impairment_account(a))
    ack_nedskr_koncern_ub = sum(v['ub'] for a,v in balances.items() if is_impairment_account(a))

    # --- movements from #TRANS / #RES ---
    resultatandel_koncern = 0.0
    arets_nedskr_koncern = 0.0
    aterfor_nedskr_koncern = 0.0

    for ln in lines:
        t = ln.strip()
        if t.startswith("#RES") or t.startswith("#TRANS"):
            parts = t.split()
            if len(parts) >= 4:
                acct, amount = parts[2], _f(parts[3])
                # share of result from HB/KB etc.
                if acct in ("8030","8240"):
                    resultatandel_koncern += amount
                # impairment movement on 1318 / text-matched
                if is_impairment_account(acct):
                    if amount > 0:
                        arets_nedskr_koncern += amount
                    else:
                        aterfor_nedskr_koncern += abs(amount)

    # --- detect cash payout of previous year's share (voucher-level) ---
    # Find #VER blocks and classify
    utbetalning_resultatandel_koncern = 0.0
    ver_blocks = re.findall(r'#VER[^\n]*\{(.*?)\}', sie_text, flags=re.DOTALL)
    for block in ver_blocks:
        trans = re.findall(r'#TRANS\s+(\d{3,4})\s+\{\}\s+([-0-9\s,\.]+)', block)
        if not trans:
            continue
        has_822x = False
        has_8030_8240 = False
        credit_131x = 0.0
        debit_19xx  = 0.0
        for acct, amt_s in trans:
            amt = _f(amt_s)
            if acct.startswith('822'):
                has_822x = True
            if acct in ('8030','8240'):
                has_8030_8240 = True
            if acct.startswith('131') and amt < 0:
                credit_131x += abs(amt)
            if acct.startswith('19') and amt > 0:
                debit_19xx += amt
        # Payout voucher: reduce 131x against bank, with no sale/result accounts
        if credit_131x > 0 and debit_19xx > 0 and not has_822x and not has_8030_8240:
            utbetalning_resultatandel_koncern += min(credit_131x, debit_19xx)

    # Redovisat värde: subtract ABS of impairment (impairment often negative in #UB)
    red_varde_koncern = koncern_ub - abs(ack_nedskr_koncern_ub)

    if debug:
        print(f"KONCERN-K2: IB AV={koncern_ib:.2f}, UB AV={koncern_ub:.2f}")
        print(f"KONCERN-K2: IB IMP={ack_nedskr_koncern_ib:.2f}, UB IMP={ack_nedskr_koncern_ub:.2f}")
        print(f"KONCERN-K2: Årets resultatandel={resultatandel_koncern:.2f}, Payout={utbetalning_resultatandel_koncern:.2f}")
        print(f"KONCERN-K2: Redovisat värde={red_varde_koncern:.2f}")

    # expose both new & legacy keys
    return {
        "koncern_ib": koncern_ib,
        "koncern_ub": koncern_ub,
        "ack_nedskr_koncern_ib": ack_nedskr_koncern_ib,
        "ack_nedskr_koncern_ub": ack_nedskr_koncern_ub,
        "arets_nedskr_koncern": arets_nedskr_koncern,
        "aterfor_nedskr_koncern": aterfor_nedskr_koncern,
        "resultatandel_koncern": resultatandel_koncern,
        "arets_resultatandel_koncern": resultatandel_koncern,  # alias for mappings expecting this
        "utbetalning_resultatandel_koncern": utbetalning_resultatandel_koncern,
        "red_varde_koncern": red_varde_koncern,
    }