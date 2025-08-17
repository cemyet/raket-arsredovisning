from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class CompanyData(BaseModel):
    """Företagsdata från .SE-fil"""
    organization_number: str
    company_name: str
    fiscal_year: int
    previous_year: int
    current_end_date: str
    previous_end_date: str

class ReportRequest(BaseModel):
    """Request för att generera rapport"""
    user_id: str
    se_file_path: str
    company_data: CompanyData
    
    # Användarinput från frontend
    yearly_result: float = Field(..., description="Årets resultat")
    dividend: Optional[float] = Field(0, description="Utdelning")
    significant_events: Optional[str] = Field("Inga väsentliga händelser under året har rapporterats.", description="Väsentliga händelser")
    depreciation_periods: Optional[Dict[str, int]] = Field(default_factory=dict, description="Avskrivningstider")
    employee_count: Optional[int] = Field(..., description="Medelantal anställda")
    location: Optional[str] = Field(..., description="Ort")
    board_members: Optional[List[str]] = Field(default_factory=list, description="Styrelseledamöter")

class ReportResponse(BaseModel):
    """Response för genererad rapport"""
    success: bool
    report_id: str
    download_url: str
    message: str
    generated_at: datetime = Field(default_factory=datetime.now)

class UserReport(BaseModel):
    """Användarens sparade rapport"""
    id: str
    user_id: str
    report_id: str
    company_name: str
    fiscal_year: int
    created_at: datetime
    download_url: str

class CompanyInfo(BaseModel):
    """Företagsinformation från Allabolag.se"""
    organization_number: str
    company_name: str
    business_description: str
    location: str
    board_members: List[str]
    employee_count: Optional[int]
    key_figures: Dict[str, Any]

class ManagementReportData(BaseModel):
    """Förvaltningsberättelse data"""
    business_description: str = Field(..., description="Verksamhetsbeskrivning")
    significant_events: str = Field(..., description="Väsentliga händelser under räkenskapsåret")
    development_work: str = Field(..., description="Forsknings- och utvecklingsarbete")
    financial_position: Dict[str, str] = Field(..., description="Finansiell ställning")
    risk_management: str = Field(..., description="Riskhantering och osäkerhetsfaktorer")
    future_outlook: str = Field(..., description="Förväntad framtida utveckling")
    environmental_impact: Optional[str] = Field(None, description="Miljöpåverkan")
    personnel_information: Optional[str] = Field(None, description="Personalförhållanden")

class ManagementReportRequest(BaseModel):
    """Request för förvaltningsberättelse"""
    organization_number: str
    company_name: str
    fiscal_year: int
    management_report: ManagementReportData

class ManagementReportResponse(BaseModel):
    """Response för förvaltningsberättelse"""
    success: bool
    validation_result: Dict[str, Any]
    submission_id: Optional[str] = None
    message: str

class BolagsverketCompanyInfo(BaseModel):
    """Företagsinformation från Bolagsverket API"""
    organization_number: str
    company_name: str
    latest_event: Optional[Dict[str, Any]] = None
    status: Optional[str] = None 