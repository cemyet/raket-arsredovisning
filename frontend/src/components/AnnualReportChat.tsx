import { useState, useEffect, useRef } from "react";
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
import { TaxCalculation } from "./TaxCalculation";
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
  taxApproved: boolean; // New field for tax approval
  skattAretsResultat: number | null; // New field for tax amount
  ink2Data?: any[]; // INK2 tax calculation data
  inkBeraknadSkatt?: number | null; // Calculated tax amount
  inkBokfordSkatt?: number | null; // Booked tax amount
  taxChoice?: string; // Tax choice: 'calculated', 'manual', 'booked'
  editableAmounts?: boolean; // Whether amounts are editable
  // Pension tax variables
  pensionPremier?: number | null;
  sarskildLoneskattPension?: number | null;
  sarskildLoneskattPensionCalculated?: number | null;
  justeringSarskildLoneskatt?: number | null;
  sarskildLoneskattPensionSubmitted?: number | null;
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
  
  // Scroll ref for auto-scrolling
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

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
    taxApproved: false, // New field for tax approval
    skattAretsResultat: null, // New field for tax amount
    ink2Data: [], // INK2 tax calculation data
    inkBeraknadSkatt: null, // Calculated tax amount
    inkBokfordSkatt: null, // Booked tax amount
    taxChoice: '', // Tax choice
    editableAmounts: false, // Whether amounts are editable
    // Pension tax variables
    pensionPremier: null,
    sarskildLoneskattPension: null,
    sarskildLoneskattPensionCalculated: null,
    justeringSarskildLoneskatt: null,
    sarskildLoneskattPensionSubmitted: null
  });

  // Auto-scroll to tax section when step becomes 0.3
  useEffect(() => {
    if (currentStep === 0.3) {
      setTimeout(() => {
        const taxSection = document.querySelector('[data-section="tax-calculation"]');
        if (taxSection) {
          taxSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
    }
  }, [currentStep]);

  // Auto-scroll chat to bottom when messages change or when showing 3+ option buttons
  const scrollToBottom = () => {
    if (messagesEndRef.current && chatContainerRef.current) {
      const container = chatContainerRef.current;
      const messagesEnd = messagesEndRef.current;
      
      // Calculate if we need extra space for option buttons
      const optionButtons = container.querySelectorAll('[role="button"]');
      const hasMultipleOptions = optionButtons.length >= 3;
      
      // Scroll with extra offset if multiple options are shown
      const scrollOffset = hasMultipleOptions ? 200 : 50;
      
      container.scrollTo({
        top: messagesEnd.offsetTop - scrollOffset,
        behavior: 'smooth'
      });
    }
  };

  // Auto-scroll when messages change
  useEffect(() => {
    const timer = setTimeout(scrollToBottom, 100);
    return () => clearTimeout(timer);
  }, [messages, currentStep]);

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
        // Check if we have tax data from SE file (including 0)
        if (companyData.skattAretsResultat !== null) {
          const taxAmount = Math.round(companyData.skattAretsResultat).toLocaleString('sv-SE');
          addMessage(`Den bokförda skatten är ${taxAmount} kr. Vill du godkänna den eller vill du se över de skattemässiga justeringarna?`, true, "🏛️");
          setCurrentStep(0.25); // New step for tax confirmation
        } else {
          // No tax data found, go directly to dividends
          addMessage("Vill ni göra någon utdelning av vinsten?", true, "💰");
          setCurrentStep(0.5);
        }
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

  const handleTaxApproval = (approved: boolean) => {
    setCompanyData(prev => ({ ...prev, taxApproved: approved }));
    addMessage(approved ? "Ja, godkänn skatten" : "Nej, jag vill se över justeringarna", false);
    
    if (approved) {
      // If tax is approved, continue to dividends
      setTimeout(() => {
        addMessage("Perfekt! Vill ni göra någon utdelning av vinsten?", true, "💰");
        setCurrentStep(0.5);
      }, 1000);
    } else {
      // Show tax preview immediately by setting step to 0.3
      setCurrentStep(0.3); // Set step immediately to show tax preview
      setTimeout(() => {
        addMessage("Skatteberäkningen visas i förhandsvisningen till höger.", true, "");
        // First show the calculated tax amount
        setTimeout(() => {
          const beraknadSkatt = companyData.inkBeraknadSkatt ? Math.round(companyData.inkBeraknadSkatt).toLocaleString('sv-SE') : '0';
          addMessage(`Beräknad skatt efter skattemässiga justeringar är ${beraknadSkatt} kr.`, true, "⚖️");
          
          // Then check pension tax condition
          setTimeout(() => {
            checkPensionTax();
          }, 800);
        }, 800);
      }, 500);
    }
  };

  const checkPensionTax = () => {
    const pensionPremier = companyData.pensionPremier || 0;
    const sarskildLoneskattPension = companyData.sarskildLoneskattPension || 0;
    const sarskildLoneskattPensionCalculated = companyData.sarskildLoneskattPensionCalculated || 0;
    
    // Check if calculated > booked (meaning there's a discrepancy)
    if (sarskildLoneskattPensionCalculated > sarskildLoneskattPension) {
      // Show pension tax discrepancy message
      setTimeout(() => {
        const pensionPremierFormatted = Math.round(pensionPremier).toLocaleString('sv-SE');
        const calculatedFormatted = Math.round(sarskildLoneskattPensionCalculated).toLocaleString('sv-SE');
        const bookedFormatted = Math.round(sarskildLoneskattPension).toLocaleString('sv-SE');
        
        addMessage(`Innan vi fortsätter med skatteuträkningen vill jag göra dig uppmärksam på att särskild löneskatt på pensionförsäkringspremier inte verkar vara bokförd. Inbetalda pensionförsäkringspremier under året uppgår till ${pensionPremierFormatted} kr och den särskilda löneskatten borde uppgå till ${calculatedFormatted} kr men endast ${bookedFormatted} kr verkar vara bokfört. Vill du att vi justerar den särskilda löneskatten och därmed årets resultat enligt våra beräkningar?`, true, "⚠️");
        setCurrentStep(0.32); // New step for pension tax options
      }, 1000);
    } else {
      // No discrepancy, go directly to final tax question
      askFinalTaxQuestion();
    }
  };

  const askFinalTaxQuestion = () => {
    setTimeout(() => {
      const beraknadSkatt = companyData.inkBeraknadSkatt ? Math.round(companyData.inkBeraknadSkatt).toLocaleString('sv-SE') : '0';
      addMessage(`Beräknad skatt efter skattemässiga justeringar är ${beraknadSkatt} kr. Vill du godkänna denna skatt eller vill du göra manuella ändringar? Eller vill du hellre att vi godkänner och använder den bokförda skatten?`, true, "⚖️");
      setCurrentStep(0.35); // Step for tax choice
    }, 1000);
  };

  const handlePensionTaxChoice = (choice: string) => {
    const pensionPremier = companyData.pensionPremier || 0;
    const sarskildLoneskattPension = companyData.sarskildLoneskattPension || 0;
    const sarskildLoneskattPensionCalculated = companyData.sarskildLoneskattPensionCalculated || 0;
    
    if (choice === 'adjust') {
      // Option 1: Adjust to calculated amount
      const adjustment = sarskildLoneskattPensionCalculated - sarskildLoneskattPension;
      addMessage(`Justera särskild löneskatt till ${Math.round(sarskildLoneskattPensionCalculated).toLocaleString('sv-SE')} kr`, false);
      
      setCompanyData(prev => ({
        ...prev,
        justeringSarskildLoneskatt: adjustment
      }));
      
      // Trigger recalculation with pension tax adjustment
      triggerPensionTaxRecalculation(adjustment);
      
      setTimeout(() => {
        addMessage("Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkning till höger.", true, "✅");
        setTimeout(() => {
          askFinalTaxQuestion();
        }, 1000);
      }, 1000);
      
    } else if (choice === 'keep') {
      // Option 2: Keep current booked amount
      addMessage(`Behåll nuvarande bokförd särskild löneskatt ${Math.round(sarskildLoneskattPension).toLocaleString('sv-SE')} kr`, false);
      setTimeout(() => {
        askFinalTaxQuestion();
      }, 1000);
      
    } else if (choice === 'custom') {
      // Option 3: Enter custom amount
      addMessage("Ange belopp för eget särskild löneskatt", false);
      setTimeout(() => {
        addMessage("Vänligen ange önskat belopp för särskild löneskatt på pensionförsäkringspremier:", true, "💰");
        setCurrentStep(0.33); // Step for custom pension tax input
        setShowInput(true);
        setInputValue("");
      }, 1000);
    }
  };

  const handleCustomPensionTaxSubmit = () => {
    const amount = parseFloat(inputValue) || 0;
    const sarskildLoneskattPension = companyData.sarskildLoneskattPension || 0;
    const adjustment = amount - sarskildLoneskattPension;
    
    addMessage(`${amount.toLocaleString('sv-SE')} kr`, false);
    
    setCompanyData(prev => ({
      ...prev,
      sarskildLoneskattPensionSubmitted: amount,
      justeringSarskildLoneskatt: adjustment
    }));
    
    // Trigger recalculation with pension tax adjustment
    triggerPensionTaxRecalculation(adjustment);
    
    setTimeout(() => {
      addMessage("Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkning till höger.", true, "✅");
      setTimeout(() => {
        askFinalTaxQuestion();
      }, 1000);
    }, 1000);
    
    setShowInput(false);
    setInputValue("");
  };

  const triggerPensionTaxRecalculation = async (adjustment: number) => {
    console.log('🔥 triggerPensionTaxRecalculation called with adjustment:', adjustment);
    if (!companyData.seFileData) {
      console.log('❌ No seFileData available for recalculation');
      return;
    }
    
    try {
      const result = await apiService.recalculateInk2({
        current_accounts: companyData.seFileData.current_accounts || {},
        fiscal_year: companyData.fiscalYear,
        rr_data: companyData.seFileData.rr_data || [],
        br_data: companyData.seFileData.br_data || [],
        manual_amounts: {}, // No manual edits, just pension tax adjustment
        justering_sarskild_loneskatt: adjustment
      });
      
      if (result.success) {
        console.log('DEBUG: Pension tax recalculation successful');
        console.log('DEBUG: New ink2_data length:', result.ink2_data.length);
        
        // Check if INK_sarskild_loneskatt is in the response
        const sarskildRow = result.ink2_data.find((item: any) => item.variable_name === 'INK_sarskild_loneskatt');
        if (sarskildRow) {
          console.log('DEBUG: INK_sarskild_loneskatt in API response:', sarskildRow);
        } else {
          console.log('DEBUG: INK_sarskild_loneskatt NOT in API response');
          console.log('DEBUG: All variables in response:', result.ink2_data.map((item: any) => item.variable_name));
        }
        
        // Update company data with new INK2 data including the pension tax adjustment
        setCompanyData(prev => ({
          ...prev,
          ink2Data: result.ink2_data,
          // Update calculated tax amounts from the recalculated data
          inkBeraknadSkatt: result.ink2_data.find((item: any) => item.variable_name === 'INK_beraknad_skatt')?.amount || prev.inkBeraknadSkatt
        }));
      }
    } catch (error) {
      console.error('Failed to recalculate pension tax:', error);
    }
  };

  const handleTaxChoice = (choice: string) => {
    setCompanyData(prev => ({ 
      ...prev, 
      taxChoice: choice,
      editableAmounts: choice === 'manual'
    }));
    
    if (choice === 'calculated') {
      const amount = companyData.inkBeraknadSkatt ? Math.round(companyData.inkBeraknadSkatt).toLocaleString('sv-SE') : '0';
      addMessage(`Godkänn och använd beräknad skatt ${amount} kr`, false);
      setTimeout(() => {
        addMessage("Perfekt! Vill ni göra någon utdelning av vinsten?", true, "💰");
        setCurrentStep(0.5);
      }, 1000);
    } else if (choice === 'manual') {
      addMessage("Gör manuella ändringar i skattejusteringarna", false);
      setTimeout(() => {
        addMessage("Du kan nu redigera beloppen i förhandsvisningen. Klicka 'Godkänn och uppdatera skatt' när du är klar.", true, "✏️");
        // Stay on current step, amounts become editable
      }, 1000);
    } else if (choice === 'booked') {
      const amount = companyData.inkBokfordSkatt ? Math.round(companyData.inkBokfordSkatt).toLocaleString('sv-SE') : '0';
      addMessage(`Godkänn och använd bokförd skatt ${amount} kr`, false);
      setTimeout(() => {
        addMessage("Perfekt! Vill ni göra någon utdelning av vinsten?", true, "💰");
        setCurrentStep(0.5);
      }, 1000);
    }
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
    let skattAretsResultat = null;
    

    
    // Try to extract net result from RR data
    if (data.data?.rr_data) {
      const netResultItem = data.data.rr_data.find((item: any) => 
        item.id === 'ÅR' || item.label?.toLowerCase().includes('årets resultat')
      );
      if (netResultItem && netResultItem.current_amount !== null) {
        extractedResults = Math.abs(netResultItem.current_amount).toString();
      }
      
      // Extract SumAretsResultat for chat options (check RR first, then BR)
      let sumAretsResultatItem = data.data.rr_data.find((item: any) => 
        item.variable_name === 'SumAretsResultat'
      );
      if (!sumAretsResultatItem && data.data?.br_data) {
        sumAretsResultatItem = data.data.br_data.find((item: any) => 
          item.variable_name === 'SumAretsResultat'
        );
      }
      if (sumAretsResultatItem && sumAretsResultatItem.current_amount !== null) {
        sumAretsResultat = Math.abs(sumAretsResultatItem.current_amount);

      }
      
      // Extract SkattAretsResultat for tax confirmation
      const skattAretsResultatItem = data.data.rr_data.find((item: any) => 
        item.variable_name === 'SkattAretsResultat'
      );
      if (skattAretsResultatItem && skattAretsResultatItem.current_amount !== null) {
        skattAretsResultat = Math.abs(skattAretsResultatItem.current_amount);
      }
    }
    
    // Extract SumFrittEgetKapital from BR data  
    if (data.data?.br_data) {
      const sumFrittEgetKapitalItem = data.data.br_data.find((item: any) => 
        item.variable_name === 'SumFrittEgetKapital'
      );
      if (sumFrittEgetKapitalItem && sumFrittEgetKapitalItem.current_amount !== null) {
        sumFrittEgetKapital = Math.abs(sumFrittEgetKapitalItem.current_amount);
      }
    }
    
    // Extract calculated tax amounts from INK2 data
    let inkBeraknadSkatt = null;
    let inkBokfordSkatt = null;
    if (data.data?.ink2_data) {
      const beraknadItem = data.data.ink2_data.find((item: any) => 
        item.variable_name === 'INK_beraknad_skatt'
      );
      if (beraknadItem && beraknadItem.amount !== null) {
        inkBeraknadSkatt = Math.abs(beraknadItem.amount);
      }
      
      const bokfordItem = data.data.ink2_data.find((item: any) => 
        item.variable_name === 'INK_bokford_skatt'
      );
      if (bokfordItem && bokfordItem.amount !== null) {
        inkBokfordSkatt = Math.abs(bokfordItem.amount);
      }
    }
    
    // Extract pension tax variables from response
    let pensionPremier = data.data?.pension_premier || null;
    let sarskildLoneskattPension = data.data?.sarskild_loneskatt_pension || null;
    let sarskildLoneskattPensionCalculated = data.data?.sarskild_loneskatt_pension_calculated || null;
    
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
      skattAretsResultat: skattAretsResultat,
      ink2Data: data.data?.ink2_data || [],
      inkBeraknadSkatt: inkBeraknadSkatt,
      inkBokfordSkatt: inkBokfordSkatt,
      pensionPremier: pensionPremier,
      sarskildLoneskattPension: sarskildLoneskattPension,
      sarskildLoneskattPensionCalculated: sarskildLoneskattPensionCalculated,
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
            // Ask about tax first if we have tax data (including 0)
            if (skattAretsResultat !== null) {
              const taxAmount = Math.round(skattAretsResultat).toLocaleString('sv-SE');
              addMessage(`Den bokförda skatten är ${taxAmount} kr. Vill du godkänna den eller vill du se över de skattemässiga justeringarna?`, true, "🏛️");
              setCurrentStep(0.25); // New step for tax confirmation
            } else {
              // No tax data found, go directly to dividends
              addMessage("Vill ni göra någon utdelning av vinsten?", true, "💰");
              setCurrentStep(0.5);
            }
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
                <div className="flex items-center">
                  <img 
                    src="/raketrapport (logo).png" 
                    alt="RaketRapport" 
                    className="h-12 w-auto"
                  />
                </div>
                {currentStep > 0 && (
                  <div className="text-xs text-muted-foreground">
                    {currentStep}/{TOTAL_STEPS}
                  </div>
                )}
              </div>
            </div>

            {/* Chat Messages */}
            <div ref={chatContainerRef} className="flex-1 overflow-auto">
              <div className="px-6 py-6 space-y-1">
                {messages.map((message, index) => (
                  <ChatMessage
                    key={index}
                    message={message.text}
                    isBot={message.isBot}
                    emoji={message.emoji}
                  />
                ))}
                {/* Invisible div to mark the end of messages for scrolling */}
                <div ref={messagesEndRef} />
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
                    onClick={currentStep < 1 ? handleResultInput : currentStep === 0.33 ? handleCustomPensionTaxSubmit : currentStep === 0.5 ? handleCustomDividendInput : handleEventsText}
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

              {currentStep === 0.25 && (
                <div className="space-y-3">
                  <OptionButton onClick={() => handleTaxApproval(true)}>
                    Ja, godkänn skatten
                  </OptionButton>
                  <OptionButton onClick={() => handleTaxApproval(false)}>
                    Nej, jag vill se över justeringarna
                  </OptionButton>
                </div>
              )}

              {currentStep === 0.35 && (
                <div className="space-y-3">
                  <OptionButton onClick={() => handleTaxChoice('calculated')}>
                    Godkänn och använd beräknad skatt {companyData.inkBeraknadSkatt ? Math.round(companyData.inkBeraknadSkatt).toLocaleString('sv-SE') : '0'} kr
                  </OptionButton>
                  <OptionButton onClick={() => handleTaxChoice('manual')}>
                    Gör manuella ändringar i skattejusteringarna
                  </OptionButton>
                  <OptionButton onClick={() => handleTaxChoice('booked')}>
                    Godkänn och använd bokförd skatt {companyData.inkBokfordSkatt ? Math.round(companyData.inkBokfordSkatt).toLocaleString('sv-SE') : '0'} kr
                  </OptionButton>
                </div>
              )}

              {/* Pension tax check options - Step 0.32 */}
              {currentStep === 0.32 && (
                <div className="space-y-3">
                  <OptionButton onClick={() => handlePensionTaxChoice('adjust')}>
                    Justera särskild löneskatt till {companyData.sarskildLoneskattPensionCalculated ? Math.round(companyData.sarskildLoneskattPensionCalculated).toLocaleString('sv-SE') : '0'} kr
                  </OptionButton>
                  <OptionButton onClick={() => handlePensionTaxChoice('keep')}>
                    Behåll nuvarande bokförd särskild löneskatt {companyData.sarskildLoneskattPension ? Math.round(companyData.sarskildLoneskattPension).toLocaleString('sv-SE') : '0'} kr
                  </OptionButton>
                  <OptionButton onClick={() => handlePensionTaxChoice('custom')}>
                    Ange belopp för eget särskild löneskatt
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
              <AnnualReportPreview companyData={companyData} currentStep={currentStep} editableAmounts={companyData.editableAmounts} />
            </div>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
