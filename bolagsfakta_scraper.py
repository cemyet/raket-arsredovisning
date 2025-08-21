#!/usr/bin/env python3
"""
Bolagsfakta.se Scraper - Koncern Information
Scrapes parent company and subsidiary information from bolagsfakta.se
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from typing import Dict, List, Optional, Tuple
import urllib.parse

class BolagsfaktaScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'sv-SE,sv;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.base_url = "https://www.bolagsfakta.se"
    
    def search_company_by_org_number(self, org_number: str) -> Optional[str]:
        """
        Search for a company by organization number and return the company URL
        """
        # Clean org number (remove dashes and spaces)
        clean_org = re.sub(r'[-\s]', '', org_number)
        
        # Search URL
        search_url = f"{self.base_url}/sok?vad={clean_org}"
        
        try:
            print(f"Söker på: {search_url}")
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for company links in search results
            company_links = soup.find_all('a', href=re.compile(r'/foretag/'))
            
            if company_links:
                # Get the first company link
                company_url = company_links[0].get('href')
                if company_url.startswith('/'):
                    full_url = f"{self.base_url}{company_url}"
                else:
                    full_url = company_url
                
                print(f"Hittade bolag: {full_url}")
                return full_url
            
            return None
            
        except Exception as e:
            print(f"Error searching for company: {e}")
            return None
    
    def get_company_info(self, company_url: str) -> Dict:
        """
        Get company information including parent company and subsidiaries
        """
        try:
            print(f"Hämtar information från: {company_url}")
            response = self.session.get(company_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Initialize result dictionary
            result = {
                'company_name': '',
                'org_number': '',
                'parent_company': None,
                'subsidiaries': [],
                'in_koncern': False,
                'total_companies_in_koncern': 0
            }
            
            # Extract company name and org number from the page
            result['company_name'] = self._extract_company_name(soup)
            result['org_number'] = self._extract_org_number(soup)
            
            # Look for koncern information
            koncern_info = self._extract_koncern_info(soup)
            result.update(koncern_info)
            
            return result
            
        except Exception as e:
            print(f"Error getting company info: {e}")
            return {}
    
    def _extract_company_name(self, soup: BeautifulSoup) -> str:
        """Extract company name from the page"""
        # Look for company name in various possible locations
        name_selectors = [
            'h1',
            '[class*="company-name"]',
            '[class*="title"]',
            '.company-name',
            '.title',
            '.company-title'
        ]
        
        for selector in name_selectors:
            try:
                element = soup.select_one(selector)
                if element and element.get_text().strip():
                    return element.get_text().strip()
            except:
                continue
        
        return ""
    
    def _extract_org_number(self, soup: BeautifulSoup) -> str:
        """Extract organization number from the page"""
        # Look for org number pattern in text
        org_pattern = r'\b\d{6}-\d{4}\b'
        text_content = soup.get_text()
        match = re.search(org_pattern, text_content)
        
        if match:
            return match.group()
        
        return ""
    
    def _extract_koncern_info(self, soup: BeautifulSoup) -> Dict:
        """Extract koncern information from the page"""
        result = {
            'parent_company': None,
            'subsidiaries': [],
            'in_koncern': False,
            'total_companies_in_koncern': 0
        }
        
        # Get all text content
        page_text = soup.get_text()
        
        # Look for koncern-related information
        # Check for various patterns that indicate koncern membership
        koncern_patterns = [
            r'ingår i (?:en )?koncern',
            r'moderbolag',
            r'dotterbolag',
            r'koncernstruktur',
            r'ägarbolag'
        ]
        
        for pattern in koncern_patterns:
            if re.search(pattern, page_text, re.IGNORECASE):
                result['in_koncern'] = True
                break
        
        if result['in_koncern']:
            print("Bolaget ingår i en koncern")
            
            # Look for parent company information
            parent_patterns = [
                r'moderbolag[:\s]*([^\n]+)',
                r'ägarbolag[:\s]*([^\n]+)',
                r'parent company[:\s]*([^\n]+)'
            ]
            
            for pattern in parent_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    parent_name = match.group(1).strip()
                    result['parent_company'] = {
                        'name': parent_name,
                        'org_number': '',
                        'location': ''
                    }
                    print(f"Hittade moderbolag: {parent_name}")
                    break
            
            # Look for subsidiaries
            subsidiary_patterns = [
                r'dotterbolag[:\s]*([^\n]+)',
                r'subsidiaries[:\s]*([^\n]+)',
                r'(\d+)\s*dotterbolag'
            ]
            
            for pattern in subsidiary_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    if pattern == r'(\d+)\s*dotterbolag':
                        num_subsidiaries = int(match.group(1))
                        result['total_companies_in_koncern'] = num_subsidiaries
                        print(f"Hittade {num_subsidiaries} dotterbolag")
                    else:
                        subsidiary_text = match.group(1).strip()
                        print(f"Hittade dotterbolagsinformation: {subsidiary_text}")
                    break
            
            # Look for koncern structure link
            koncern_structure_link = self._find_koncern_structure_link(soup)
            if koncern_structure_link:
                print(f"Hittade koncernstruktur-länk: {koncern_structure_link}")
                subsidiaries_info = self._get_subsidiaries_from_structure_page(koncern_structure_link)
                result['subsidiaries'] = subsidiaries_info
            else:
                # If no koncern structure link found, try to find subsidiaries directly on the page
                print("Ingen koncernstruktur-länk hittad, söker direkt på sidan...")
                subsidiaries_info = self._find_subsidiaries_on_page(soup)
                result['subsidiaries'] = subsidiaries_info
        
        return result
    
    def _find_koncern_structure_link(self, soup: BeautifulSoup) -> Optional[str]:
        """Find the link to the koncern structure page"""
        # Look for links that might lead to koncern structure
        koncern_keywords = ['koncern', 'struktur', 'organisation', 'ägare', 'ownership']
        
        for link in soup.find_all('a', href=True):
            link_text = link.get_text().lower()
            href = link.get('href')
            
            # Check if link text contains koncern-related keywords
            for keyword in koncern_keywords:
                if keyword in link_text:
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    elif href.startswith('http'):
                        return href
        
        # Also look for links to organisation/ownership pages
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if any(keyword in href.lower() for keyword in ['organisation', 'struktur', 'koncern', 'agare']):
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                elif href.startswith('http'):
                    return href
        
        return None
    
    def _find_subsidiaries_on_page(self, soup: BeautifulSoup) -> List[Dict]:
        """Find subsidiaries directly on the company page"""
        subsidiaries = []
        
        # Look for company structure tree on the page
        company_structure = soup.find('ul', class_='company-structure-tree')
        if company_structure:
            print("Hittade company-structure-tree på sidan")
            
            # Look for Holtback Equity AB and its subsidiaries
            target_company_link = None
            for link in company_structure.find_all('a', href=True):
                if "Holtback_Equity_AB" in link.get('href') and "Holtback Equity AB" in link.get_text():
                    target_company_link = link
                    print(f"Hittade Holtback Equity AB: {link.get('href')}")
                    break
            
            if target_company_link:
                # Find the parent li element that contains Holtback Equity AB
                parent_li = target_company_link.find_parent('li')
                if parent_li:
                    # Look for the child ul that contains the subsidiaries
                    child_ul = parent_li.find('ul', class_='company-structure-tree')
                    if child_ul:
                        print("Hittade dotterbolagssektion på sidan")
                        
                        # Find all company links in the child ul
                        subsidiary_links = child_ul.find_all('a', href=re.compile(r'/\d+-'))
                        
                        for link in subsidiary_links:
                            company_name = link.get_text().strip()
                            href = link.get('href')
                            
                            # Extract org number from href (format: /5567078174-Holtback_Equity_AB)
                            org_match = re.search(r'/(\d+)-', href)
                            org_number = org_match.group(1) if org_match else ""
                            
                            # Look for ownership percentage in the parent div
                            parent_div = link.find_parent('div', class_='company-structure-tree__name')
                            ownership_percentage = ""
                            if parent_div:
                                # Look for the paragraph that contains "Kontrollerar:"
                                for p in parent_div.find_all('p'):
                                    p_text = p.get_text()
                                    if "Kontrollerar:" in p_text:
                                        # Extract percentage
                                        percentage_match = re.search(r'(\d+)%', p_text)
                                        if percentage_match:
                                            ownership_percentage = percentage_match.group(1)
                                        elif "Majoritetsägd" in p_text:
                                            ownership_percentage = "Majoritetsägd"
                                        break
                            
                            if company_name:
                                print(f"Hittade dotterbolag: {company_name} ({ownership_percentage})")
                                
                                subsidiary_info = {
                                    'name': company_name,
                                    'org_number': org_number,
                                    'location': '',
                                    'ownership_percentage': ownership_percentage
                                }
                                
                                subsidiaries.append(subsidiary_info)
        
        return subsidiaries
    
    def _get_subsidiaries_from_structure_page(self, structure_url: str) -> List[Dict]:
        """Get subsidiary information from the koncern structure page"""
        try:
            print(f"Hämtar koncernstruktur från: {structure_url}")
            response = self.session.get(structure_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            subsidiaries = []
            
            # Look for Holtback Equity AB specifically
            print("Söker efter Holtback Equity AB i koncernstrukturen...")
            
            # Find the link to Holtback Equity AB
            target_company_link = None
            for link in soup.find_all('a', href=True):
                if "Holtback_Equity_AB" in link.get('href') and "Holtback Equity AB" in link.get_text():
                    target_company_link = link
                    print(f"Hittade Holtback Equity AB: {link.get('href')}")
                    break
            
            if target_company_link:
                # Find the parent li element that contains Holtback Equity AB
                parent_li = target_company_link.find_parent('li')
                if parent_li:
                    # Look for the child ul that contains the subsidiaries
                    child_ul = parent_li.find('ul', class_='company-structure-tree')
                    if child_ul:
                        print("Hittade dotterbolagssektion")
                        
                        # Find all company links in the child ul
                        subsidiary_links = child_ul.find_all('a', href=re.compile(r'/\d+-'))
                        
                        for link in subsidiary_links:
                            company_name = link.get_text().strip()
                            href = link.get('href')
                            
                            # Extract org number from href (format: /5567078174-Holtback_Equity_AB)
                            org_match = re.search(r'/(\d+)-', href)
                            org_number = org_match.group(1) if org_match else ""
                            
                            # Look for ownership percentage in the parent div
                            parent_div = link.find_parent('div', class_='company-structure-tree__name')
                            ownership_percentage = ""
                            if parent_div:
                                # Look for the paragraph that contains "Kontrollerar:"
                                for p in parent_div.find_all('p'):
                                    p_text = p.get_text()
                                    if "Kontrollerar:" in p_text:
                                        # Extract percentage
                                        percentage_match = re.search(r'(\d+)%', p_text)
                                        if percentage_match:
                                            ownership_percentage = percentage_match.group(1)
                                        elif "Majoritetsägd" in p_text:
                                            ownership_percentage = "Majoritetsägd"
                                        break
                            
                            if company_name:
                                print(f"Hittade dotterbolag: {company_name} ({ownership_percentage})")
                                
                                subsidiary_info = {
                                    'name': company_name,
                                    'org_number': org_number,
                                    'location': '',
                                    'ownership_percentage': ownership_percentage
                                }
                                
                                subsidiaries.append(subsidiary_info)
                    else:
                        print("Kunde inte hitta dotterbolagssektion")
                else:
                    print("Kunde inte hitta parent li element för Holtback Equity AB")
            else:
                print("Kunde inte hitta Holtback Equity AB på sidan")
            
            return subsidiaries
            
        except Exception as e:
            print(f"Error getting subsidiaries from structure page: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_company_details_from_link(self, link: str) -> Optional[Dict]:
        """Get company details from a company link"""
        try:
            response = self.session.get(link, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            return {
                'name': self._extract_company_name(soup),
                'org_number': self._extract_org_number(soup),
                'location': self._extract_location(soup),
                'ownership_percentage': ''
            }
            
        except Exception as e:
            print(f"Error getting details from link {link}: {e}")
            return None
    
    def _extract_location(self, soup: BeautifulSoup) -> str:
        """Extract company location from the page"""
        # Look for address information
        address_selectors = [
            '[class*="address"]',
            '[class*="location"]',
            'address',
            '.address',
            '.location'
        ]
        
        for selector in address_selectors:
            try:
                element = soup.select_one(selector)
                if element and element.get_text().strip():
                    return element.get_text().strip()
            except:
                continue
        
        # Look for address patterns in text
        text_content = soup.get_text()
        address_patterns = [
            r'Adress[:\s]*([^\n]+)',
            r'Säte[:\s]*([^\n]+)',
            r'Postadress[:\s]*([^\n]+)'
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""

def main():
    scraper = BolagsfaktaScraper()
    
    print("=== Bolagsfakta.se Koncern Scraper ===")
    print("Skriv 'quit' för att avsluta\n")
    
    while True:
        org_number = input("Ange organisationsnummer: ").strip()
        
        if org_number.lower() == 'quit':
            break
        
        if not org_number:
            print("Vänligen ange ett organisationsnummer.")
            continue
        
        print(f"\nSöker efter bolag med organisationsnummer: {org_number}")
        
        # Search for company
        company_url = scraper.search_company_by_org_number(org_number)
        
        if not company_url:
            print("Kunde inte hitta bolaget. Kontrollera organisationsnumret.")
            continue
        
        print(f"Hittade bolag: {company_url}")
        print("Hämtar koncerninformation...")
        
        # Get company information
        company_info = scraper.get_company_info(company_url)
        
        if not company_info:
            print("Kunde inte hämta information om bolaget.")
            continue
        
        # Display results
        print("\n" + "="*50)
        print(f"BOLAG: {company_info.get('company_name', 'Okänt')}")
        print(f"ORG.NR: {company_info.get('org_number', 'Okänt')}")
        print("="*50)
        
        if company_info.get('in_koncern'):
            print(f"✅ Bolaget ingår i en koncern med {company_info.get('total_companies_in_koncern', 0)} bolag totalt.")
            
            # Parent company information
            parent = company_info.get('parent_company')
            if parent:
                print("\n📋 MODERBOLAG:")
                print(f"   Namn: {parent.get('name', 'Okänt')}")
                print(f"   Org.nr: {parent.get('org_number', 'Okänt')}")
                print(f"   Säte: {parent.get('location', 'Okänt')}")
            else:
                print("\n📋 MODERBOLAG: Kunde inte hämta information")
            
            # Subsidiaries information
            subsidiaries = company_info.get('subsidiaries', [])
            if subsidiaries:
                print(f"\n🏢 DOTTERBOLAG ({len(subsidiaries)} st):")
                for i, sub in enumerate(subsidiaries, 1):
                    print(f"   {i}. {sub.get('name', 'Okänt')}")
                    print(f"      Org.nr: {sub.get('org_number', 'Okänt')}")
                    print(f"      Säte: {sub.get('location', 'Okänt')}")
                    print(f"      Ägarandel: {sub.get('ownership_percentage', 'Okänt')}%")
                    print()
            else:
                print("\n🏢 DOTTERBOLAG: Kunde inte hämta information")
        else:
            print("❌ Bolaget ingår inte i någon koncern.")
        
        print("="*50)
        print()

if __name__ == "__main__":
    main()
