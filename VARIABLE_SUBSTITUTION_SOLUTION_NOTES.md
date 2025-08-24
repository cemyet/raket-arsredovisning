# Variable Substitution Solution Notes

## Problem Summary
We encountered multiple issues with variable substitution in the chat flow system where calculated values were not displaying correctly in chat messages.

## Issues Encountered and Solutions

### Issue 1: inkBeraknadSkatt Not Persisting (Step 401)
**Problem**: When moving from step 303 to 401, the calculated `inkBeraknadSkatt` value was reset to the original value instead of showing the updated value.

**Root Cause**: The `substituteVariables` function was prioritizing `companyData` values over context values due to incorrect spread operator order.

**Solution**:
```typescript
// PROBLEMATIC CODE:
const fullContext = {
  ...context,        // Correct values (65,323)
  ...companyData,    // ❌ This OVERWROTE correct values with old values (117,276)
};

// FIXED CODE:
const fullContext = {
  ...companyData,
  ...context,  // ✅ Context values now override companyData values
  // Plus explicit fallbacks for each variable
  inkBeraknadSkatt: context.inkBeraknadSkatt || companyData.inkBeraknadSkatt || 0,
  // ... other variables
};
```

**Key Lesson**: Spread operator order matters - later spreads override earlier ones.

### Issue 2: SkattAretsResultat Showing Wrong Value (Step 104)
**Problem**: Chat message showed "Den bokförda skatten är 553 622 kr" instead of "0 kr".

**Root Cause**: Search logic was too broad and was finding `SumResultatForeSkatt` instead of `SkattAretsResultat`.

**Solution**:
```typescript
// PROBLEMATIC CODE:
const skattAretsResultatItem = fileData.data.rr_data.find((item: any) => 
  item.variable_name === 'SkattAretsResultat' ||
  item.id === 'SKATT' ||
  item.label?.toLowerCase().includes('skatt')  // ❌ Too broad!
);

// FIXED CODE:
// First try to find exact variable name match
let skattAretsResultatItem = fileData.data.rr_data.find((item: any) => 
  item.variable_name === 'SkattAretsResultat'
);

// If not found, try ID match
if (!skattAretsResultatItem) {
  skattAretsResultatItem = fileData.data.rr_data.find((item: any) => 
    item.id === 'SKATT'
  );
}

// If still not found, try label match but exclude wrong variables
if (!skattAretsResultatItem) {
  skattAretsResultatItem = fileData.data.rr_data.find((item: any) => 
    item.label?.toLowerCase().includes('skatt') && 
    item.variable_name !== 'SumResultatForeSkatt' &&
    item.variable_name !== 'SumResultatEfterFinansiellaPoster'
  );
}
```

**Key Lesson**: Always prioritize exact variable name matches over fuzzy label matching.

### Issue 3: SumAretsResultat Showing Wrong Value (Step 103)
**Problem**: Chat message showed "Årets resultat är: 0 kr" instead of "553 622 kr".

**Root Cause**: Same issue as Issue 2 - search logic was finding `SkattAretsResultat` instead of `SumAretsResultat`.

**Solution**: Applied the same prioritized search logic as Issue 2, but for `SumAretsResultat`:
```typescript
// First try to find exact variable name match in RR data
let sumAretsResultatItem = fileData.data.rr_data.find((item: any) => 
  item.variable_name === 'SumAretsResultat'
);

// If not found in RR, try ID match in RR
if (!sumAretsResultatItem) {
  sumAretsResultatItem = fileData.data.rr_data.find((item: any) => 
    item.id === 'ÅR'
  );
}

// If still not found in RR, try label match but exclude SkattAretsResultat
if (!sumAretsResultatItem) {
  sumAretsResultatItem = fileData.data.rr_data.find((item: any) => 
    item.label?.toLowerCase().includes('årets resultat') &&
    item.variable_name !== 'SkattAretsResultat'
  );
}
```

### Issue 4: Negative Zero Display
**Problem**: Values showing as "-0 kr" instead of "0 kr".

**Root Cause**: `Math.round()` function can return negative zero.

**Solution**:
```typescript
skattAretsResultat = Math.round(skattAretsResultatItem.current_amount);
// Fix negative zero issue
if (skattAretsResultat === -0) skattAretsResultat = 0;
```

### Issue 5: Decimal Formatting
**Problem**: Numbers showing with decimals (e.g., "15 193,553 kr" instead of "15 193 kr").

**Root Cause**: `Intl.NumberFormat` was using default formatting which includes decimals.

**Solution**:
```typescript
// PROBLEMATIC CODE:
new Intl.NumberFormat('sv-SE').format(value)

// FIXED CODE:
new Intl.NumberFormat('sv-SE', { 
  minimumFractionDigits: 0, 
  maximumFractionDigits: 0 
}).format(value)
```

## Debugging Techniques Used

### 1. Detailed Logging
Added comprehensive logging to track value flow:
```typescript
console.log('🔍 Searching for SkattAretsResultat in RR data...');
console.log('🔍 Available RR items:', fileData.data.rr_data.map((item: any) => ({
  variable_name: item.variable_name,
  id: item.id,
  label: item.label,
  current_amount: item.current_amount
})));
console.log('🔍 Substitution variables:', substitutionVars);
console.log('🔍 Substituted question text:', questionText);
```

### 2. Database Mapping Verification
Checked the RR mapping file (`variable_mapping_rr_rows.csv`) to understand the correct variable names and their relationships.

### 3. Step-by-Step Value Tracking
Tracked values through the entire flow:
- File processing → Variable extraction → Context building → Substitution → Display

## Key Lessons Learned

1. **Spread Operator Order**: Always prioritize context values over stale companyData values
2. **Exact Variable Matching**: Use exact variable name matches before fuzzy label matching
3. **Explicit Fallbacks**: Add explicit fallbacks for critical variables
4. **Number Formatting**: Always specify decimal formatting options
5. **Negative Zero Handling**: Check for and handle negative zero values
6. **Comprehensive Logging**: Use detailed logging to track value flow through the system

## Files Modified

- `frontend/src/components/DatabaseDrivenChat.tsx` - Main chat component with all fixes
- `DEBUGGING_NOTES.md` - General debugging notes
- `VARIABLE_SUBSTITUTION_SOLUTION_NOTES.md` - This file

## Working Version

- **Tag**: `v1.0.0-working-variables`
- **Commit**: `bdcaceb`
- **Status**: All variable substitution and formatting issues resolved

## Future Prevention

1. **Code Review Checklist**: Always check spread operator order in variable substitution
2. **Search Logic**: Use exact variable name matching as first priority
3. **Number Formatting**: Always specify decimal formatting options
4. **Testing**: Test variable substitution with edge cases (0, negative values, decimals)

## Related Database Tables

- `public.chat_flow` - Chat flow configuration with variable placeholders
- `variable_mapping_rr` - RR variable mappings
- `variable_mapping_br` - BR variable mappings

## Date
Solved: January 2025

















