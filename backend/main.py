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
# from services.report_generator import ReportGenerator  # Disabled - using DatabaseParser instead
from services.supabase_service import SupabaseService
from services.database_parser import DatabaseParser
from services.supabase_database import db
from services.bolagsverket_service import BolagsverketService
from models.schemas import (
    ReportRequest, ReportResponse, CompanyData, 
    ManagementReportRequest, ManagementReportResponse, 
    BolagsverketCompanyInfo, ManagementReportData
)

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
# report_generator = ReportGenerator()  # Disabled - using DatabaseParser instead
supabase_service = SupabaseService()
bolagsverket_service = BolagsverketService()

def get_supabase_client():
    """Get Supabase client from the service"""
    if not supabase_service.client:
        raise HTTPException(status_code=500, detail="Supabase client not available")
    return supabase_service.client

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
        current_accounts, previous_accounts, current_ib_accounts, previous_ib_accounts = parser.parse_account_balances(se_content)
        company_info = parser.extract_company_info(se_content)
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts)
        
        # Pass RR data to BR parsing so calculated values from RR are available
        br_data = parser.parse_br_data(current_accounts, previous_accounts, rr_data)
        
        # Parse INK2 data (tax calculations) - pass RR data for variable references
        ink2_data = parser.parse_ink2_data(current_accounts, company_info.get('fiscal_year'), rr_data)
        
        # Parse Noter data (notes) - pass SE content and user toggles if needed
        try:
            noter_data = parser.parse_noter_data(se_content)
            print(f"Successfully parsed {len(noter_data)} Noter items")
        except Exception as e:
            print(f"Error parsing Noter data: {e}")
            noter_data = []
        
        # Calculate pension tax variables for frontend
        pension_premier = abs(float(current_accounts.get('7410', 0.0)))
        sarskild_loneskatt_pension = abs(float(current_accounts.get('7531', 0.0)))
        # Get sarskild_loneskatt rate from global variables
        sarskild_loneskatt_rate = float(parser.global_variables.get('sarskild_loneskatt', 0.0))
        sarskild_loneskatt_pension_calculated = pension_premier * sarskild_loneskatt_rate
        
        # Store financial data in database (but don't fail if storage fails)
        stored_ids = {}
        if company_info.get('organization_number'):
            company_id = company_info['organization_number']
            fiscal_year = company_info.get('fiscal_year', datetime.now().year)
            
            try:
                # Store the parsed financial data
                stored_ids = parser.store_financial_data(company_id, fiscal_year, rr_data, br_data)
                print(f"Stored financial data with IDs: {stored_ids}")
            except Exception as e:
                print(f"Warning: Could not store financial data: {e}")
                stored_ids = {}
        
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
                "noter_data": noter_data,
                "rr_count": len(rr_data),
                "br_count": len(br_data),
                "ink2_count": len(ink2_data),
                "noter_count": len(noter_data),
                "pension_premier": pension_premier,
                "sarskild_loneskatt_pension": sarskild_loneskatt_pension,
                "sarskild_loneskatt_pension_calculated": sarskild_loneskatt_pension_calculated
            },
            "message": "SE-fil laddad framgångsrikt"
        }
        
    except Exception as e:
        import traceback
        error_detail = f"Fel vid laddning av fil: {str(e)}"
        full_traceback = traceback.format_exc()
        print(f"ERROR in upload_se_file: {error_detail}")
        print(f"Full traceback: {full_traceback}")
        # Return more detailed error for debugging (you may want to remove this in production)
        raise HTTPException(status_code=500, detail=f"Fel vid laddning av fil: {str(e)} | Traceback: {full_traceback}")

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
        current_accounts, previous_accounts, current_ib_accounts, previous_ib_accounts = parser.parse_account_balances(se_content)
        company_info = parser.extract_company_info(se_content)
        rr_data = parser.parse_rr_data(current_accounts, previous_accounts)
        br_data = parser.parse_br_data(current_accounts, previous_accounts)
        
        print(f"Parsed {len(current_accounts)} current year accounts, {len(previous_accounts)} previous year accounts")
        print(f"Generated {len(rr_data)} RR items, {len(br_data)} BR items")
        
        # Store financial data in database (but don't fail if storage fails)
        stored_ids = {}
        if company_info.get('organization_number'):
            company_id = company_info['organization_number']
            fiscal_year = company_info.get('fiscal_year', datetime.now().year)
            
            try:
                # Store the parsed financial data
                stored_ids = parser.store_financial_data(company_id, fiscal_year, rr_data, br_data)
                print(f"Stored financial data with IDs: {stored_ids}")
            except Exception as e:
                print(f"Warning: Could not store financial data: {e}")
                stored_ids = {}
        
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
    ink4_16_underskott_adjustment: Optional[float] = 0.0

@app.get("/api/chat-flow/{step_number}")
async def get_chat_flow_step(step_number: int):
    """
    Get chat flow step by step number
    """
    try:
        supabase = get_supabase_client()
        
        # Query the chat_flow table with new structure
        result = supabase.table('chat_flow').select('*').eq('step_number', step_number).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Step not found")
        
        step_data = result.data[0]
        
        # Convert to new format with options array
        options = []
        
        # Add no_option if it exists
        if step_data.get('no_option_value'):
            options.append({
                "option_order": 0,
                "option_text": None,
                "option_value": step_data['no_option_value'],
                "next_step": step_data.get('no_option_next_step'),
                "action_type": step_data.get('no_option_action_type'),
                "action_data": step_data.get('no_option_action_data')
            })
        
        # Add regular options
        for i in range(1, 5):
            option_text = step_data.get(f'option{i}_text')
            option_value = step_data.get(f'option{i}_value')
            
            if option_text and option_value:
                options.append({
                    "option_order": i,
                    "option_text": option_text,
                    "option_value": option_value,
                    "next_step": step_data.get(f'option{i}_next_step'),
                    "action_type": step_data.get(f'option{i}_action_type'),
                    "action_data": step_data.get(f'option{i}_action_data')
                })
        
        # Return the step data with new structure
        return {
            "success": True,
            "step_number": step_data['step_number'],
            "block": step_data.get('block'),
            "question_text": step_data['question_text'],
            "question_icon": step_data.get('question_icon'),
            "question_type": step_data['question_type'],
            "input_type": step_data.get('input_type'),
            "input_placeholder": step_data.get('input_placeholder'),
            "show_conditions": step_data.get('show_conditions'),
            "options": options
        }
        
    except Exception as e:
        print(f"Error getting chat flow step: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting chat flow step: {str(e)}")

@app.get("/api/chat-flow/next/{current_step}")
async def get_next_chat_flow_step(current_step: int):
    """
    Get the next chat flow step in sequence
    """
    try:
        supabase = get_supabase_client()
        
        # Find the next step number greater than current_step
        result = supabase.table('chat_flow').select('step_number').gt('step_number', current_step).order('step_number').limit(1).execute()
        
        if not result.data:
            return {"success": True, "next_step": None}  # End of flow
        
        next_step = result.data[0]['step_number']
        return await get_chat_flow_step(next_step)
        
    except Exception as e:
        print(f"Error getting next chat flow step: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting next chat flow step: {str(e)}")

@app.post("/api/chat-flow/process-choice")
async def process_chat_choice(request: dict):
    """
    Process user choice and return next action
    """
    try:
        step_number = request.get("step_number")
        option_value = request.get("option_value")
        context = request.get("context", {})
        
        print(f"🔍 Processing choice: step={step_number}, option={option_value}, context={context}")
        
        # Get the current step to find the selected option
        step_data = await get_chat_flow_step(step_number)
        print(f"🔍 Step data for {step_number}: {step_data}")
        if not step_data["success"]:
            raise HTTPException(status_code=404, detail="Step not found")
        
        # Find the selected option
        selected_option = None
        print(f"🔍 Available options: {[opt['option_value'] for opt in step_data['options']]}")
        for option in step_data["options"]:
            if option["option_value"] == option_value:
                selected_option = option
                break
        
        print(f"🔍 Selected option: {selected_option}")
        if not selected_option:
            raise HTTPException(status_code=400, detail=f"Invalid option '{option_value}'. Available: {[opt['option_value'] for opt in step_data['options']]}")
        
        # Process variable substitution in the result
        result = {
            "action_type": selected_option["action_type"],
            "action_data": selected_option["action_data"],
            "next_step": selected_option["next_step"]
        }
        
        # Apply variable substitution if context is provided
        if context:
            result = substitute_variables(result, context)
        
        return {"success": True, "result": result}
        
    except Exception as e:
        import traceback
        print(f"Error processing chat choice: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing chat choice: {str(e)}")

def substitute_variables(data, context):
    """Replace {variable} placeholders with actual values"""
    import json
    data_str = json.dumps(data) if data else "{}"
    
    import re
    for key, value in context.items():
        placeholder = f"{{{key}}}"
        # Use regex to ensure exact placeholder match (though curly braces make this safer already)
        if isinstance(value, (int, float)):
            # Format numbers with Swedish locale
            formatted_value = f"{value:,.0f}".replace(',', ' ')
            data_str = re.sub(re.escape(placeholder), formatted_value, data_str)
        else:
            data_str = re.sub(re.escape(placeholder), str(value), data_str)
    
    return json.loads(data_str)

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
            print(f"🔥 Injecting INK4.14a unused tax loss: {request.ink4_14a_outnyttjat_underskott}")
        if request.ink4_16_underskott_adjustment and request.ink4_16_underskott_adjustment != 0:
            manual_amounts['ink4_16_underskott_adjustment'] = request.ink4_16_underskott_adjustment
            print(f"📊 Injecting ink4_16_underskott_adjustment: {request.ink4_16_underskott_adjustment}")
        if request.justering_sarskild_loneskatt and request.justering_sarskild_loneskatt != 0:
            manual_amounts['justering_sarskild_loneskatt'] = request.justering_sarskild_loneskatt
            print(f"💰 Injecting pension tax adjustment: {request.justering_sarskild_loneskatt}")
        
        # Parse INK2 data with manual overrides
        ink2_data = parser.parse_ink2_data_with_overrides(
            current_accounts=current_accounts,
            fiscal_year=request.fiscal_year or datetime.now().year,
            rr_data=request.rr_data,
            br_data=request.br_data,
            manual_amounts=manual_amounts
        )
        
        return {
            "success": True,
            "ink2_data": ink2_data
        }
        
    except Exception as e:
        print(f"Error in recalculate_ink2: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recalculating INK2: {str(e)}")

@app.post("/api/calculate-periodiseringsfonder")
async def calculate_periodiseringsfonder(request: dict):
    """
    Calculate periodiseringsfonder data from SE file accounts
    """
    try:
        supabase = get_supabase_client()
        current_accounts = request.get('current_accounts', {})
        
        # Get mapping data from database
        result = supabase.table('periodiseringsfond_mapping').select('*').order('row_id').execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Periodiseringsfond mapping not found")
        
        periodiseringsfonder_data = []
        calculated_values = {}
        
        # Process each row
        for row in result.data:
            item = {
                'variable_name': row['variable_name'],
                'row_title': row['row_title'],
                'header': row['header'],
                'always_show': row['always_show'],
                'show_amount': row['show_amount'],
                'is_calculated': row['is_calculated'],
                'amount': 0
            }
            
            if row['is_calculated'] and row['calculation_formula']:
                # Handle calculated fields (like Pfonder_sum and Schablonranta)
                formula = row['calculation_formula']
                
                if 'Pfonder_sum*statslaneranta' in formula:
                    # Calculate schablonranta (need statslaneranta from somewhere)
                    pfonder_sum = calculated_values.get('Pfonder_sum', 0)
                    statslaneranta = 0.016  # 1.6% - this should come from settings/config
                    item['amount'] = pfonder_sum * statslaneranta
                    calculated_values[row['variable_name']] = item['amount']
                elif '+' in formula:
                    # Sum formula like Pfonder_minus1+Pfonder_minus2+...
                    total = 0
                    for var_name in formula.split('+'):
                        var_name = var_name.strip()
                        total += calculated_values.get(var_name, 0)
                    item['amount'] = total
                    calculated_values[row['variable_name']] = item['amount']
                    
            elif row['accounts_included']:
                # Get account balance from SE file
                account_number = row['accounts_included']
                account_balance = current_accounts.get(account_number, 0)
                item['amount'] = float(account_balance)
                calculated_values[row['variable_name']] = item['amount']
            
            periodiseringsfonder_data.append(item)
        
        return {
            "success": True,
            "periodiseringsfonder_data": periodiseringsfonder_data
        }
        
    except Exception as e:
        print(f"Error calculating periodiseringsfonder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error calculating periodiseringsfonder: {str(e)}")

# Förvaltningsberättelse endpoints

@app.get("/forvaltningsberattelse/template")
async def get_management_report_template():
    """
    Hämta mall för förvaltningsberättelse
    """
    try:
        template = bolagsverket_service.get_management_report_template()
        return {
            "success": True,
            "template": template,
            "message": "Template hämtad framgångsrikt"
        }
    except Exception as e:
        print(f"Error getting template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/forvaltningsberattelse/validate", response_model=dict)
async def validate_management_report(management_report: ManagementReportData):
    """
    Validera förvaltningsberättelse data
    """
    try:
        validation_result = await bolagsverket_service.validate_management_report(
            management_report.dict()
        )
        
        return {
            "success": True,
            "validation_result": validation_result,
            "message": "Validation completed"
        }
    except Exception as e:
        print(f"Error validating management report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bolagsverket/company/{org_number}", response_model=dict)
async def get_company_info_from_bolagsverket(org_number: str):
    """
    Hämta företagsinformation från Bolagsverket API
    """
    try:
        # Validate org number format (should be 10 digits)
        if not org_number.isdigit() or len(org_number) != 10:
            raise HTTPException(
                status_code=400, 
                detail="Organization number must be 10 digits"
            )
        
        company_info = await bolagsverket_service.get_company_info(org_number)
        
        if not company_info:
            raise HTTPException(
                status_code=404, 
                detail=f"No information found for organization {org_number}"
            )
        
        return {
            "success": True,
            "company_info": company_info,
            "message": "Företagsinformation hämtad från Bolagsverket"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching company info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bolagsverket/documents/{org_number}", response_model=dict)
async def get_company_documents_from_bolagsverket(org_number: str):
    """
    Hämta dokumentlista för företag från Bolagsverket API
    """
    try:
        # Validate org number format (should be 10 digits)
        if not org_number.isdigit() or len(org_number) != 10:
            raise HTTPException(
                status_code=400, 
                detail="Organization number must be 10 digits"
            )
        
        document_list = await bolagsverket_service.get_document_list(org_number)
        
        if document_list is None:
            raise HTTPException(
                status_code=404, 
                detail=f"No documents found for organization {org_number}"
            )
        
        return {
            "success": True,
            "document_list": document_list,
            "message": "Dokumentlista hämtad från Bolagsverket"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching document list: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bolagsverket/document/{document_id}", response_model=dict)
async def get_document_from_bolagsverket(document_id: str):
    """
    Hämta specifikt dokument från Bolagsverket API
    """
    try:
        document = await bolagsverket_service.get_document(document_id)
        
        if not document:
            raise HTTPException(
                status_code=404, 
                detail=f"Document {document_id} not found"
            )
        
        return {
            "success": True,
            "document": document,
            "message": "Dokument hämtat från Bolagsverket"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bolagsverket/health", response_model=dict)
async def check_bolagsverket_health():
    """
    Kontrollera hälsa för Bolagsverket API
    """
    try:
        is_healthy = await bolagsverket_service.check_api_health()
        
        return {
            "success": True,
            "healthy": is_healthy,
            "message": "Bolagsverket API health check completed"
        }
    except Exception as e:
        print(f"Error checking Bolagsverket health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/forvaltningsberattelse/submit", response_model=ManagementReportResponse)
async def submit_management_report(report_request: ManagementReportRequest):
    """
    Skicka in förvaltningsberättelse till Bolagsverket
    """
    try:
        # First validate the management report
        validation_result = await bolagsverket_service.validate_management_report(
            report_request.management_report.dict()
        )
        
        if not validation_result["valid"]:
            return ManagementReportResponse(
                success=False,
                validation_result=validation_result,
                message="Validation failed. Please correct the errors before submitting."
            )
        
        # Prepare the complete annual report data structure
        annual_report_data = {
            "organizationNumber": report_request.organization_number,
            "companyName": report_request.company_name,
            "fiscalYear": report_request.fiscal_year,
            "managementReport": report_request.management_report.dict(),
            "submissionDate": datetime.now().isoformat()
        }
        
        # Submit to Bolagsverket
        submission_result = await bolagsverket_service.submit_annual_report(
            report_request.organization_number,
            annual_report_data
        )
        
        if submission_result:
            return ManagementReportResponse(
                success=True,
                validation_result=validation_result,
                submission_id=submission_result.get("submissionId"),
                message="Förvaltningsberättelse submitted successfully to Bolagsverket"
            )
        else:
            return ManagementReportResponse(
                success=False,
                validation_result=validation_result,
                message="Failed to submit to Bolagsverket. Please try again later."
            )
            
    except Exception as e:
        print(f"Error submitting management report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get port from environment variable (Railway sets this)
    port = int(os.environ.get("PORT", 8080))
    
    uvicorn.run(app, host="0.0.0.0", port=port) 