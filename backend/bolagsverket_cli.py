#!/usr/bin/env python3
"""
Interactive CLI for Bolagsverket API
"""
import asyncio
import json
import os
import requests
from datetime import datetime
from services.bolagsverket_service import BolagsverketService

async def main():
    """Main CLI function"""
    print("🏢 Bolagsverket API CLI Tool")
    print("=" * 50)
    
    # Initialize service
    service = BolagsverketService()
    
    while True:
        try:
            # Get organization number from user
            org_number = input("\n📝 Enter organization number (or 'quit' to exit): ").strip()
            
            if org_number.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            # Clean the organization number (remove dashes and spaces)
            org_number = org_number.replace('-', '').replace(' ', '')
            
            # Validate format
            if not org_number.isdigit() or len(org_number) != 10:
                print("❌ Error: Organization number must be 10 digits")
                continue
            
            print(f"\n🔍 Fetching information for: {org_number}")
            print("-" * 50)
            
            # 1. Get company information
            print("📊 Getting company information...")
            company_info = await service.get_company_info(org_number)
            
            if not company_info:
                print("❌ No company information found")
                continue
            
            # Display company information
            display_company_info(company_info)
            
            # 2. Get document list
            print("\n📄 Getting annual reports...")
            document_list = await service.get_document_list(org_number)
            
            if not document_list or not document_list.get('dokument'):
                print("ℹ️  No annual reports available for this company")
                continue
            
            # Display document list with numbers for selection
            documents = document_list.get('dokument', [])
            display_annual_reports_list(documents)
            
            # 3. Ask user which document to download
            if documents:
                await interactive_download_selection(service, documents, org_number)
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"💥 Error: {str(e)}")

def display_company_info(company_info):
    """Display company information in a readable format"""
    if not company_info.get('organisationer'):
        print("❌ No organization data found")
        return
    
    org = company_info['organisationer'][0]
    
    print("\n🏢 COMPANY INFORMATION")
    print("=" * 30)
    
    # Basic info
    if org.get('organisationsnamn', {}).get('organisationsnamnLista'):
        names = org['organisationsnamn']['organisationsnamnLista']
        for name_info in names:
            name_type = name_info.get('organisationsnamntyp', {}).get('klartext', 'Unknown')
            print(f"📛 {name_type}: {name_info.get('namn', 'N/A')}")
    
    # Organization details
    print(f"🔢 Organization Number: {org.get('organisationsidentitet', {}).get('identitetsbeteckning', 'N/A')}")
    print(f"📅 Registration Date: {org.get('organisationsdatum', {}).get('registreringsdatum', 'N/A')}")
    print(f"🏛️  Legal Form: {org.get('organisationsform', {}).get('klartext', 'N/A')}")
    
    # Address
    if org.get('postadressOrganisation', {}).get('postadress'):
        addr = org['postadressOrganisation']['postadress']
        print(f"📍 Address: {addr.get('utdelningsadress', 'N/A')}")
        if addr.get('coAdress'):
            print(f"   Care of: {addr.get('coAdress')}")
        print(f"   Postal: {addr.get('postnummer', 'N/A')} {addr.get('postort', 'N/A')}")
    
    # Business description
    if org.get('verksamhetsbeskrivning', {}).get('beskrivning'):
        desc = org['verksamhetsbeskrivning']['beskrivning']
        print(f"📋 Business Description: {desc[:100]}{'...' if len(desc) > 100 else ''}")
    
    # Status information
    if org.get('avregistreradOrganisation'):
        print(f"⚠️  Status: LIQUIDATED")
        print(f"   Deregistration Date: {org['avregistreradOrganisation'].get('avregistreringsdatum', 'N/A')}")
        if org.get('avregistreringsorsak', {}).get('klartext'):
            print(f"   Reason: {org['avregistreringsorsak']['klartext']}")
    else:
        print("✅ Status: ACTIVE")

def display_annual_reports_list(documents):
    """Display annual reports list with selection numbers"""
    print("\n📄 AVAILABLE ANNUAL REPORTS")
    print("=" * 35)
    
    if not documents:
        print("No annual reports available")
        return
    
    for i, doc in enumerate(documents, 1):
        period_end = doc.get('rapporteringsperiodTom', 'N/A')
        registration = doc.get('registreringstidpunkt', 'N/A')
        doc_format = doc.get('filformat', 'N/A')
        
        # Extract year from period end for cleaner display
        year = period_end.split('-')[0] if period_end != 'N/A' else 'Unknown'
        
        print(f"\n📋 [{i}] Annual Report {year}")
        print(f"    Period End: {period_end}")
        print(f"    Registration: {registration}")
        print(f"    Format: {doc_format}")
        print(f"    Document ID: {doc.get('dokumentId', 'N/A')}")

async def interactive_download_selection(service, documents, org_number):
    """Ask user which document to download and process it"""
    print(f"\n💾 Found {len(documents)} annual report(s)")
    
    while True:
        try:
            choice = input(f"\n📥 Which report would you like to download? (1-{len(documents)}, or 'skip' to continue): ").strip().lower()
            
            if choice in ['skip', 's', 'n', 'no']:
                print("⏭️  Skipping download")
                return
            
            # Try to parse as number
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(documents):
                    selected_doc = documents[choice_num - 1]
                    await download_and_extract_document(service, selected_doc, org_number)
                    
                    # Ask if they want to download another
                    if len(documents) > 1:
                        another = input("\n📥 Download another report? (y/n): ").strip().lower()
                        if another not in ['y', 'yes']:
                            break
                    else:
                        break
                else:
                    print(f"❌ Please enter a number between 1 and {len(documents)}")
            except ValueError:
                print("❌ Please enter a valid number or 'skip'")
                
        except KeyboardInterrupt:
            print("\n⏭️  Skipping download")
            return

async def download_and_extract_document(service, document, org_number):
    """Download and extract a specific document"""
    document_id = document.get('dokumentId')
    period_end = document.get('rapporteringsperiodTom', 'Unknown')
    registration_date = document.get('registreringstidpunkt', 'Unknown')
    
    # Extract year for filename
    year = period_end.split('-')[0] if period_end != 'Unknown' else 'latest'
    
    print(f"\n📥 DOWNLOADING ANNUAL REPORT")
    print("=" * 35)
    print(f"📅 Period End: {period_end}")
    print(f"📅 Registration: {registration_date}")
    print(f"🆔 Document ID: {document_id}")
    
    # Create downloads folder
    downloads_dir = os.path.expanduser("~/Downloads")
    if not os.path.exists(downloads_dir):
        downloads_dir = "./downloads"
        os.makedirs(downloads_dir, exist_ok=True)
    
    print(f"📁 Download folder: {downloads_dir}")
    
    try:
        # Download the document
        print(f"\n📥 Downloading...")
        document_data = await service.get_document(document_id)
        
        if not document_data or len(document_data) == 0:
            print(f"❌ Failed to retrieve document or document is empty")
            return
        
        # Determine file extension based on format
        file_format = document.get('filformat', 'application/zip')
        if 'zip' in file_format:
            extension = '.zip'
        elif 'pdf' in file_format:
            extension = '.pdf'
        else:
            extension = '.bin'
        
        # Create filename with year
        filename = f"{org_number}_{year}{extension}"
        filepath = os.path.join(downloads_dir, filename)
        
        # Save the document
        if isinstance(document_data, bytes):
            with open(filepath, 'wb') as f:
                f.write(document_data)
        else:
            print(f"⚠️  Unexpected document data type: {type(document_data)}")
            return
        
        print(f"✅ Downloaded: {filename}")
        print(f"📏 Size: {os.path.getsize(filepath):,} bytes")
        
        # Ask if user wants to extract and analyze
        if extension == '.zip':
            extract = input("\n🔍 Extract and analyze the ZIP file? (y/n): ").strip().lower()
            if extract in ['y', 'yes']:
                await extract_and_analyze_document(service, document_id, filepath)
        
    except Exception as e:
        print(f"❌ Error downloading document: {str(e)}")

async def extract_and_analyze_document(service, document_id, filepath):
    """Extract and analyze the downloaded document"""
    print(f"\n🔍 EXTRACTING AND ANALYZING DOCUMENT")
    print("=" * 40)
    
    extracted_data = await service.get_and_extract_document(document_id)
    
    if extracted_data:
        print(f"✅ Successfully extracted document!")
        print(f"📁 Extract directory: {extracted_data['extract_dir']}")
        
        if 'zip_info' in extracted_data:
            print(f"📦 ZIP contains {extracted_data['total_files']} files")
            print(f"📏 Total size: {extracted_data['zip_info']['size']:,} bytes")
        
        if 'processed_files' in extracted_data:
            print(f"📄 Processed {len(extracted_data['processed_files'])} XHTML files:")
            
            for j, file_info in enumerate(extracted_data['processed_files'], 1):
                print(f"\n📋 File {j}: {file_info['filename']}")
                print(f"   Title: {file_info['title']}")
                print(f"   📁 Full path: {file_info['filepath']}")
                
                # Show content preview
                preview = file_info['text_content'][:200]
                print(f"   Preview: {preview}...")
        
        print(f"\n💾 Files saved to: {extracted_data['extract_dir']}")
        print(f"📁 ZIP file saved to: {filepath}")
        print(f"✅ Extraction completed successfully!")
        
        # Ask if user wants detailed analysis
        show_details = input("\n🔍 Show detailed content analysis? (y/n): ").strip().lower()
        if show_details in ['y', 'yes']:
            await show_detailed_analysis(extracted_data)
    else:
        print("❌ Failed to extract document")

async def download_latest_document(service, document_list, org_number):
    """Download and extract only the latest document"""
    documents = document_list.get('dokument', [])
    if not documents:
        print("❌ No documents available")
        return
    
    # Find the latest document (highest number or most recent date)
    latest_doc = find_latest_document(documents)
    if not latest_doc:
        print("❌ Could not determine latest document")
        return
    
    document_id = latest_doc.get('dokumentId')
    period_end = latest_doc.get('rapporteringsperiodTom', 'Unknown')
    registration_date = latest_doc.get('registreringstidpunkt', 'Unknown')
    
    print(f"\n📥 DOWNLOADING LATEST DOCUMENT")
    print("=" * 35)
    print(f"📅 Period End: {period_end}")
    print(f"📅 Registration: {registration_date}")
    print(f"🆔 Document ID: {document_id}")
    
    # Create downloads folder
    downloads_dir = os.path.expanduser("~/Downloads")
    if not os.path.exists(downloads_dir):
        downloads_dir = "./downloads"
        os.makedirs(downloads_dir, exist_ok=True)
    
    print(f"📁 Download folder: {downloads_dir}")
    
    try:
        # Download the document
        print(f"\n📥 Downloading latest document...")
        document_data = await service.get_document(document_id)
        
        if not document_data or len(document_data) == 0:
            print(f"❌ Failed to retrieve document or document is empty")
            return
        
        # Determine file extension based on format
        file_format = latest_doc.get('filformat', 'application/zip')
        if 'zip' in file_format:
            extension = '.zip'
        elif 'pdf' in file_format:
            extension = '.pdf'
        else:
            extension = '.bin'
        
        # Create filename with year
        year = period_end.split('-')[0] if period_end != 'Unknown' else 'latest'
        filename = f"{org_number}_{year}{extension}"
        filepath = os.path.join(downloads_dir, filename)
        
        # Save the document
        if isinstance(document_data, bytes):
            with open(filepath, 'wb') as f:
                f.write(document_data)
        else:
            print(f"⚠️  Unexpected document data type: {type(document_data)}")
            return
        
        print(f"✅ Downloaded: {filename}")
        print(f"📏 Size: {os.path.getsize(filepath)} bytes")
        
        # Extract and analyze the document
        print(f"\n🔍 EXTRACTING AND ANALYZING LATEST DOCUMENT")
        print("=" * 45)
        
        extracted_data = await service.get_and_extract_document(document_id)
        
        if extracted_data:
            print(f"✅ Successfully extracted document!")
            print(f"📁 Extract directory: {extracted_data['extract_dir']}")
            
            if 'zip_info' in extracted_data:
                print(f"📦 ZIP contains {extracted_data['total_files']} files")
                print(f"📏 Total size: {extracted_data['zip_info']['size']} bytes")
            
            if 'processed_files' in extracted_data:
                print(f"📄 Processed {len(extracted_data['processed_files'])} XHTML files:")
                
                for j, file_info in enumerate(extracted_data['processed_files'], 1):
                    print(f"\n📋 File {j}: {file_info['filename']}")
                    print(f"   Title: {file_info['title']}")
                    
                    # Show key sections
                    soup = file_info['parsed_html']
                    sections = []
                    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                        if tag.get_text().strip():
                            sections.append(tag.get_text().strip())
                    
                    if sections:
                        print(f"   Key sections:")
                        for section in sections[:10]:  # Show first 10 sections
                            print(f"     - {section}")
                    
                    # Show content preview
                    preview = file_info['text_content'][:500]
                    print(f"   Content preview: {preview}...")
                    
                    # Show file structure
                    print(f"   📁 Full file path: {file_info['filepath']}")
            
            print(f"\n💾 Files saved to: {extracted_data['extract_dir']}")
            print(f"📁 ZIP file saved to: {filepath}")
            print(f"✅ Process completed successfully!")
            
            # Ask if user wants to see more details
            show_details = input("\n🔍 Do you want to see detailed XHTML content analysis? (y/n): ").strip().lower()
            if show_details in ['y', 'yes']:
                await show_detailed_analysis(extracted_data)
            
        else:
            print("❌ Failed to extract document")
        
    except Exception as e:
        print(f"❌ Error processing latest document: {str(e)}")

def find_latest_document(documents):
    """Find the latest document based on period end date or registration date"""
    if not documents:
        return None
    
    # Try to sort by period end date first (most recent first)
    try:
        sorted_docs = sorted(
            documents, 
            key=lambda x: x.get('rapporteringsperiodTom', '1900-01-01'), 
            reverse=True
        )
        return sorted_docs[0]
    except:
        # Fallback: try to sort by registration date
        try:
            sorted_docs = sorted(
                documents, 
                key=lambda x: x.get('registreringstidpunkt', '1900-01-01'), 
                reverse=True
            )
            return sorted_docs[0]
        except:
            # Last resort: return the first document
            return documents[0]

async def show_detailed_analysis(extracted_data):
    """Show detailed analysis of the extracted XHTML content"""
    if not extracted_data or 'processed_files' not in extracted_data:
        print("❌ No processed files to analyze")
        return
    
    print(f"\n🔍 DETAILED XHTML CONTENT ANALYSIS")
    print("=" * 45)
    
    for i, file_info in enumerate(extracted_data['processed_files'], 1):
        print(f"\n📋 Analyzing file {i}: {file_info['filename']}")
        print("-" * 50)
        
        soup = file_info['parsed_html']
        
        # 1. Document structure
        print(f"📊 Document Structure:")
        all_headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        print(f"   Total headers: {len(all_headers)}")
        
        # 2. Show all sections with hierarchy
        print(f"\n📑 All Sections (with hierarchy):")
        for header in all_headers[:20]:  # Show first 20 headers
            level = int(header.name[1])
            indent = "  " * (level - 1)
            print(f"{indent}{header.name.upper()}: {header.get_text().strip()}")
        
        # 3. Find tables
        tables = soup.find_all('table')
        print(f"\n📊 Tables found: {len(tables)}")
        for j, table in enumerate(tables[:3], 1):  # Show first 3 tables
            rows = table.find_all('tr')
            print(f"   Table {j}: {len(rows)} rows")
        
        # 4. Find financial data
        financial_keywords = ['resultat', 'intäkter', 'kostnader', 'tillgångar', 'skulder', 'eget kapital', 'omsättning']
        financial_sections = []
        
        for keyword in financial_keywords:
            elements = soup.find_all(text=lambda text: text and keyword.lower() in text.lower())
            if elements:
                financial_sections.extend(elements[:3])  # First 3 matches per keyword
        
        if financial_sections:
            print(f"\n💰 Financial Data Found:")
            for section in financial_sections[:10]:
                text = section.strip()[:100]
                if text:
                    print(f"   - {text}...")
        
        # 5. Show file size and content stats
        content = file_info['content']
        print(f"\n📏 Content Statistics:")
        print(f"   File size: {len(content)} characters")
        print(f"   Text content: {len(file_info['text_content'])} characters")
        print(f"   Lines: {len(content.split(chr(10)))}")
        
        # 6. Show first 1000 characters of content
        print(f"\n📄 Content Preview (first 1000 characters):")
        preview = content[:1000]
        print(f"   {preview}...")
        
        print(f"\n" + "="*50)

if __name__ == "__main__":
    asyncio.run(main())
