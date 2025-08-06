import { useState } from "react";
import { ChatMessage } from "./ChatMessage";
import { ProgressIndicator } from "./ProgressIndicator";
import { OptionButton } from "./OptionButton";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { AnnualReportPreview } from "./AnnualReportPreview";
import { FileUpload } from "./FileUpload";
import { useToast } from "@/hooks/use-toast";
import { Plus, Upload, TestTube } from "lucide-react";
import { apiService } from "@/services/api";

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
  sumAretsResultat?: number; // From SE file RR data
  sumFrittEgetKapital?: number; // From SE file RR data
}

const TOTAL_STEPS = 5;

export function AnnualReportChat() {
  const { toast } = useToast();
  const [currentStep, setCurrentStep] = useState(-1); // Start at -1 for SE file upload
  const [showInput, setShowInput] = useState(false);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [inputValue, setInputValue] = useState("");
  
  // Format number input with thousand separators
  const formatNumberInput = (value: string) => {
    // Remove all non-digits
    const numbers = value.replace(/\D/g, '');
    if (numbers === '') return '';
    
    // Format with Swedish thousand separators
    return parseInt(numbers).toLocaleString('sv-SE');
  };

  const [messages, setMessages] = useState([
    {
      text: "Hej! 👋 Välkommen till RaketRapport! Jag hjälper dig att skapa din årsredovisning på bara 5 minuter.",
      isBot: true,
      emoji: "🚀"
    },
    {
      text: "Ladda upp din .SE fil från bokföringsprogrammet för att automatiskt skapa din årsredovisning:",
      isBot: true,
      emoji: "📁"
    }
  ]);

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
    ]
  });

  // Debug logging - after all state declarations


  const addMessage = (text: string, isBot = true, emoji?: string) => {
    setMessages(prev => [...prev, { text, isBot, emoji }]);
  };

  const handleResultInput = () => {
    const result = parseFloat(inputValue);
    if (isNaN(result)) return;
    
    setCompanyData(prev => ({ ...prev, result }));
    addMessage(inputValue + " kr", false);
    
    if (result > 0) {
      addMessage("Stort grattis till vinsten! 🎉 Det är fantastiskt!", true, "🎉");
      setTimeout(() => {
        addMessage("Vill ni göra någon utdelning av vinsten?", true, "💰");
        setCurrentStep(0.5);
      }, 1000);
    } else {
      addMessage("Tack för informationen. Inga utdelningar att hantera då.", true);
      setTimeout(() => {
        setCurrentStep(1);
        addMessage("Har något särskilt hänt i verksamheten under året?", true, "📋");
      }, 1000);
    }
    
    setShowInput(false);
    setInputValue("");
  };

  const handleCustomDividendInput = () => {
    // Parse the formatted input by removing thousand separators
    const amount = parseFloat(inputValue.replace(/\s/g, '').replace(/\u00A0/g, '')); // Remove spaces and non-breaking spaces
    if (isNaN(amount) || amount < 0) return;
    
    setCompanyData(prev => ({ ...prev, customDividend: amount }));
    addMessage(`${inputValue} kr`, false);
    
    setTimeout(() => {
      setCurrentStep(1);
      addMessage("Perfekt! Nu går vi vidare. Har något särskilt hänt i verksamheten under året?", true, "📋");
    }, 1000);
    
    setShowInput(false);
    setInputValue("");
  };

  const handleDividend = (type: string) => {
    setCompanyData(prev => ({ ...prev, dividend: type }));
    addMessage(type === "0" ? "0 kr utdelning" : type, false);
    
    setTimeout(() => {
      setCurrentStep(1);
      addMessage("Perfekt! Nu går vi vidare. Har något särskilt hänt i verksamheten under året?", true, "📋");
    }, 1000);
  };

  const handleEvents = (hasEvents: boolean) => {
    setCompanyData(prev => ({ ...prev, hasEvents }));
    addMessage(hasEvents ? "Ja, det har hänt saker" : "Nej, inget särskilt", false);
    
    if (hasEvents) {
      setTimeout(() => {
        addMessage("Berätta gärna kort vad som hänt! (t.ex. 'ny lokal', 'anställt ny VD')", true, "✏️");
        setShowInput(true);
      }, 1000);
    } else {
      setCompanyData(prev => ({ ...prev, significantEvents: "Inga väsentliga händelser under året har rapporterats." }));
      setTimeout(() => {
        setCurrentStep(2);
        addMessage("Okej! Nu till avskrivningstider. Vill du använda samma som förra året? (Inventarier 5 år, Bilar 10 år)", true, "🔧");
      }, 1000);
    }
  };

  const handleEventsText = () => {
    setCompanyData(prev => ({ ...prev, significantEvents: inputValue }));
    addMessage(inputValue, false);
    
    setTimeout(() => {
      setCurrentStep(2);
      addMessage("Perfekt! Nu till avskrivningstider. Vill du använda samma som förra året?", true, "🔧");
      setShowInput(false);
      setInputValue("");
    }, 1000);
  };

  const handleDepreciation = (keep: boolean) => {
    setCompanyData(prev => ({ ...prev, depreciation: keep ? "samma" : "ändra" }));
    addMessage(keep ? "Ja, samma som förra året" : "Nej, jag vill ändra", false);
    
    setTimeout(() => {
      setCurrentStep(3);
      addMessage("Bra! Hur många har varit anställda i år? Förra året var det 2 personer.", true, "👥");
    }, 1000);
  };

  const adjustEmployees = (change: number) => {
    const newCount = Math.max(0, companyData.employees + change);
    setCompanyData(prev => ({ ...prev, employees: newCount }));
  };

  const confirmEmployees = () => {
    addMessage(`${companyData.employees} anställda`, false);
    
    setTimeout(() => {
      setCurrentStep(4);
      addMessage("Slutligen, stämmer ort, datum och styrelseuppgifter?", true, "📍");
    }, 1000);
  };

  const confirmFinalDetails = () => {
    addMessage("Ja, allt stämmer", false);
    
    setTimeout(() => {
      setCurrentStep(5);
      addMessage("Fantastiskt! 🎉 Alla uppgifter är insamlade. Nu kan vi generera din årsredovisning!", true, "🎯");
    }, 1000);
  };

  const generatePDF = () => {
    addMessage("Generera PDF", false);
    addMessage("Perfekt! Din årsredovisning genereras nu... 📄⚡", true, "⚡");
    // Här skulle vi skicka till backend för PDF-generering
  };

  const convertNewParserFormat = (data: any) => {
    // Convert new parser format to old format for frontend compatibility
    const converted = {
      ...data,
      data: {
        ...data,
        // Convert RR data from current_amount/previous_amount to amount
        rr_data: data.rr_sample?.map((item: any) => ({
          ...item,
          amount: item.current_amount || item.amount,
          previous_amount: item.previous_amount
        })) || [],
        // Convert BR data from current_amount/previous_amount to amount
        br_data: data.br_sample?.map((item: any) => ({
          ...item,
          amount: item.current_amount || item.amount,
          previous_amount: item.previous_amount
        })) || [],
        // Convert account balances
        accountBalances: data.current_accounts_sample || {},
        previousAccountBalances: data.previous_accounts_sample || {},
        // Add company info
        company_info: data.company_info || {},
        current_accounts_count: data.current_accounts_count || 0,
        previous_accounts_count: data.previous_accounts_count || 0
      }
    };
    
    
    return converted;
  };

  /* REMOVED: testParser function - no longer needed since normal upload works perfectly
  const testParser = async (file: File) => {
    try {
      addMessage("🧪 Testar ny databas-driven parser...", true, "🔬");
      
      // REMOVED: testParser API call
      
      addMessage(`✅ Parser test lyckades!`, true, "✅");
      addMessage(`📊 Hittade ${result.current_accounts_count} konton`, true, "📊");
      addMessage(`📈 ${result.rr_count} RR-poster, ${result.br_count} BR-poster`, true, "📈");
      

      
      // Convert new format to old format and store for preview
      const convertedData = convertNewParserFormat(result);
      
      
      setCompanyData(prev => ({ 
        ...prev, 
        seFileData: convertedData.data
      }));
      
    } catch (error) {
      console.error('Parser test failed:', error);
      addMessage(`❌ Parser test misslyckades: ${error instanceof Error ? error.message : 'Okänt fel'}`, true, "❌");
      toast({
        title: "Parser Test Failed",
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: "destructive",
      });
    }
  }; */

  const handleFileProcessed = (data: any) => {

    
    // Handle new database-driven parser format
    let extractedResults = null;
    let sumAretsResultat = null;
    let sumFrittEgetKapital = null;
    
    // Try to extract net result from RR data
    if (data.data?.rr_data) {
      const netResultItem = data.data.rr_data.find((item: any) => 
        item.id === 'ÅR' || item.label?.toLowerCase().includes('årets resultat')
      );
      if (netResultItem && netResultItem.current_amount !== null) {
        extractedResults = Math.abs(netResultItem.current_amount).toString();
      }
      
      // Extract SumAretsResultat for chat options
      const sumAretsResultatItem = data.data.rr_data.find((item: any) => 
        item.variable_name === 'SumAretsResultat' ||
        item.label?.toLowerCase().includes('årets resultat') ||
        item.label?.toLowerCase().includes('sumaretsresultat')
      );
      if (sumAretsResultatItem && sumAretsResultatItem.current_amount !== null) {
        sumAretsResultat = Math.abs(sumAretsResultatItem.current_amount);
      }
      
      // Extract SumFrittEgetKapital for chat options
      const sumFrittEgetKapitalItem = data.data.rr_data.find((item: any) => 
        item.variable_name === 'SumFrittEgetKapital' ||
        item.label?.toLowerCase().includes('sumfrittegetkapital') ||
        item.label?.toLowerCase().includes('fritt eget kapital')
      );
      if (sumFrittEgetKapitalItem && sumFrittEgetKapitalItem.current_amount !== null) {
        sumFrittEgetKapital = Math.abs(sumFrittEgetKapitalItem.current_amount);
      }
    }
    
    // Fallback to legacy extraction if needed
    if (!extractedResults && data.data?.accountBalances) {
      const resultAccounts = ['8999', '8910'];
      for (const account of resultAccounts) {
        if (data.data.accountBalances[account]) {
          extractedResults = Math.abs(data.data.accountBalances[account]).toString();
          break;
        }
      }
    }
    
    // Store the complete structured data including calculated values
    setCompanyData(prev => ({ 
      ...prev, 
      seFileData: data.data,
      results: extractedResults || prev.results,
      sumAretsResultat: sumAretsResultat,
      sumFrittEgetKapital: sumFrittEgetKapital,
      organizationNumber: data.data?.company_info?.organization_number || data.data?.organization_number || prev.organizationNumber,
      fiscalYear: data.data?.company_info?.fiscal_year || data.data?.fiscal_year || prev.fiscalYear,
      location: data.data?.company_info?.location || prev.location,
      date: data.data?.company_info?.date || data.data?.end_date || prev.date
    }));

    setTimeout(() => {
      addMessage("Perfekt! 🎉 Komplett årsredovisning skapad från SE-filen.", true, "✅");
      setTimeout(() => {
        if (extractedResults || sumAretsResultat) {
          const displayAmount = sumAretsResultat ? Math.round(sumAretsResultat).toLocaleString('sv-SE') : extractedResults;
          addMessage(`Årets resultat: ${displayAmount} kr. Se fullständig rapport till höger!`, true, "💰");
          setTimeout(() => {
            addMessage("Vill ni göra någon utdelning av vinsten?", true, "💰");
            setCurrentStep(0.5);
          }, 1500);
        } else {
          addMessage("Jag kunde inte hitta årets resultat automatiskt i filen. Låt mig fråga dig om det.", true, "🤖");
          setTimeout(() => {
            addMessage("Vad blev årets resultat?", true, "💰");
            setCurrentStep(0);
            setShowInput(true);
          }, 1000);
        }
      }, 1000);
    }, 1000);

    setShowFileUpload(false);
  };


  const handleUseFileUpload = () => {

    addMessage("Ja, jag har en SE-fil", false);
    setTimeout(() => {
      addMessage("Bra! Ladda upp din .SE fil så analyserar jag den åt dig. 📁", true, "📤");
  
      setShowFileUpload(true);
    }, 1000);
  };

  const startProcess = () => {
    addMessage("Låt oss börja!", false);
    setTimeout(() => {
      addMessage("Underbart! Första frågan: Vad blev årets resultat?", true, "💰");
      setShowInput(true);
    }, 1000);
  };

  return (
    <div className="h-screen bg-background font-sans">
      <ResizablePanelGroup direction="horizontal" className="h-full">
        {/* Chat Panel */}
        <ResizablePanel defaultSize={30} minSize={25}>
          <div className="h-full flex flex-col">
            {/* Clean Header */}
            <div className="px-6 py-4 border-b border-border">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-base font-medium text-foreground">RaketRapport</h1>
                  <p className="text-xs text-muted-foreground">Årsredovisning på 5 minuter</p>
                </div>
                {currentStep > 0 && (
                  <div className="text-xs text-muted-foreground">
                    {currentStep}/{TOTAL_STEPS}
                  </div>
                )}
              </div>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-auto">
              <div className="px-6 py-6 space-y-1">
                {messages.map((message, index) => (
                  <ChatMessage
                    key={index}
                    message={message.text}
                    isBot={message.isBot}
                    emoji={message.emoji}
                  />
                ))}
              </div>
            </div>

            {/* Clean Input Area */}
            <div className="px-6 py-4">
              {/* Text input area with arrow button */}
              {(showInput && (currentStep < 1 || currentStep === 1 || currentStep === 0.5)) && (
                <div className="flex items-end gap-3">
                  {currentStep < 1 ? (
                    <Input
                      type="number"
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      placeholder="Ange belopp i kr..."
                      className="flex-1 border-none bg-transparent text-base focus-visible:ring-0 focus-visible:ring-offset-0 px-0"
                    />
                  ) : currentStep === 0.5 ? (
                    <Input
                      type="text"
                      value={inputValue}
                      onChange={(e) => {
                        const formatted = formatNumberInput(e.target.value);
                        setInputValue(formatted);
                      }}
                      placeholder="Ange utdelningsbelopp i kr..."
                      className="flex-1 border-none bg-transparent text-base focus-visible:ring-0 focus-visible:ring-offset-0 px-0"
                    />
                  ) : (
                    <Textarea
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      placeholder="Beskriv kort vad som hänt..."
                      className="flex-1 border-none bg-transparent text-base resize-none min-h-[40px] focus-visible:ring-0 focus-visible:ring-offset-0 px-0"
                    />
                  )}
                  <Button
                    onClick={currentStep < 1 ? handleResultInput : currentStep === 0.5 ? handleCustomDividendInput : handleEventsText}
                    className="w-7 h-7 rounded-full bg-foreground hover:bg-foreground/90 p-0 flex-shrink-0"
                  >
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                      className="text-background"
                    >
                      <path
                        d="M12 19V5M5 12L12 5L19 12"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </Button>
                </div>
              )}

              {/* File Upload - Only show at start before any data processing */}
              {currentStep === -1 && !companyData.seFileData && (
                <div className="space-y-3">
                  <FileUpload 
                    onFileProcessed={handleFileProcessed} 
                  />
                </div>
              )}

              {/* Option buttons for non-input steps */}
              {currentStep === 0 && !showInput && (
                <div className="space-y-3">
                  <OptionButton onClick={startProcess}>
                    Låt oss börja!
                  </OptionButton>
                </div>
              )}

              {currentStep === 0.5 && (
                <div className="space-y-3">
                  <OptionButton onClick={() => handleDividend("0")}>
                    0 kr
                  </OptionButton>
                  <OptionButton onClick={() => handleDividend(`Hela årets vinst (${companyData.sumAretsResultat ? Math.round(companyData.sumAretsResultat).toLocaleString('sv-SE') : 0} kr)`)}>
                    Hela årets vinst ({companyData.sumAretsResultat ? Math.round(companyData.sumAretsResultat).toLocaleString('sv-SE') : 0} kr)
                  </OptionButton>
                  <OptionButton onClick={() => handleDividend(`Allt utdelningsbart kapital (${companyData.sumFrittEgetKapital ? Math.round(companyData.sumFrittEgetKapital).toLocaleString('sv-SE') : 0} kr)`)}>
                    Allt utdelningsbart kapital ({companyData.sumFrittEgetKapital ? Math.round(companyData.sumFrittEgetKapital).toLocaleString('sv-SE') : 0} kr)
                  </OptionButton>
                  <OptionButton onClick={() => setShowInput(true)}>
                    Annat belopp
                  </OptionButton>
                </div>
              )}

              {currentStep === 1 && !showInput && (
                <div className="space-y-3">
                  <OptionButton onClick={() => handleEvents(true)}>
                    Ja, det har hänt saker
                  </OptionButton>
                  <OptionButton onClick={() => handleEvents(false)}>
                    Nej, inget särskilt
                  </OptionButton>
                </div>
              )}

              {currentStep === 2 && (
                <div className="space-y-3">
                  <OptionButton onClick={() => handleDepreciation(true)}>
                    Ja, samma som förra året
                  </OptionButton>
                  <OptionButton onClick={() => handleDepreciation(false)}>
                    Nej, jag vill ändra
                  </OptionButton>
                </div>
              )}

              {currentStep === 3 && (
                <div className="space-y-4">
                  <div className="flex items-center justify-center space-x-6 bg-muted rounded-xl p-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => adjustEmployees(-1)}
                      disabled={companyData.employees <= 0}
                    >
                      ➖
                    </Button>
                    <span className="text-2xl font-bold min-w-[3rem] text-center">
                      {companyData.employees}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => adjustEmployees(1)}
                    >
                      ➕
                    </Button>
                  </div>
                  <OptionButton onClick={confirmEmployees}>
                    Bekräfta antal anställda
                  </OptionButton>
                </div>
              )}

              {currentStep === 4 && (
                <div className="space-y-4">
                  <div className="bg-muted rounded-xl p-4 space-y-2 text-sm">
                    <div><strong>Ort:</strong> {companyData.location}</div>
                    <div><strong>Datum:</strong> {companyData.date}</div>
                    <div><strong>Styrelse:</strong></div>
                    {companyData.boardMembers.map((member, index) => (
                      <div key={index} className="ml-4">
                        {member.name} ({member.personalNumber})
                      </div>
                    ))}
                  </div>
                  <OptionButton onClick={confirmFinalDetails}>
                    Ja, allt stämmer
                  </OptionButton>
                </div>
              )}

              {currentStep === 5 && (
                <div className="space-y-3">
                  <OptionButton onClick={generatePDF}>
                    Generera PDF - Din årsredovisning är klar!
                  </OptionButton>
                </div>
              )}
            </div>
          </div>
        </ResizablePanel>

        <ResizableHandle withHandle />

        {/* Annual Report Preview Panel */}
        <ResizablePanel defaultSize={60} minSize={40}>
          <div className="h-full">
            <div className="px-6 py-4 border-b border-border">
              <h2 className="text-base font-medium text-foreground">Förhandsvisning</h2>
              <p className="text-xs text-muted-foreground">Din årsredovisning uppdateras live</p>
            </div>
            <div className="p-6 h-full overflow-auto">
              <AnnualReportPreview companyData={companyData} currentStep={currentStep} />
            </div>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
