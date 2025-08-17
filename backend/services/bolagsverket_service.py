import os
import requests
import json
import uuid
import io
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

load_dotenv()

class BolagsverketService:
    """
    Service for integrating with Bolagsverket DIAR API
    Handles authentication and API calls for annual report operations
    """
    
    def __init__(self):
        # Production credentials
        self.client_id = "oH7J10u23a8r4YZMtid91N7fQ98a"
        self.client_secret = "xvD1Q2FcTIKVaYZUd9Q7N_0lfwka"
        self.api_base_url = "https://gw.api.bolagsverket.se/vardefulla-datamangder/v1"
        self.auth_url = "https://portal.api.bolagsverket.se/oauth2/token"
        
        # Token management
        self.access_token = None
        self.token_expires_at = None
        
        self.logger = logging.getLogger(__name__)
        
        if not self.client_id or not self.client_secret:
            self.logger.warning("Bolagsverket API credentials missing. Using mock mode.")
            self.mock_mode = True
        else:
            self.mock_mode = False
    
    async def _get_access_token(self) -> Optional[str]:
        """
        Get or refresh access token using OAuth2 client credentials flow
        """
        if self.mock_mode:
            return "mock_token"
            
        # Check if current token is still valid
        if (self.access_token and self.token_expires_at and 
            datetime.now() < self.token_expires_at):
            return self.access_token
        
        try:
            # Request new token with scope for valuable data
            token_data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "vardefulla-datamangder:read"
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            response = requests.post(
                self.auth_url,
                data=token_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                token_response = response.json()
                self.access_token = token_response.get("access_token")
                expires_in = token_response.get("expires_in", 3600)
                
                # Set expiry time with 5 minute buffer
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                
                self.logger.info("Successfully obtained Bolagsverket access token")
                return self.access_token
            else:
                self.logger.error(f"Failed to get access token: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting access token: {str(e)}")
            return None
    
    async def check_api_health(self) -> bool:
        """
        Check if Bolagsverket API is responding
        
        Returns:
            True if API is healthy, False otherwise
        """
        if self.mock_mode:
            return True
        
        token = await self._get_access_token()
        if not token:
            return False
        
        try:
            url = f"{self.api_base_url}/isalive"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "X-Request-Id": str(uuid.uuid4())
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            return response.status_code == 200
            
        except Exception as e:
            self.logger.error(f"Error checking API health: {str(e)}")
            return False

    async def get_company_info(self, org_number: str) -> Optional[Dict[str, Any]]:
        """
        Get company information from Bolagsverket
        
        Args:
            org_number: Swedish organization number (10 digits)
            
        Returns:
            Dict with company information or None if error
        """
        if self.mock_mode:
            return {
                "organizationNumber": org_number,
                "companyName": f"Mock Company {org_number}",
                "status": "ACTIVE"
            }
        
        token = await self._get_access_token()
        if not token:
            return None
        
        try:
            url = f"{self.api_base_url}/organisationer"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Request-Id": str(uuid.uuid4())
            }
            
            # Request body for organization lookup
            request_data = {
                "identitetsbeteckning": org_number
            }
            
            response = requests.post(url, json=request_data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                self.logger.warning(f"No company info found for organization {org_number}")
                return None
            else:
                self.logger.error(f"API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching company info: {str(e)}")
            return None

    async def get_document_list(self, org_number: str) -> Optional[Dict[str, Any]]:
        """
        Get document list for a company
        
        Args:
            org_number: Swedish organization number (10 digits)
            
        Returns:
            Dict with document list or None if error
        """
        if self.mock_mode:
            return {
                "organisationnummer": org_number,
                "dokument": [
                    {
                        "dokumentId": "mock-doc-1",
                        "dokumentTyp": "Årsredovisning",
                        "datum": "2024-12-31",
                        "status": "GODKÄND"
                    }
                ]
            }
        
        token = await self._get_access_token()
        if not token:
            return None
        
        try:
            url = f"{self.api_base_url}/dokumentlista"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Request-Id": str(uuid.uuid4())
            }
            
            # Request body for document list
            request_data = {
                "identitetsbeteckning": org_number
            }
            
            response = requests.post(url, json=request_data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                self.logger.warning(f"No documents found for organization {org_number}")
                return None
            else:
                self.logger.error(f"API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching document list: {str(e)}")
            return None

    async def get_document(self, document_id: str) -> Optional[bytes]:
        """
        Get a specific document by ID
        
        Args:
            document_id: Document identifier from document list
            
        Returns:
            Binary document data or None if error
        """
        if self.mock_mode:
            return b"Mock document content"
        
        token = await self._get_access_token()
        if not token:
            return None
        
        try:
            url = f"{self.api_base_url}/dokument/{document_id}"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "*/*",  # Accept any content type
                "X-Request-Id": str(uuid.uuid4())
            }
            
            response = requests.get(url, headers=headers, timeout=60)
            
            if response.status_code == 200:
                if len(response.content) == 0:
                    self.logger.warning(f"Document {document_id} returned empty content")
                    return None
                return response.content
            elif response.status_code == 404:
                self.logger.warning(f"Document {document_id} not found")
                return None
            else:
                self.logger.error(f"API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error fetching document: {str(e)}")
            return None

    async def get_and_extract_document(self, document_id: str, extract_dir: str = None) -> Optional[Dict[str, Any]]:
        """
        Get a document, extract it if it's a ZIP file, and return the extracted content
        
        Args:
            document_id: Document identifier from document list
            extract_dir: Directory to extract files to (optional)
            
        Returns:
            Dict with extracted file information or None if error
        """
        import zipfile
        import tempfile
        import os
        from bs4 import BeautifulSoup
        
        # Get the document
        document_data = await self.get_document(document_id)
        if not document_data:
            return None
        
        try:
            # Create temporary directory if none provided
            if not extract_dir:
                extract_dir = tempfile.mkdtemp(prefix=f"bolagsverket_{document_id}_")
            
            # Check if it's a ZIP file by trying to open it
            try:
                with zipfile.ZipFile(io.BytesIO(document_data), 'r') as zip_ref:
                    # Extract all files
                    zip_ref.extractall(extract_dir)
                    
                    # Find XHTML files
                    xhtml_files = []
                    for root, dirs, files in os.walk(extract_dir):
                        for file in files:
                            if file.endswith('.xhtml') or file.endswith('.xml'):
                                xhtml_files.append(os.path.join(root, file))
                    
                    # Process XHTML files
                    processed_files = []
                    for xhtml_file in xhtml_files:
                        try:
                            with open(xhtml_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # Parse XHTML with BeautifulSoup
                            soup = BeautifulSoup(content, 'html.parser')
                            
                            # Extract useful information
                            file_info = {
                                'filename': os.path.basename(xhtml_file),
                                'filepath': xhtml_file,
                                'content': content,
                                'parsed_html': soup,
                                'title': soup.find('title').get_text() if soup.find('title') else 'No title',
                                'text_content': soup.get_text()[:500] + '...' if len(soup.get_text()) > 500 else soup.get_text()
                            }
                            
                            processed_files.append(file_info)
                            
                        except Exception as e:
                            self.logger.error(f"Error processing XHTML file {xhtml_file}: {str(e)}")
                    
                    return {
                        'document_id': document_id,
                        'extract_dir': extract_dir,
                        'total_files': len(zip_ref.namelist()),
                        'xhtml_files': xhtml_files,
                        'processed_files': processed_files,
                        'zip_info': {
                            'file_list': zip_ref.namelist(),
                            'size': len(document_data)
                        }
                    }
                    
            except zipfile.BadZipFile:
                # Not a ZIP file, return as binary data
                return {
                    'document_id': document_id,
                    'extract_dir': extract_dir,
                    'is_zip': False,
                    'binary_data': document_data,
                    'size': len(document_data)
                }
                
        except Exception as e:
            self.logger.error(f"Error extracting document {document_id}: {str(e)}")
            return None

    async def get_company_annual_report_info(self, org_number: str) -> Optional[Dict[str, Any]]:
        """
        Get annual report information for a company (legacy method for compatibility)
        
        Args:
            org_number: Swedish organization number (10 digits)
            
        Returns:
            Dict with company annual report information or None if error
        """
        # Use the new document list method
        return await self.get_document_list(org_number)
    
    async def submit_annual_report(self, org_number: str, report_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Submit annual report including management report (förvaltningsberättelse)
        
        Args:
            org_number: Swedish organization number
            report_data: Complete annual report data including management report
            
        Returns:
            Submission result or None if error
        """
        if self.mock_mode:
            return {
                "submissionId": f"mock_submission_{org_number}_{datetime.now().isoformat()}",
                "status": "RECEIVED",
                "submissionDate": datetime.now().isoformat(),
                "organizationNumber": org_number
            }
        
        token = await self._get_access_token()
        if not token:
            return None
        
        try:
            # This would be the actual submission endpoint
            # The exact structure depends on Bolagsverket's API specification
            url = f"{self.api_base_url}/lamna-in-arsredovisning/v1.2/inlamning"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Format the data according to Bolagsverket's schema
            submission_data = {
                "organizationNumber": org_number,
                "annualReport": report_data,
                "submissionDate": datetime.now().isoformat()
            }
            
            response = requests.post(
                url, 
                json=submission_data, 
                headers=headers, 
                timeout=60
            )
            
            if response.status_code in [200, 201, 202]:
                return response.json()
            else:
                self.logger.error(f"Submission error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error submitting annual report: {str(e)}")
            return None
    
    async def validate_management_report(self, management_report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate management report (förvaltningsberättelse) data structure
        
        Args:
            management_report_data: Management report data to validate
            
        Returns:
            Validation result with errors if any
        """
        errors = []
        warnings = []
        
        # Required fields for Swedish management reports
        required_fields = [
            "businessDescription",  # Verksamhetsbeskrivning
            "significantEvents",    # Väsentliga händelser
            "developmentWork",      # Utvecklingsarbete
            "financialPosition",    # Finansiell ställning
            "riskManagement",       # Riskhantering
            "futureOutlook"         # Framtidsutsikter
        ]
        
        # Check required fields
        for field in required_fields:
            if field not in management_report_data or not management_report_data[field]:
                errors.append(f"Required field '{field}' is missing or empty")
        
        # Check text length requirements (Swedish regulations)
        if "businessDescription" in management_report_data:
            desc_length = len(management_report_data["businessDescription"])
            if desc_length < 100:
                warnings.append("Business description is quite short (< 100 characters)")
            elif desc_length > 2000:
                warnings.append("Business description is very long (> 2000 characters)")
        
        # Validate financial position section
        if "financialPosition" in management_report_data:
            fin_pos = management_report_data["financialPosition"]
            if isinstance(fin_pos, dict):
                required_fin_fields = ["liquidity", "profitability", "solvency"]
                for field in required_fin_fields:
                    if field not in fin_pos:
                        warnings.append(f"Financial position should include '{field}' analysis")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "fieldCount": len(management_report_data),
            "validatedAt": datetime.now().isoformat()
        }
    
    def get_management_report_template(self) -> Dict[str, Any]:
        """
        Get a template structure for Swedish management report (förvaltningsberättelse)
        
        Returns:
            Template dict with required sections
        """
        return {
            "businessDescription": {
                "description": "Beskrivning av verksamheten",
                "content": "",
                "required": True,
                "maxLength": 2000
            },
            "significantEvents": {
                "description": "Väsentliga händelser under räkenskapsåret",
                "content": "",
                "required": True,
                "maxLength": 1500
            },
            "developmentWork": {
                "description": "Forsknings- och utvecklingsarbete",
                "content": "",
                "required": True,
                "maxLength": 1000
            },
            "financialPosition": {
                "description": "Finansiell ställning",
                "content": {
                    "liquidity": "",
                    "profitability": "",
                    "solvency": ""
                },
                "required": True
            },
            "riskManagement": {
                "description": "Riskhantering och osäkerhetsfaktorer",
                "content": "",
                "required": True,
                "maxLength": 1500
            },
            "futureOutlook": {
                "description": "Förväntad framtida utveckling",
                "content": "",
                "required": True,
                "maxLength": 1000
            },
            "environmentalImpact": {
                "description": "Miljöpåverkan (om tillämpligt)",
                "content": "",
                "required": False,
                "maxLength": 800
            },
            "personnelInformation": {
                "description": "Personalförhållanden",
                "content": "",
                "required": False,
                "maxLength": 500
            }
        }
