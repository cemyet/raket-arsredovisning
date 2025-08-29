# Account Preclassification Implementation Summary

## Overview
Successfully implemented the account preclassification system as requested. The system adds intelligent account-to-row mapping using company information from Bolagsfakta scraper and customizable business rules.

## Files Created/Modified

### 1. New Module: `backend/account_preclass/`
- **`__init__.py`**: Package initialization
- **`preclass.py`**: Complete preclassification engine with:
  - SIE file parsing for account data
  - Supabase BR mapping integration  
  - Bolagsfakta company info integration
  - Contextual account classification
  - Reclass logging and audit trails

### 2. Environment Configuration: `backend/env.example`
Added required environment variables:
- `SUPABASE_KEY`: Service role key for preclassification module
- `PRECLASSIFY_ACCOUNTS=true`: Enable/disable preclassification
- `K2_KONCERN_USE_PRECLASS=true`: Enable preclass for K2 koncern parser
- `PRECLASSIFY_STRICT=false`: Strict mode for override conflicts

### 3. Main Application: `backend/main.py`
- Added preload step after SIE import, before parsers
- Integrated Bolagsfakta scraper for company info
- Cached preclass results in parser context
- Added audit logging to API responses
- Created `/preclass-audit/{org_number}` endpoint

### 4. Database Parser: `backend/services/database_parser.py`
- Modified `calculate_variable_value()` to use preclass results
- Added caching for current/previous year detection
- BR parser now consumes `ctx.preclass.per_account` for row placement

### 5. K2 Koncern Parser: `backend/services/koncern_k2_parser.py`
- Added feature flag check for `K2_KONCERN_USE_PRECLASS`
- Modified function signature to accept `preclass_result` parameter
- Bypasses old reclass logic when preclass is enabled
- Returns preclass-based row mappings

## Key Features Implemented

### 1. Intelligent Account Classification
- **Alias Extraction**: Extracts company names from account descriptions
- **Bolagsfakta Integration**: Uses parent/subsidiary info for better classification
- **Contextual Mapping**: Maps accounts to appropriate BR rows based on:
  - Account number ranges (1310-1329 koncern, 1330-1339 intresse)
  - Account name analysis (fordringar, skulder, andelar, etc.)
  - Company relationship detection

### 2. Feature Flag System
- `PRECLASSIFY_ACCOUNTS`: Master toggle
- `K2_KONCERN_USE_PRECLASS`: K2 koncern parser integration
- `PRECLASSIFY_STRICT`: Strict mode for override handling

### 3. Audit and Logging
- **Reclass Log**: Detailed account reclassification tracking
- **API Integration**: Logs included in upload response
- **Audit Endpoint**: Dedicated endpoint for explainability

### 4. Fallback Support
- When preclass fails or is disabled, falls back to default mappings
- Non-breaking changes - existing logic preserved
- Graceful error handling with warnings

## Integration Points

### 1. Processing Pipeline
```
SIE Import → Preclassify Accounts → Cache Results → BR/K2 Parsers
```

### 2. Data Flow
- **Input**: SIE file + Company info from Bolagsfakta
- **Processing**: Account classification and BR row mapping
- **Output**: Enhanced BR totals and audit logs

### 3. Parser Integration
- **BR Parser**: Uses preclass row assignments for account grouping
- **K2 Koncern**: Bypasses old logic when preclass enabled
- **Other Parsers**: Unchanged (INK2, RR, Noter calculations unaffected)

## API Changes

### Upload Response Enhancement
```json
{
  "data": {
    // ... existing fields ...
    "preclass_log": [
      {
        "account": "1681",
        "name": "Kortfristiga fordringar, RH Property",
        "from": "12|Övriga fordringar",
        "to": "15|Kortfristiga fordringar koncern",
        "reason": "Koncern fordringar (ST)"
      }
    ],
    "preclass_enabled": true
  }
}
```

### New Audit Endpoint
```
GET /preclass-audit/{org_number}
```

## Testing and Validation

### Enable Features
1. Set environment variables in `.env`:
   ```
   PRECLASSIFY_ACCOUNTS=true
   K2_KONCERN_USE_PRECLASS=true
   PRECLASSIFY_STRICT=false
   ```

2. Upload SE file and check response for:
   - `preclass_enabled: true`
   - Non-empty `preclass_log` array
   - Different BR totals where reclassification occurred

### Verify Integration
- BR parser should show "BR: Using preclass value..." logs
- K2 koncern should show "K2 KONCERN: Using preclass results..." logs
- Bolagsfakta info should be retrieved and used for alias detection

## Benefits Delivered

1. **Improved Accuracy**: Better account-to-row mapping using company context
2. **Transparency**: Full audit trail of all reclassifications  
3. **Flexibility**: Feature flags allow gradual rollout and testing
4. **Compatibility**: Non-breaking changes preserve existing functionality
5. **Extensibility**: Framework supports future enhancements

## Future Enhancements

1. **Database Storage**: Store preclass logs in database for historical analysis
2. **UI Integration**: Frontend display of reclassification explanations
3. **Machine Learning**: ML-based classification improvements
4. **Additional Parsers**: Extend to other note types beyond K2 koncern
5. **Performance**: Caching of Bolagsfakta results

## Dependencies

- All existing dependencies maintained
- `supabase` package already included in requirements.txt
- `beautifulsoup4` and `requests` already available for Bolagsfakta scraper

The implementation is complete and ready for testing with the specified feature flags.
