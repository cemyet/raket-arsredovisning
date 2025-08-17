#!/usr/bin/env python3
"""
Simple test for document download
"""
import asyncio
import os
from services.bolagsverket_service import BolagsverketService

async def test_document_download():
    """Test document download with a specific organization"""
    
    print("🔍 Testing document download...")
    
    # Test organization number
    org_number = "5563555456"  # Åmyra Förlag Aktiebolag (has documents)
    
    service = BolagsverketService()
    
    try:
        # 1. Get document list
        print(f"📄 Getting document list for {org_number}...")
        document_list = await service.get_document_list(org_number)
        
        if not document_list or not document_list.get('dokument'):
            print("❌ No documents found")
            return
        
        documents = document_list['dokument']
        print(f"✅ Found {len(documents)} documents")
        
        # 2. Try to download the first document
        if documents:
            first_doc = documents[0]
            document_id = first_doc.get('dokumentId')
            file_format = first_doc.get('filformat', 'application/zip')
            
            print(f"📥 Downloading document: {document_id}")
            print(f"📋 Format: {file_format}")
            
            # Get the document
            document_data = await service.get_document(document_id)
            
            if document_data and len(document_data) > 0:
                # Determine file extension
                if 'zip' in file_format:
                    extension = '.zip'
                elif 'pdf' in file_format:
                    extension = '.pdf'
                else:
                    extension = '.bin'
                
                # Save the file
                filename = f"{org_number}_document{extension}"
                with open(filename, 'wb') as f:
                    f.write(document_data)
                
                print(f"✅ Successfully downloaded: {filename}")
                print(f"📏 File size: {len(document_data)} bytes")
                
                # Check if it's a valid ZIP file
                if extension == '.zip':
                    import zipfile
                    try:
                        with zipfile.ZipFile(filename, 'r') as zip_ref:
                            file_list = zip_ref.namelist()
                            print(f"📦 ZIP contains {len(file_list)} files:")
                            for file in file_list[:5]:  # Show first 5 files
                                print(f"   - {file}")
                            if len(file_list) > 5:
                                print(f"   ... and {len(file_list) - 5} more files")
                    except zipfile.BadZipFile:
                        print("⚠️  File is not a valid ZIP file")
                
            else:
                print("❌ Failed to download document or document is empty")
        
    except Exception as e:
        print(f"💥 Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_document_download())

