#!/usr/bin/env python3
"""
Test script to verify Bolagsverket API access token creation
"""
import requests
import json
from datetime import datetime

def test_bolagsverket_token():
    """Test getting access token from Bolagsverket API"""
    
    # Production credentials
    client_id = "oH7J10u23a8r4YZMtid91N7fQ98a"
    client_secret = "xvD1Q2FcTIKVaYZUd9Q7N_0lfwka"
    auth_url = "https://portal.api.bolagsverket.se/oauth2/token"
    
    print("🔐 Testing Bolagsverket API access token creation...")
    print(f"📅 Time: {datetime.now().isoformat()}")
    print(f"🔗 Auth URL: {auth_url}")
    print(f"🆔 Client ID: {client_id}")
    print(f"🔑 Client Secret: {client_secret[:8]}...")
    print("-" * 50)
    
    try:
        # Request token with scope for valuable data
        token_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "vardefulla-datamangder:read vardefulla-datamangder:ping"
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        print("📤 Sending token request...")
        response = requests.post(
            auth_url,
            data=token_data,
            headers=headers,
            timeout=30
        )
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            token_response = response.json()
            print("✅ SUCCESS: Access token obtained!")
            print(f"🎫 Access Token: {token_response.get('access_token', 'N/A')[:20]}...")
            print(f"⏰ Expires In: {token_response.get('expires_in', 'N/A')} seconds")
            print(f"📝 Token Type: {token_response.get('token_type', 'N/A')}")
            print(f"🎯 Scope: {token_response.get('scope', 'N/A')}")
            
            # Test using the token to access an API endpoint
            access_token = token_response.get('access_token')
            if access_token:
                print("\n🧪 Testing API access with token...")
                test_api_access(access_token)
                
        else:
            print("❌ FAILED: Could not get access token")
            print(f"📄 Response Text: {response.text}")
            
    except Exception as e:
        print(f"💥 ERROR: {str(e)}")

def test_api_access(access_token):
    """Test accessing Bolagsverket API with the token"""
    
    # Test endpoint - you might need to adjust this based on actual API documentation
    test_url = "https://api.bolagsverket.se/hamta-arsredovisningsinformation/v1.4/arendestatus/5561234567"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    try:
        print(f"🔗 Testing API endpoint: {test_url}")
        response = requests.get(test_url, headers=headers, timeout=30)
        
        print(f"📊 API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: API access working!")
            data = response.json()
            print(f"📄 Response Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        elif response.status_code == 404:
            print("ℹ️  INFO: No data found for test organization number (expected)")
        else:
            print(f"⚠️  WARNING: API returned status {response.status_code}")
            print(f"📄 Response Text: {response.text}")
            
    except Exception as e:
        print(f"💥 ERROR testing API access: {str(e)}")

if __name__ == "__main__":
    test_bolagsverket_token()

