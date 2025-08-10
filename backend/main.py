from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import tempfile
import shutil
from datetime import datetime
import json

# Importera våra moduler
from services.report_generator import ReportGenerator
from services.supabase_service import SupabaseService
from services.database_parser import DatabaseParser
from services.supabase_database import db
from models.schemas import ReportRequest, ReportResponse, CompanyData

app = FastAPI(
    title="Raketrapport API",
    description="API för att generera årsredovisningar enligt K2",
    version="1.0.0"
)

# CORS middleware för React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:8080",
        "https://raketrapport.se",
        "https://www.raketrapport.se",
        "https://raket-arsredovisning.vercel.app",
        "https://raketrapport-production.up.railway.app"  # Railway backend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initiera services
report_generator = ReportGenerator()
supabase_service = SupabaseService()

@app.get("/")
async def root():
    return {"message": "Raketrapport API är igång! 🚀"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/upload-se-file", response_model=dict)
async def upload_se_file(file: UploadFile = File(...)):
    """
    Laddar upp en .SE-fil och extraherar grundläggande information
    """
    if not file.filename.lower().endswith('.se'):
        raise HTTPException(status_code=400, detail="Endast .SE-filer accepteras")
    
    try:
        # Skapa temporär fil
        with tempfile.NamedTemporaryFile(delete=False, suffix='.se') as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
        
        # Read SE file content with encoding detection
        encodings = ['iso-8859-1', 'windows-1252', 'utf-8', 'cp1252']
        se_content = None
        
        for encoding in encodings:
            try:
                with open(temp_path, 'r', encoding=encoding) as f:
                    se_content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if se_content is None:
            raise HTTPException(status_code=500, detail="Kunde inte läsa SE-filen med någon av de försökta kodningarna")
        
        # Use the new database-driven parser
        parser = DatabaseParser()
        current_accounts, previous_accounts = parser.parse_account_balances(se_content)
        company_info = parser.extract_company_info(se_content)
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts)
        
        # Pass RR data to BR parsing so calculated values from RR are available
        br_data = parser.parse_br_data(current_accounts, previous_accounts, rr_data)
        
        # Parse INK2 data (tax calculations) - pass RR data for variable references
        ink2_data = parser.parse_ink2_data(current_accounts, company_info.get('fiscal_year'), rr_data)
        
        # Calculate pension tax variables for frontend
        pension_premier = abs(float(current_accounts.get('7410', 0.0)))
        sarskild_loneskatt_pension = abs(float(current_accounts.get('7531', 0.0)))
        # Get sarskild_loneskatt rate from global variables
        sarskild_loneskatt_rate = float(parser.global_variables.get('sarskild_loneskatt', 0.0))
        sarskild_loneskatt_pension_calculated = pension_premier * sarskild_loneskatt_rate
        
        # Store financial data in database
        if company_info.get('organization_number'):
            company_id = company_info['organization_number']
            fiscal_year = company_info.get('fiscal_year', datetime.now().year)
            
            # Store the parsed financial data
            stored_ids = parser.store_financial_data(company_id, fiscal_year, rr_data, br_data)
            print(f"Stored financial data with IDs: {stored_ids}")
        
        # Rensa upp temporär fil
        os.unlink(temp_path)
        
        return {
            "success": True,
            "data": {
                "company_info": company_info,
                "current_accounts_count": len(current_accounts),
                "previous_accounts_count": len(previous_accounts),
                "current_accounts_sample": dict(list(current_accounts.items())[:10]),
                "previous_accounts_sample": dict(list(previous_accounts.items())[:10]),
                "current_accounts": current_accounts,  # Add full accounts for recalculation
                "rr_data": rr_data,
                "br_data": br_data,
                "ink2_data": ink2_data,
                "rr_count": len(rr_data),
                "br_count": len(br_data),
                "ink2_count": len(ink2_data),
                "pension_premier": pension_premier,
                "sarskild_loneskatt_pension": sarskild_loneskatt_pension,
                "sarskild_loneskatt_pension_calculated": sarskild_loneskatt_pension_calculated
            },
            "message": "SE-fil laddad framgångsrikt"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid laddning av fil: {str(e)}")

@app.post("/generate-report", response_model=ReportResponse)
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks
):
    """
    Genererar årsredovisning baserat på .SE-fil och användarinput
    """
    try:
        # Generera rapport
        report_data = await report_generator.generate_full_report(request)
        
        # Spara till Supabase (i bakgrunden)
        background_tasks.add_task(
            supabase_service.save_report,
            request.user_id,
            report_data
        )
        
        return ReportResponse(
            success=True,
            report_id=report_data["report_id"],
            download_url=f"/download-report/{report_data['report_id']}",
            message="Rapport genererad framgångsrikt!"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid generering av rapport: {str(e)}")

@app.get("/download-report/{report_id}")
async def download_report(report_id: str):
    """
    Laddar ner genererad PDF-rapport
    """
    try:
        file_path = report_generator.get_report_path(report_id)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Rapport hittades inte")
        
        return FileResponse(
            path=file_path,
            filename=f"arsredovisning_{report_id}.pdf",
            media_type="application/pdf"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid nedladdning: {str(e)}")

@app.get("/user-reports/{user_id}")
async def get_user_reports(user_id: str):
    """
    Hämtar användarens tidigare rapporter
    """
    try:
        reports = await supabase_service.get_user_reports(user_id)
        return {"reports": reports}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid hämtning av rapporter: {str(e)}")

@app.get("/company-info/{organization_number}")
async def get_company_info(organization_number: str):
    """
    Hämtar företagsinformation från Allabolag.se
    """
    try:
        company_info = await report_generator.scrape_company_info(organization_number)
        return company_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid hämtning av företagsinfo: {str(e)}")

@app.post("/update-formula/{row_id}")
async def update_formula(row_id: int, formula: str):
    """
    Updates calculation formula for a specific row in the database
    """
    try:
        parser = DatabaseParser()
        success = parser.update_calculation_formula(row_id, formula)
        
        if success:
            return {"success": True, "message": f"Formula updated for row {row_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update formula")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating formula: {str(e)}")

@app.post("/test-parser", response_model=dict)
async def test_parser(file: UploadFile = File(...)):
    """
    Test endpoint for the new database-driven parser
    """
    print(f"Received file: {file.filename}, size: {file.size if hasattr(file, 'size') else 'unknown'}")
    
    if not file.filename.lower().endswith('.se'):
        raise HTTPException(status_code=400, detail=f"Endast .SE-filer accepteras. Fick: {file.filename}")
    
    try:
        # Skapa temporär fil
        with tempfile.NamedTemporaryFile(delete=False, suffix='.se') as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = temp_file.name
        
        print(f"Created temp file: {temp_path}")
        
        # Read SE file content - try different encodings
        se_content = None
        encodings_to_try = ['iso-8859-1', 'windows-1252', 'utf-8', 'cp1252']
        
        for encoding in encodings_to_try:
            try:
                with open(temp_path, 'r', encoding=encoding) as f:
                    se_content = f.read()
                print(f"Successfully read file with {encoding} encoding")
                break
            except UnicodeDecodeError as e:
                print(f"Failed to read with {encoding} encoding: {e}")
                continue
        
        if se_content is None:
            raise Exception("Could not read file with any supported encoding")
        
        print(f"Read {len(se_content)} characters from file")
        
        # Initialize parser
        parser = DatabaseParser()
        
        # Parse data
        current_accounts, previous_accounts = parser.parse_account_balances(se_content)
        company_info = parser.extract_company_info(se_content)
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts)
        br_data = parser.parse_br_data(current_accounts, previous_accounts)
        
        print(f"Parsed {len(current_accounts)} current year accounts, {len(previous_accounts)} previous year accounts")
        print(f"Generated {len(rr_data)} RR items, {len(br_data)} BR items")
        
        # Store financial data in database
        if company_info.get('organization_number'):
            company_id = company_info['organization_number']
            fiscal_year = company_info.get('fiscal_year', datetime.now().year)
            
            # Store the parsed financial data
            stored_ids = parser.store_financial_data(company_id, fiscal_year, rr_data, br_data)
            print(f"Stored financial data with IDs: {stored_ids}")
        
        # Rensa upp temporär fil
        os.unlink(temp_path)
        
        return {
            "success": True,
            "company_info": company_info,
            "current_accounts_count": len(current_accounts),
            "previous_accounts_count": len(previous_accounts),
            "current_accounts_sample": dict(list(current_accounts.items())[:10]),  # First 10 current accounts
            "previous_accounts_sample": dict(list(previous_accounts.items())[:10]),  # First 10 previous accounts
            "rr_count": len(rr_data),
            "rr_sample": rr_data[:5],  # First 5 RR items
            "br_count": len(br_data),
            "br_sample": br_data[:5],  # First 5 BR items
            "message": "Parser test completed successfully"
        }
        
    except Exception as e:
        print(f"Error in test_parser: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fel vid parser test: {str(e)}")

@app.get("/financial-data/{company_id}/{fiscal_year}")
async def get_financial_data(company_id: str, fiscal_year: int):
    """
    Retrieve stored financial data for a specific company and fiscal year
    """
    try:
        parser = DatabaseParser()
        data = parser.get_financial_data(company_id, fiscal_year)
        
        return {
            "success": True,
            "company_id": company_id,
            "fiscal_year": fiscal_year,
            "data": data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving financial data: {str(e)}")

@app.get("/financial-data/companies")
async def list_companies_with_data():
    """
    List all companies that have financial data stored
    """
    try:
        result = supabase.table('financial_data').select('company_id, fiscal_year, report_type').execute()
        
        # Group by company
        companies = {}
        for record in result.data:
            company_id = record['company_id']
            if company_id not in companies:
                companies[company_id] = []
            companies[company_id].append({
                'fiscal_year': record['fiscal_year'],
                'report_type': record['report_type']
            })
        
        return {
            "success": True,
            "companies": companies
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing companies: {str(e)}")

@app.post("/api/recalculate-ink2")
async def recalculate_ink2(data: dict):
    """
    Recalculate INK2 values with manual amount overrides
    """
    try:
        current_accounts = data.get('current_accounts', {})
        fiscal_year = data.get('fiscal_year')
        rr_data = data.get('rr_data', [])
        br_data = data.get('br_data', [])
        manual_amounts = data.get('manual_amounts', {})
        justering_sarskild_loneskatt = data.get('justering_sarskild_loneskatt', 0)
        
        # Initialize parser
        parser = DatabaseParser()
        
        # Add pension tax adjustment to manual amounts if provided
        if justering_sarskild_loneskatt != 0:
            manual_amounts['justering_sarskild_loneskatt'] = justering_sarskild_loneskatt
        
        # Recalculate INK2 with manual overrides
        ink2_data = parser.parse_ink2_data_with_overrides(
            current_accounts, 
            fiscal_year, 
            rr_data, 
            br_data, 
            manual_amounts
        )
        
        return {
            "success": True,
            "ink2_data": ink2_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fel vid omberäkning: {str(e)}")

@app.get("/api/database/tables/{table_name}")
async def read_database_table(table_name: str, columns: str = "*", order_by: str = None):
    """
    Read data from a database table
    """
    try:
        data = db.read_table(table_name, columns=columns, order_by=order_by)
        return {
            "success": True,
            "table": table_name,
            "count": len(data),
            "data": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading table {table_name}: {str(e)}")

@app.post("/api/database/tables/{table_name}")
async def write_database_table(table_name: str, data: dict):
    """
    Insert data into a database table
    """
    try:
        rows = data.get('rows', [])
        success = db.write_table(table_name, rows)
        return {
            "success": success,
            "table": table_name,
            "inserted": len(rows) if success else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing to table {table_name}: {str(e)}")

@app.get("/api/database/ink2-mappings")
async def get_ink2_mappings():
    """
    Get all INK2 variable mappings
    """
    try:
        mappings = db.get_ink2_mappings()
        return {
            "success": True,
            "count": len(mappings),
            "data": mappings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting INK2 mappings: {str(e)}")

@app.get("/api/database/check-sarskild-loneskatt")
async def check_sarskild_loneskatt():
    """
    Check if INK_sarskild_loneskatt mapping exists
    """
    try:
        exists = db.check_ink_sarskild_loneskatt_exists()
        mapping = db.get_ink_sarskild_loneskatt_mapping() if exists else None
        return {
            "success": True,
            "exists": exists,
            "mapping": mapping
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking sarskild loneskatt: {str(e)}")

@app.post("/api/database/add-sarskild-loneskatt")
async def add_sarskild_loneskatt_mapping():
    """
    Add INK_sarskild_loneskatt mapping if it doesn't exist
    """
    try:
        # Check if it already exists
        if db.check_ink_sarskild_loneskatt_exists():
            return {
                "success": True,
                "message": "INK_sarskild_loneskatt mapping already exists",
                "created": False
            }
        
        # Add the mapping
        success = db.add_ink2_mapping(
            variable_name='INK_sarskild_loneskatt',
            row_title='Justering särskild löneskatt pensionspremier',
            accounts_included=None,
            calculation_formula='justering_sarskild_loneskatt',
            show_amount='TRUE',
            is_calculated='FALSE',
            always_show=None,  # Show only if amount != 0
            style='NORMAL',
            show_tag='FALSE',
            explainer='Justering av särskild löneskatt på pensionförsäkringspremier för att korrigera eventuella skillnader mellan bokfört och beräknat belopp.',
            block='INK4',
            header='FALSE'
        )
        
        return {
            "success": success,
            "message": "INK_sarskild_loneskatt mapping created" if success else "Failed to create mapping",
            "created": success
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding sarskild loneskatt mapping: {str(e)}")

class RecalculateRequest(BaseModel):
    current_accounts: dict
    fiscal_year: Optional[int] = None
    rr_data: List[dict]
    br_data: List[dict]
    manual_amounts: dict
    justering_sarskild_loneskatt: Optional[float] = 0.0
    ink4_14a_outnyttjat_underskott: Optional[float] = 0.0

@app.post("/api/recalculate-ink2")
async def recalculate_ink2(request: RecalculateRequest):
    """
    Recalculate INK2 data with manual amounts and adjustments
    """
    try:
        parser = DatabaseParser()
        
        # Convert current_accounts to have float values
        current_accounts = {k: float(v) for k, v in request.current_accounts.items()}
        
        # Inject special adjustment values into manual_amounts
        manual_amounts = dict(request.manual_amounts)
        if request.ink4_14a_outnyttjat_underskott and request.ink4_14a_outnyttjat_underskott > 0:
            manual_amounts['INK4.14a'] = request.ink4_14a_outnyttjat_underskott
        
        # Parse INK2 data with manual overrides
        ink2_data = parser.parse_ink2_data_with_overrides(
            current_accounts=current_accounts,
            fiscal_year=request.fiscal_year or datetime.now().year,
            rr_data=request.rr_data,
            br_data=request.br_data,
            manual_amounts=manual_amounts,
            justering_sarskild_loneskatt=request.justering_sarskild_loneskatt
        )
        
        return {
            "success": True,
            "ink2_data": ink2_data
        }
        
    except Exception as e:
        print(f"Error in recalculate_ink2: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recalculating INK2: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get port from environment variable (Railway sets this)
    port = int(os.environ.get("PORT", 8000))
    
    uvicorn.run(app, host="0.0.0.0", port=port) 