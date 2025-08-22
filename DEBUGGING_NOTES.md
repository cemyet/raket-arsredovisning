# Debugging Notes: Variable Substitution Issues

## Problem Description
When moving through chat flow steps, calculated values (like `inkBeraknadSkatt`) were not persisting correctly. The frontend logs showed correct values being calculated and passed, but the final displayed text still showed old/incorrect values.

## Symptoms
- ✅ Frontend logs show correct calculated values
- ✅ API calls receive correct data
- ✅ Substitution variables object contains correct values
- ❌ Final substituted text shows wrong/old values
- ❌ Values appear to "reset" when moving between steps

## Root Cause
The issue was in the `substituteVariables` function in `frontend/src/components/DatabaseDrivenChat.tsx`:

```typescript
// PROBLEMATIC CODE:
const fullContext = {
  ...context,        // Correct values (e.g., 65,323)
  ...companyData,    // ❌ This OVERWRITES correct values with old values (e.g., 117,276)
  // ...
};
```

The spread operator order was wrong - `...companyData` was overwriting the correct values from `...context`.

## Solution
Fix the spread operator order and add explicit fallbacks:

```typescript
// FIXED CODE:
const fullContext = {
  ...companyData,
  ...context,  // ✅ Context values now override companyData values
  unusedTaxLossAmount: context.unusedTaxLossAmount || companyData.unusedTaxLossAmount || 0,
  inkBeraknadSkatt: context.inkBeraknadSkatt || companyData.inkBeraknadSkatt || 0,
  inkBokfordSkatt: context.inkBokfordSkatt || companyData.inkBokfordSkatt || 0,
  SkattAretsResultat: context.SkattAretsResultat || companyData.skattAretsResultat || 0,
  // ... other variables with explicit fallbacks
};
```

## Debugging Steps for Similar Issues

1. **Check frontend logs** for calculated values:
   ```javascript
   console.log('💰 Updated inkBeraknadSkatt:', updatedInkBeraknadSkatt);
   console.log('🔍 Substitution variables:', substitutionVars);
   console.log('🔍 Substituted question text:', questionText);
   ```

2. **Verify API calls** are receiving correct data:
   ```javascript
   console.log('🔍 API call - ink2DataToUse:', ink2DataToUse?.length, 'items');
   console.log('🔍 API call - inkBeraknadSkattItem:', inkBeraknadSkattItem);
   ```

3. **Check substitution variables object** - if this shows correct values but final text is wrong, the issue is in `substituteVariables` function

4. **Look for spread operator conflicts** in `substituteVariables` function

5. **Verify variable name consistency** between:
   - Database chat flow variables (e.g., `{inkBeraknadSkatt}`)
   - Frontend context object keys
   - Backend variable names

## Key Lessons
- **Spread operator order matters** - later spreads override earlier ones
- **Always prioritize context values** over stale companyData values
- **Add explicit fallbacks** for critical variables
- **Use detailed logging** to track value flow through the system
- **Check both frontend and backend** substitution logic

## Related Files
- `frontend/src/components/DatabaseDrivenChat.tsx` - Main chat component
- `frontend/src/services/api.ts` - API service for chat flow
- `backend/main.py` - Backend chat flow endpoints
- `chat_flow_rows (5).csv` - Database chat flow configuration

## Date
Fixed: January 2025
















