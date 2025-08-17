#!/usr/bin/env python3
"""
Test script for Bolagsverket API endpoints
"""
import asyncio
import json
from datetime import datetime
from services.bolagsverket_service import BolagsverketService

async def test_bolagsverket_api():
    """Test all Bolagsverket API endpoints"""
    
    print("🔐 Testing Bolagsverket API endpoints...")
    print(f"📅 Time: {datetime.now().isoformat()}")
    print("-" * 60)
    
    # Initialize service
    service = BolagsverketService()
    
    # Test organization number
    test_org_number = "5563555456"  # Remove dash for API call
    
    try:
        # 1. Test API health
        print("1️⃣ Testing API health...")
        health_status = await service.check_api_health()
        if health_status:
            print("✅ API is healthy and responding")
        else:
            print("❌ API health check failed")
        print()
        
        # 2. Test company info
        print("2️⃣ Testing company info...")
        company_info = await service.get_company_info(test_org_number)
        if company_info:
            print("✅ Company info retrieved successfully")
            print(f"📄 Response: {json.dumps(company_info, indent=2, ensure_ascii=False)}")
        else:
            print("❌ Failed to get company info")
        print()
        
        # 3. Test document list
        print("3️⃣ Testing document list...")
        document_list = await service.get_document_list(test_org_number)
        if document_list:
            print("✅ Document list retrieved successfully")
            print(f"📄 Response: {json.dumps(document_list, indent=2, ensure_ascii=False)}")
            
            # If we have documents, test getting the first one
            if document_list.get('dokument') and len(document_list['dokument']) > 0:
                first_doc = document_list['dokument'][0]
                document_id = first_doc.get('dokumentId')
                
                if document_id:
                    print(f"\n4️⃣ Testing document retrieval for ID: {document_id}")
                    document = await service.get_document(document_id)
                    if document:
                        print("✅ Document retrieved successfully")
                        print(f"📄 Document info: {json.dumps(document, indent=2, ensure_ascii=False)}")
                    else:
                        print("❌ Failed to get document")
        else:
            print("❌ Failed to get document list")
        print()
        
        # 4. Test legacy method for compatibility
        print("5️⃣ Testing legacy annual report info method...")
        annual_report_info = await service.get_company_annual_report_info(test_org_number)
        if annual_report_info:
            print("✅ Legacy method working (returns document list)")
        else:
            print("❌ Legacy method failed")
        print()
        
    except Exception as e:
        print(f"💥 ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_bolagsverket_api())
