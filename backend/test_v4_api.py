#!/usr/bin/env python3
"""
Test script for Bolagsverket foretagsinformation/v4 API endpoint
"""
import asyncio
import json
import requests
import uuid
from datetime import datetime, timedelta
from services.bolagsverket_service import BolagsverketService

class BolagsverketV4Service(BolagsverketService):
    """
    Extended service to test the v4 foretagsinformation endpoint
    """
    
    def __init__(self):
        super().__init__()
        # Override the API base URL to use v4 endpoint
        self.v4_base_url = "https://gw.api.bolagsverket.se/foretagsinformation/v4"
    
    async def get_company_info_v4(self, org_number: str) -> dict:
        """
        Get company information using the v4 foretagsinformation endpoint
        
        Args:
            org_number: Swedish organization number (10 digits)
            
        Returns:
            Dict with company information or None if error
        """
        if self.mock_mode:
            return {
                "endpoint": "v4",
                "organizationNumber": org_number,
                "companyName": f"Mock Company {org_number} (V4)",
                "status": "ACTIVE"
            }
        
        token = await self._get_access_token()
        if not token:
            return {"error": "Could not get access token"}
        
        try:
            # Try different possible endpoints under v4
            endpoints_to_try = [
                f"{self.v4_base_url}/organisationer",
                f"{self.v4_base_url}/organisation",
                f"{self.v4_base_url}/company",
                f"{self.v4_base_url}/foretagsuppgifter",
                f"{self.v4_base_url}/bolagsuppgifter",
                f"{self.v4_base_url}",  # Base endpoint
            ]
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Request-Id": str(uuid.uuid4())
            }
            
            results = {}
            
            for endpoint in endpoints_to_try:
                try:
                    print(f"\n🔍 Testing endpoint: {endpoint}")
                    
                    # Try GET request first
                    response = requests.get(f"{endpoint}?identitetsbeteckning={org_number}", headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        print(f"✅ GET Success: {endpoint}")
                        results[f"GET_{endpoint}"] = {
                            "status_code": response.status_code,
                            "data": response.json() if response.text else None,
                            "headers": dict(response.headers)
                        }
                    elif response.status_code == 404:
                        print(f"❌ GET 404: {endpoint}")
                        results[f"GET_{endpoint}"] = {"status_code": 404, "error": "Not found"}
                    else:
                        print(f"⚠️  GET {response.status_code}: {endpoint}")
                        results[f"GET_{endpoint}"] = {
                            "status_code": response.status_code,
                            "error": response.text[:200] if response.text else "No response text"
                        }
                    
                    # Try POST request with body
                    request_data = {
                        "identitetsbeteckning": org_number
                    }
                    
                    response = requests.post(endpoint, json=request_data, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        print(f"✅ POST Success: {endpoint}")
                        results[f"POST_{endpoint}"] = {
                            "status_code": response.status_code,
                            "data": response.json() if response.text else None,
                            "headers": dict(response.headers)
                        }
                    elif response.status_code == 404:
                        print(f"❌ POST 404: {endpoint}")
                        results[f"POST_{endpoint}"] = {"status_code": 404, "error": "Not found"}
                    else:
                        print(f"⚠️  POST {response.status_code}: {endpoint}")
                        results[f"POST_{endpoint}"] = {
                            "status_code": response.status_code,
                            "error": response.text[:200] if response.text else "No response text"
                        }
                        
                except Exception as e:
                    print(f"💥 Error testing {endpoint}: {str(e)}")
                    results[f"ERROR_{endpoint}"] = {"error": str(e)}
            
            return results
                
        except Exception as e:
            print(f"💥 General error: {str(e)}")
            return {"error": str(e)}

    async def discover_v4_endpoints(self) -> dict:
        """
        Try to discover what endpoints are available under v4
        """
        token = await self._get_access_token()
        if not token:
            return {"error": "Could not get access token"}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "X-Request-Id": str(uuid.uuid4())
        }
        
        # Try to get the base v4 endpoint
        try:
            print(f"\n🔍 Discovering v4 base endpoint...")
            response = requests.get(self.v4_base_url, headers=headers, timeout=30)
            
            return {
                "base_endpoint": self.v4_base_url,
                "status_code": response.status_code,
                "response_text": response.text[:500] if response.text else "No response",
                "headers": dict(response.headers),
                "content_type": response.headers.get('content-type', 'Unknown')
            }
            
        except Exception as e:
            return {"error": str(e)}

async def main():
    """Test the v4 API endpoint"""
    print("🚀 Testing Bolagsverket foretagsinformation/v4 API")
    print("=" * 60)
    
    service = BolagsverketV4Service()
    
    # Test organization number
    org_number = input("\n📝 Enter organization number to test (or press Enter for 5567078174): ").strip()
    if not org_number:
        org_number = "5567078174"
    
    # Clean the organization number
    org_number = org_number.replace('-', '').replace(' ', '')
    
    if not org_number.isdigit() or len(org_number) != 10:
        print("❌ Invalid organization number format")
        return
    
    print(f"\n🎯 Testing with organization number: {org_number}")
    
    # First, discover the base endpoint
    print(f"\n📡 Step 1: Discovering v4 base endpoint...")
    discovery_result = await service.discover_v4_endpoints()
    print(f"Discovery result:")
    print(json.dumps(discovery_result, indent=2, ensure_ascii=False))
    
    # Then test company info endpoints
    print(f"\n📡 Step 2: Testing company info endpoints...")
    company_result = await service.get_company_info_v4(org_number)
    print(f"\nCompany info results:")
    print(json.dumps(company_result, indent=2, ensure_ascii=False))
    
    # Compare with v1 endpoint
    print(f"\n📡 Step 3: Comparing with current v1 endpoint...")
    v1_result = await service.get_company_info(org_number)
    if v1_result:
        print(f"✅ V1 endpoint returned data")
        print(f"V1 data keys: {list(v1_result.keys())}")
        if 'organisationer' in v1_result:
            print(f"V1 organizations count: {len(v1_result['organisationer'])}")
    else:
        print(f"❌ V1 endpoint returned no data")

if __name__ == "__main__":
    asyncio.run(main())


