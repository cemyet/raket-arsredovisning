#!/usr/bin/env python3
"""
Test script for document extraction and XHTML processing
"""
import asyncio
import os
from services.bolagsverket_service import BolagsverketService

async def test_document_extraction():
    """Test document extraction and XHTML processing"""
    
    print("🔍 Testing document extraction and XHTML processing...")
    
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
        
        # 2. Extract and process the first document
        if documents:
            first_doc = documents[0]
            document_id = first_doc.get('dokumentId')
            file_format = first_doc.get('filformat', 'application/zip')
            
            print(f"📥 Extracting document: {document_id}")
            print(f"📋 Format: {file_format}")
            
            # Extract the document
            extracted_data = await service.get_and_extract_document(document_id)
            
            if extracted_data:
                print(f"✅ Successfully extracted document!")
                print(f"📁 Extract directory: {extracted_data['extract_dir']}")
                
                if 'zip_info' in extracted_data:
                    print(f"📦 ZIP file info:")
                    print(f"   Total files: {extracted_data['total_files']}")
                    print(f"   File size: {extracted_data['zip_info']['size']} bytes")
                    print(f"   Files in ZIP:")
                    for file in extracted_data['zip_info']['file_list']:
                        print(f"     - {file}")
                
                if 'xhtml_files' in extracted_data:
                    print(f"\n📄 XHTML files found: {len(extracted_data['xhtml_files'])}")
                    for xhtml_file in extracted_data['xhtml_files']:
                        print(f"   - {os.path.basename(xhtml_file)}")
                
                if 'processed_files' in extracted_data:
                    print(f"\n🔍 Processed XHTML files:")
                    for i, file_info in enumerate(extracted_data['processed_files'], 1):
                        print(f"\n📋 File {i}: {file_info['filename']}")
                        print(f"   Title: {file_info['title']}")
                        print(f"   Content preview: {file_info['text_content'][:200]}...")
                        
                        # Show some structure from the XHTML
                        soup = file_info['parsed_html']
                        
                        # Look for common annual report sections
                        sections = []
                        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                            if tag.get_text().strip():
                                sections.append(f"{tag.name}: {tag.get_text().strip()}")
                        
                        if sections:
                            print(f"   Sections found:")
                            for section in sections[:10]:  # Show first 10 sections
                                print(f"     - {section}")
                
                # Keep the extracted files for inspection
                print(f"\n💾 Extracted files saved to: {extracted_data['extract_dir']}")
                print("   You can inspect the XHTML files manually in this directory.")
                
            else:
                print("❌ Failed to extract document")
        
    except Exception as e:
        print(f"💥 Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_document_extraction())

