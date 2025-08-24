# BYGG K2 Integration Notes

## Critical Bug Fix - Januar 2025

### 🐛 **The Bug: BYGG Variables Overwritten with 0.0**

**Issue**: Frontend showed 0 kr for calculated BYGG values despite backend calculating correctly.

**Root Cause**: Logic order bug in `database_parser.py` - Noter parsing first pass:

```python
# ❌ OLD (BUGGY) ORDER:
1. Check if variable_name exists
2. Check if accounts_included is empty → OVERWRITE with 0.0 ⚠️
3. Check if variable is BYGG → Skip (never reached!)

# ✅ NEW (FIXED) ORDER:  
1. Check if variable_name exists
2. Check if variable is BYGG → Skip (preserves K2 values) ✅
3. Check if accounts_included is empty → OVERWRITE with 0.0
```

**Variables Affected**:
- `arets_inkop_bygg` (no accounts_included)
- `arets_fsg_bygg` (no accounts_included) 
- `arets_omklass_bygg` (no accounts_included)
- `arets_avskr_bygg` (no accounts_included)
- All other BYGG variables without accounts_included

**Fix Location**: `backend/services/database_parser.py` lines 1468-1471
**Commit**: `37df857` - "Fix BYGG variable overwrite bug in Noter parsing"

### ✅ **How BYGG K2 Integration Works Now**

1. **K2 Parser**: `bygg_k2_parser.py` calculates precise building values from transaction analysis
2. **Pre-load**: Values stored in `calculated_variables` with K2 results
3. **First Pass**: BYGG variables completely skipped (no database interference)
4. **Second Pass**: BYGG variables completely skipped (no formula processing)
5. **Final Results**: Uses pre-loaded K2 values from `calculated_variables`

**Result**: Zero database interference - BYGG values flow cleanly from K2 parser to frontend.

---

## 🔄 **Next: Extend to Maskiner and Inventarier**

### **Current State**:
- ✅ **BYGG** (Byggnader och mark): K2 parser integration complete
- ⏳ **MASKIN** (Maskiner och andra tekniska anläggningar): Database calculation
- ⏳ **INV** (Inventarier, verktyg och installationer): Database calculation

### **Database Variable Names to Migrate**:

**MASKIN Block (rows 52-83)**:
- `maskiner_ib`, `maskiner_ub` 
- `arets_inkop_maskiner`, `arets_fsg_maskiner`, `arets_omklass_maskiner`
- `ack_avskr_maskiner_ib`, `ack_avskr_maskiner_ub`, `arets_avskr_maskiner`
- `ack_nedskr_maskiner_ib`, `ack_nedskr_maskiner_ub`, `arets_nedskr_maskiner`
- `red_varde_maskiner`

**INV Block (rows 84-137+)**:
- `inventarier_ib`, `inventarier_ub`
- `arets_inkop_inventarier`, `arets_fsg_inventarier`, `arets_omklass_inventarier` 
- `ack_avskr_inventarier_ib`, `ack_avskr_inventarier_ub`, `arets_avskr_inventarier`
- `red_varde_inventarier`

### **Implementation Plan**:

1. **Create K2 Parsers**:
   - `maskin_k2_parser.py` - Machinery transaction analysis
   - `inventarier_k2_parser.py` - Equipment transaction analysis

2. **Update Database Parser**:
   - Add MASKIN variables to `bygg_variables` set (rename to `k2_variables`)
   - Add INV variables to `k2_variables` set
   - Import and run all K2 parsers in `parse_noter_data()`

3. **Account Ranges**:
   - **MASKIN**: 1210-1217 (accounts_included in CSV)
   - **INV**: 1220-1227;1230-1237;1240-1247;1250-1257 (accounts_included in CSV)

### **Code Structure**:
```python
# In parse_noter_data():
bygg_k2_data = parse_bygg_k2_from_sie_text(se_content, debug=True)
maskin_k2_data = parse_maskin_k2_from_sie_text(se_content, debug=True)  # NEW
inv_k2_data = parse_inventarier_k2_from_sie_text(se_content, debug=True)  # NEW

# Combine all K2 results
k2_variables = set(bygg_k2_data.keys()) | set(maskin_k2_data.keys()) | set(inv_k2_data.keys())

# Pre-load all K2 values
for var_name, value in {**bygg_k2_data, **maskin_k2_data, **inv_k2_data}.items():
    calculated_variables[var_name] = {'current': value, 'previous': 0.0}
```

---

## 🧠 **Key Lessons Learned**

1. **Order Matters**: Check special cases (BYGG/K2 variables) BEFORE general cases
2. **Preserve Pre-loaded Values**: Never overwrite calculated_variables after K2 pre-loading
3. **Complete Separation**: K2 variables should NEVER touch database calculation logic
4. **Debug Variable Names**: Use CSV export to verify database variable names match parser output

---

## 📊 **Testing Checklist for Future K2 Extensions**

- [ ] K2 parser produces correct variable names (match CSV)
- [ ] Values pre-loaded into calculated_variables 
- [ ] Variables skipped in first pass (no database calculation)
- [ ] Variables skipped in second pass (no formula processing)
- [ ] Frontend displays calculated values (not 0 kr)
- [ ] No overwrites in accounts_included logic


