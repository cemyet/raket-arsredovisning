import re
import unicodedata
from collections import defaultdict

# ---- Regex patterns for precise matching ----
ACK_IMP_PAT = re.compile(r'\b(?:ack(?:[.\s]*nedskr\w*)|ackum\w*|nedskriv\w*)\b', re.IGNORECASE)
FORDR_PAT   = re.compile(r'\b(fordran|fordringar|lan|lån|ranta|ränta|amort|avbetal)\b', re.IGNORECASE)

# ---- Sale P&L accounts for distinguishing real sales from cash settlements ----
SALE_PNL = tuple(range(8220, 8230))  # resultat vid försäljning av andelar (BAS 822x)

def parse_koncern_k2_from_sie_text_original(sie_text: str, debug: bool = True) -> dict:
    """
    ORIGINAL KONCERN-note (K2) parser from before preclass implementation.
    This is the exact version that was working correctly.
    """

    # ---------- Utils ----------
    def _normalize(s: str) -> str:
        """Normalize text for comparison."""
        s = unicodedata.normalize('NFKD', s)
        s = ''.join(c for c in s if not unicodedata.combining(c))
        return s.lower().strip()

    def _to_float(s: str) -> float:
        """Convert string to float, handling Swedish decimal format."""
        return float(s.strip().replace(" ", "").replace(",", "."))

    def _has(text: str, *subs) -> bool:
        return any(sub in text for sub in subs)

    # ---------- Pre-normalize SIE text ----------
    sie_text = sie_text.replace("\u00A0", " ").replace("\t", " ")
    lines = sie_text.splitlines()

    # ---------- Read #KONTO (account names) & #SRU ----------
    konto_name = {}   # acct -> normalized name
    sru_codes = {}    # acct -> sru
    for line in lines:
        line = line.strip()
        if line.startswith("#KONTO"):
            parts = line.split(None, 2)
            if len(parts) >= 3:
                acct = parts[1]
                name = parts[2].strip('"')
                konto_name[acct] = _normalize(name)
        elif line.startswith("#SRU"):
            parts = line.split()
            if len(parts) >= 3:
                acct, sru = parts[1], parts[2]
                sru_codes[acct] = sru

    # ---------- Account classification ----------
    def is_share_account(acct: str) -> bool:
        """Check if account is a share account (not receivables)."""
        if acct in konto_name:
            name = konto_name[acct]
            # Exclude receivables
            if FORDR_PAT.search(name):
                return False
            # Include shares/AAT keywords
            if _has(name, "andel", "aktie", "tillskott", "aat"):
                return True
        # Default ranges
        return acct.startswith("131")

    def is_aat_account(acct: str) -> bool:
        """Check if account is specifically for AAT (aktieägartillskott)."""
        if acct in konto_name:
            name = konto_name[acct]
            if _has(name, "tillskott", "aat"):
                return True
        return False

    def is_impairment_account(acct: str) -> bool:
        """Check if account tracks accumulated impairment."""
        if acct in konto_name:
            name = konto_name[acct]
            if ACK_IMP_PAT.search(name):
                return True
        return acct == "1318"  # Standard accumulated impairment

    # ---------- Parse transactions ----------
    transactions = []
    balances = defaultdict(lambda: {"ib": 0.0, "ub": 0.0})

    for line in lines:
        line = line.strip()
        
        # Parse #IB, #UB, #RES
        if line.startswith(("#IB", "#UB", "#RES")):
            parts = line.split()
            if len(parts) >= 4:
                tag, year, acct, amount = parts[0], parts[1], parts[2], _to_float(parts[3])
                if year in ("0", "-1") and is_share_account(acct):
                    if tag == "#IB":
                        balances[acct]["ib"] = amount
                    elif tag == "#UB":
                        balances[acct]["ub"] = amount
        
        # Parse #TRANS
        elif line.startswith("#TRANS"):
            parts = line.split()
            if len(parts) >= 4:
                acct, amount = parts[2], _to_float(parts[3])
                transactions.append({"account": acct, "amount": amount})

    # ---------- Calculate movements ----------
    if debug:
        print("=== ORIGINAL K2 KONCERN DEBUG ===")
        print(f"Found {len(balances)} accounts with balances:")
        for acct, bal in balances.items():
            if is_share_account(acct):
                print(f"  Account {acct} ({konto_name.get(acct, 'Unknown')}): IB={bal['ib']:.2f}, UB={bal['ub']:.2f}")
        
        print(f"Found {len(transactions)} transactions:")
        for i, trans in enumerate(transactions[:10]):  # Show first 10
            acct = trans["account"]
            print(f"  Trans {i+1}: Account {acct} ({konto_name.get(acct, 'Unknown')}): {trans['amount']:.2f}")
        if len(transactions) > 10:
            print(f"  ... and {len(transactions) - 10} more transactions")

    # IB/UB totals (all share accounts)
    koncern_ib = sum(bal["ib"] for acct, bal in balances.items() if is_share_account(acct))
    koncern_ub = sum(bal["ub"] for acct, bal in balances.items() if is_share_account(acct))
    
    if debug:
        print(f"ORIGINAL: koncern_ib = {koncern_ib:.2f} (sum of IB for share accounts)")
        print(f"ORIGINAL: koncern_ub = {koncern_ub:.2f} (sum of UB for share accounts)")

    # Purchases (positive movements in share accounts, excluding AAT)
    inkop_koncern = 0.0
    purchase_details = []
    for trans in transactions:
        acct = trans["account"]
        if is_share_account(acct) and not is_aat_account(acct) and trans["amount"] > 0:
            inkop_koncern += trans["amount"]
            purchase_details.append(f"Account {acct} ({konto_name.get(acct, 'Unknown')}): +{trans['amount']:.2f}")
    
    if debug:
        print(f"ORIGINAL: inkop_koncern = {inkop_koncern:.2f}")
        if purchase_details:
            print("  Purchase details:")
            for detail in purchase_details:
                print(f"    {detail}")
        else:
            print("  No purchases found")

    # Sales (negative movements in share accounts with P&L accounts)
    fsg_koncern = 0.0
    sale_accounts = set()
    for trans in transactions:
        acct = trans["account"]
        if acct.startswith("822") and int(acct) in SALE_PNL:
            sale_accounts.add(acct)
    
    if sale_accounts:
        for trans in transactions:
            acct = trans["account"]
            if is_share_account(acct) and not is_aat_account(acct) and trans["amount"] < 0:
                fsg_koncern += abs(trans["amount"])

    # AAT movements
    aktieagartillskott_lamnad_koncern = 0.0
    aktieagartillskott_aterbetald_koncern = 0.0
    for trans in transactions:
        acct = trans["account"]
        if is_aat_account(acct):
            if trans["amount"] > 0:
                aktieagartillskott_lamnad_koncern += trans["amount"]
            else:
                aktieagartillskott_aterbetald_koncern += abs(trans["amount"])

    # Result share (from 8030/8240 accounts)
    resultatandel_koncern = 0.0
    for trans in transactions:
        acct = trans["account"]
        if acct in ("8030", "8240"):
            resultatandel_koncern += trans["amount"]

    # Impairment calculations
    ack_nedskr_koncern_ib = sum(bal["ib"] for acct, bal in balances.items() if is_impairment_account(acct))
    ack_nedskr_koncern_ub = sum(bal["ub"] for acct, bal in balances.items() if is_impairment_account(acct))
    
    arets_nedskr_koncern = 0.0
    aterfor_nedskr_koncern = 0.0
    for trans in transactions:
        acct = trans["account"]
        if is_impairment_account(acct):
            if trans["amount"] > 0:
                arets_nedskr_koncern += trans["amount"]
            else:
                aterfor_nedskr_koncern += abs(trans["amount"])

    # Other movements (fusion, reclassification)
    fusion_koncern = 0.0
    omklass_koncern = 0.0
    aterfor_nedskr_fsg_koncern = 0.0
    aterfor_nedskr_fusion_koncern = 0.0
    omklass_nedskr_koncern = 0.0

    # Derived value
    red_varde_koncern = koncern_ub - ack_nedskr_koncern_ub

    if debug:
        print(f"ORIGINAL: red_varde_koncern = {red_varde_koncern:.2f} (koncern_ub - ack_nedskr_koncern_ub)")
        print("=== ORIGINAL K2 KONCERN FINAL RESULTS ===")
        print(f"  koncern_ib: {koncern_ib:.2f}")
        print(f"  koncern_ub: {koncern_ub:.2f}")
        print(f"  inkop_koncern: {inkop_koncern:.2f}")
        print(f"  red_varde_koncern: {red_varde_koncern:.2f}")
        print("=== END ORIGINAL DEBUG ===")

    return {
        # Asset movements
        "koncern_ib": koncern_ib,
        "inkop_koncern": inkop_koncern,
        "fusion_koncern": fusion_koncern,
        "aktieagartillskott_lamnad_koncern": aktieagartillskott_lamnad_koncern,
        "aktieagartillskott_aterbetald_koncern": aktieagartillskott_aterbetald_koncern,
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
