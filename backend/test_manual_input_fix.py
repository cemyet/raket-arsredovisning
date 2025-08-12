#!/usr/bin/env python3
"""
Test script to verify manual input fixes for pension tax and unused tax loss
"""

import json
from services.database_parser import DatabaseParser

def test_manual_inputs():
    """Test that manual inputs are correctly injected and calculated"""
    
    # Mock data for testing
    current_accounts = {
        '7410': 100000.0,  # Pension premiums
        '8999': 500000.0,  # Net result
    }
    
    rr_data = [
        {'variable_name': 'SumAretsResultat', 'current_amount': 500000.0},
        {'variable_name': 'SkattAretsResultat', 'current_amount': 100000.0},
    ]
    
    br_data = []
    
    parser = DatabaseParser()
    
    print("🧪 Testing manual input fixes...")
    print("=" * 50)
    
    # Test 1: Manual pension tax adjustment
    print("\n1️⃣ Testing manual pension tax adjustment...")
    manual_amounts = {
        'justering_sarskild_loneskatt': 15000.0  # Manual adjustment
    }
    
    result1 = parser.parse_ink2_data_with_overrides(
        current_accounts=current_accounts,
        fiscal_year=2024,
        rr_data=rr_data,
        br_data=br_data,
        manual_amounts=manual_amounts
    )
    
    # Find INK_sarskild_loneskatt in results
    sarskild_item = next((item for item in result1 if item['variable_name'] == 'INK_sarskild_loneskatt'), None)
    if sarskild_item:
        print(f"✅ INK_sarskild_loneskatt found: {sarskild_item['amount']}")
    else:
        print("❌ INK_sarskild_loneskatt not found")
    
    # Test 2: Manual unused tax loss
    print("\n2️⃣ Testing manual unused tax loss...")
    manual_amounts = {
        'INK4.14a': 50000.0  # Manual unused tax loss
    }
    
    result2 = parser.parse_ink2_data_with_overrides(
        current_accounts=current_accounts,
        fiscal_year=2024,
        rr_data=rr_data,
        br_data=br_data,
        manual_amounts=manual_amounts
    )
    
    # Find INK4.14a in results
    ink4_14a_item = next((item for item in result2 if item['variable_name'] == 'INK4.14a'), None)
    if ink4_14a_item:
        print(f"✅ INK4.14a found: {ink4_14a_item['amount']}")
        if ink4_14a_item['amount'] == 50000.0:
            print("✅ INK4.14a value matches manual input!")
        else:
            print(f"❌ INK4.14a value mismatch: expected 50000.0, got {ink4_14a_item['amount']}")
    else:
        print("❌ INK4.14a not found")
    
    # Test 3: Combined manual inputs
    print("\n3️⃣ Testing combined manual inputs...")
    manual_amounts = {
        'justering_sarskild_loneskatt': 15000.0,
        'INK4.14a': 50000.0
    }
    
    result3 = parser.parse_ink2_data_with_overrides(
        current_accounts=current_accounts,
        fiscal_year=2024,
        rr_data=rr_data,
        br_data=br_data,
        manual_amounts=manual_amounts
    )
    
    # Check both values
    sarskild_combined = next((item for item in result3 if item['variable_name'] == 'INK_sarskild_loneskatt'), None)
    ink4_14a_combined = next((item for item in result3 if item['variable_name'] == 'INK4.14a'), None)
    
    if sarskild_combined and ink4_14a_combined:
        print(f"✅ Combined test: INK_sarskild_loneskatt={sarskild_combined['amount']}, INK4.14a={ink4_14a_combined['amount']}")
    else:
        print("❌ Combined test failed")
    
    # Test 4: Check final tax calculation
    print("\n4️⃣ Testing final tax calculation with manual inputs...")
    beraknad_skatt = next((item for item in result3 if item['variable_name'] == 'INK_beraknad_skatt'), None)
    if beraknad_skatt:
        print(f"✅ Final calculated tax: {beraknad_skatt['amount']}")
    else:
        print("❌ Final tax calculation failed")
    
    print("\n" + "=" * 50)
    print("🎯 Test completed!")
    
    return result3

if __name__ == "__main__":
    test_manual_inputs()
