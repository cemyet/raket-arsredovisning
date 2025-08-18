import { useState } from "react";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { AnnualReportPreview } from "./AnnualReportPreview";
import DatabaseDrivenChat from "./DatabaseDrivenChat";

interface CompanyData {
  result: number | null;
  results?: string; // For extracted results from SE file
  dividend: string;
  customDividend?: number;
  significantEvents: string;
  hasEvents: boolean;
  depreciation: string;
  employees: number;
  location: string;
  date: string;
  boardMembers: Array<{ name: string; personalNumber: string }>;
  seFileData?: any; // Store processed SE file data
  organizationNumber?: string; // From SE file
  fiscalYear?: number; // From SE file
  companyName?: string; // From SE file
  sumAretsResultat?: number; // From SE file RR data
  sumFrittEgetKapital?: number; // From SE file RR data
  taxApproved: boolean; // New field for tax approval
  skattAretsResultat: number | null; // New field for tax amount
  ink2Data?: any[]; // INK2 tax calculation data
  inkBeraknadSkatt?: number | null; // Calculated tax amount
  inkBokfordSkatt?: number | null; // Booked tax amount
  noterData?: any[]; // Noter data
  taxChoice?: string; // Tax choice: 'calculated', 'manual', 'booked'
  editableAmounts?: boolean; // Whether amounts are editable
  // Preview and editing control flags
  showTaxPreview?: boolean; // Controls tax preview visibility
  showRRBR?: boolean; // Controls RR/BR data visibility
  taxEditingEnabled?: boolean; // Controls tax editing mode
  // Pension tax variables
  pensionPremier?: number | null;
  sarskildLoneskattPension?: number | null;
  sarskildLoneskattPensionCalculated?: number | null;
  justeringSarskildLoneskatt?: number | null;
  sarskildLoneskattPensionSubmitted?: number | null;
  // Unused tax loss variables
  unusedTaxLossAmount?: number | null;
}

export function AnnualReportChat() {
  const [companyData, setCompanyData] = useState<CompanyData>({
    result: null,
    dividend: "",
    significantEvents: "",
    hasEvents: false,
    depreciation: "samma",
    employees: 2,
    location: "Stockholm",
    date: new Date().toLocaleDateString("sv-SE"),
    boardMembers: [
      { name: "Anna Andersson", personalNumber: "851201-1234" }
    ],
    taxApproved: false,
    skattAretsResultat: null
  });

  return (
    <div className="h-screen w-full bg-background overflow-hidden">
      <ResizablePanelGroup direction="horizontal" className="h-full">
        {/* Chat Panel */}
        <ResizablePanel defaultSize={30} minSize={20} maxSize={50}>
          <div className="relative h-full">
            {/* Sticky Header */}
            <div className="sticky top-0 z-10 px-6 py-4 border-b border-border bg-background">
              <div className="flex items-center justify-between h-8">
                <div className="flex items-center">
                  <img 
                    src="/raketrapport v3 (logo).png"
                    alt="RaketRapport" 
                    className="h-8 w-auto"
                  />
                </div>
              </div>
            </div>

            {/* Database-Driven Chat */}
            <DatabaseDrivenChat 
              companyData={companyData}
              onDataUpdate={(updates) => {
                console.log('🔄 PARENT: onDataUpdate called with:', updates);
                console.log('🔄 PARENT: Current companyData before update:', companyData);
                setCompanyData(prev => {
                  const newData = { ...prev, ...updates };
                  console.log('🔄 PARENT: Merged companyData after update:', newData);
                  console.log('🔄 PARENT: showTaxPreview =', newData.showTaxPreview, 'showRRBR =', newData.showRRBR);
                  return newData;
                });
              }}
            />
          </div>
        </ResizablePanel>

        <ResizableHandle />

        {/* Annual Report Preview Panel */}
        <ResizablePanel defaultSize={70} minSize={50}>
          <div className="relative h-full">
            <div className="sticky top-0 z-10 px-6 py-4 border-b border-border bg-background">
              <div className="h-8 flex flex-col justify-center">
                {companyData.companyName ? (
                  <>
                    <h2 className="text-base font-medium text-foreground">{companyData.companyName}</h2>
                    <p className="text-xs text-muted-foreground">Årsredovisning {companyData.fiscalYear}</p>
                  </>
                ) : (
                  <>
                    <h2 className="text-base font-medium text-foreground">Förhandsvisning</h2>
                    <p className="text-xs text-muted-foreground">Din årsredovisning uppdateras live</p>
                  </>
                )}
              </div>
            </div>
            <div className="p-6 h-full overflow-auto pt-5">
              {console.log('🔍 PARENT: About to render AnnualReportPreview with companyData:', companyData)}
              {console.log('🔍 PARENT: Flags - showTaxPreview:', companyData.showTaxPreview, 'showRRBR:', companyData.showRRBR, 'taxEditingEnabled:', companyData.taxEditingEnabled)}
              <AnnualReportPreview 
                companyData={companyData}
                currentStep={0} 
                editableAmounts={false}
                onDataUpdate={(updates) => {
                  console.log('🔄 PREVIEW: onDataUpdate called with:', updates);
                  setCompanyData(prev => {
                    const newData = { ...prev, ...updates };
                    console.log('🔄 PREVIEW: merged state:', newData);
                    return newData;
                  });
                }}
              />
              {console.log('🔍 PARENT: Finished rendering AnnualReportPreview')}
            </div>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
