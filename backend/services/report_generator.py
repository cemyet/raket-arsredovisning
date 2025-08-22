import os
import uuid
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List
import asyncio

# Import the new database-driven parser
from services.database_parser import DatabaseParser

# Note: Legacy imports from merged_rr_br_not removed since this module is not available
# and ReportGenerator is currently disabled in favor of DatabaseParser

class ReportGenerator:
    def __init__(self):
        self.reports_dir = "reports"
        self.temp_dir = "temp"
        self._ensure_directories()
        
        # Initialize the new database-driven parser
        self.database_parser = DatabaseParser()
    
    def _ensure_directories(self):
        """Skapar nödvändiga mappar"""
        for directory in [self.reports_dir, self.temp_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def extract_company_data(self, se_file_path: str) -> Dict[str, Any]:
        """
        Extraherar grundläggande företagsdata från .SE-fil
        """
        try:
            # Extrahera organisationsnummer
            organization_number = extract_orgnr_from_se(se_file_path)
            
            # Extrahera räkenskapsår
            current_year, previous_year, current_end_date_raw, previous_end_date_raw, current_year_string, previous_year_string, current_end_date_iso, previous_end_date_iso = extract_fiscal_year_robust(se_file_path)
            
            # Extrahera kontosaldo för att få grundläggande info
            account_balances, prev_year_balances = extract_account_balances_from_se(se_file_path)
            
            return {
                "organization_number": organization_number,
                "company_name": f"Företag {organization_number}",  # Kan förbättras med Allabolag-scraping
                "fiscal_year": current_year,
                "previous_year": previous_year,
                "current_end_date": current_end_date_string,
                "previous_end_date": previous_end_date_string,
                "account_count": len(account_balances),
                "has_data": len(account_balances) > 0
            }
            
        except Exception as e:
            raise Exception(f"Fel vid extrahering av företagsdata: {str(e)}")
    
    async def generate_full_report(self, request: 'ReportRequest') -> Dict[str, Any]:
        """
        Genererar komplett årsredovisning baserat på request
        """
        try:
            # Generera unikt rapport-ID
            report_id = str(uuid.uuid4())
            
            # Skapa temporär mapp för denna rapport
            temp_report_dir = os.path.join(self.temp_dir, report_id)
            os.makedirs(temp_report_dir, exist_ok=True)
            
            # Kopiera .SE-fil till temporär mapp
            temp_se_path = os.path.join(temp_report_dir, "data.se")
            shutil.copy2(request.se_file_path, temp_se_path)
            
            # Read SE file content for the new parser
            with open(temp_se_path, 'r', encoding='utf-8') as f:
                se_content = f.read()
            
            # Use the new database-driven parser
            print("🔄 Using new database-driven parser...")
            
            # Parse account balances using new parser
            current_accounts, previous_accounts, current_ib_accounts, previous_ib_accounts = self.database_parser.parse_account_balances(se_content)
            print(f"📊 Parsed {len(current_accounts)} current year accounts, {len(previous_accounts)} previous year accounts")
            
            # Parse RR and BR data using new parser
            rr_data = self.database_parser.parse_rr_data(current_accounts, previous_accounts)
            br_data = self.database_parser.parse_br_data(current_accounts, previous_accounts)
            
            # Parse INK2 data (tax calculations)
            ink2_data = self.database_parser.parse_ink2_data(
                current_accounts=current_accounts,
                fiscal_year=company_data.get('fiscal_year')
            )
            
            print(f"📈 Parsed {len(rr_data)} RR items, {len(br_data)} BR items, and {len(ink2_data)} INK2 items")
            
            # Store financial data in database
            company_id = request.company_data.organization_number  # Using organization_number as company_id for now
            fiscal_year = request.company_data.fiscal_year
            
            stored_ids = self.database_parser.store_financial_data(
                company_id, 
                fiscal_year, 
                rr_data, 
                br_data
            )
            print(f"💾 Stored financial data: {stored_ids}")
            
            # Convert new parser data to old format for PDF generation
            # This is a temporary bridge until PDF generation is updated
            df_rr = self._convert_rr_data_to_old_format(rr_data)
            df_rr_prev = self._convert_rr_data_to_old_format([])  # TODO: Extract previous year RR data
            df_br = self._convert_br_data_to_old_format(br_data)
            df_br_prev = self._convert_br_data_to_old_format([])  # TODO: Extract previous year BR data
            
            # Extrahera räkenskapsår för PDF-generering
            current_year, previous_year, current_end_date_raw, previous_end_date_raw, current_year_string, previous_year_string, current_end_date_iso, previous_end_date_iso = extract_fiscal_year_robust(temp_se_path)
            
            # Generera PDF:er
            rr_pdf_path = os.path.join(temp_report_dir, "RR_temp.pdf")
            br_pdf_path = os.path.join(temp_report_dir, "BR_temp.pdf")
            forvaltning_pdf_path = os.path.join(temp_report_dir, "Forvaltning_temp.pdf")
            noter_pdf_path = os.path.join(temp_report_dir, "Not_temp.pdf")
            
            # Skapa förvaltningsberättelse med användarinput
            create_management_report_pdf(
                forvaltning_pdf_path,
                temp_se_path,
                df_rr_prev,
                verksamhet_text=request.company_data.get("business_description", "Bolaget skall driva konsultverksamhet..."),
                sate=request.location,
                vasentliga_handelser=request.significant_events,
                ars_resultat_exakt=request.yearly_result,
                balanserat_resultat_exakt=0  # Kan beräknas från BR
            )
            
            # Exportera RR och BR
            export_pdf(df_rr, df_rr_prev, rr_pdf_path, current_year_string, previous_year_string)
            export_pdf_br(df_br, df_br_prev, br_pdf_path, current_end_date_string, previous_end_date_string)
            
            # Skapa noter
            create_notes_pdf(
                noter_pdf_path,
                temp_se_path,
                current_year=current_year,
                previous_year=previous_year
            )
            
            # Slå samman alla PDF:er
            final_pdf_path = os.path.join(self.reports_dir, f"arsredovisning_{report_id}.pdf")
            merge_all_pdfs(forvaltning_pdf_path, rr_pdf_path, br_pdf_path, noter_pdf_path, final_pdf_path)
            
            # Rensa upp temporära filer
            shutil.rmtree(temp_report_dir)
            
            return {
                "report_id": report_id,
                "pdf_path": final_pdf_path,
                "generated_at": datetime.now().isoformat(),
                "company_name": request.company_data.company_name,
                "fiscal_year": request.company_data.fiscal_year,
                "parsed_accounts": len(current_accounts),
                "rr_items": len(rr_data),
                "br_items": len(br_data)
            }
            
        except Exception as e:
            raise Exception(f"Fel vid generering av rapport: {str(e)}")
    
    def _convert_rr_data_to_old_format(self, rr_data: List[Dict[str, Any]]) -> Any:
        """Convert new RR data format to old format for PDF generation"""
        # This is a temporary bridge function
        # TODO: Update PDF generation to use new format directly
        import pandas as pd
        
        if not rr_data:
            return pd.DataFrame()
        
        # Convert to DataFrame format expected by old PDF generation
        df_data = []
        for item in rr_data:
            df_data.append({
                'Radrubrik': item['label'],
                'Belopp': item['current_amount'] if item['current_amount'] is not None else 0.0,
                'Level': item['level'],
                'Style': item['style'],
                'Bold': item['bold']
            })
        
        return pd.DataFrame(df_data)
    
    def _convert_br_data_to_old_format(self, br_data: List[Dict[str, Any]]) -> Any:
        """Convert new BR data format to old format for PDF generation"""
        # This is a temporary bridge function
        # TODO: Update PDF generation to use new format directly
        import pandas as pd
        
        if not br_data:
            return pd.DataFrame()
        
        # Convert to DataFrame format expected by old PDF generation
        df_data = []
        for item in br_data:
            df_data.append({
                'Radrubrik': item['label'],
                'Belopp': item['current_amount'] if item['current_amount'] is not None else 0.0,
                'Level': item['level'],
                'Style': item['style'],
                'Bold': item['bold'],
                'Type': item.get('type', 'asset')
            })
        
        return pd.DataFrame(df_data)
    
    def get_report_path(self, report_id: str) -> str:
        """Hämtar sökväg till genererad rapport"""
        return os.path.join(self.reports_dir, f"arsredovisning_{report_id}.pdf")
    
    async def scrape_company_info(self, organization_number: str) -> Dict[str, Any]:
        """
        Hämtar företagsinformation från Allabolag.se
        """
        try:
            # Använd befintlig scraping-funktion
            company_data = scrape_allabolag_data(organization_number, 2024, 2023, 2022, 2021)
            
            if company_data:
                return {
                    "organization_number": organization_number,
                    "company_name": company_data.get("company_name", ""),
                    "business_description": company_data.get("verksamhet", ""),
                    "location": company_data.get("sate", ""),
                    "board_members": company_data.get("styrelse_medlemmar", []),
                    "employee_count": company_data.get("antal_anstallda", 0),
                    "key_figures": company_data.get("nyckeltal", {})
                }
            else:
                return {
                    "organization_number": organization_number,
                    "company_name": f"Företag {organization_number}",
                    "business_description": "Information kunde inte hämtas",
                    "location": "",
                    "board_members": [],
                    "employee_count": 0,
                    "key_figures": {}
                }
                
        except Exception as e:
            raise Exception(f"Fel vid hämtning av företagsinfo: {str(e)}") 