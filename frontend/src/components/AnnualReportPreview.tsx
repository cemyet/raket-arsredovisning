'use client';

import { useState, useEffect } from 'react';
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { calculateRRSums, extractKeyMetrics, formatAmount, type SEData } from '@/utils/seFileCalculations';
import { apiService } from '@/services/api';
import { Periodiseringsfonder } from './Periodiseringsfonder';
import { Noter } from './Noter';

interface CompanyData {
  results?: string;
  result?: number | null;
  dividend: string;
  customDividend?: number;
  significantEvents: string;
  hasEvents: boolean;
  depreciation: string;
  employees: number;
  location: string;
  date: string;
  boardMembers: Array<{ name: string; personalNumber: string }>;
  ink2Data?: any[]; // INK2 tax calculation data
  showTaxPreview?: boolean; // Show tax calculation module
  showRRBR?: boolean;
  taxEditingEnabled?: boolean;
  editableAmounts?: Record<string, number>;
  unusedTaxLossAmount?: number;
  justeringSarskildLoneskatt?: number;
  pensionPremier?: number;
  sarskildLoneskattPension?: number;
  sarskildLoneskattPensionCalculated?: number;
  noterData?: Array<{
    row_id: number;
    row_title: string;
    current_amount: number;
    previous_amount: number;
    variable_name: string;
    show_tag: boolean;
    accounts_included: string;
    account_details?: Array<{
      account_id: string;
      account_text: string;
      balance: number;
    }>;
    block: string;
    always_show: boolean;
    toggle_show: boolean;
    style: string;
  }>;
  seFileData?: SEData & {
    current_accounts?: Record<string, number>;
    annualReport?: {
      header: {
        organization_number: string;
        fiscal_year: number;
        company_name: string;
        location: string;
        date: string;
      };
      financial_results: {
        revenue: number;
        operating_profit: number;
        net_result: number;
        total_assets: number;
        income_statement: any[];
        balance_sheet: any[];
      };
      significant_events: string[];
      depreciation_policy: string;
      employees: {
        count: number;
        description: string;
      };
      board_members: Array<{
        name: string;
        role: string;
      }>;
    };
    // Previous year data from parse-se-python
    income_statement_year_minus1?: Array<{
      id: string;
      label: string;
      amount: number | null;
      level: number;
      section: string;
      bold: boolean;
      sru: string;
    }>;
    balance_sheet_year_minus1?: Array<{
      id: string;
      label: string;
      amount: number;
      level: number;
      section: string;
      type: string;
      bold: boolean;
    }>;
    rr_data?: Array<{
      id: string;
      label: string;
      current_amount: number | null;
      previous_amount: number | null;
      level: number;
      section: string;
      bold?: boolean;
      style?: string;
      block_group?: string;
    }>;
    br_data?: Array<{
      id: string;
      label: string;
      current_amount: number | null;
      previous_amount: number | null;
      level: number;
      section: string;
      type: 'asset' | 'liability' | 'equity';
      bold?: boolean;
      style?: string;
      block_group?: string;
    }>;
    ink2_data?: Array<{
      row_id: number;
      row_title: string;
      amount: number;
      variable_name: string;
      show_tag: boolean;
      accounts_included: string;
      show_amount?: boolean;
      style?: string;
      is_calculated?: boolean;
      always_show?: boolean | null;
      explainer?: string;
      block?: string;
      header?: boolean;
      account_details?: Array<{
        account_id: string;
        account_text: string;
        balance: number;
      }>;
    }>;
         company_info?: {
       organization_number?: string;
       fiscal_year?: number;
       company_name?: string;
       location?: string;
       date?: string;
     };
     significant_events?: string[];
     depreciation_policy?: string;
     employees?: {
       count: number;
       description: string;
     };
     board_members?: Array<{
       name: string;
       role: string;
     }>;
  };
  organizationNumber?: string;
  fiscalYear?: number;
  // Previous year data from parse-se-python (camelCase keys)
  incomeStatementYearMinus1?: Array<{
    id: string;
    label: string;
    amount: number | null;
    level: number;
    section: string;
    bold: boolean;
    sru: string;
  }>;
  balanceSheetYearMinus1?: Array<{
    id: string;
    label: string;
    amount: number;
    level: number;
    section: string;
    type: string;
    bold: boolean;
  }>;
}

interface AnnualReportPreviewProps {
  companyData: CompanyData;
  currentStep: number;
  editableAmounts?: boolean;
  onDataUpdate?: (updates: Partial<any>) => void;
}

// Database-driven always_show logic - no more hardcoded arrays

export function AnnualReportPreview({ companyData, currentStep, editableAmounts = false, onDataUpdate }: AnnualReportPreviewProps) {
  // Safe access; never destructure undefined
  const cd = companyData as CompanyData;
  
  // Debug logging at the top to confirm mounting
  console.log('🔍 AnnualReportPreview MOUNTED');
  console.log('🔍 Props:', {
    editableAmounts,
    currentStep,
    hasOnDataUpdate: !!onDataUpdate,
    companyDataKeys: Object.keys(cd)
  });
  console.log('🔍 Rendering flags:', {
    showTaxPreview: cd.showTaxPreview,
    showRRBR: cd.showRRBR,
    taxEditingEnabled: cd.taxEditingEnabled,
    editableAmounts: cd.editableAmounts
  });

  // Requirement 2: inputs become editable when taxEditingEnabled OR editableAmounts is true
  const isEditing = Boolean(cd.taxEditingEnabled || editableAmounts);
  console.log('🔍 isEditing calculated as:', isEditing, '(taxEditingEnabled:', cd.taxEditingEnabled, 'editableAmounts:', editableAmounts, ')');

  // Requirement 1: render when showTaxPreview OR showRRBR is true
  if (!cd.showTaxPreview && !cd.showRRBR) {
    console.log('🔍 AnnualReportPreview mounted but not rendering (both showTaxPreview and showRRBR are false)');
    return null;
  }
  
  const [showAllRR, setShowAllRR] = useState(false);
  const [showAllBR, setShowAllBR] = useState(false);

  const [editedAmounts, setEditedAmounts] = useState<Record<string, number>>({});
  const [originalAmounts, setOriginalAmounts] = useState<Record<string, number>>({});
  const [recalculatedData, setRecalculatedData] = useState<any[]>([]);

  // Get new database-driven parser data (moved up to avoid initialization errors)
  const seFileData = cd.seFileData;
  const rrData = seFileData?.rr_data || [];
  const brData = seFileData?.br_data || [];
  const ink2Data = cd.ink2Data || seFileData?.ink2_data || [];
  const companyInfo = seFileData?.company_info || {};

  // Capture original amounts when isEditing becomes true (for undo functionality)
  useEffect(() => {
    if (isEditing && Object.keys(originalAmounts).length === 0) {
      const currentData = recalculatedData.length > 0 ? recalculatedData : ink2Data;
      const amounts: Record<string, number> = {};
      currentData.forEach((item: any) => {
        if ((!item.is_calculated || item.variable_name === 'INK_sarskild_loneskatt') && item.show_amount) {
          amounts[item.variable_name] = item.amount || 0;
        }
      });
      setOriginalAmounts(amounts);
    }
  }, [isEditing, ink2Data, recalculatedData, originalAmounts]);



  // Undo all changes
  const handleUndo = async () => {
    setEditedAmounts(originalAmounts);
    await recalculateValues(originalAmounts);
  };

  // Recalculate dependent values when amounts change
  const recalculateValues = async (updatedAmounts: Record<string, number>) => {
    try {
      console.log('Recalculating with amounts:', updatedAmounts);
      
      // Handle pension tax field mapping and preserve existing values
      const preservedAmounts = { ...updatedAmounts };
      
      // Preserve INK4.14a (unused tax loss) if it exists and not being manually edited
      if (companyData.unusedTaxLossAmount && !('INK4.14a' in updatedAmounts)) {
        preservedAmounts['INK4.14a'] = companyData.unusedTaxLossAmount;
        console.log('Preserving existing INK4.14a (unused tax loss):', companyData.unusedTaxLossAmount);
      }
      
      // If user edited INK_sarskild_loneskatt, convert it to justering_sarskild_loneskatt for backend
      if ('INK_sarskild_loneskatt' in updatedAmounts) {
        // Frontend stores positive value, backend expects justering_sarskild_loneskatt (positive = increase, negative = decrease)
        preservedAmounts.justering_sarskild_loneskatt = updatedAmounts.INK_sarskild_loneskatt;
        delete preservedAmounts.INK_sarskild_loneskatt; // Remove the INK version
        console.log('Converting INK_sarskild_loneskatt to justering_sarskild_loneskatt:', preservedAmounts.justering_sarskild_loneskatt);
      } else if (typeof companyData.justeringSarskildLoneskatt === 'number' && companyData.justeringSarskildLoneskatt !== 0) {
        // Preserve existing numeric value if not being edited
        preservedAmounts.justering_sarskild_loneskatt = companyData.justeringSarskildLoneskatt;
        console.log('Preserving existing justering_sarskild_loneskatt:', companyData.justeringSarskildLoneskatt);
      }
      
      // Call backend API to recalculate INK2 values using API service
      const result = await apiService.recalculateInk2({
        current_accounts: seFileData?.current_accounts || {},
        fiscal_year: seFileData?.company_info?.fiscal_year,
        rr_data: seFileData?.rr_data || [],
        br_data: seFileData?.br_data || [],
        manual_amounts: preservedAmounts
      });
      
      if (result.success) {
        // Update the seFileData with new calculated values
        if (companyData.seFileData) {
          companyData.seFileData.ink2_data = result.ink2_data;
          // Force re-render by updating the state
          setRecalculatedData(result.ink2_data);
        }
        console.log('Successfully recalculated INK2 values');
      } else {
        console.error('Failed to recalculate: API returned success=false');
      }
    } catch (error) {
      console.error('Error recalculating values:', error);
    }
  };
  
  // Debug logging

  

  
  // No fallback needed - database-driven parser provides all data

  // Helper function to get styling classes and style based on style
  const getStyleClasses = (style?: string) => {
    const baseClasses = 'grid gap-4';
    let additionalClasses = '';
    
    // Handle bold styling for header styles only
    if (style === 'H0' || style === 'H1' || style === 'H2' || style === 'H3' || style === 'S1' || style === 'S2' || style === 'S3') {
      additionalClasses += ' font-semibold';
    }
    
    // Handle specific styling for S2 and S3 (thin grey lines above and below)
    if (style === 'S2' || style === 'S3') {
      additionalClasses += ' border-t border-b border-gray-200 pt-1 pb-1';
    }
    
    return {
      className: `${baseClasses}${additionalClasses}`,
      style: { gridTemplateColumns: '4fr 0.5fr 1fr 1fr' }
    };
  };

  // Same styling semantics as RR/BR but for INK2's 2-column layout
  const getInkStyleClasses = (style?: string) => {
    const baseClasses = 'grid gap-4';
    let additionalClasses = '';

    // Support legacy and T-styles (TH1/TH2/TH3/TS1/TS2/TS3/TNORMAL)
    const s = style || '';
    
    // Bold styles - TNORMAL should NOT be bold
    const boldStyles = ['H0','H1','H2','H3','S1','S2','S3','TH0','TH1','TH2','TH3','TS1','TS2','TS3'];
    if (boldStyles.includes(s)) {
      additionalClasses += ' font-semibold';
    }
    
    // Line styles - only S2/S3/TS2/TS3 get darker lines
    const lineStyles = ['S2','S3','TS2','TS3'];
    if (lineStyles.includes(s)) {
      additionalClasses += ' border-t border-b border-gray-300 pt-1 pb-1';
    }

    // Indentation for TNORMAL only
    const indentStyles = ['TNORMAL'];
    const indentation = indentStyles.includes(s) ? ' pl-6' : '';

    return {
      className: `${baseClasses}${additionalClasses}${indentation}`,
      style: { gridTemplateColumns: '3fr 1fr' }
    };
  };

  // Helper function to format amount (show 0 kr instead of -0 kr)
  const formatAmountDisplay = (amount: number | null): string => {
    if (amount === null || amount === undefined) {
      return '';
    }
    if (amount === 0 || amount === -0) {
      return '0 kr';
    }
    return `${formatAmount(amount)} kr`;
  };

  // Helper function to check if a block should be shown
  const shouldShowBlock = (data: any[], startIndex: number, endIndex: number, alwaysShowItems: string[], showAll: boolean): boolean => {
    if (showAll) return true;
    
    // Check if any item in the block has non-zero amounts or is in always show list
    for (let i = startIndex; i <= endIndex && i < data.length; i++) {
      const item = data[i];
      const hasNonZeroAmount = (item.current_amount !== null && item.current_amount !== 0 && item.current_amount !== -0) ||
                              (item.previous_amount !== null && item.previous_amount !== 0 && item.previous_amount !== -0);
      const isAlwaysShow = alwaysShowItems.includes(item.label);
      
      if (hasNonZeroAmount || isAlwaysShow) {
        return true;
      }
    }
    return false;
  };

  // Helper function to check if a block group has any content
  const blockGroupHasContent = (data: any[], blockGroup: string): boolean => {
    if (!blockGroup) return true; // Show items without block_group
    
    const blockItems = data.filter(item => item.block_group === blockGroup);
    
    for (const item of blockItems) {
      const isHeading = item.style && ['H0', 'H1', 'H2', 'H3', 'S1', 'S2', 'S3'].includes(item.style);
      if (isHeading) continue; // Skip headings when checking block content
      
      const hasNonZeroAmount = (item.current_amount !== null && item.current_amount !== 0 && item.current_amount !== -0) ||
                              (item.previous_amount !== null && item.previous_amount !== 0 && item.previous_amount !== -0);
      const isAlwaysShow = item.always_show === true; // Use database field
      
      if (hasNonZeroAmount || isAlwaysShow) {
        return true;
      }
    }
    return false;
  };

  // Helper function to check if a row should be shown
  const shouldShowRow = (item: any, showAll: boolean, data: any[]): boolean => {
    if (showAll) return true;
    
    // Check if this is a heading
    const isHeading = item.style && ['H0', 'H1', 'H2', 'H3'].includes(item.style);
    
    if (isHeading) {
      // For headings, check if their block group has content
      if (item.block_group) {
        return blockGroupHasContent(data, item.block_group);
      }
      // NEW: Even headings without block_group must follow always_show rule
      return item.always_show === true;
    }
    
    // NEW LOGIC: If amount is 0 for both years, hide unless always_show = true
    const hasNonZeroAmount = (item.current_amount !== null && item.current_amount !== 0 && item.current_amount !== -0) ||
                            (item.previous_amount !== null && item.previous_amount !== 0 && item.previous_amount !== -0);
    const isAlwaysShow = item.always_show === true; // Use database field
    
    // Show if: (has non-zero amount) OR (always_show = true)
    return hasNonZeroAmount || isAlwaysShow;
  };

  // Helper function to get note value for specific rows
  const getNoteValue = (label: string): string => {
    if (label === 'Personalkostnader') {
      return '2';
    }
    return '';
  };

  const getPreviewContent = () => {
    // Show empty state only if we have no data and are at step 0
    if (currentStep === 0 && !rrData.length && !brData.length) {
      return (
        <div className="text-center py-20">
          <div className="text-muted-foreground mb-4">
            <div className="w-16 h-16 mx-auto mb-4 rounded-lg bg-muted flex items-center justify-center">
              📄
            </div>
            <h3 className="text-lg font-medium mb-2">Årsredovisning</h3>
            <p className="text-sm">Din rapport kommer att visas här när du börjar processen</p>
          </div>
        </div>
      );
    }

    // Show preview content if we have data, regardless of currentStep
    if (!rrData.length && !brData.length) {
      return (
        <div className="text-center py-20">
          <div className="text-muted-foreground mb-4">
            <div className="w-16 h-16 mx-auto mb-4 rounded-lg bg-muted flex items-center justify-center">
              ⏳
            </div>
            <h3 className="text-lg font-medium mb-2">Laddar data...</h3>
            <p className="text-sm">Bearbetar SE-fil data</p>
          </div>
        </div>
      );
    }

    // Use structured data from Python if available
    const headerData = companyInfo || {
      organization_number: companyData.organizationNumber || 'XXX XXX-XXXX',
      fiscal_year: companyData.fiscalYear || new Date().getFullYear(),
      company_name: 'Företag AB',
      location: companyData.location || 'Stockholm',
      date: companyData.date || new Date().toLocaleDateString('sv-SE')
    };

    return (
      <div className="space-y-6">
        {/* Company Header */}
        <div className="border-b pb-4">
          <h1 className="text-2xl font-bold text-foreground">Årsredovisning</h1>
          <h2 className="text-xl font-semibold text-foreground mt-2">{headerData.company_name}</h2>
          <p className="text-sm text-muted-foreground">
            Organisationsnummer: {headerData.organization_number || 'Ej tillgängligt'}
          </p>
          <p className="text-sm text-muted-foreground">
            Räkenskapsår: {headerData.fiscal_year}
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            {[headerData.location, headerData.date].filter(Boolean).join(', ')}
          </p>
        </div>

        {/* Financial Results Section */}
        {(
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Resultaträkning</h2>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-muted-foreground">Visa alla rader</span>
                <Switch
                  checked={showAllRR}
                  onCheckedChange={setShowAllRR}
                  className={`${showAllRR ? 'bg-green-500' : 'bg-gray-300'}`}
                />
              </div>
            </div>
            
            {/* Column Headers */}
            <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '4fr 0.5fr 1fr 1fr'}}>
              <span></span>
              <span className="text-right">Not</span>
              <span className="text-right">{headerData.fiscal_year}</span>
              <span className="text-right">{headerData.fiscal_year - 1}</span>
            </div>

            {/* Income Statement Rows */}
            {rrData.length > 0 ? (
              rrData.map((item, index) => {
                if (!shouldShowRow(item, showAllRR, rrData)) {
                  return null;
                }
                
                return (
                  <div 
                    key={index} 
                    className={`${getStyleClasses(item.style).className} ${
                      item.level === 0 ? 'border-b pb-1' : ''
                    }`}
                    style={getStyleClasses(item.style).style}
                  >
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="text-right font-medium">
                      {getNoteValue(item.label)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmountDisplay(item.current_amount)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmountDisplay(item.previous_amount)}
                    </span>
                  </div>
                );
              })
            ) : (
              <div className="text-sm text-muted-foreground">
                <span className="text-xs text-muted-foreground">SE-fil</span>
                <span>Data från uppladdad SE-fil</span>
              </div>
            )}
          </div>
        )}

        {/* Balance Sheet Section */}
        {(
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Balansräkning</h2>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-muted-foreground">Visa alla rader</span>
                <Switch
                  checked={showAllBR}
                  onCheckedChange={setShowAllBR}
                  className={`${showAllBR ? 'bg-green-500' : 'bg-gray-300'}`}
                />
              </div>
            </div>
            
            {/* Column Headers */}
            <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '4fr 0.5fr 1fr 1fr'}}>
              <span></span>
              <span className="text-right">Not</span>
              <span className="text-right">{headerData.fiscal_year}</span>
              <span className="text-right">{headerData.fiscal_year - 1}</span>
            </div>

            {/* Balance Sheet Rows */}
            {brData.length > 0 ? (
              brData.map((item, index) => {
                if (!shouldShowRow(item, showAllBR, brData)) {
                  return null;
                }
                
                return (
                  <div 
                    key={index} 
                    className={`${getStyleClasses(item.style).className} ${
                      item.level === 0 ? 'border-b pb-1' : ''
                    }`}
                    style={getStyleClasses(item.style).style}
                  >
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="text-right font-medium">
                      {getNoteValue(item.label)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmountDisplay(item.current_amount)}
                    </span>
                    <span className="text-right font-medium">
                      {formatAmountDisplay(item.previous_amount)}
                    </span>
                  </div>
                );
              })
            ) : (
              <div className="text-sm text-muted-foreground">
                <span className="text-xs text-muted-foreground">SE-fil</span>
                <span>Data från uppladdad SE-fil</span>
              </div>
            )}
          </div>
        )}

        {/* Tax Calculation Section */}
        {companyData.showTaxPreview && ink2Data && ink2Data.length > 0 && (
          <div className="space-y-4 bg-gradient-to-r from-yellow-50 to-amber-50 p-4 rounded-lg border border-yellow-200" data-section="tax-calculation">
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-foreground border-b pb-2">Skatteberäkning</h2>
              <p className="text-sm leading-relaxed font-normal font-sans text-foreground mt-3">
                Här nedan visas endast de vanligaste skattemässiga justeringarna. Belopp har automatiskt hämtats från bokföringen, men det går bra att justera dem manuellt här. Fullständiga justeringar är möjliga att göra i INK2S-blanketten innan inlämning.
              </p>
            </div>
            
            {/* Column Headers */}
            <div className="grid gap-4 text-sm text-muted-foreground border-b pb-1 font-semibold" style={{gridTemplateColumns: '3fr 1fr'}}>
              <span></span>
              <span className="text-right">{headerData.fiscal_year}</span>
            </div>

            {/* Tax Calculation Rows */}
            {(() => {
              const allData = recalculatedData.length > 0 ? recalculatedData : ink2Data;
              
              // Find INK_sarskild_loneskatt row for conditional logic
              const sarskildRow = allData.find((item: any) => item.variable_name === 'INK_sarskild_loneskatt');
              
              // Helper function to check if any row in a block should be shown
              const shouldShowBlockContent = (blockName: string): boolean => {
                if (!blockName) return true; // Items without block are always evaluated individually
                
                return allData.some((item: any) => {
                  if (item.block !== blockName || item.header === true) return false; // Skip headers and other blocks
                  
                  // Check individual row visibility rules
                  if (item.show_amount === 'NEVER') return false;
                  
                  // Handle always_show with new boolean/null logic
                  if (item.always_show === true) return true;
                  if (item.always_show === false) return false;
                  
                  // For always_show = null/undefined, show only if amount is non-zero
                  return item.amount !== null && item.amount !== undefined && 
                         item.amount !== 0 && item.amount !== -0;
                });
              };
              
              return allData.filter((item: any) => {
                // Always exclude rows explicitly marked to never show
                if (item.show_amount === 'NEVER') return false;

                // In manual edit mode, use the same filtering rules as non-edit mode
                if (isEditing) {
                  // Always exclude rows explicitly marked to never show
                  if (item.always_show === false) return false;
                  
                  if (item.header === true) {
                    return shouldShowBlockContent(item.block);
                  }
                  
                  // Same logic as non-edit mode: show if always_show=true OR (always_show=null AND amount≠0)
                  if (item.always_show === true) return true;
                  
                  // For always_show = null/undefined, only show if amount is non-zero
                  const hasNonZeroAmount = item.amount !== null && item.amount !== undefined && 
                                         item.amount !== 0 && item.amount !== -0;
                  return hasNonZeroAmount;
                }

                // Normal (read-only) mode filter logic
                // Check always_show rules first
                if (item.always_show === true) return true;
                if (item.always_show === false) return false;

                if (item.header === true) {
                  return shouldShowBlockContent(item.block);
                }

                // For non-headers with always_show = null/undefined, show only if amount is non-zero
                const hasNonZeroAmount = item.amount !== null && item.amount !== undefined && 
                                       item.amount !== 0 && item.amount !== -0;
                
                // Row filtering logic applied
                
                return hasNonZeroAmount;
              });
            })().map((item, index) => (
              <div
                key={index}
                className={getInkStyleClasses(item.style).className}
                style={getInkStyleClasses(item.style).style}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-muted-foreground">{item.row_title}</span>
                    {item.explainer && item.explainer.trim() && (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button className="w-4 h-4 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center hover:bg-blue-600 transition-colors">
                              i
                            </button>
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            <p className="text-xs font-normal">{item.explainer}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                  </div>
                  {item.show_tag && item.account_details && item.account_details.length > 0 && (
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button variant="outline" size="sm" className="ml-2 h-5 px-2 text-xs">
                          SHOW
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[500px] p-4 bg-white border shadow-lg">
                        <div className="space-y-3">
                          <h4 className="font-medium text-sm">Detaljer för {item.row_title}</h4>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b">
                                  <th className="text-left py-2">Konto</th>
                                  <th className="text-left py-2"></th>
                                  <th className="text-right py-2">{seFileData?.company_info?.fiscal_year || 'Belopp'}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {item.account_details.map((detail, detailIndex) => (
                                  <tr key={detailIndex} className="border-b">
                                    <td className="py-2">{detail.account_id}</td>
                                    <td className="py-2">{detail.account_text}</td>
                                    <td className="text-right py-2">
                                      {new Intl.NumberFormat('sv-SE', {
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0
                                      }).format(detail.balance)} kr
                                    </td>
                                  </tr>
                                ))}
                                {/* Sum row */}
                                <tr className="border-t border-gray-300 font-semibold">
                                  <td className="py-2">Summa</td>
                                  <td className="py-2"></td>
                                  <td className="text-right py-2">
                                    {new Intl.NumberFormat('sv-SE', {
                                      minimumFractionDigits: 0,
                                      maximumFractionDigits: 0
                                    }).format(item.account_details.reduce((sum: number, detail: any) => sum + detail.balance, 0))} kr
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  )}
                  
                  {/* Custom SHOW button for INK_sarskild_loneskatt - only show if there's a discrepancy */}
                  {item.variable_name === 'INK_sarskild_loneskatt' && 
                   companyData.sarskildLoneskattPensionCalculated > companyData.sarskildLoneskattPension && (
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button variant="outline" size="sm" className="ml-2 h-5 px-2 text-xs">
                          SHOW
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-[500px] p-4 bg-white border shadow-lg">
                        <div className="space-y-3">
                          <h4 className="font-medium text-sm">{item.row_title}</h4>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b">
                                  <th className="text-left py-2">Konto</th>
                                  <th className="text-left py-2"></th>
                                  <th className="text-right py-2">{seFileData?.company_info?.fiscal_year || 'Belopp'}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {/* Account 7410 - Pension premier */}
                                <tr className="border-b">
                                  <td className="py-2">7410</td>
                                  <td className="py-2 text-left">Pensionspremier</td>
                                  <td className="text-right py-2">
                                    {(() => {
                                      const pensionPremier = companyData.pensionPremier || 0;
                                      const formatted = new Intl.NumberFormat('sv-SE', {
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0
                                      }).format(pensionPremier);
                                      return `${formatted} kr`;
                                    })()}
                                  </td>
                                </tr>
                                {/* Sum row with special calculation - merged columns */}
                                <tr className="border-t border-gray-300">
                                  <td className="py-2" colSpan={2}>
                                    Särskild löneskatt (24,26%)
                                  </td>
                                  <td className="text-right py-2">
                                    {(() => {
                                      const rate = companyData.sarskildLoneskattPensionCalculated || 0;
                                      const formatted = new Intl.NumberFormat('sv-SE', {
                                        minimumFractionDigits: 0,
                                        maximumFractionDigits: 0
                                      }).format(rate);
                                      return `${formatted} kr`;
                                    })()}
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  )}
                </div>
                 <span className="text-right font-medium">
                  {item.show_amount === 'NEVER' || item.header ? '' :
                    (isEditing && (!item.is_calculated || item.variable_name === 'INK_sarskild_loneskatt') && item.show_amount) ? (
                      (() => {
                        // Field is editable
                        return (
                          <input
                            type="number"
                            className="w-32 px-1 py-1 text-sm border border-gray-400 rounded text-right font-medium h-7 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                            value={
                              item.variable_name === 'INK_sarskild_loneskatt' 
                                ? Math.abs(editedAmounts[item.variable_name] ?? item.amount ?? 0)
                                : (editedAmounts[item.variable_name] ?? item.amount ?? 0)
                            }
                            onChange={(e) => {
                              // Only allow positive values for manual editing
                              const rawValue = Math.abs(parseFloat(e.target.value)) || 0;
                              const value = item.variable_name === 'INK_sarskild_loneskatt' ? -rawValue : rawValue;
                              setEditedAmounts(prev => ({
                                ...prev,
                                [item.variable_name]: value
                              }));
                            }}
                            onBlur={(e) => {
                              const rawValue = parseFloat(e.target.value) || 0;
                              // Force positive values only
                              const correctedValue = Math.abs(rawValue);
                              const finalValue = item.variable_name === 'INK_sarskild_loneskatt' ? -correctedValue : correctedValue;
                              const updatedAmounts = { ...editedAmounts, [item.variable_name]: finalValue };
                              setEditedAmounts(updatedAmounts);
                              recalculateValues(updatedAmounts);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                const rawValue = parseFloat(e.currentTarget.value) || 0;
                                // Force positive values only
                                const correctedValue = Math.abs(rawValue);
                                const finalValue = item.variable_name === 'INK_sarskild_loneskatt' ? -correctedValue : correctedValue;
                                const updatedAmounts = { ...editedAmounts, [item.variable_name]: finalValue };
                                setEditedAmounts(updatedAmounts);
                                recalculateValues(updatedAmounts);
                                e.currentTarget.blur(); // Remove focus
                              }
                            }}
                            step="0.01"
                            min="0"
                          />
                        );
                      })()
                    ) : (
                      (() => {
                        // Field not editable
                        return (
                        (item.amount !== null && item.amount !== undefined) ? 
                        (item.amount === 0 || item.amount === -0 ? '0 kr' : (() => {
                        // Tax calculation should always show integers with Swedish formatting and kr suffix
                        return new Intl.NumberFormat('sv-SE', {
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0
                        }).format(item.amount) + ' kr';
                        })()) : '0 kr'
                        );
                      })()
                    )
                  }
                </span>
              </div>
            ))}
            
            {/* Tax Action Buttons */}
            {isEditing && (
              <div className="pt-4 border-t border-gray-200 flex justify-between">
                {/* Undo Button - Left */}
                <Button 
                  onClick={handleUndo}
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"/>
                  </svg>
                  Ångra ändringar
                </Button>
                
                {/* Update Button - Right */}
                <Button 
                  onClick={() => {
                    // Handle tax update - this would typically update the chat state
                    console.log('Updated amounts:', editedAmounts);
                  }}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 flex items-center gap-2"
                >
                  Godkänn och uppdatera skatt
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"/>
                  </svg>
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Periodiseringsfonder Section */}
        <Periodiseringsfonder 
          companyData={companyData}
          onDataUpdate={onDataUpdate}
        />

        {/* Noter Section */}
        {companyData.noterData && companyData.noterData.length > 0 && (
          <Noter 
            noterData={companyData.noterData}
            fiscalYear={companyData.fiscalYear}
            previousYear={companyData.fiscalYear ? companyData.fiscalYear - 1 : undefined}
          />
        )}

        {/* Significant Events Section */}
        {currentStep >= 2 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground border-b pb-2">Väsentliga händelser</h2>
            <div className="text-sm text-muted-foreground space-y-2">
              {seFileData?.significant_events ? (
                seFileData.significant_events.map((event, index) => (
                  <p key={index}>• {event}</p>
                ))
              ) : (
                <p>{companyData.significantEvents || "Inga väsentliga händelser att rapportera."}</p>
              )}
            </div>
          </div>
        )}

        {/* Depreciation Policy */}
        {currentStep >= 3 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground border-b pb-2">Avskrivningsprinciper</h2>
            <p className="text-sm text-muted-foreground">
              {seFileData?.depreciation_policy || 
               (companyData.depreciation === "samma" 
                 ? "Samma avskrivningstider som föregående år tillämpas."
                 : "Förändrade avskrivningstider tillämpas detta år."
               )
              }
            </p>
          </div>
        )}

        {/* Employee Information */}
        {currentStep >= 4 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground border-b pb-2">Personal</h2>
            <p className="text-sm text-muted-foreground">
              {seFileData?.employees?.description || 
               `Antal anställda under räkenskapsåret: ${seFileData?.employees?.count || companyData.employees}`
              }
            </p>
          </div>
        )}

        {/* Board Members */}
        {currentStep >= 5 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground border-b pb-2">Styrelse</h2>
            <div className="space-y-2">
              {seFileData?.board_members ? (
                seFileData.board_members.map((member, index) => (
                  <div key={index} className="text-sm">
                    <span className="font-medium">{member.name}</span>
                    <span className="text-muted-foreground ml-2">({member.role})</span>
                  </div>
                ))
              ) : (
                companyData.boardMembers.map((member, index) => (
                  <div key={index} className="text-sm">
                    <span className="font-medium">{member.name}</span>
                    <span className="text-muted-foreground ml-2">({member.personalNumber})</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col">
      <Card className="flex-1 p-6 bg-card border-border">
        <div className="overflow-y-auto max-h-full">
          {getPreviewContent()}
          {/* Extra padding to ensure last row is visible */}
          <div className="h-20"></div>
        </div>
      </Card>
    </div>
  );
}
