#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robust Swedish Company Group Info Scraper (Ratsit-first)
- Deterministic BeautifulSoup parsing for Moderbolag/Dotterbolag
- Optional, narrow OpenAI fallback if markup variant defeats the parser
"""

import os
import re
import html
import json
import requests
from typing import Optional, List, Dict, Tuple

from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# Optional OpenAI fallback (set OPENAI_API_KEY to enable)
try:
    from openai import OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    _HAS_OPENAI = bool(OPENAI_API_KEY)
    _OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY) if _HAS_OPENAI else None
except Exception:
    _HAS_OPENAI = False
    _OPENAI_CLIENT = None

# Optional JS rendering (Playwright) for expanding Koncernträd
_HAS_PLAYWRIGHT = False
try:
    if os.getenv("USE_PLAYWRIGHT", "0") == "1":
        from playwright.sync_api import sync_playwright  # type: ignore
        _HAS_PLAYWRIGHT = True
except Exception:
    _HAS_PLAYWRIGHT = False


# --------------------- Scraper ---------------------

class RatsitGroupScraper:
    def __init__(self, *, timeout: int = 25):
        self.sess = requests.Session()
        self.sess.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) RatsitGroupScraper/2.0",
            "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8"
        })
        self.timeout = timeout

    # ---------------- Utils ----------------

    @staticmethod
    def _clean_text(t: Optional[str]) -> str:
        if not t:
            return ""
        return re.sub(r"\s+", " ", html.unescape(t)).strip()

    @staticmethod
    def _org_digits(orgnr: str) -> str:
        return re.sub(r"\D", "", orgnr or "")

    @staticmethod
    def _norm_orgnr(orgnr: Optional[str]) -> Optional[str]:
        if not orgnr:
            return None
        digits = re.sub(r"\D", "", orgnr)
        if len(digits) == 10:
            return digits[:6] + "-" + digits[6:]
        m = re.search(r"\b\d{6}-\d{4}\b", orgnr)
        return m.group(0) if m else None

    # ------------- Name → Orgnr (Ratsit search) -------------

    def resolve_orgnr_by_name(self, name: str) -> Optional[str]:
        """
        Resolve orgnr from a company name.
        Strategy: try Allabolag search first (often more reliable),
        then fall back to Ratsit search page.
        """
        try:
            # 1) Allabolag search
            url_ab = "https://www.allabolag.se/what/" + requests.utils.quote(name)
            r = self.sess.get(url_ab, timeout=self.timeout)
            if r.status_code == 200:
                m = re.search(r"\b\d{6}-\d{4}\b", r.text)
                if m:
                    return m.group(0)
        except Exception:
            pass
        try:
            # 2) Fallback: Ratsit search
            url_rs = "https://www.ratsit.se/sok/foretag/" + requests.utils.quote(name)
            r = self.sess.get(url_rs, timeout=self.timeout)
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, "html.parser")
            container = soup.find(id=re.compile(r"results|lista|search", re.I)) or soup
            text = container.get_text(" ", strip=True)
            m = re.search(r"\b\d{6}-\d{4}\b", text)
            return m.group(0) if m else None
        except Exception:
            return None

    # ---------------- Fetch company page ----------------

    def fetch_company_page(self, orgnr: str) -> Tuple[str, str]:
        url = "https://www.ratsit.se/" + self._org_digits(orgnr)
        r = self.sess.get(url, timeout=self.timeout)
        if r.status_code == 200:
            return r.text, r.url
        return "", url

    def fetch_allabolag_org_page(self, orgnr: str) -> Tuple[str, str]:
        """Try to fetch Allabolag organisation page for complete subsidiary list."""
        digits = self._org_digits(orgnr)
        # Try /organisation first
        for path in (f"https://www.allabolag.se/{digits}/organisation", f"https://www.allabolag.se/{digits}"):
            try:
                r = self.sess.get(path, timeout=self.timeout)
                if r.status_code == 200 and r.text:
                    return r.text, r.url
            except Exception:
                continue
        return "", ""

    def render_koncern_tree_html(self, orgnr: str) -> Tuple[str, str]:
        """Use Playwright to click 'Visa Koncernträd' and return expanded HTML (if enabled)."""
        if not _HAS_PLAYWRIGHT:
            return "", ""
        url = "https://www.ratsit.se/" + self._org_digits(orgnr)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(user_agent=self.sess.headers.get("User-Agent", ""))
                page = ctx.new_page()
                page.goto(url, timeout=self.timeout * 1000)
                page.wait_for_load_state("networkidle")
                # Try clicking variants of the button text
                for label in ["Visa Koncernträd", "Visa koncernträd", "Koncernträd", "Visa"]:
                    try:
                        btn = page.get_by_text(label, exact=False)
                        if btn and btn.count() > 0:
                            btn.first.click(timeout=3000)
                            page.wait_for_load_state("networkidle")
                            page.wait_for_timeout(800)
                            break
                    except Exception:
                        continue
                html = page.content()
                final_url = page.url
                browser.close()
                return html, final_url
        except Exception:
            return "", url

    def _extract_company_name_candidates(self, html: str) -> List[str]:
        """Extract candidate company names (AB/KB/HB/Kommanditbolag) from HTML."""
        out: List[str] = []
        if not html:
            return out
        soup = BeautifulSoup(html, "html.parser")
        # Anchor texts
        for a in soup.find_all("a", href=True):
            nm = self._clean_text(a.get_text(" ", strip=True))
            if nm and re.search(r"(AB|KB|HB|Kommanditbolag)\b", nm):
                out.append(nm)
        # Headings
        for h in soup.find_all(["h1", "h2", "h3", "h4"]):
            nm = self._clean_text(h.get_text())
            if nm and re.search(r"(AB|KB|HB|Kommanditbolag)\b", nm):
                out.append(nm)
        # Dedup while preserving order
        seen = set()
        uniq: List[str] = []
        for nm in out:
            if nm not in seen:
                seen.add(nm)
                uniq.append(nm)
        return uniq

    def parse_allabolag_subsidiaries(self, html: str) -> List[Dict]:
        """Heuristic parse of subsidiaries from Allabolag organisation page."""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        # Prefer scanning near labels
        root = None
        for lab in (r"\bDotterbolag\b", r"\bOrganisation\b", r"\bKoncern\b"):
            root = soup.find(string=re.compile(lab, re.I))
            if root:
                root = root.find_parent(["section", "div", "article", "li"]) or soup
                break
        if not root:
            root = soup

        out: List[Dict] = []
        seen = set()
        # Collect link texts as candidates
        for a in root.find_all("a", href=True):
            nm = self._clean_text(a.get_text(" ", strip=True))
            if not nm:
                continue
            if not re.search(r"(AB|KB|HB|Kommanditbolag)\b", nm):
                continue
            if nm in seen:
                continue
            seen.add(nm)
            # Try find orgnr nearby in the document text
            ctx_pat = rf"{re.escape(nm)}[^A-Z]*?(\d{{6}}-\d{{4}})"
            om = re.search(ctx_pat, text)
            sub_org = om.group(1) if om else None
            out.append({"name": nm, "org_number": self._norm_orgnr(sub_org) if sub_org else None, "sate": None})
        return out

    def resolve_company_details_by_name(self, name: str) -> Dict[str, Optional[str]]:
        """
        Resolve a company's org number and seat by name using name→orgnr, then fetch page.
        Returns {"org_number": str|None, "sate": str|None, "company_name": str|None}
        """
        org_candidate = self.resolve_orgnr_by_name(name)
        if not org_candidate:
            return {"org_number": None, "sate": None, "company_name": None}
        html, _ = self.fetch_company_page(org_candidate)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            cname, seat = self._parse_header(soup)
            return {"org_number": self._norm_orgnr(org_candidate), "sate": seat, "company_name": cname}
        return {"org_number": self._norm_orgnr(org_candidate), "sate": None, "company_name": None}

    # ---------------- Parsing helpers ----------------

    def _parse_header(self, soup: BeautifulSoup) -> Tuple[str, str]:
        name = ""
        sate = ""
        h = soup.find(["h1", "h2"])
        if h:
            heading = self._clean_text(h.get_text())
            # Clean variants like "Vill du veta mer om <Company>?"
            m_special = re.search(r"Vill du veta mer om\s+(.+?)\s*\?", heading, re.I)
            if m_special:
                name = self._clean_text(m_special.group(1))
            else:
                name = heading
        text = soup.get_text(" ", strip=True)
        m = re.search(r"(Säte)\s*[:\-]?\s*([A-Za-zÅÄÖåäö \-]+)", text)
        if m:
            sate = self._clean_text(m.group(2))
        return name, sate

    def _find_labeled_section(self, soup: BeautifulSoup, label_regex: str) -> Optional[BeautifulSoup]:
        """
        Find a section by label text (e.g., "Moderbolag"/"Dotterbolag").
        We search for a text node matching the regex and return a reasonable
        ancestor container to scan for links and nearby metadata.
        """
        label_node = soup.find(string=re.compile(label_regex, re.I))
        if not label_node:
            return None
        # Prefer a semantic container ancestor
        container = label_node.find_parent(["section", "article", "div", "li"]) or soup
        return container

    def _extract_companies_near(self, root: BeautifulSoup) -> List[Dict]:
        out: List[Dict] = []
        for a in root.find_all("a", href=True):
            nm = self._clean_text(a.get_text(" ", strip=True))
            if not nm:
                continue
            # Look for orgnr close to the link
            tail = a.find_next(string=re.compile(r"\b\d{6}-\d{4}\b|\b\d{10}\b"))
            org = None
            if tail:
                mt = re.search(r"\b\d{6}-\d{4}\b|\b\d{10}\b", str(tail))
                if mt:
                    org = self._norm_orgnr(mt.group(0))
            # Optional seat near the link
            seat = None
            small = a.find_next(["small", "span"])
            if small:
                ms = re.search(r"(Säte)\s*[:\-]?\s*([A-Za-zÅÄÖåäö \-]+)", self._clean_text(small.get_text()))
                if ms:
                    seat = self._clean_text(ms.group(2))
            out.append({"name": nm, "org_number": org, "sate": seat})
        return out

    def _openai_extract_fallback(self, html: str, orgnr: str, company_name: str) -> Tuple[Optional[Dict], List[Dict]]:
        """Very narrow fallback: ask OpenAI to extract parent & subsidiaries from HTML."""
        if not _HAS_OPENAI or not html:
            return None, []
        try:
            system_prompt = (
                "You are a Swedish company data analyst. Extract parent company and subsidiaries from the provided HTML. "
                "Return ONLY a valid JSON object with fields: parent_company {name, org_number}, subsidiaries [ {name, org_number} ]. "
                "If nothing found, use empty values."
            )
            user_prompt = f"HTML for {company_name} ({orgnr}):\n\n" + html[:40000]
            resp = _OPENAI_CLIENT.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=1200,
            )
            content = resp.choices[0].message.content or "{}"
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"```(?:json)?\n?", "", content).strip("`")
            data = json.loads(content)
            parent = data.get("parent_company") or None
            subs = data.get("subsidiaries") or []
            # Normalize org numbers
            if parent and parent.get("org_number"):
                parent["org_number"] = self._norm_orgnr(parent["org_number"]) or parent.get("org_number")
            for s in subs:
                if s.get("org_number"):
                    s["org_number"] = self._norm_orgnr(s["org_number"]) or s.get("org_number")
            return parent, subs
        except Exception:
            return None, []

    def parse_parent_and_subs(self, html: str) -> Tuple[Optional[Dict], List[Dict]]:
        if not html:
            return None, []
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Parent - look for "Moderbolag"/"Koncernmoderbolag" followed by a company name
        parent = None
        parent_patterns = [
            r"Koncernmoderbolag\s+([A-ZÅÄÖ][A-Za-zÅÄÖåäö\s&]+?(?:AB|KB|HB|Kommanditbolag))",
            r"Moderbolag\s+([A-ZÅÄÖ][A-Za-zÅÄÖåäö\s&]+?(?:AB|KB|HB|Kommanditbolag))(?:\s|$)",
        ]
        for pattern in parent_patterns:
            match = re.search(pattern, text)
            if match:
                parent_name = self._clean_text(match.group(1))
                parent_context = text[max(0, match.start()-120):match.end()+120]
                org_match = re.search(r"\b\d{6}-\d{4}\b", parent_context)
                parent_org = org_match.group(0) if org_match else None
                parent = {"name": parent_name, "org_number": self._norm_orgnr(parent_org) if parent_org else None, "sate": None}
                break

        # Subsidiaries - prose pattern like: "är ett moderbolag med två dotterbolag, A och B."
        subs: List[Dict] = []
        prose_patterns = [
            r"är ett moderbolag med \d+ dotterbolag,\s*([^.]+)",
            r"är ett moderbolag med (?:två|tre|fyra|fem) dotterbolag,\s*([^.]+)",
        ]
        prose_match = None
        for pat in prose_patterns:
            prose_match = re.search(pat, text)
            if prose_match:
                break
        if prose_match:
            subsidiary_text = prose_match.group(1)
            parts = re.split(r",\s*|\s+och\s+|\s+samt\s+", subsidiary_text)
            seen = set()
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                company_patterns = [
                    r"^([A-ZÅÄÖ][A-Za-zÅÄÖåäö\s&\-]*?(?:AB|KB|HB|Kommanditbolag))(?:\s|$)",
                    r"^([A-ZÅÄÖ][A-Za-zÅÄÖåäö\s&\-]*? II AB)(?:\s|$)",
                ]
                matched = False
                for cp in company_patterns:
                    m2 = re.search(cp, part)
                    if m2:
                        nm = self._clean_text(m2.group(1))
                        matched = True
                    if matched:
                        if nm and nm not in seen:
                            seen.add(nm)
                            ctx_pat = rf"{re.escape(nm)}[^A-Z]*?(\d{{6}}-\d{{4}})"
                            om = re.search(ctx_pat, text)
                            sub_org = om.group(1) if om else None
                            subs.append({"name": nm, "org_number": self._norm_orgnr(sub_org) if sub_org else None, "sate": None})
                        break
                if not matched:
                    # Fallback: patterns containing 'Aktiebolaget' without trailing AB
                    if re.search(r"\bAktiebolaget\b", part):
                        nm = self._clean_text(part)
                        if nm and nm not in seen:
                            seen.add(nm)
                            ctx_pat = rf"{re.escape(nm)}[^A-Z]*?(\d{{6}}-\d{{4}})"
                            om = re.search(ctx_pat, text)
                            sub_org = om.group(1) if om else None
                            subs.append({"name": nm, "org_number": self._norm_orgnr(sub_org) if sub_org else None, "sate": None})

        # Fallback: labeled sections if prose extraction didn't yield
        if not subs:
            sec_subs = self._find_labeled_section(soup, r"\bDotterbolag\b")
            if sec_subs:
                entries = self._extract_companies_near(sec_subs)
                seen = set()
                for s in entries:
                    key = (s.get("org_number") or "", s.get("name") or "")
                    if key in seen:
                        continue
                    seen.add(key)
                    if s.get("org_number"):
                        s["org_number"] = self._norm_orgnr(s["org_number"])
                    subs.append(s)

        # Optional OpenAI fallback if still empty
        if not parent and not subs:
            p2, s2 = self._openai_extract_fallback(html, "", "")
            parent = parent or p2
            subs = subs or s2

        return parent, subs

    # main method compatible with existing interface
    def get_company_group_info(self, orgnr: Optional[str] = None, company_name: Optional[str] = None) -> Dict:
        return self.get_group_info(orgnr=orgnr, name=company_name)

    # main
    def get_group_info(self, *, orgnr: Optional[str], name: Optional[str]) -> Dict:
        if not orgnr and not name:
            raise ValueError("Provide orgnr or name")

        if not orgnr and name:
            orgnr = self.resolve_orgnr_by_name(name)
            if not orgnr:
                return {"company_name": name or "", "orgnr": "", "sate": "", "parent_company": None, "subsidiaries": [], "sources": []}

        norm_org = self._norm_orgnr(orgnr) or (orgnr or "")
        html, final_url = self.fetch_company_page(norm_org)
        if not html:
            return {"company_name": name or "", "orgnr": norm_org, "sate": "", "parent_company": None, "subsidiaries": [], "sources": [final_url] if final_url else []}

        soup = BeautifulSoup(html, "html.parser")
        cname, sate = self._parse_header(soup)
        parent, subs = self.parse_parent_and_subs(html)

        # Secondary enrichment: resolve orgnr and seat for subsidiaries lacking details
        enriched_subs: List[Dict] = []
        for s in subs:
            nm = s.get("name") or ""
            org = s.get("org_number")
            seat = s.get("sate")
            if nm and (not org or not seat):
                details = self.resolve_company_details_by_name(nm)
                if not org:
                    s["org_number"] = details.get("org_number")
                if not seat:
                    s["sate"] = details.get("sate")
            enriched_subs.append(s)
        subs = enriched_subs

        # If Ratsit text indicated more subsidiaries than parsed, try Allabolag organisation page
        try:
            text = soup.get_text(" ", strip=True)
            word_to_num = {"två": 2, "tre": 3, "fyra": 4, "fem": 5}
            expected = None
            m_num = re.search(r"är ett moderbolag med (\d+) dotterbolag", text)
            if m_num:
                expected = int(m_num.group(1))
            else:
                m_word = re.search(r"är ett moderbolag med (två|tre|fyra|fem) dotterbolag", text, re.I)
                if m_word:
                    expected = word_to_num.get(m_word.group(1).lower())
            # Handle suffix phrasing: "... samt 1 dotterbolag till"
            # If present, bump expectation by that many beyond already listed names
            more = None
            m_more_num = re.search(r"samt\s+(\d+)\s+dotterbolag\s+till", text, re.I)
            if m_more_num:
                more = int(m_more_num.group(1))
            else:
                m_more_word = re.search(r"samt\s+(ett|en|två|tre|fyra|fem)\s+dotterbolag\s+till", text, re.I)
                if m_more_word:
                    word_map = {"ett": 1, "en": 1, **word_to_num}
                    more = word_map.get(m_more_word.group(1).lower())
            if more is not None and (expected is None or expected < len(subs) + more):
                expected = len(subs) + more
            if expected and len(subs) < expected:
                ab_html, _ = self.fetch_allabolag_org_page(norm_org)
                candidates = self.parse_allabolag_subsidiaries(ab_html)
                # Deduplicate and add missing ones
                known_names = {s.get("name") for s in subs}
                for c in candidates:
                    if c.get("name") and c["name"] not in known_names:
                        # resolve details to fill seat/org if needed
                        det = self.resolve_company_details_by_name(c["name"]) if (not c.get("org_number") or not c.get("sate")) else None
                        if det:
                            if not c.get("org_number"):
                                c["org_number"] = det.get("org_number")
                            if not c.get("sate"):
                                c["sate"] = det.get("sate")
                        subs.append(c)
                        known_names.add(c["name"])
                        if len(subs) >= expected:
                            break
                # If still missing, try Playwright to expand Koncernträd and mine candidates
                if len(subs) < expected:
                    exp_html, _ = self.render_koncern_tree_html(norm_org)
                    if exp_html:
                        names = self._extract_company_name_candidates(exp_html)
                        # Remove top-level and parent names
                        top_name = cname or (name or "")
                        parent_name = parent.get("name") if parent else None
                        names = [n for n in names if n not in (top_name, parent_name)]
                        for nm in names:
                            if nm not in known_names:
                                det = self.resolve_company_details_by_name(nm)
                                subs.append({
                                    "name": nm,
                                    "org_number": det.get("org_number"),
                                    "sate": det.get("sate")
                                })
                                known_names.add(nm)
                                if len(subs) >= expected:
                                    break
        except Exception:
            pass

        return {"company_name": cname or (name or ""), "orgnr": norm_org, "sate": sate, "parent_company": parent or None, "subsidiaries": subs, "sources": [final_url]}


# --------------------- FastAPI app (optional) ---------------------

app = FastAPI(title="Ratsit Group Info API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

scraper = RatsitGroupScraper()

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/group-info")
def group_info(
    orgnr: Optional[str] = Query(None, description="Swedish orgnr, e.g. 556707-8174"),
    name: Optional[str] = Query(None, description="Company name (used if orgnr missing)")
):
    if not orgnr and not name:
        raise HTTPException(status_code=400, detail="Provide orgnr or name.")
    try:
        data = scraper.get_group_info(orgnr=orgnr, name=name)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def test_scraper():
    print("=== TESTING RATSIT SCRAPER ===")
    sc = RatsitGroupScraper()
    print("Testing with: Holtback Real Estate AB")
    result = sc.get_company_group_info(company_name="Holtback Real Estate AB")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nSUMMARY:")
    print("Company: " + str(result.get('company_name', 'N/A')))
    print("Org number: " + str(result.get('orgnr', 'N/A')))
    parent_status = "Yes" if result.get('parent_company') else "None"
    print("Parent company: " + parent_status)
    print("Subsidiaries found: " + str(len(result.get('subsidiaries', []))))
    if result.get('subsidiaries'):
        for i, sub in enumerate(result['subsidiaries']):
            print("  {}. {}".format(i+1, sub.get('name', 'N/A')))


if __name__ == "__main__":
    test_scraper()
