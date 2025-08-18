"""
Database-driven parser for SE files
Replaces hardcoded BR_STRUCTURE and RR_STRUCTURE with database queries
"""

import os
from typing import Dict, List, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

class DatabaseParser:
    """Database-driven parser for financial data"""
    
    def __init__(self):
        self.rr_mappings = None
        self.br_mappings = None
        self.ink2_mappings = None
        self.noter_mappings = None
        self.global_variables = None
        self.accounts_lookup = None
        self._load_mappings()
    
    def _load_mappings(self):
        """Load variable mappings from database"""
        try:
            # Load RR mappings
            rr_response = supabase.table('variable_mapping_rr').select('*').execute()
            self.rr_mappings = rr_response.data
            
            # Load BR mappings
            br_response = supabase.table('variable_mapping_br').select('*').execute()
            self.br_mappings = br_response.data
            
            # Load INK2 mappings
            ink2_response = supabase.table('variable_mapping_ink2').select('*').execute()
            self.ink2_mappings = ink2_response.data
            
            # Load Noter mappings
            noter_response = supabase.table('variable_mapping_noter').select('*').execute()
            self.noter_mappings = noter_response.data
            
            # Debug logging for specific problematic variables
            for mapping in self.ink2_mappings:
                var_name = mapping.get('variable_name', '')
                if var_name in ['INK4.15', 'INK4.16', 'INK_bokford_skatt']:
                    print(f"DEBUG BACKEND MAPPING {var_name}: always_show={mapping.get('always_show')} (type: {type(mapping.get('always_show'))})")
            
            # Load global variables (normalize values to floats; treat % values as decimals)
            global_vars_response = supabase.table('global_variables').select('*').execute()
            self.global_variables = {}
            for var in global_vars_response.data:
                name = var.get('variable_name')
                raw = var.get('value')
                had_percent = False
                if isinstance(raw, str) and '%' in raw:
                    had_percent = True
                if isinstance(raw, (int, float)):
                    value = float(raw)
                else:
                    text = str(raw or '').strip().replace('%', '').replace(' ', '').replace(',', '.')
                    try:
                        value = float(text)
                    except ValueError:
                        value = 0.0
                if had_percent or name.lower().startswith('skattesats'):
                    # Convert percent like 20.6 to 0.206
                    value = value / 100.0
                self.global_variables[name] = value
            
            # Load accounts lookup (map by both int and string id for robustness)
            accounts_response = supabase.table('accounts_table').select('*').execute()
            self.accounts_lookup = {}
            for acc in accounts_response.data:
                acc_id = acc.get('account_id')
                text = acc.get('account_text') or f"Konto {acc_id}"
                # int key
                try:
                    self.accounts_lookup[int(acc_id)] = text
                except Exception:
                    pass
                # string key
                self.accounts_lookup[str(acc_id)] = text
            
            print(f"Loaded {len(self.rr_mappings)} RR mappings, {len(self.br_mappings)} BR mappings, {len(self.ink2_mappings)} INK2 mappings, and {len(self.noter_mappings)} Noter mappings")
            
        except Exception as e:
            print(f"Error loading mappings: {e}")
            self.rr_mappings = []
            self.br_mappings = []
            self.ink2_mappings = []
            self.noter_mappings = []
            self.global_variables = {}
            self.accounts_lookup = {}
    
    def parse_account_balances(self, se_content: str) -> Dict[str, float]:
        """Parse account balances from SE file content using the correct format"""
        current_accounts = {}
        previous_accounts = {}
        
        # Parse SE file content to extract account balances
        lines = se_content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Handle BR accounts: #UB (Uppgjord Balans) - both years
            if line.startswith('#UB '):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        fiscal_year = int(parts[1])
                        account_id = parts[2]
                        balance = float(parts[3])
                        
                        if fiscal_year == 0:  # Current year
                            current_accounts[account_id] = balance
                        elif fiscal_year == -1:  # Previous year
                            previous_accounts[account_id] = balance
                    except (ValueError, TypeError):
                        continue
                        
            # Handle RR accounts: #RES (Resultat) - both years
            elif line.startswith('#RES '):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        fiscal_year = int(parts[1])
                        account_id = parts[2]
                        balance = float(parts[3])
                        
                        if fiscal_year == 0:  # Current year
                            current_accounts[account_id] = balance
                        elif fiscal_year == -1:  # Previous year
                            previous_accounts[account_id] = balance
                    except (ValueError, TypeError):
                        continue
                        
            # Handle legacy #VER format (fallback)
            elif line.startswith('#VER'):
                parts = line.split()
                if len(parts) >= 3:
                    account_id = parts[1]
                    try:
                        balance = float(parts[2])
                        current_accounts[account_id] = balance
                    except ValueError:
                        continue
        
        print(f"Parsed {len(current_accounts)} current year accounts, {len(previous_accounts)} previous year accounts")
        if current_accounts:
            print(f"Sample current accounts: {dict(list(current_accounts.items())[:5])}")
        if previous_accounts:
            print(f"Sample previous accounts: {dict(list(previous_accounts.items())[:5])}")
        
        return current_accounts, previous_accounts
    
    def calculate_variable_value(self, mapping: Dict[str, Any], accounts: Dict[str, float]) -> float:
        """Calculate value for a specific variable based on its mapping"""
        total = 0.0
        
        # Get account ranges to include
        start = mapping.get('accounts_included_start')
        end = mapping.get('accounts_included_end')
        
        # Include accounts in range
        if start and end:
            for account_id in range(start, end + 1):
                account_str = str(account_id)
                if account_str in accounts:
                    total += accounts[account_str]
        
        # Include additional specific accounts
        additional_accounts = mapping.get('accounts_included')
        if additional_accounts:
            for account_spec in additional_accounts.split(';'):
                account_spec = account_spec.strip()
                if '-' in account_spec:
                    # Range specification (e.g., "4910-4931")
                    range_start, range_end = map(int, account_spec.split('-'))
                    for account_id in range(range_start, range_end + 1):
                        account_str = str(account_id)
                        if account_str in accounts:
                            total += accounts[account_str]
                else:
                    # Single account
                    if account_spec in accounts:
                        total += accounts[account_spec]
        
        # Exclude accounts in range
        exclude_start = mapping.get('accounts_excluded_start')
        exclude_end = mapping.get('accounts_excluded_end')
        
        if exclude_start and exclude_end:
            for account_id in range(exclude_start, exclude_end + 1):
                account_str = str(account_id)
                if account_str in accounts:
                    total -= accounts[account_str]
        
        # Exclude additional specific accounts
        excluded_accounts = mapping.get('accounts_excluded')
        if excluded_accounts:
            for account_spec in excluded_accounts.split(';'):
                account_spec = account_spec.strip()
                if '-' in account_spec:
                    # Range specification
                    range_start, range_end = map(int, account_spec.split('-'))
                    for account_id in range(range_start, range_end + 1):
                        account_str = str(account_id)
                        if account_str in accounts:
                            total -= accounts[account_str]
                else:
                    # Single account
                    if account_spec in accounts:
                        total -= accounts[account_str]
        
        # Apply sign based on SE file data structure
        # All account balances from 2000-8989 need to be reversed regardless of balance_type
        
        # Check if any accounts in the 2000-8989 range are being used
        should_reverse = False
        
        # Check account range
        start = mapping.get('accounts_included_start')
        end = mapping.get('accounts_included_end')
        if start and end and 2000 <= start <= 8989:
            should_reverse = True
        
        # Check additional specific accounts
        additional_accounts = mapping.get('accounts_included')
        if additional_accounts:
            for account_spec in additional_accounts.split(';'):
                account_spec = account_spec.strip()
                if '-' in account_spec:
                    # Range specification
                    range_start, range_end = map(int, account_spec.split('-'))
                    if 2000 <= range_start <= 8989:
                        should_reverse = True
                        break
                else:
                    # Single account
                    try:
                        account_id = int(account_spec)
                        if 2000 <= account_id <= 8989:
                            should_reverse = True
                            break
                    except ValueError:
                        continue
        
        # Optional explicit sign override from mapping column (e.g., '+/-' or 'sign')
        sign_override = mapping.get('+/-') or mapping.get('sign') or mapping.get('plus_minus')
        if sign_override:
            s = str(sign_override).strip()
            if s == '+':
                total = abs(total)
            elif s == '-':
                total = -abs(total)

        if should_reverse:
            return -total
        else:
            return total
    
    def calculate_formula_value(self, mapping: Dict[str, Any], accounts: Dict[str, float], existing_results: List[Dict[str, Any]], use_previous_year: bool = False, rr_data: List[Dict[str, Any]] = None) -> float:
        """Calculate value using a formula that references variable names"""
        formula = mapping.get('calculation_formula', '')
        if not formula:
            return 0.0
        

        
        # Parse formula like "NETTOOMSATTNING + OVRIGA_INTEKNINGAR"
        # Use variable names instead of row references
        import re
        
        # Replace variable references with their calculated values
        # Formula format: variable names like SumRorelseintakter, SumRorelsekostnader, etc.
        # Use word boundaries to match complete variable names
        pattern = r'\b([A-Z][a-zA-Z0-9_]*)\b'
        
        def replace_variable(match):
            var_name = match.group(1)
            # Use the new helper method to get calculated values
            value = self._get_calculated_value(var_name, existing_results, use_previous_year, rr_data)

            return str(value)
        
        # Replace all variable references
        formula_with_values = re.sub(pattern, replace_variable, formula)
        
        try:
            # Evaluate the formula
            result = eval(formula_with_values)
            return float(result)
        except Exception as e:
            print(f"Formula evaluation error: {e}")
            return 0.0
    
    def parse_rr_data(self, current_accounts: Dict[str, float], previous_accounts: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """Parse RR (Resultaträkning) data using database mappings"""
        if not self.rr_mappings:
            return []
        
        results = []
        

        
        # First pass: Create all rows with direct calculations
        for mapping in self.rr_mappings:
            if not mapping.get('show_amount'):
                # Header row - no calculation needed
                results.append({
                    'id': mapping['row_id'],
                    'label': mapping['row_title'],
                    'current_amount': None,
                    'previous_amount': None,
                    'level': self._get_level_from_style(mapping['style']),
                    'section': 'RR',
                    'bold': mapping['style'] in ['H0', 'H1', 'H2', 'H4'],
                    'style': mapping['style'],
                    'variable_name': mapping['variable_name'],
                    'is_calculated': mapping['is_calculated'],
                    'calculation_formula': mapping['calculation_formula'],
                    'show_amount': mapping['show_amount'],
                    'block_group': mapping.get('block_group'),
                    'always_show': self._normalize_always_show(mapping.get('always_show', False))
                })
            else:
                # Data row - calculate amounts for both years
                if mapping.get('is_calculated'):
                    # For calculated items, set to 0 initially, will be updated in second pass
                    current_amount = 0.0
                    previous_amount = 0.0
                else:
                    # Direct account calculation
                    current_amount = self.calculate_variable_value(mapping, current_accounts)
                    previous_amount = self.calculate_variable_value(mapping, previous_accounts or {})
                

                
                results.append({
                    'id': mapping['row_id'],
                    'label': mapping['row_title'],
                    'current_amount': current_amount,
                    'previous_amount': previous_amount,
                    'level': self._get_level_from_style(mapping['style']),
                    'section': 'RR',
                    'bold': mapping['style'] in ['H0', 'H1', 'H2', 'H4'],
                    'style': mapping['style'],
                    'variable_name': mapping['variable_name'],
                    'is_calculated': mapping['is_calculated'],
                    'calculation_formula': mapping['calculation_formula'],
                    'show_amount': mapping['show_amount'],
                    'block_group': mapping.get('block_group'),
                    'always_show': self._normalize_always_show(mapping.get('always_show', False))
                })
        
        # Second pass: Calculate formulas using all available data
        
        # Sort calculated mappings by row_id to ensure dependencies are calculated first
        calculated_mappings = [(i, mapping) for i, mapping in enumerate(self.rr_mappings) 
                              if mapping.get('is_calculated')]
        calculated_mappings.sort(key=lambda x: int(x[1]['row_id']))
        
        for i, mapping in calculated_mappings:

                
                current_amount = self.calculate_formula_value(mapping, current_accounts, results, use_previous_year=False)
                previous_amount = self.calculate_formula_value(mapping, previous_accounts or {}, results, use_previous_year=True)

                
                # Find and update the correct result by row_id
                for result in results:
                    if result['id'] == mapping['row_id']:
                        result['current_amount'] = current_amount
                        result['previous_amount'] = previous_amount
                        break
        
        # Store calculated values in database for future use
        self.store_calculated_values(results, 'RR')
        
        # Sort results by ID to ensure correct order
        results.sort(key=lambda x: int(x['id']))
        
        return results
    
    def store_calculated_values(self, results: List[Dict[str, Any]], report_type: str):
        """Store calculated values in database for future retrieval"""
        try:
            # Create a dictionary of variable_name -> current_amount for calculated items
            calculated_values = {}
            for item in results:
                if item.get('is_calculated') and item.get('variable_name'):
                    # Include all calculated items, even if current_amount is 0 or -0
                    current_amount = item.get('current_amount')
                    if current_amount is not None:  # This includes 0, -0, and other values
                        calculated_values[item['variable_name']] = current_amount
            
            if calculated_values:
                # Store in a temporary table or update existing records
                # This will be used when formulas reference these variables
                for var_name, value in calculated_values.items():
                    # You might want to store this in a separate table or update existing records
                    # For now, we'll just use it in memory
                    pass
                    
        except Exception as e:
            print(f"Error storing calculated values: {e}")
    
    def _get_calculated_value(self, variable_name: str, results: List[Dict[str, Any]], use_previous_year: bool = False, rr_data: List[Dict[str, Any]] = None) -> float:
        """Get calculated value for a variable from results or RR data"""
        # First check in the current results (BR data)
        for item in results:
            if item.get('variable_name') == variable_name:
                value = item.get('previous_amount' if use_previous_year else 'current_amount', 0)
                return value if value is not None else 0
        
        # If not found in current results, check in RR data
        if rr_data:
            for item in rr_data:
                if item.get('variable_name') == variable_name:
                    value = item.get('previous_amount' if use_previous_year else 'current_amount', 0)
                    return value if value is not None else 0
        
        return 0
    
    def parse_br_data(self, current_accounts: Dict[str, float], previous_accounts: Dict[str, float] = None, rr_data: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Parse BR (Balansräkning) data using database mappings"""
        if not self.br_mappings:
            return []
        
        results = []
        
        # First pass: Create all rows with direct calculations
        for mapping in self.br_mappings:
            if not mapping.get('show_amount'):
                # Header row - no calculation needed
                results.append({
                    'id': mapping['row_id'],
                    'label': mapping['row_title'],
                    'current_amount': None,
                    'previous_amount': None,
                    'level': self._get_level_from_style(mapping['style']),
                    'section': 'BR',
                    'type': self._get_balance_type(mapping),
                    'bold': mapping['style'] in ['H0', 'H1', 'H2', 'H4'],
                    'style': mapping['style'],
                    'variable_name': mapping['variable_name'],
                    'is_calculated': mapping['is_calculated'],
                    'calculation_formula': mapping['calculation_formula'],
                    'show_amount': mapping['show_amount'],
                    'block_group': mapping.get('block_group'),
                    'always_show': self._normalize_always_show(mapping.get('always_show', False))
                })
            else:
                # Data row - calculate amounts for both years
                if mapping.get('is_calculated'):
                    # For calculated items, set to 0 initially, will be updated in second pass
                    current_amount = 0.0
                    previous_amount = 0.0
                else:
                    # Direct account calculation
                    current_amount = self.calculate_variable_value(mapping, current_accounts)
                    previous_amount = self.calculate_variable_value(mapping, previous_accounts or {})
                
                results.append({
                    'id': mapping['row_id'],
                    'label': mapping['row_title'],
                    'current_amount': current_amount,
                    'previous_amount': previous_amount,
                    'level': self._get_level_from_style(mapping['style']),
                    'section': 'BR',
                    'type': self._get_balance_type(mapping),
                    'bold': mapping['style'] in ['H0', 'H1', 'H2', 'H4'],
                    'style': mapping['style'],
                    'variable_name': mapping['variable_name'],
                    'is_calculated': mapping['is_calculated'],
                    'calculation_formula': mapping['calculation_formula'],
                    'show_amount': mapping['show_amount'],
                    'block_group': mapping.get('block_group'),
                    'always_show': self._normalize_always_show(mapping.get('always_show', False))
                })
        
        # Second pass: Calculate formulas using all available data
        # Sort calculated mappings by row_id to ensure dependencies are calculated first
        calculated_mappings = [(i, mapping) for i, mapping in enumerate(self.br_mappings) 
                              if mapping.get('is_calculated')]
        calculated_mappings.sort(key=lambda x: int(x[1]['row_id']))
        
        for i, mapping in calculated_mappings:
                current_amount = self.calculate_formula_value(mapping, current_accounts, results, use_previous_year=False, rr_data=rr_data)
                previous_amount = self.calculate_formula_value(mapping, previous_accounts or {}, results, use_previous_year=True, rr_data=rr_data)
                
                # Find and update the correct result by row_id
                for result in results:
                    if result['id'] == mapping['row_id']:
                        result['current_amount'] = current_amount
                        result['previous_amount'] = previous_amount
                        break
        
        # Store calculated values in database for future use
        self.store_calculated_values(results, 'BR')
        
        # Sort results by ID to ensure correct order
        results.sort(key=lambda x: int(x['id']))
        

        
        return results
    
    def _get_level_from_style(self, style: str) -> int:
        """Get hierarchy level from style"""
        style_map = {
            'H0': 0,
            'H1': 1,
            'H2': 2,
            'H3': 3,
            'H4': 4,  # Replace S1, S2, S3 with H4
            'NORMAL': 4,
            'S1': 4,  # Map S1 to H4 level
            'S2': 4,  # Map S2 to H4 level
            'S3': 4   # Map S3 to H4 level
        }
        return style_map.get(style, 4)
    
    def _get_balance_type(self, mapping: Dict[str, Any]) -> str:
        """Get balance type (asset/liability/equity) from mapping"""
        balance_type = mapping.get('balance_type', 'DEBIT')
        
        # Simple mapping - you might need to refine this based on your BR structure
        if balance_type == 'DEBIT':
            return 'asset'
        elif balance_type == 'CREDIT':
            # Determine if it's liability or equity based on account ranges
            start = mapping.get('accounts_included_start', 0)
            if start and start >= 2000:  # Equity accounts typically start at 2000+
                return 'equity'
            else:
                return 'liability'
        else:
            return 'asset'  # Default
    
    def ensure_financial_data_columns(self, rr_data: List[Dict[str, Any]], br_data: List[Dict[str, Any]]) -> None:
        """Ensure that the financial_data table has columns for all variables"""
        # Temporarily disabled - exec_sql function doesn't exist in database
        # TODO: Implement proper dynamic column creation when database supports it
        pass

    def store_financial_data(self, company_id: str, fiscal_year: int, 
                           rr_data: List[Dict[str, Any]], br_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """Store parsed financial data in the database"""
        try:
            # Temporarily disabled dynamic column creation
            # self.ensure_financial_data_columns(rr_data, br_data)
            
            # Store RR data
            rr_values = {}
            for item in rr_data:
                if item['current_amount'] is not None and item['variable_name']:
                    rr_values[item['variable_name']] = item['current_amount']
            
            if rr_values:
                supabase.table('financial_data').upsert({
                    'company_id': company_id,
                    'fiscal_year': fiscal_year,
                    'report_type': 'RR',
                    **rr_values
                }).execute()
            
            # Store BR data
            br_values = {}
            for item in br_data:
                if item['current_amount'] is not None and item['variable_name']:
                    br_values[item['variable_name']] = item['current_amount']
            
            if br_values:
                supabase.table('financial_data').upsert({
                    'company_id': company_id,
                    'fiscal_year': fiscal_year,
                    'report_type': 'BR',
                    **br_values
                }).execute()
            
            return {
                'rr_id': f"{company_id}_{fiscal_year}_RR",
                'br_id': f"{company_id}_{fiscal_year}_BR"
            }
            
        except Exception as e:
            print(f"Error storing financial data: {e}")
            return {}
    
    def get_financial_data(self, company_id: str, fiscal_year: int) -> Dict[str, Any]:
        """Retrieve financial data from database"""
        try:
            rr_data = supabase.table('financial_data').select('*').eq('company_id', company_id).eq('fiscal_year', fiscal_year).eq('report_type', 'RR').execute()
            br_data = supabase.table('financial_data').select('*').eq('company_id', company_id).eq('fiscal_year', fiscal_year).eq('report_type', 'BR').execute()
            
            return {
                'rr_data': rr_data.data[0] if rr_data.data else {},
                'br_data': br_data.data[0] if br_data.data else {}
            }
            
        except Exception as e:
            print(f"Error retrieving financial data: {e}")
            return {'rr_data': {}, 'br_data': {}}

    def extract_company_info(self, se_content: str) -> Dict[str, Any]:
        """Extract company information from SE file headers"""
        company_info = {}
        lines = se_content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('#FNAMN'):
                # Company name: #FNAMN "Company Name"
                parts = line.split('"', 2)
                if len(parts) >= 2:
                    company_info['company_name'] = parts[1]
                    
            elif line.startswith('#ORGNR'):
                # Organization number: #ORGNR 556610-3643
                parts = line.split()
                if len(parts) >= 2:
                    company_info['organization_number'] = parts[1]
                    
            elif line.startswith('#RAR'):
                # Fiscal year: #RAR 0 20240101 20241231
                parts = line.split()
                if len(parts) >= 4 and parts[1] == '0':  # Current year
                    company_info['fiscal_year'] = int(parts[2][:4])  # Extract year from date
                    company_info['start_date'] = parts[2]
                    company_info['end_date'] = parts[3]
        
        print(f"Extracted company info: {company_info}")
        return company_info
    
    def update_calculation_formula(self, row_id: int, formula: str) -> bool:
        """Update calculation formula for a specific row in the database"""
        try:
            # Update the formula in variable_mapping_br table
            response = supabase.table('variable_mapping_br').update({
                'calculation_formula': formula,
                'is_calculated': True
            }).eq('id', row_id).execute()
            
            print(f"Successfully updated formula for row {row_id}: {formula}")
            return True
            
        except Exception as e:
            print(f"Error updating formula for row {row_id}: {e}")
            return False
    
    def parse_ink2_data(self, current_accounts: Dict[str, float], fiscal_year: int = None, rr_data: List[Dict[str, Any]] = None, br_data: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Parse INK2 tax calculation data using database mappings.
        Returns simplified structure: row_title and amount only.
        """
        # Force reload mappings to get fresh data from database
        self._load_mappings()
        if not self.ink2_mappings:
            print("No INK2 mappings available")
            return []
        
        results = []
        
        # Sort mappings by row_id to maintain correct order
        sorted_mappings = sorted(self.ink2_mappings, key=lambda x: x.get('row_id', 0))
        
        ink_values: Dict[str, float] = {}
        for mapping in sorted_mappings:
            try:
                # Always calculate (or default to 0) so rows can be shown with blank amount if needed
                amount = self.calculate_ink2_variable_value(mapping, current_accounts, fiscal_year, rr_data, ink_values, br_data)
                
                # Special handling: hide INK4_header (duplicate "Skatteberäkning")
                variable_name = mapping.get('variable_name', '')
                if variable_name == 'INK4_header':
                    continue  # Skip this row entirely
                
                # Return all rows - let frontend handle visibility logic
                result = {
                        'row_id': mapping.get('row_id'),
                        'row_title': mapping.get('row_title', ''),
                        'amount': amount,
                        'variable_name': mapping.get('variable_name', ''),
                        'show_tag': mapping.get('show_tag', False),
                        'accounts_included': mapping.get('accounts_included', ''),
                        'account_details': self._get_account_details(mapping.get('accounts_included', ''), current_accounts) if mapping.get('show_tag', False) else None,
                        'show_amount': self._normalize_show_amount(mapping.get('show_amount', True)),
                        'is_calculated': self._normalize_is_calculated(mapping.get('is_calculated', True)),
                        'always_show': self._normalize_always_show(mapping.get('always_show', False)),
                        'style': mapping.get('style'),
                        'explainer': mapping.get('explainer', ''),
                        'block': mapping.get('block', ''),
                        'header': mapping.get('header', False)
                    }
                results.append(result)
                # store for later formula dependencies
                var_name = mapping.get('variable_name')
                if var_name:
                    ink_values[var_name] = amount
                    
            except Exception as e:
                print(f"Error processing INK2 mapping {mapping.get('variable_name', 'unknown')}: {e}")
                continue
        
        return results
    
    def parse_ink2_data_with_overrides(self, current_accounts: Dict[str, float], fiscal_year: int = None, 
                                       rr_data: List[Dict[str, Any]] = None, br_data: List[Dict[str, Any]] = None,
                                       manual_amounts: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Parse INK2 tax calculation data with manual amount overrides for dynamic recalculation.
        """
        # Force reload mappings to get fresh data from database
        self._load_mappings()
        if not self.ink2_mappings:
            print("No INK2 mappings available")
            return []
        
        manual_amounts = manual_amounts or {}
        results = []
        
        # Sort mappings by row_id to maintain correct order
        sorted_mappings = sorted(self.ink2_mappings, key=lambda x: x.get('row_id', 0))
        
        ink_values: Dict[str, float] = {}
        
        # Inject justering_sarskild_loneskatt into ink_values if provided
        if 'justering_sarskild_loneskatt' in manual_amounts:
            ink_values['justering_sarskild_loneskatt'] = manual_amounts['justering_sarskild_loneskatt']
            print(f"Injected justering_sarskild_loneskatt: {manual_amounts['justering_sarskild_loneskatt']}")
        
        # Inject INK4.14a (outnyttjat underskott) into ink_values if provided
        if 'INK4.14a' in manual_amounts:
            ink_values['INK4.14a'] = manual_amounts['INK4.14a']
            print(f"Injected INK4.14a: {manual_amounts['INK4.14a']}")
        
        # Inject underskott adjustment for INK4.16 if provided
        if 'ink4_16_underskott_adjustment' in manual_amounts:
            ink_values['ink4_16_underskott_adjustment'] = manual_amounts['ink4_16_underskott_adjustment']
            print(f"Injected ink4_16_underskott_adjustment: {manual_amounts['ink4_16_underskott_adjustment']}")
        
        
        for mapping in sorted_mappings:
            try:
                variable_name = mapping.get('variable_name', '')
                
                # Force recalculation of dependent summary values even if not manually edited
                force_recalculate = variable_name in ['INK_skattemassigt_resultat', 'INK_beraknad_skatt']
                
                # Check if this value has been manually overridden (but only for non-calculated fields)
                if variable_name in manual_amounts and not force_recalculate:
                    amount = manual_amounts[variable_name]
                    ink_values[variable_name] = amount  # Store for dependencies
                    print(f"Using manual override for {variable_name}: {amount}")
                else:
                    # Calculate normally (or force recalculate for dependent values)
                    amount = self.calculate_ink2_variable_value(mapping, current_accounts, fiscal_year, rr_data, ink_values, br_data)
                    # Round all INK2 values to 0 decimals (skattemässigt resultat already has special rounding)
                    if variable_name != 'INK_skattemassigt_resultat':
                        amount = round(amount, 0)
                    # IMPORTANT: Store calculated values for later formulas
                    ink_values[variable_name] = amount
                    if variable_name in ['INK_skattemassigt_resultat', 'INK_beraknad_skatt']:
                        print(f"Calculated {variable_name}: {amount} (available ink_values: {list(ink_values.keys())})")
                
                # Keep only essential debug for important tax calculations
                
                # Special handling: hide INK4_header (duplicate "Skatteberäkning")
                if variable_name == 'INK4_header':
                    continue  # Skip this row entirely
                
                # Return all rows - let frontend handle visibility logic
                # Get account details for SHOW button if needed
                account_details = []
                if mapping.get('show_tag') and mapping.get('accounts_included'):
                    account_details = self._get_account_details(mapping['accounts_included'], current_accounts)
                
                results.append({
                        'row_id': mapping.get('row_id', 0),
                        'row_title': mapping['row_title'],
                        'amount': amount,
                        'variable_name': variable_name,
                        'show_tag': mapping.get('show_tag', False),
                        'accounts_included': mapping.get('accounts_included', ''),
                        'show_amount': self._normalize_show_amount(mapping.get('show_amount')),
                        'style': mapping.get('style', 'NORMAL'),
                        'is_calculated': self._normalize_is_calculated(mapping.get('is_calculated')),
                        'always_show': self._normalize_always_show(mapping.get('always_show', False)),
                        'explainer': mapping.get('explainer', ''),
                        'block': mapping.get('block', ''),
                        'header': mapping.get('header', False),
                        'account_details': account_details
                    })
                
            except Exception as e:
                print(f"Error processing INK2 mapping {mapping.get('variable_name', 'unknown')}: {e}")
                continue
        
        return results


    def _normalize_show_amount(self, value: Any) -> bool:
        """Normalize show_amount to boolean. Handles string 'TRUE'/'FALSE' from database."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.upper() == 'TRUE'
        return bool(value)
    
    def _normalize_is_calculated(self, value: Any) -> bool:
        """Normalize is_calculated to boolean. Handles string 'TRUE'/'FALSE' from database."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.upper() == 'TRUE'
        return bool(value)
    
    def _normalize_always_show(self, value: Any) -> Any:
        """Normalize always_show to boolean or null values."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized == 'TRUE':
                return True
            elif normalized == 'FALSE':
                return False
            else:
                return None  # Empty/null means conditional (show if amount != 0)
        return None  # Default to conditional
    
    def calculate_ink2_variable_value(self, mapping: Dict[str, Any], accounts: Dict[str, float], fiscal_year: int = None, rr_data: List[Dict[str, Any]] = None, ink_values: Optional[Dict[str, float]] = None, br_data: Optional[List[Dict[str, Any]]] = None) -> float:
        """
        Calculate the value for an INK2 variable using accounts and formulas.
        """
        variable_name = mapping.get('variable_name', '')

        # Helper to fetch RR variables
        def rr(var: str) -> float:
            if not rr_data:
                return 0.0
            for item in rr_data:
                if item.get('variable_name') == var:
                    value = item.get('current_amount')
                    return float(value) if value is not None else 0.0
            return 0.0

        # Explicit logic for key variables
        if variable_name == 'INK4.1':
            sum_arets = rr('SumAretsResultat')
            return sum_arets if sum_arets > 0 else 0.0
        if variable_name == 'INK4.2':
            sum_arets = rr('SumAretsResultat')
            return -sum_arets if sum_arets < 0 else 0.0
        if variable_name == 'INK4.3a':
            return rr('SkattAretsResultat')
        if variable_name == 'INK4.6a':
            # Periodiseringsfonder previous_year * statslaneranta
            rate = float(self.global_variables.get('statslaneranta', 0.0))
            prev = 0.0
            if br_data:
                for item in br_data:
                    if item.get('variable_name') == 'Periodiseringsfonder':
                        val = item.get('previous_amount')
                        prev = float(val) if val is not None else 0.0
                        break
            return prev * rate
        
        # New pension tax variables
        if variable_name == 'pension_premier':
            # Amount in account 7410
            return abs(float(accounts.get('7410', 0.0)))
        if variable_name == 'sarskild_loneskatt_pension':
            # Amount in account 7531
            return abs(float(accounts.get('7531', 0.0)))
        if variable_name == 'sarskild_loneskatt_pension_calculated':
            # pension_premier * sarskild_loneskatt (global variable)
            pension_premier = abs(float(accounts.get('7410', 0.0)))
            rate = float(self.global_variables.get('sarskild_loneskatt', 0.0))
            result = pension_premier * rate
            # Round to 0 decimals for tax module
            return round(result, 0)
        if variable_name == 'INK_sarskild_loneskatt':
            # Hardcoded formula: -justering_sarskild_loneskatt
            justering = float(ink_values.get('justering_sarskild_loneskatt', 0.0)) if ink_values else 0.0
            result = -justering
            # Round to 0 decimals for tax module
            result = round(result, 0)
            print(f"INK_sarskild_loneskatt: justering={justering}, result={result}")
            return result
        

        
        if variable_name == 'INK_skattemassigt_resultat':
            def v(name: str) -> float:
                if not ink_values:
                    return 0.0
                return float(ink_values.get(name, 0.0))
            
            # Hardcoded formula: INK4.1-INK4.2+INK4.3b+INK4.3c-INK4.4a-INK4.4b-INK4.5a-INK4.5b-INK4.5c+INK4.6a+INK4.6b+INK4.6c+INK4.6d+INK4.6e-INK4.7a+INK4.7b-INK4.7c+INK4.7d+INK4.7e-INK4.7f-INK4.8a+INK4.8b+INK4.8c-INK4.8d+INK4.9(+)-INK4.9(-)+INK4.10(+)-INK4.10(-)-INK4.11+INK4.12+INK4.13(+)-INK4.13(-)-INK4.14a+INK4.14b+INK4.14c-justering_sarskild_loneskatt
            justering = float(ink_values.get('justering_sarskild_loneskatt', 0.0)) if ink_values else 0.0
            total = (
                v('INK4.1') - v('INK4.2') + v('INK4.3b') + v('INK4.3c')
                - v('INK4.4a') - v('INK4.4b') - v('INK4.5a') - v('INK4.5b') - v('INK4.5c')
                + v('INK4.6a') + v('INK4.6b') + v('INK4.6c') + v('INK4.6d') + v('INK4.6e')
                - v('INK4.7a') + v('INK4.7b') - v('INK4.7c') + v('INK4.7d') + v('INK4.7e') - v('INK4.7f')
                - v('INK4.8a') + v('INK4.8b') + v('INK4.8c') - v('INK4.8d')
                + v('INK4.9(+)') - v('INK4.9(-)')
                + v('INK4.10(+)') - v('INK4.10(-)')
                - v('INK4.11') + v('INK4.12') + v('INK4.13(+)') - v('INK4.13(-)')
                - v('INK4.14a') + v('INK4.14b') + v('INK4.14c')
                - justering  # Subtract pension tax adjustment
            )
            # Apply FLOOR(total, 100) - round down to nearest 100 per Skatteverket rules
            floored_total = int(total // 100) * 100
            print(f"INK_skattemassigt_resultat: raw_total={total}, floored={floored_total}")
            return float(floored_total)
        if variable_name == 'INK4.15':
            def v(name: str) -> float:
                if not ink_values:
                    return 0.0
                return float(ink_values.get(name, 0.0))
            
            # Hardcoded formula: MAX(0, INK4.1-INK4.2+INK4.3a+INK4.3b+INK4.3c-INK4.4a-INK4.4b-INK4.5a-INK4.5b-INK4.5c+INK4.6a+INK4.6b+INK4.6c+INK4.6d+INK4.6e-INK4.7a+INK4.7b-INK4.7c+INK4.7d+INK4.7e-INK4.7f-INK4.8a+INK4.8b+INK4.8c-INK4.8d+INK4.9(+)-INK4.9(-)+INK4.10(+)-INK4.10(-)-INK4.11+INK4.12+INK4.13(+)-INK4.13(-)-INK4.14a+INK4.14b+INK4.14c-justering_sarskild_loneskatt)
            justering = float(ink_values.get('justering_sarskild_loneskatt', 0.0)) if ink_values else 0.0
            total = (
                v('INK4.1') - v('INK4.2') + v('INK4.3a') + v('INK4.3b') + v('INK4.3c')
                - v('INK4.4a') - v('INK4.4b') - v('INK4.5a') - v('INK4.5b') - v('INK4.5c')
                + v('INK4.6a') + v('INK4.6b') + v('INK4.6c') + v('INK4.6d') + v('INK4.6e')
                - v('INK4.7a') + v('INK4.7b') - v('INK4.7c') + v('INK4.7d') + v('INK4.7e') - v('INK4.7f')
                - v('INK4.8a') + v('INK4.8b') + v('INK4.8c') - v('INK4.8d')
                + v('INK4.9(+)') - v('INK4.9(-)')
                + v('INK4.10(+)') - v('INK4.10(-)')
                - v('INK4.11') + v('INK4.12') + v('INK4.13(+)') - v('INK4.13(-)')
                - v('INK4.14a') + v('INK4.14b') + v('INK4.14c')
                - justering  # Subtract pension tax adjustment
            )
            # MAX(0, total) - show only if positive
            return float(max(0, round(total)))
        if variable_name == 'INK4.16':
            def v(name: str) -> float:
                if not ink_values:
                    return 0.0
                return float(ink_values.get(name, 0.0))
            
            # Hardcoded formula: IF(INK4.1-INK4.2+INK4.3a+INK4.3b+INK4.3c-INK4.4a-INK4.4b-INK4.5a-INK4.5b-INK4.5c+INK4.6a+INK4.6b+INK4.6c+INK4.6d+INK4.6e-INK4.7a+INK4.7b-INK4.7c+INK4.7d+INK4.7e-INK4.7f-INK4.8a+INK4.8b+INK4.8c-INK4.8d+INK4.9(+)-INK4.9(-)+INK4.10(+)-INK4.10(-)-INK4.11+INK4.12+INK4.13(+)-INK4.13(-)-INK4.14a+INK4.14b+INK4.14c-justering_sarskild_loneskatt < 0, sum, 0)
            justering = float(ink_values.get('justering_sarskild_loneskatt', 0.0)) if ink_values else 0.0
            total = (
                v('INK4.1') - v('INK4.2') + v('INK4.3a') + v('INK4.3b') + v('INK4.3c')
                - v('INK4.4a') - v('INK4.4b') - v('INK4.5a') - v('INK4.5b') - v('INK4.5c')
                + v('INK4.6a') + v('INK4.6b') + v('INK4.6c') + v('INK4.6d') + v('INK4.6e')
                - v('INK4.7a') + v('INK4.7b') - v('INK4.7c') + v('INK4.7d') + v('INK4.7e') - v('INK4.7f')
                - v('INK4.8a') + v('INK4.8b') + v('INK4.8c') - v('INK4.8d')
                + v('INK4.9(+)') - v('INK4.9(-)')
                + v('INK4.10(+)') - v('INK4.10(-)')
                - v('INK4.11') + v('INK4.12') + v('INK4.13(+)') - v('INK4.13(-)')
                - v('INK4.14a') + v('INK4.14b') + v('INK4.14c')
                - justering  # Subtract pension tax adjustment
            )
            # IF(total < 0, abs(total), 0) - show absolute value if negative, otherwise 0
            return float(abs(total) if total < 0 else 0)
        if variable_name == 'INK_bokford_skatt':
            return rr('SkattAretsResultat')
        if variable_name == 'INK_beraknad_skatt':
            base = 0.0
            if ink_values:
                base = float(ink_values.get('INK_skattemassigt_resultat', 0.0))
            if base <= 0:
                return 0.0
            # base is already rounded down to nearest 100 in INK_skattemassigt_resultat
            rate = float(self.global_variables.get('skattesats', 0.0))
            tax_amount = base * rate
            # Round to whole kronor: ≥50 öre up, <50 öre down
            rounded_tax = round(tax_amount)
            print(f"INK_beraknad_skatt: base={base}, rate={rate}, tax_amount={tax_amount}, rounded={rounded_tax}")
            return float(rounded_tax)

        # If there's a calculation formula, use it
        if mapping.get('calculation_formula'):
            return self.calculate_ink2_formula_value(mapping, accounts, fiscal_year, rr_data, ink_values)
        
        # Otherwise, sum the included accounts (use absolute values for positive-only variables)
        account_sum = self.sum_included_accounts(mapping.get('accounts_included', ''), accounts)
        # Variables that should always be positive (account-based calculations)
        positive_only_variables = [
            'INK4.3c', 'INK4.4a', 'INK4.5b', 'INK4.5c', 
            'INK4.6a', 'INK4.6c', 'INK4.21'
        ]
        if variable_name in positive_only_variables:
            return abs(account_sum)
        return account_sum
    
    def calculate_ink2_formula_value(self, mapping: Dict[str, Any], accounts: Dict[str, float], fiscal_year: int = None, rr_data: List[Dict[str, Any]] = None, ink_values: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate value using formula that may reference global variables.
        """
        variable_name = mapping.get('variable_name', '')
        formula = mapping.get('calculation_formula', '')
        if not formula:
            return 0.0
        
        try:
            # Replace global variable references using safe curly brace syntax
            formula_with_values = formula
            for var_name, var_value in self.global_variables.items():
                # Safe replacement: only replace {variable_name} patterns
                placeholder = f"{{{var_name}}}"
                if placeholder in formula_with_values:
                    formula_with_values = formula_with_values.replace(placeholder, str(var_value))
            
            # Replace RR variable references if RR data is available
            if rr_data:
                rr_variables = {}
                for item in rr_data:
                    if item.get('variable_name'):
                        rr_variables[item['variable_name']] = item.get('current_amount', 0) or 0
                
                # Replace RR variable references - Use regex with word boundaries to prevent partial matches
                import re
                for var_name, var_value in rr_variables.items():
                    # Use word boundaries (\b) to match whole words only
                    pattern = r'\b' + re.escape(var_name) + r'\b'
                    if re.search(pattern, formula_with_values):
                        formula_with_values = re.sub(pattern, str(var_value), formula_with_values)
                        # Variable replacement completed
            
            # Keep formula debugging minimal
            
            # Replace INK variable references with their calculated values
            if ink_values:
                import re
                for var_name, var_value in ink_values.items():
                    # Use word boundaries to match whole words only
                    pattern = r'\b' + re.escape(var_name) + r'\b'
                    if re.search(pattern, formula_with_values):
                        # Get the sign from the mapping for this variable
                        var_mapping = next((m for m in self.ink2_mappings if m.get('variable_name') == var_name), None)
                        if var_mapping:
                            sign_column = var_mapping.get('*/+/-', '+')
                            if sign_column == '-':
                                # Apply negative sign for subtraction
                                formula_with_values = re.sub(pattern, f"(-{var_value})", formula_with_values)
                            else:
                                # Use positive value (+ or *)
                                formula_with_values = re.sub(pattern, str(var_value), formula_with_values)
                        else:
                            # Fallback: use value as-is
                            formula_with_values = re.sub(pattern, str(var_value), formula_with_values)
                        
            # Replace account references (format: account_XXXX)
            import re
            account_pattern = r'account_(\d+)'
            matches = re.findall(account_pattern, formula_with_values)
            for account_id in matches:
                account_value = accounts.get(account_id, 0)
                # Use word boundaries for account replacement too
                account_pattern = r'\baccount_' + re.escape(account_id) + r'\b'
                formula_with_values = re.sub(account_pattern, str(account_value), formula_with_values)
            
            # Clean up formula for Python evaluation
            # Handle common Excel-like syntax issues
            formula_with_values = self._clean_formula_for_python(formula_with_values)
            
            # Evaluate the formula safely
            # Note: In production, consider using a safer eval alternative
            return float(eval(formula_with_values))
            
        except Exception as e:
            print(f"Error evaluating formula '{formula}': {e}")
            return 0.0
    
    def _clean_formula_for_python(self, formula: str) -> str:
        """
        Interpret and convert formula logic to executable Python code.
        This handles the actual business logic from the calculation_formula column.
        """
        formula = formula.strip()
        if not formula:
            return '0'
        
        # Handle specific formula patterns based on your database content
        
        # Pattern 1: Simple variable references (e.g., "SumResultatForeSkatt")
        if formula.isalnum() or ('_' in formula and formula.replace('_', '').isalnum()):
            # This is likely a variable reference - it should already be replaced by RR variables
            return '0'  # If we get here, the variable wasn't found
        
        # Pattern 2: "IF statement" logic (e.g., "if >0 = formula")
        if formula.lower().startswith('if '):
            # Extract the condition and formula parts
            # Example: "if >0 = INK4.1-INK4.2+..." becomes conditional logic
            parts = formula.split(' = ', 1)
            if len(parts) == 2:
                condition_part = parts[0].replace('if ', '').strip()
                formula_part = parts[1].strip()
                
                # Convert condition (e.g., ">0", "<0")
                if condition_part == '>0':
                    return f'max(0, {self._convert_ink_formula(formula_part)})'
                elif condition_part == '<0':
                    return f'min(0, {self._convert_ink_formula(formula_part)})'
            return '0'
        
        # Pattern 3: Direct INK formula references (e.g., "INK4.1-INK4.2+INK4.3c...")
        if 'INK4.' in formula:
            return self._convert_ink_formula(formula)
        
        # Pattern 4: FLOOR function (e.g., "FLOOR(value;precision) * rate")
        if 'FLOOR(' in formula:
            import re
            # Replace FLOOR(value;precision) with int(value/precision)*precision
            formula = re.sub(r'FLOOR\(([^;]+);([^)]+)\)', r'(int(\1/\2)*\2)', formula)
        
        # Pattern 5: Simple arithmetic with known variables
        # Clean up operators and return as-is for eval()
        formula = formula.replace(' * ', '*').replace(' + ', '+').replace(' - ', '-').replace(' / ', '/')
        
        return formula
    
    def _convert_ink_formula(self, formula: str) -> str:
        """
        Convert INK4.x variable references to actual calculated values.
        This is a placeholder - in practice, you'd need to either:
        1. Pre-calculate all INK4 values in order, or
        2. Create a dependency resolver
        """
        # For now, return 0 for complex INK formulas since they reference other INK variables
        # that may not be calculated yet. This needs a more sophisticated approach.
        return '0'
    
    def sum_included_accounts(self, accounts_included: str, accounts: Dict[str, float]) -> float:
        """
        Sum the values of included accounts.
        accounts_included format: "6072;6992;7632" or "6000-6999"
        """
        if not accounts_included:
            return 0.0
        
        total = 0.0
        
        # Split by semicolon for multiple accounts/ranges
        account_specs = accounts_included.split(';')
        
        for spec in account_specs:
            spec = spec.strip()
            if not spec:
                continue
                
            if '-' in spec:
                # Range format: "6000-6999"
                try:
                    start, end = spec.split('-')
                    start_num = int(start.strip())
                    end_num = int(end.strip())
                    
                    for account_id, balance in accounts.items():
                        try:
                            account_num = int(account_id)
                            if start_num <= account_num <= end_num:
                                total += balance
                        except ValueError:
                            continue
                            
                except ValueError:
                    print(f"Invalid range format: {spec}")
                    continue
            else:
                # Single account
                try:
                    account_id = spec.strip()
                    total += accounts.get(account_id, 0.0)
                except Exception:
                    print(f"Invalid account format: {spec}")
                    continue
        
        return total
    
    def _get_account_details(self, accounts_included: str, accounts: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Get detailed account information for popup display.
        Returns list with account_id, account_text, and balance.
        """
        if not accounts_included:
            return []
        
        details = []
        
        # Split by semicolon for multiple accounts/ranges
        account_specs = accounts_included.split(';')
        
        for spec in account_specs:
            spec = spec.strip()
            if not spec:
                continue
                
            if '-' in spec:
                # Range format: "6000-6999"
                try:
                    start, end = spec.split('-')
                    start_num = int(start.strip())
                    end_num = int(end.strip())
                    
                    for account_id, balance in accounts.items():
                        try:
                            account_num = int(account_id)
                            if start_num <= account_num <= end_num and balance != 0:
                                details.append({
                                    'account_id': account_id,
                                    'account_text': self._get_account_text(account_num),
                                    'balance': balance
                                })
                        except ValueError:
                            continue
                            
                except ValueError:
                    continue
            else:
                # Single account
                try:
                    account_id = spec.strip()
                    balance = accounts.get(account_id, 0.0)
                    if balance != 0:  # Only include accounts with non-zero balance
                        details.append({
                            'account_id': account_id,
                            'account_text': self._get_account_text(account_id),
                            'balance': balance
                        })
                except Exception:
                    continue
        
        # Sort by account_id
        details.sort(key=lambda x: int(x['account_id']))
        return details

    def _get_account_text(self, account_id: Any) -> str:
        """Return kontotext for given account id using cache and DB fallback."""
        # Try int key
        try:
            acc_int = int(account_id)
            if acc_int in self.accounts_lookup:
                return self.accounts_lookup[acc_int]
        except Exception:
            acc_int = None
        # Try string key
        key_str = str(account_id)
        if key_str in self.accounts_lookup:
            return self.accounts_lookup[key_str]
        # Fallback: query Supabase directly and update cache
        try:
            resp = supabase.table('accounts_table').select('account_text,account_id').eq('account_id', key_str).limit(1).execute()
            if resp.data:
                text = resp.data[0].get('account_text') or f'Konto {key_str}'
                if acc_int is not None:
                    self.accounts_lookup[acc_int] = text
                self.accounts_lookup[key_str] = text
                return text
        except Exception:
            pass
        return f'Konto {key_str}'
    
    def parse_noter_data(self, current_accounts: Dict[str, float], previous_accounts: Dict[str, float] = None, user_toggles: Dict[str, bool] = None) -> List[Dict[str, Any]]:
        """
        Parse Noter (Notes) data using database mappings.
        Returns structure with current_amount and previous_amount for both fiscal year and previous year.
        """
        # Force reload mappings to get fresh data from database
        self._load_mappings()
        if not self.noter_mappings:
            print("No Noter mappings available")
            return []
        
        results = []
        user_toggles = user_toggles or {}
        
        # Sort mappings by row_id to maintain correct order
        sorted_mappings = sorted(self.noter_mappings, key=lambda x: x.get('row_id', 0))
        
        for mapping in sorted_mappings:
            try:
                # Check visibility rules
                always_show = self._normalize_always_show(mapping.get('always_show', False))
                toggle_show = self._normalize_always_show(mapping.get('toggle_show', False))
                block = mapping.get('block', '')
                
                # Show if always_show=true OR (always_show=false AND toggle_show=true AND block toggle is on)
                should_show = always_show or (not always_show and toggle_show and user_toggles.get(block, False))
                
                if not should_show:
                    continue
                
                # Calculate amounts for both years
                current_amount = 0.0
                previous_amount = 0.0
                
                if self._normalize_is_calculated(mapping.get('calculated', False)):
                    # Use formula calculation (would need to implement formula logic)
                    # For now, return 0 for calculated fields
                    current_amount = 0.0
                    previous_amount = 0.0
                else:
                    # Sum included accounts
                    accounts_included = mapping.get('accounts_included', '')
                    if accounts_included:
                        current_amount = self.sum_included_accounts(accounts_included, current_accounts)
                        if previous_accounts:
                            previous_amount = self.sum_included_accounts(accounts_included, previous_accounts)
                
                # Only include if amounts are non-zero or always_show
                if current_amount != 0 or previous_amount != 0 or always_show:
                    result = {
                        'row_id': mapping.get('row_id'),
                        'row_title': mapping.get('row_title', ''),
                        'current_amount': current_amount,
                        'previous_amount': previous_amount,
                        'variable_name': mapping.get('variable_name', ''),
                        'show_tag': mapping.get('show_tag', False),
                        'accounts_included': mapping.get('accounts_included', ''),
                        'account_details': self._get_account_details(mapping.get('accounts_included', ''), current_accounts) if mapping.get('show_tag', False) else None,
                        'block': mapping.get('block', ''),
                        'always_show': always_show,
                        'toggle_show': toggle_show
                    }
                    results.append(result)
                    
            except Exception as e:
                print(f"Error processing Noter mapping {mapping.get('variable_name', 'unknown')}: {e}")
                continue
        
        return results
