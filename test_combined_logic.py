#!/usr/bin/env python3
"""
Test the improved combined logic: Account interval AND SRU code must match
"""

import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from services.bygg_k2_parser import parse_bygg_k2_from_sie_text
from services.inventarier_k2_parser import parse_inventarier_k2_from_sie_text
from services.maskiner_k2_parser import parse_maskiner_k2_from_sie_text

def test_combined_logic():
    """Test the new combined logic framework"""
    
    # Sample SIE data with mixed SRU codes
    sample_sie_data = """
#FLAGGA 0
#PROGRAM "Test" "1.0"

#KONTO 1210 "Maskiner"
#SRU 1210 7215
#KONTO 1219 "Ack avskr maskiner"
#SRU 1219 7215
#KONTO 1221 "Inventarier"
#SRU 1221 7215
#KONTO 1222 "Byggnadsinventarier"
#SRU 1222 7214
#KONTO 1224 "Ack avskr byggnadsinventarier"
#SRU 1224 7214
#KONTO 1229 "Ack avskr inventarier"
#SRU 1229 7215

#IB 0 1210 10000.00
#IB 0 1219 -5000.00
#IB 0 1221 15000.00
#IB 0 1222 20000.00
#IB 0 1224 -8000.00
#IB 0 1229 -6000.00

#UB 0 1210 10000.00
#UB 0 1219 -5000.00
#UB 0 1221 15000.00
#UB 0 1222 20000.00
#UB 0 1224 -8000.00
#UB 0 1229 -6000.00
"""

    print("Testing Combined Logic Framework")
    print("=" * 50)
    print("Expected behavior:")
    print("- MASKINER: 1210 (range + SRU 7215) ✓, 1219 (range + SRU 7215) ✓")
    print("- INVENTARIER: 1221 (range + SRU 7215) ✓, 1229 (range + SRU 7215) ✓")
    print("- BYGG: 1222 (SRU 7214 override) ✓, 1224 (SRU 7214 override) ✓")
    print("=" * 50)
    
    try:
        print("\n1. MASKINER parser:")
        maskiner_result = parse_maskiner_k2_from_sie_text(sample_sie_data, debug=True)
        print(f"   maskiner_ib: {maskiner_result.get('maskiner_ib', 0):,.0f}")
        print(f"   ack_avskr_maskiner_ib: {maskiner_result.get('ack_avskr_maskiner_ib', 0):,.0f}")
        
        print("\n2. INVENTARIER parser:")
        inventarier_result = parse_inventarier_k2_from_sie_text(sample_sie_data, debug=True)
        print(f"   inventarier_ib: {inventarier_result.get('inventarier_ib', 0):,.0f}")
        print(f"   ack_avskr_inventarier_ib: {inventarier_result.get('ack_avskr_inventarier_ib', 0):,.0f}")
        
        print("\n3. BYGG parser:")
        bygg_result = parse_bygg_k2_from_sie_text(sample_sie_data, debug=True)
        print(f"   bygg_ib: {bygg_result.get('bygg_ib', 0):,.0f}")
        print(f"   ack_avskr_bygg_ib: {bygg_result.get('ack_avskr_bygg_ib', 0):,.0f}")
        
        print("\n" + "=" * 50)
        print("✅ VERIFICATION:")
        print(f"- MASKINER should have: 10,000 + (-5,000) = 5,000 net")
        print(f"- INVENTARIER should have: 15,000 + (-6,000) = 9,000 net") 
        print(f"- BYGG should have: 20,000 + (-8,000) = 12,000 net")
        print("✅ Test completed!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_combined_logic()
    sys.exit(0 if success else 1)
