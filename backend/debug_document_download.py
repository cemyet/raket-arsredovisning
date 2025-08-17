#!/usr/bin/env python3
"""
Debug script for document download
"""
import asyncio
import requests
import uuid
from services.bolagsverket_service import BolagsverketService

async def debug_document_download():
    """Debug document download process"""
    
    print("🔍 Debugging document download...")
    
    # Test with a known document ID
    document_id = "707d736e-cda8-4e07-b076-fdf04bf2f0eb_paket"  # From previous test
    
    service = BolagsverketService()
    
    # Get access token
    token = await service._get_access_token()
    if not token:
        print("❌ Failed to get access token")
        return
    
    print(f"✅ Got access token: {token[:20]}...")
    
    # Try direct request
    url = f"https://gw.api.bolagsverket.se/vardefulla-datamangder/v1/dokument/{document_id}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "*/*",
        "X-Request-Id": str(uuid.uuid4())
    }
    
    print(f"🔗 Requesting: {url}")
    print(f"📋 Headers: {headers}")
    
    try:
        response = requests.get(url, headers=headers, timeout=60)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        print(f"📏 Content Length: {len(response.content)}")
        
        if response.status_code == 200:
            if len(response.content) > 0:
                print(f"✅ Success! Content type: {response.headers.get('Content-Type', 'Unknown')}")
                print(f"📄 First 100 bytes: {response.content[:100]}")
                
                # Save to file
                filename = f"debug_document_{document_id}.zip"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                print(f"💾 Saved to: {filename}")
            else:
                print("⚠️  Empty response content")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"📄 Response text: {response.text}")
            
    except Exception as e:
        print(f"💥 Exception: {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_document_download())

