import React, { useState, useEffect, useRef } from 'react';
import { apiService } from '@/services/api';
import { ChatMessage } from './ChatMessage';
import { OptionButton } from './OptionButton';
import { FileUpload } from './FileUpload';

interface ChatStep {
  step_number: number;
  block?: string;
  question_text: string;
  question_icon?: string;
  question_type: string;
  input_type?: string;
  input_placeholder?: string;
  show_conditions?: any;
}

interface ChatOption {
  option_order: number;
  option_text: string | null;
  option_value: string;
  next_step?: number;
  action_type: string;
  action_data?: any;
}

interface ChatMessage {
  id: string;
  text: string;
  isBot: boolean;
  icon?: string;
  timestamp: Date;
}

interface ChatFlowProps {
  companyData: any;
  onDataUpdate: (updates: Partial<any>) => void;
}

interface ChatFlowResponse {
  success: boolean;
  step_number: number;
  block?: string;
  question_text: string;
  question_icon?: string;
  question_type: string;
  input_type?: string;
  input_placeholder?: string;
  show_conditions?: any;
  options: ChatOption[];
}

  const DatabaseDrivenChat: React.FC<ChatFlowProps> = ({ companyData, onDataUpdate }) => {
    // State to store the most recent calculated values
    const [globalInk2Data, setGlobalInk2Data] = useState<any[]>([]);
    const [globalInkBeraknadSkatt, setGlobalInkBeraknadSkatt] = useState<number>(0);
  const [currentStep, setCurrentStep] = useState<number>(101); // Start with introduction
  const [currentQuestion, setCurrentQuestion] = useState<ChatStep | null>(null);
  const [currentOptions, setCurrentOptions] = useState<ChatOption[]>([]);
  const [lastLoadedOptions, setLastLoadedOptions] = useState<ChatOption[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [showInput, setShowInput] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [inputType, setInputType] = useState('text');
  const [inputPlaceholder, setInputPlaceholder] = useState('');
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    setTimeout(() => {
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, 100);
  };

  // Substitute variables in text
  const substituteVariables = (text: string, context: Record<string, any> = {}): string => {
    let result = text;
    
    // Create context from company data, but prioritize context values over companyData
    const fullContext = {
      ...companyData,
      ...context,  // Context values should override companyData values
      unusedTaxLossAmount: context.unusedTaxLossAmount || companyData.unusedTaxLossAmount || 0,
      inkBeraknadSkatt: context.inkBeraknadSkatt || companyData.inkBeraknadSkatt || 0,
      inkBokfordSkatt: context.inkBokfordSkatt || companyData.inkBokfordSkatt || 0,
      SkattAretsResultat: context.SkattAretsResultat || companyData.skattAretsResultat || 0,
      pension_premier: context.pension_premier || companyData.pensionPremier || 0,
      sarskild_loneskatt_pension: context.sarskild_loneskatt_pension || companyData.sarskildLoneskattPension || 0,
      sarskild_loneskatt_pension_calculated: context.sarskild_loneskatt_pension_calculated || companyData.sarskildLoneskattPensionCalculated || 0
    };

    // Replace variables
    for (const [key, value] of Object.entries(fullContext)) {
      const placeholder = `{${key}}`;
      if (result.includes(placeholder)) {
        if (typeof value === 'number') {
          const formatted = new Intl.NumberFormat('sv-SE', { 
            minimumFractionDigits: 0, 
            maximumFractionDigits: 0 
          }).format(value);
          result = result.replace(new RegExp(`\\{${key}\\}`, 'g'), formatted);
        } else {
          result = result.replace(new RegExp(`\\{${key}\\}`, 'g'), String(value || ''));
        }
      }
    }

    return result;
  };

  // Add message to chat
  const addMessage = (text: string, isBot: boolean = true, icon?: string) => {
    // Prevent adding empty messages
    if (!text || text.trim() === '') {
      console.log('🚫 Skipping empty message');
      return;
    }
    
    const message: ChatMessage = {
      id: Date.now().toString(),
      text: substituteVariables(text),
      isBot,
      icon,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, message]);
    scrollToBottom();
  };

  // Load a chat step
  const loadChatStep = async (stepNumber: number, updatedInk2Data?: any[]) => {
    try {
      console.log(`🔄 Loading step ${stepNumber}...`);
      
      // Use updated ink2Data if provided, otherwise use global data, otherwise use companyData.ink2Data
      const ink2DataToUse = updatedInk2Data || globalInk2Data || companyData.ink2Data;
      console.log('🔍 API call - ink2DataToUse:', ink2DataToUse?.length, 'items');
      if (ink2DataToUse && ink2DataToUse.length > 0) {
        const inkBeraknadSkattItem = ink2DataToUse.find((item: any) => 
          item.variable_name === 'INK_beraknad_skatt'
        );
        console.log('🔍 API call - inkBeraknadSkattItem:', inkBeraknadSkattItem);
      }
      const response: ChatFlowResponse = await apiService.getChatFlowStep(stepNumber);
      
      if (response.success) {
        setCurrentStep(stepNumber);
        
        // Handle no_option automatically if it exists
        const noOption = response.options.find(opt => opt.option_order === 0);
        if (noOption) {
          console.log('🚀 Auto-executing no_option:', noOption);
          console.log('No option details:', {
            option_value: noOption.option_value,
            next_step: noOption.next_step,
            action_type: noOption.action_type,
            action_data: noOption.action_data
          });
          
          // For message-type steps with no_option, show the message first, then execute the no_option
          if (response.question_type === 'message') {
            // Get the most recent inkBeraknadSkatt value from global data first, then INK2 data
            let mostRecentInkBeraknadSkatt = globalInkBeraknadSkatt || companyData.inkBeraknadSkatt;
            if (ink2DataToUse && ink2DataToUse.length > 0) {
              const inkBeraknadSkattItem = ink2DataToUse.find((item: any) => 
                item.variable_name === 'INK_beraknad_skatt'
              );
              if (inkBeraknadSkattItem && inkBeraknadSkattItem.amount !== undefined) {
                mostRecentInkBeraknadSkatt = inkBeraknadSkattItem.amount;
                console.log('💰 Using most recent inkBeraknadSkatt from INK2 data for message step:', mostRecentInkBeraknadSkatt);
              }
            }
            
            // Substitute variables in question text
            const questionText = substituteVariables(response.question_text, {
              SumAretsResultat: companyData.sumAretsResultat ? new Intl.NumberFormat('sv-SE').format(companyData.sumAretsResultat) : '0',
              SkattAretsResultat: companyData.skattAretsResultat ? new Intl.NumberFormat('sv-SE').format(companyData.skattAretsResultat) : '0',
              pension_premier: companyData.pensionPremier ? new Intl.NumberFormat('sv-SE').format(companyData.pensionPremier) : '0',
              sarskild_loneskatt_pension_calculated: companyData.sarskildLoneskattPensionCalculated ? new Intl.NumberFormat('sv-SE').format(companyData.sarskildLoneskattPensionCalculated) : '0',
              sarskild_loneskatt_pension: companyData.sarskildLoneskattPension ? new Intl.NumberFormat('sv-SE').format(companyData.sarskildLoneskattPension) : '0',
              inkBeraknadSkatt: mostRecentInkBeraknadSkatt ? new Intl.NumberFormat('sv-SE').format(mostRecentInkBeraknadSkatt) : '0',
              inkBokfordSkatt: companyData.inkBokfordSkatt ? new Intl.NumberFormat('sv-SE').format(companyData.inkBokfordSkatt) : '0',
              unusedTaxLossAmount: companyData.unusedTaxLossAmount ? new Intl.NumberFormat('sv-SE').format(companyData.unusedTaxLossAmount) : '0'
            });
            
            // Add the message first
            addMessage(questionText, true, response.question_icon);
          }
          
          // Execute no_option with the correct step number and updated data
          await handleOptionSelect(noOption, stepNumber, updatedInk2Data);
          return; // Don't continue with normal flow since no_option handles navigation
        }
        
        // Get the most recent inkBeraknadSkatt value from global data first, then INK2 data
        let mostRecentInkBeraknadSkatt = globalInkBeraknadSkatt || companyData.inkBeraknadSkatt;
        if (ink2DataToUse && ink2DataToUse.length > 0) {
          const inkBeraknadSkattItem = ink2DataToUse.find((item: any) => 
            item.variable_name === 'INK_beraknad_skatt'
          );
          if (inkBeraknadSkattItem && inkBeraknadSkattItem.amount !== undefined) {
            mostRecentInkBeraknadSkatt = inkBeraknadSkattItem.amount;
            console.log('💰 Using most recent inkBeraknadSkatt from INK2 data:', mostRecentInkBeraknadSkatt);
          }
        }
        
        // Substitute variables in question text
        console.log('🔍 Loading step', stepNumber, 'with inkBeraknadSkatt:', mostRecentInkBeraknadSkatt);
        const substitutionVars = {
          SumAretsResultat: companyData.sumAretsResultat ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(companyData.sumAretsResultat) : '0',
          SkattAretsResultat: companyData.skattAretsResultat ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(companyData.skattAretsResultat) : '0',
          pension_premier: companyData.pensionPremier ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(companyData.pensionPremier) : '0',
          sarskild_loneskatt_pension_calculated: companyData.sarskildLoneskattPensionCalculated ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(companyData.sarskildLoneskattPensionCalculated) : '0',
          sarskild_loneskatt_pension: companyData.sarskildLoneskattPension ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(companyData.sarskildLoneskattPension) : '0',
          inkBeraknadSkatt: mostRecentInkBeraknadSkatt ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(mostRecentInkBeraknadSkatt) : '0',
          inkBokfordSkatt: companyData.inkBokfordSkatt ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(companyData.inkBokfordSkatt) : '0',
          unusedTaxLossAmount: companyData.unusedTaxLossAmount ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(companyData.unusedTaxLossAmount) : '0'
        };
        console.log('🔍 Substitution variables:', substitutionVars);
        const questionText = substituteVariables(response.question_text, substitutionVars);
        console.log('🔍 Substituted question text:', questionText);
        
        // Add the question message
        addMessage(questionText, true, response.question_icon);

        // Special handling for manual editing step (402):
        // - Ensure editing is enabled in the preview
        // - Suppress chat options to avoid accidental auto-selection
        // - Scroll the preview into view so inputs are visible
        if (stepNumber === 402) {
          console.log('🔥 STEP 402 TRIGGERED - Calling onDataUpdate with flags');
          onDataUpdate({ taxEditingEnabled: true, editableAmounts: true, showTaxPreview: true });
          console.log('🔥 STEP 402 onDataUpdate called successfully');
          setCurrentOptions([]);
          setTimeout(() => {
            const taxModule = document.querySelector('[data-section="tax-calculation"]');
            if (taxModule) {
              taxModule.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          }, 200);
        } else {
          // Store all options (unfiltered) for submit logic
          setLastLoadedOptions(response.options);
          
          // Store filtered options for display with variable substitution
          const substitutedOptions = response.options
            .filter(opt => opt.option_order > 0 && opt.option_value !== 'submit') // Exclude no_option and submit options
            .map(option => ({
              ...option,
              option_text: option.option_text ? substituteVariables(option.option_text, substitutionVars) : option.option_text
            }));
          setCurrentOptions(substitutedOptions);
        }
        
        // Check if we should show input instead of options
        if (response.question_type === 'input') {
          setShowInput(true);
          setInputType(response.input_type || 'text');
          setInputPlaceholder(response.input_placeholder || '');
        } else {
          // Ensure input is hidden for non-input steps
          setShowInput(false);
          setInputValue('');
        }
      }
    } catch (error) {
      console.error('❌ Error loading chat step:', error);
      addMessage('Något gick fel vid laddning av chatten. Försök ladda om sidan.', true, '❌');
    }
  };

  // Evaluate conditions for showing a step
  const evaluateConditions = (conditions: any): boolean => {
    if (!conditions) return true;

    try {
      // Parse JSON conditions if string
      const parsedConditions = typeof conditions === 'string' ? JSON.parse(conditions) : conditions;
      
      // Check for complex mathematical conditions  
      if (parsedConditions.formula) {
        // For step 201: Should show if sarskild_loneskatt_pension_calculated > sarskild_loneskatt_pension
        // The calculated amount is already computed by backend using the correct global rate
        const pensionPremier = companyData.pensionPremier || 0;
        const sarskildLoneskattPension = companyData.sarskildLoneskattPension || 0;
        const sarskildLoneskattPensionCalculated = companyData.sarskildLoneskattPensionCalculated || 0;
        
        console.log('🔍 Step 201 condition debug:');
        console.log('📊 pension_premier:', pensionPremier);
        console.log('📊 sarskild_loneskatt_pension (booked):', sarskildLoneskattPension);
        console.log('📊 sarskild_loneskatt_pension_calculated:', sarskildLoneskattPensionCalculated);
        
        // Show step 201 if there are pension premiums AND calculated tax > booked tax
        const shouldShow = pensionPremier > 0 && sarskildLoneskattPensionCalculated > sarskildLoneskattPension;
        console.log('💡 Should show step 201?', shouldShow);
        
        return shouldShow;
      }

      // Simple condition evaluation for backward compatibility
      for (const [key, condition] of Object.entries(parsedConditions)) {
        const value = (companyData as any)[key];
        
        if (typeof condition === 'object' && condition !== null) {
          if ('gt' in condition) {
            const compareValue = typeof condition.gt === 'string' 
              ? (companyData as any)[condition.gt] 
              : condition.gt;
            if (!(value > compareValue)) return false;
          }
          // Add more condition types as needed
        }
      }

      return true;
    } catch (e) {
      console.error('Error parsing conditions:', e);
      return true; // Default to showing step if condition parsing fails
    }
  };

  // Handle option selection
  const handleOptionSelect = async (option: ChatOption, explicitStepNumber?: number, updatedInk2Data?: any[]) => {
    try {
      // Add user message only if there's actual text
      const optionText = option.option_text || '';
      if (optionText && optionText.trim() !== '') {
        addMessage(optionText, false);
      }

      // Handle special cases first
      // Handle custom tax options to bypass API call
      if (option.option_value === 'approve_tax') {
        // Hide tax preview and go directly to dividends
        onDataUpdate({ showTaxPreview: false });
        setTimeout(() => loadChatStep(501), 1000);
        return;
      }
      
      if (option.option_value === 'review_adjustments') {
        // Show tax module using the flag
        onDataUpdate({ showTaxPreview: true });
        // Auto-scroll to tax module after a short delay
        setTimeout(() => {
          const taxModule = document.querySelector('[data-section="tax-calculation"]');
          const scrollContainer = document.querySelector('.overflow-auto');
          if (taxModule && scrollContainer) {
            const containerRect = scrollContainer.getBoundingClientRect();
            const taxRect = taxModule.getBoundingClientRect();
            const scrollTop = scrollContainer.scrollTop + taxRect.top - containerRect.top - 10; // 5-7pt padding from top
            
            scrollContainer.scrollTo({
              top: scrollTop,
              behavior: 'smooth'
            });
          }
        }, 500);
        
        // Check conditions for step 201 before navigating
        setTimeout(async () => {
          try {
            const step201Response = await apiService.getChatFlowStep(201) as ChatFlowResponse;
            if (step201Response.success && step201Response.show_conditions) {
              const shouldShow = evaluateConditions(step201Response.show_conditions);
              console.log('🔍 Step 201 condition evaluation:', shouldShow);
              
              if (shouldShow) {
                loadChatStep(201);
              } else {
                // Skip to step 301 if condition not met
                console.log('⏭️ Skipping step 201, going to 301');
                loadChatStep(301);
              }
            } else {
              // No conditions, proceed normally
              loadChatStep(201);
            }
          } catch (error) {
            console.error('Error checking step 201 conditions:', error);
            // Fallback to normal navigation
            loadChatStep(201);
          }
        }, 1000);
        return;
      }
      
      // Handle pension tax adjustments
      if (option.option_value === 'adjust_calculated') {
        // Set pension tax adjustment to calculated value
        onDataUpdate({ justeringSarskildLoneskatt: 'calculated' });
        
        // Trigger recalculation to update tax preview
        if (companyData.seFileData && companyData.sarskildLoneskattPensionCalculated) {
          try {
            const result = await apiService.recalculateInk2({
              current_accounts: companyData.seFileData.current_accounts || {},
              fiscal_year: companyData.fiscalYear,
              rr_data: companyData.seFileData.rr_data || [],
              br_data: companyData.seFileData.br_data || [],
              manual_amounts: {},
              justering_sarskild_loneskatt: companyData.sarskildLoneskattPensionCalculated
            });
            
            if (result.success) {
              onDataUpdate({ ink2Data: result.ink2_data });
            }
          } catch (error) {
            console.error('Error recalculating tax:', error);
          }
        }
        
        try {
          const step202Response = await apiService.getChatFlowStep(202) as ChatFlowResponse;
          addMessage(step202Response.question_text, true, step202Response.question_icon);
        } catch (error) {
          console.error('❌ Error fetching step 202:', error);
          addMessage('Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkningen till höger.', true, '✅');
        }
        setTimeout(() => loadChatStep(301), 1000); // Go to underskott question
        return;
      }
      
      if (option.option_value === 'keep_current') {
        // Keep current pension tax
        onDataUpdate({ justeringSarskildLoneskatt: 'current' });
        setTimeout(() => loadChatStep(301), 1000); // Go to underskott question
        return;
      }
      
      // Handle "no unused tax loss" from step 301
      if (option.option_value === 'none' && (explicitStepNumber || currentStep) === 301) {
        // Set unused tax loss to 0 and trigger tax recalculation
        onDataUpdate({ unusedTaxLossAmount: 0 });
        
        // Trigger recalculation to update inkBeraknadSkatt
        if (companyData.seFileData) {
          try {
            const justeringSarskildLoneskattValue = companyData.justeringSarskildLoneskatt === 'calculated' 
              ? (companyData.sarskildLoneskattPensionCalculated || 0) - (companyData.sarskildLoneskattPension || 0)
              : 0;
              
            console.log('🔍 Step 301 option 1 - API call parameters:');
            console.log('📊 current_accounts:', companyData.seFileData.accountBalances);
            console.log('📊 rr_data length:', companyData.seFileData.rr_data?.length || 0);
            console.log('📊 br_data length:', companyData.seFileData.br_data?.length || 0);
            console.log('📊 fiscal_year:', companyData.fiscalYear);
            console.log('📊 justering_sarskild_loneskatt:', justeringSarskildLoneskattValue);
            console.log('📊 ink4_14a_outnyttjat_underskott: 0');
            
            const response = await apiService.recalculateInk2({
              current_accounts: companyData.seFileData.current_accounts || {},
              rr_data: companyData.seFileData.rr_data || [],
              br_data: companyData.seFileData.br_data || [],
              fiscal_year: companyData.fiscalYear,
              manual_amounts: {}, // Keep manual_amounts separate
              ink4_14a_outnyttjat_underskott: 0, // No unused tax loss
              justering_sarskild_loneskatt: justeringSarskildLoneskattValue
            });
            
            if (response.success) {
              console.log('🔍 Step 301 option 1 - Tax recalculation result:', response.ink2_data);
              
              // Get the updated inkBeraknadSkatt value (same as option 2 pattern)
              const updatedInkBeraknadSkatt = response.ink2_data.find((item: any) => 
                item.variable_name === 'INK_beraknad_skatt'
              )?.amount || companyData.inkBeraknadSkatt;
              
              console.log('💰 Updated inkBeraknadSkatt for step 401:', updatedInkBeraknadSkatt);
              
              // Store values in state to ensure they're always available (same as option 2)
              setGlobalInk2Data(response.ink2_data);
              setGlobalInkBeraknadSkatt(updatedInkBeraknadSkatt);
              
              // Update the tax data in company state (same as option 2)
              onDataUpdate({
                ink2Data: response.ink2_data,
                inkBeraknadSkatt: updatedInkBeraknadSkatt,
                unusedTaxLossAmount: 0
              });
              
              // Pass updated ink2Data to step 401
              setTimeout(() => loadChatStep(401, response.ink2_data), 1000);
              return;
            }
          } catch (error) {
            console.error('Error recalculating tax for no unused loss:', error);
          }
        }
        
        setTimeout(() => loadChatStep(401), 1000);
        return;
      }

      // Note: enter_custom is now handled by database-driven flow (show_input action)

      // Get the most recent inkBeraknadSkatt value from global data first, then INK2 data
      let mostRecentInkBeraknadSkatt = globalInkBeraknadSkatt || companyData.inkBeraknadSkatt;
      const ink2DataToUse = updatedInk2Data || globalInk2Data || companyData.ink2Data;
      if (ink2DataToUse && ink2DataToUse.length > 0) {
        const inkBeraknadSkattItem = ink2DataToUse.find((item: any) => 
          item.variable_name === 'INK_beraknad_skatt'
        );
        if (inkBeraknadSkattItem && inkBeraknadSkattItem.amount !== undefined) {
          mostRecentInkBeraknadSkatt = inkBeraknadSkattItem.amount;
          console.log('💰 Using most recent inkBeraknadSkatt from INK2 data for context:', mostRecentInkBeraknadSkatt);
        }
      }
      
      // Process the choice through the API
      // Use the most recent inkBeraknadSkatt value if available
      const context = {
        unusedTaxLossAmount: companyData.unusedTaxLossAmount || 0,
        inkBeraknadSkatt: mostRecentInkBeraknadSkatt || 0,
        inkBokfordSkatt: companyData.inkBokfordSkatt || 0,
        SkattAretsResultat: companyData.skattAretsResultat || 0
      };
      
      console.log('🔍 Processing choice with context:', context);

      const response = await apiService.processChatChoice({
        step_number: explicitStepNumber || currentStep,
        option_value: option.option_value,
        context
      });

      if (response.success) {
        const { action_type, action_data, next_step } = response.result;
        
        console.log('🔍 API Response:', { action_type, action_data, next_step });

        // Process the action
        console.log('🔍 Processing action:', action_type, 'with data:', action_data);
        
        switch (action_type) {
          case 'set_variable':
            // Handle variable setting
            if (action_data?.variable && action_data?.value !== undefined) {
              console.log('🔧 Setting variable:', action_data.variable, 'to:', action_data.value);
              onDataUpdate({ [action_data.variable]: action_data.value });
            }
            break;
            
          case 'api_call':
            await handleApiCall(action_data);
            break;
            
          case 'enable_editing':
            // Enable tax editing mode immediately
            console.log('🔧 ENABLE_EDITING ACTION TRIGGERED - Setting editableAmounts to true');
            onDataUpdate({ taxEditingEnabled: true, editableAmounts: true, showTaxPreview: true });
            console.log('🔧 onDataUpdate called with:', { taxEditingEnabled: true, editableAmounts: true, showTaxPreview: true });
            // Ensure we land on the manual editing step 402
            const targetStep = next_step || 402;
            setTimeout(() => loadChatStep(targetStep), 200);
            return; // Stop further navigation below

          case 'show_input':
            // Prefer explicit navigation to the input step if provided
            if (next_step) {
              console.log('🧭 show_input: navigating to input step', next_step);
              setTimeout(() => loadChatStep(next_step, updatedInk2Data), 300);
              return; // Avoid double-navigation by skipping general nav below
            }
            // Fallback: show inline input on current step if no next_step
            setShowInput(true);
            setInputType(action_data?.input_type || 'amount');
            setInputPlaceholder(action_data?.input_placeholder || 'Ange belopp i kr...');
            break;
            
          case 'show_file_upload':
            setShowFileUpload(true);
            return; // Don't navigate to next step yet
            
          case 'navigate':
            // Simple navigation to next step
            // Show tax module for tax-related steps
            if (next_step === 201 || next_step === 202 || next_step === 203 || 
                next_step === 301 || next_step === 302 || next_step === 303 || 
                next_step === 401 || next_step === 402 || next_step === 405) {
              onDataUpdate({ showTaxPreview: true });
            }
            break;
            
          case 'process_input':
            // Handle input processing
            if (action_data?.variable) {
              // The input value should already be stored in companyData
              // This action type is mainly for navigation
            }
            break;
            
          case 'save_manual_tax':
            // Save manual tax changes
            onDataUpdate({ taxEditingEnabled: false, editableAmounts: false });
            break;
            
          case 'reset_tax_edits':
            // Reset tax editing mode
            onDataUpdate({ taxEditingEnabled: false, editableAmounts: false });
            break;
            
          case 'generate_pdf':
            // Handle PDF generation
            console.log('PDF generation requested');
            break;
            
          case 'complete_session':
            // Handle session completion
            console.log('Session completion requested');
            break;
            
          case 'show_periodiseringsfonder':
            // Show periodiseringsfonder module
            onDataUpdate({ showPeriodiseringsfonder: true });
            break;
        }

        // Navigate to next step
        console.log('🔍 General navigation check:', { next_step, action_type });
        if (next_step) {
          console.log('🚀 Navigating to step:', next_step);
          setTimeout(() => loadChatStep(next_step, updatedInk2Data), 1000);
        } else {
          console.log('❌ No next_step specified');
        }
      }
    } catch (error) {
      console.error('Error handling option:', error);
      addMessage('Något gick fel. Försök igen.', true, '❌');
    }
  };

  // Handle API calls triggered by chat actions
  const handleApiCall = async (actionData: any) => {
    if (actionData?.endpoint === 'recalculate_ink2') {
      try {
        const params = actionData.params || {};
        
        // Substitute variables in params (e.g., {unusedTaxLossAmount} -> actual value)
        const substitutedParams = { ...params };
        for (const [key, value] of Object.entries(substitutedParams)) {
          if (typeof value === 'string' && value.includes('{')) {
            // Replace {unusedTaxLossAmount} with actual value
            const substituted = value.replace(/{(\w+)}/g, (match, varName) => {
              // Special handling for unusedTaxLossAmount to ensure we get the latest value
              if (varName === 'unusedTaxLossAmount') {
                // Check if we have a pending unusedTaxLossAmount value from recent input
                const pendingValue = companyData.unusedTaxLossAmount;
                if (pendingValue && pendingValue > 0) {
                  console.log('🔥 Using pending unusedTaxLossAmount value:', pendingValue);
                  return pendingValue;
                }
              }
              return companyData[varName as keyof typeof companyData] || match;
            });
            // Convert to number if it's a numeric string
            substitutedParams[key] = isNaN(Number(substituted)) ? substituted : Number(substituted);
          }
        }
        
        console.log('🔥 API call with substituted params:', substitutedParams);
        
        // Skip the API call if we're trying to set unusedTaxLossAmount to 0 but we already have a value
        if (substitutedParams.ink4_14a_outnyttjat_underskott === 0 && companyData.unusedTaxLossAmount > 0) {
          console.log('🚫 Skipping API call - unusedTaxLossAmount already set to', companyData.unusedTaxLossAmount);
          return;
        }
        

        
        if (companyData.seFileData) {
          const result = await apiService.recalculateInk2({
            current_accounts: companyData.seFileData.current_accounts || {},
            fiscal_year: companyData.fiscalYear,
            rr_data: companyData.seFileData.rr_data || [],
            br_data: companyData.seFileData.br_data || [],
            manual_amounts: {},
            ...substitutedParams
          });
          
          if (result.success) {
            onDataUpdate({
              ink2Data: result.ink2_data,
              inkBeraknadSkatt: result.ink2_data.find((item: any) => 
                item.variable_name === 'INK_beraknad_skatt'
              )?.amount || companyData.inkBeraknadSkatt
            });
          }
        }
      } catch (error) {
        console.error('API call failed:', error);
      }
    }
  };

  // Handle input submission
  const handleInputSubmit = async () => {
    if (!inputValue.trim()) return;

    const value = inputType === 'amount' 
      ? Math.abs(parseFloat(inputValue.replace(/\s/g, '').replace(/,/g, '.')) || 0)
      : inputValue.trim();
    
    console.log('📤 Input submit - Current step:', currentStep, 'Options:', currentOptions);
    
    // Hide input immediately to prevent UI flash
    setShowInput(false);

    // Add user message
    const displayValue = inputType === 'amount' 
      ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value as number) + ' kr'
      : value;
    addMessage(displayValue, false);

    // Find the submit option for this step from the last loaded response (not filtered options)
    const submitOption = lastLoadedOptions?.find(opt => opt.option_value === 'submit');

    if (submitOption) {
      // Store the input value based on action data
      if (submitOption.action_data?.variable) {
        
        console.log('💾 Storing input value:', {
          variable: submitOption.action_data.variable,
          value: value,
          inputValue: inputValue,
          parsedValue: inputType === 'amount' ? Math.abs(parseFloat(inputValue.replace(/\s/g, '').replace(/,/g, '.')) || 0) : inputValue.trim()
        });

        // Special handling for unused tax loss amount
        if (submitOption.action_data.variable === 'unusedTaxLossAmount') {
          console.log('🔥 Calling specialized unused tax loss handler');
          await handleUnusedTaxLossSubmission(value as number);
          return; // Don't continue with normal flow
        }

        onDataUpdate({ [submitOption.action_data.variable]: value });

        // Note: Unused tax loss recalculation happens in step 303 via api_call, not here
        
        // Special handling for custom pension tax amount
        if (submitOption.action_data.variable === 'sarskildLoneskattCustom') {
          const amount = value as number;
          const sarskildLoneskattPension = companyData.sarskildLoneskattPension || 0;
          const adjustment = amount - sarskildLoneskattPension;
          
          onDataUpdate({ 
            justeringSarskildLoneskatt: 'custom',
            sarskildLoneskattPensionSubmitted: amount 
          });
          
          // Trigger recalculation to update tax preview
          if (companyData.seFileData) {
            try {
              const result = await apiService.recalculateInk2({
                current_accounts: companyData.seFileData.current_accounts || {},
                fiscal_year: companyData.fiscalYear,
                rr_data: companyData.seFileData.rr_data || [],
                br_data: companyData.seFileData.br_data || [],
                manual_amounts: {},
                justering_sarskild_loneskatt: adjustment
              });
              
              if (result.success) {
                console.log('✅ Tax recalculation successful');
                console.log('📋 New INK2 data:', result.ink2_data);
                
                // Get the updated inkBeraknadSkatt value
                const updatedInkBeraknadSkatt = result.ink2_data.find((item: any) => 
                  item.variable_name === 'INK_beraknad_skatt'
                )?.amount || companyData.inkBeraknadSkatt;
                
                console.log('💰 Updated inkBeraknadSkatt:', updatedInkBeraknadSkatt);
                
                // Store values in state to ensure they're always available (like in handleUnusedTaxLossSubmission)
                setGlobalInk2Data(result.ink2_data);
                setGlobalInkBeraknadSkatt(updatedInkBeraknadSkatt);
                console.log('🌍 Stored in state - globalInkBeraknadSkatt:', updatedInkBeraknadSkatt);
                
                // Update the tax data in company state in a single call to prevent multiple updates
                onDataUpdate({
                  ink2Data: result.ink2_data,
                  inkBeraknadSkatt: updatedInkBeraknadSkatt,
                  showTaxPreview: true
                });
                
                setShowInput(false);
                setInputValue('');

                // Navigate to step 202 with the updated ink2Data (step 202 will show its own message)
                console.log('🔄 Navigating to step 202 with updated inkBeraknadSkatt:', updatedInkBeraknadSkatt);
                loadChatStep(202, result.ink2_data);
                return;
              }
            } catch (error) {
              console.error('Error recalculating tax:', error);
            }
          }
          
          // Fallback if recalculation fails
          try {
            const step202Response = await apiService.getChatFlowStep(202) as ChatFlowResponse;
            addMessage(step202Response.question_text, true, step202Response.question_icon);
          } catch (error) {
            console.error('❌ Error fetching step 202:', error);
            addMessage('Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkningen till höger.', true, '✅');
          }
          setShowInput(false);
          setInputValue('');
          setTimeout(() => loadChatStep(202), 1000);
          return;
        }
      }

      // Navigate to next step (unless we're handling special cases)
      console.log('🔍 Navigation check:', {
        hasNextStep: !!submitOption.next_step,
        nextStep: submitOption.next_step,
        variable: submitOption.action_data?.variable,
        willNavigate: submitOption.next_step && submitOption.action_data?.variable !== 'sarskildLoneskattCustom'
      });
      
      if (submitOption.next_step && 
          submitOption.action_data?.variable !== 'sarskildLoneskattCustom') {
        console.log('🚀 Navigating to step:', submitOption.next_step);
        setShowInput(false);
        setInputValue('');
        setTimeout(() => loadChatStep(submitOption.next_step!), 500);
      } else {
        console.log('❌ Navigation blocked or no next step');
      }
    }
  };

  // Handle file upload
  const handleFileProcessed = async (fileData: any) => {
    console.log('📁 File processed:', fileData);
    
    // Extract data from the uploaded file (same logic as old system)
    let extractedResults = null;
    let sumAretsResultat = null;
    let sumFrittEgetKapital = null;
    let skattAretsResultat = null;
    
    // Try to extract net result from RR data
    if (fileData.data?.rr_data) {
      const netResultItem = fileData.data.rr_data.find((item: any) => 
        item.id === 'ÅR' || item.label?.toLowerCase().includes('årets resultat')
      );
      if (netResultItem && netResultItem.current_amount !== null) {
        extractedResults = netResultItem.current_amount.toString();
      }
      
            // Extract SumAretsResultat for chat options (check RR first, then BR)
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
      
      // If not found in RR, try BR data
      if (!sumAretsResultatItem && fileData.data?.br_data) {
        sumAretsResultatItem = fileData.data.br_data.find((item: any) => 
          item.variable_name === 'SumAretsResultat'
        );
      }
      
      // If still not found in BR, try ID match in BR
      if (!sumAretsResultatItem && fileData.data?.br_data) {
        sumAretsResultatItem = fileData.data.br_data.find((item: any) => 
          item.id === 'ÅR'
        );
      }
      
      // If still not found in BR, try label match but exclude SkattAretsResultat
      if (!sumAretsResultatItem && fileData.data?.br_data) {
        sumAretsResultatItem = fileData.data.br_data.find((item: any) => 
          item.label?.toLowerCase().includes('årets resultat') &&
          item.variable_name !== 'SkattAretsResultat'
        );
      }
      if (sumAretsResultatItem && sumAretsResultatItem.current_amount !== null) {
        sumAretsResultat = Math.round(sumAretsResultatItem.current_amount);
        console.log('📊 Found SumAretsResultat:', sumAretsResultat, 'from item:', sumAretsResultatItem);
      } else {
        console.log('❌ Could not find SumAretsResultat in RR or BR data');
        console.log('RR data keys:', fileData.data.rr_data?.map((item: any) => ({ id: item.id, variable_name: item.variable_name, label: item.label, current_amount: item.current_amount })));
        
        // Try to find any result item as fallback
        const fallbackItem = fileData.data.rr_data?.find((item: any) => 
          item.current_amount !== null && item.current_amount !== 0 && 
          (item.label?.toLowerCase().includes('resultat') || item.id?.includes('RES'))
        );
        if (fallbackItem) {
          sumAretsResultat = Math.round(fallbackItem.current_amount);
          console.log('📊 Using fallback SumAretsResultat:', sumAretsResultat, 'from item:', fallbackItem);
        }
      }
      
      // Extract SkattAretsResultat for tax confirmation
      console.log('🔍 Searching for SkattAretsResultat in RR data...');
      console.log('🔍 Available RR items:', fileData.data.rr_data.map((item: any) => ({
        variable_name: item.variable_name,
        id: item.id,
        label: item.label,
        current_amount: item.current_amount
      })));
      
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
      
      // If still not found, try label match but exclude SumResultatForeSkatt
      if (!skattAretsResultatItem) {
        skattAretsResultatItem = fileData.data.rr_data.find((item: any) => 
          item.label?.toLowerCase().includes('skatt') && 
          item.variable_name !== 'SumResultatForeSkatt' &&
          item.variable_name !== 'SumResultatEfterFinansiellaPoster'
        );
      }
      if (skattAretsResultatItem && skattAretsResultatItem.current_amount !== null) {
        skattAretsResultat = Math.round(skattAretsResultatItem.current_amount);
        // Fix negative zero issue
        if (skattAretsResultat === -0) skattAretsResultat = 0;
        console.log('💰 Found SkattAretsResultat:', skattAretsResultat, 'from item:', skattAretsResultatItem);
      } else {
        console.log('❌ Could not find SkattAretsResultat in RR data');
      }
    }
    
    // Extract SumFrittEgetKapital from BR data  
    if (fileData.data?.br_data) {
      const sumFrittEgetKapitalItem = fileData.data.br_data.find((item: any) => 
        item.variable_name === 'SumFrittEgetKapital'
      );
      if (sumFrittEgetKapitalItem && sumFrittEgetKapitalItem.current_amount !== null) {
        sumFrittEgetKapital = Math.abs(sumFrittEgetKapitalItem.current_amount);
      }
    }
    
    // Extract calculated tax amounts from INK2 data
    let inkBeraknadSkatt = null;
    let inkBokfordSkatt = null;
    if (fileData.data?.ink2_data) {
      const beraknadItem = fileData.data.ink2_data.find((item: any) => 
        item.variable_name === 'INK_beraknad_skatt'
      );
      if (beraknadItem && beraknadItem.amount !== null) {
        inkBeraknadSkatt = Math.abs(beraknadItem.amount);
      }
      
      const bokfordItem = fileData.data.ink2_data.find((item: any) => 
        item.variable_name === 'INK_bokford_skatt'
      );
      if (bokfordItem && bokfordItem.amount !== null) {
        inkBokfordSkatt = Math.abs(bokfordItem.amount);
      }
    }
    
    // Extract pension tax variables from response
    let pensionPremier = fileData.data?.pension_premier || null;
    let sarskildLoneskattPension = fileData.data?.sarskild_loneskatt_pension || null;
    let sarskildLoneskattPensionCalculated = fileData.data?.sarskild_loneskatt_pension_calculated || null;
    
    // Fallback to legacy extraction if needed
    if (!extractedResults && fileData.data?.accountBalances) {
      const resultAccounts = ['8999', '8910'];
      for (const account of resultAccounts) {
        if (fileData.data.accountBalances[account]) {
          extractedResults = Math.abs(fileData.data.accountBalances[account]).toString();
          break;
        }
      }
    }
    
    // Update company data with all extracted information
    onDataUpdate({ 
      seFileData: fileData.data,
      results: extractedResults,
      sumAretsResultat: sumAretsResultat,
      sumFrittEgetKapital: sumFrittEgetKapital,
      skattAretsResultat: skattAretsResultat,
      ink2Data: fileData.data?.ink2_data || [],
      noterData: fileData.data?.noter_data || [],
      inkBeraknadSkatt: inkBeraknadSkatt,
      inkBokfordSkatt: inkBokfordSkatt,
      pensionPremier: pensionPremier,
      sarskildLoneskattPension: sarskildLoneskattPension,
      sarskildLoneskattPensionCalculated: sarskildLoneskattPensionCalculated,
      fiscalYear: fileData.data?.company_info?.fiscal_year || new Date().getFullYear(),
      companyName: fileData.data?.company_info?.company_name || 'Företag AB',
      showRRBR: true // Show RR and BR data in preview
    });
    
    setShowFileUpload(false);
    
    // Add the success message from database (step 102)
    try {
      const step102Response = await apiService.getChatFlowStep(102) as ChatFlowResponse;
      addMessage(step102Response.question_text, true, step102Response.question_icon);
    } catch (error) {
      console.error('❌ Error fetching step 102:', error);
      addMessage('Perfekt! Resultatrapport och balansräkning är nu skapad från SE-filen.', true, '✅');
    }
    
    // Add the result overview message from database (step 103) - with variable substitution
    try {
      const step103Response = await apiService.getChatFlowStep(103) as ChatFlowResponse;
      const resultText = substituteVariables(
        step103Response.question_text,
        {
          SumAretsResultat: sumAretsResultat ? new Intl.NumberFormat('sv-SE').format(sumAretsResultat) : '0'
        }
      );
      addMessage(resultText, true, step103Response.question_icon);
    } catch (error) {
      console.error('❌ Error fetching step 103:', error);
      const resultText = substituteVariables(
        'Årets resultat är: {SumAretsResultat} kr. Se fullständig resultat- och balans rapport i preview fönstret till höger.',
        {
          SumAretsResultat: sumAretsResultat ? new Intl.NumberFormat('sv-SE').format(sumAretsResultat) : '0'
        }
      );
      addMessage(resultText, true, '💰');
    }
        
        // Add debugging for tax amount
        console.log('🏛️ Tax amount for step 104:', skattAretsResultat);
        console.log('📊 Annual result for step 103:', sumAretsResultat);
    
    // Navigate to next step after file upload
    setTimeout(async () => {
      // Show tax question if we have tax data (including 0)
      if (skattAretsResultat !== null) {
        try {
          const step104Response = await apiService.getChatFlowStep(104) as ChatFlowResponse;
          const taxAmount = new Intl.NumberFormat('sv-SE').format(skattAretsResultat);
          const taxText = substituteVariables(
            step104Response.question_text,
            {
              SkattAretsResultat: taxAmount
            }
          );
          addMessage(taxText, true, step104Response.question_icon);
          
          // Use options from database
          setCurrentOptions(step104Response.options);
        } catch (error) {
          console.error('❌ Error fetching step 104:', error);
          const taxAmount = new Intl.NumberFormat('sv-SE').format(skattAretsResultat);
          addMessage(`Den bokförda skatten är ${taxAmount} kr. Vill du godkänna den eller vill du se över de skattemässiga justeringarna?`, true, '🏛️');
          
          // Fallback hardcoded options
          setCurrentOptions([
            {
              option_order: 1,
              option_text: 'Ja, godkänn den bokförda skatten.',
              option_value: 'approve_tax',
              next_step: 501,
              action_type: 'navigate',
              action_data: null
            },
            {
              option_order: 2,
              option_text: 'Låt mig se över justeringarna!',
              option_value: 'review_adjustments',
              next_step: 201,
              action_type: 'navigate',
              action_data: null
            }
          ]);
        }
        
        // Show the tax module (yellow section) when user wants to review adjustments
        onDataUpdate({ showTaxPreview: true });
      } else {
        // No tax data found, go directly to dividends
        loadChatStep(501);
      }
    }, 1000);
  };

  // Special handler for unused tax loss submission
  const handleUnusedTaxLossSubmission = async (amount: number) => {
    try {
      console.log('🔥 Handling unused tax loss submission:', amount);
      console.log('💰 Current companyData:', { 
        justeringSarskildLoneskatt: companyData.justeringSarskildLoneskatt,
        sarskildLoneskattPensionCalculated: companyData.sarskildLoneskattPensionCalculated,
        sarskildLoneskattPensionSubmitted: companyData.sarskildLoneskattPensionSubmitted
      });
      
      // Update company data with the amount
      onDataUpdate({ unusedTaxLossAmount: amount });

      // Trigger API recalculation to update INK4.14a and all dependent tax calculations
      if (companyData.seFileData) {
        // Calculate the correct pension tax adjustment value
        let pensionTaxAdjustment = 0;
        if (companyData.justeringSarskildLoneskatt === 'calculated') {
          pensionTaxAdjustment = companyData.sarskildLoneskattPensionCalculated || 0;
        } else if (companyData.justeringSarskildLoneskatt === 'custom') {
          pensionTaxAdjustment = companyData.sarskildLoneskattPensionSubmitted || 0;
        } else if (typeof companyData.justeringSarskildLoneskatt === 'number') {
          pensionTaxAdjustment = companyData.justeringSarskildLoneskatt;
        }
        
        console.log('📊 Recalculating with:', {
          ink4_14a_outnyttjat_underskott: amount,
          justering_sarskild_loneskatt: pensionTaxAdjustment
        });
        
        const result = await apiService.recalculateInk2({
          current_accounts: companyData.seFileData.current_accounts || {},
          fiscal_year: companyData.fiscalYear,
          rr_data: companyData.seFileData.rr_data || [],
          br_data: companyData.seFileData.br_data || [],
          manual_amounts: {}, // Keep manual_amounts separate
          ink4_14a_outnyttjat_underskott: amount, // Use the correct parameter
          justering_sarskild_loneskatt: pensionTaxAdjustment
        });
        
        if (result.success) {
          console.log('✅ Tax recalculation successful');
          console.log('📋 New INK2 data:', result.ink2_data);
          
          // Check if INK4.14a was updated
          const ink4_14a = result.ink2_data.find((item: any) => 
            item.variable_name === 'INK4.14a'
          );
          console.log('🔍 INK4.14a after recalculation:', ink4_14a);
          
          // Get the updated inkBeraknadSkatt value
          const updatedInkBeraknadSkatt = result.ink2_data.find((item: any) => 
            item.variable_name === 'INK_beraknad_skatt'
          )?.amount || companyData.inkBeraknadSkatt;
          
          console.log('💰 Updated inkBeraknadSkatt:', updatedInkBeraknadSkatt);
          console.log('🔍 Full INK2 data for debugging:', result.ink2_data.filter((item: any) => 
            item.variable_name === 'INK_beraknad_skatt' || 
            item.variable_name === 'INK_skattemassigt_resultat' ||
            item.variable_name === 'INK4.14a'
          ));
          
          // Store values in state to ensure they're always available
          setGlobalInk2Data(result.ink2_data);
          setGlobalInkBeraknadSkatt(updatedInkBeraknadSkatt);
          console.log('🌍 Stored in state - globalInkBeraknadSkatt:', updatedInkBeraknadSkatt);
          
          // Update the tax data in company state in a single call to prevent multiple updates
          onDataUpdate({
            ink2Data: result.ink2_data,
            inkBeraknadSkatt: updatedInkBeraknadSkatt,
            showTaxPreview: true
          });
          
          // Hide input and clear value
          setShowInput(false);
          setInputValue('');

          // Navigate to step 303 with the updated ink2Data
          console.log('🔄 Navigating to step 303 with updated inkBeraknadSkatt:', updatedInkBeraknadSkatt);
          loadChatStep(303, result.ink2_data);

        }
      }

      // Hide input and clear value (fallback)
      setShowInput(false);
      setInputValue('');

    } catch (error) {
      console.error('❌ Error handling unused tax loss:', error);
      addMessage('Något gick fel vid uppdatering av underskottet. Försök igen.', true, '❌');
    }
  };

  // Initialize chat on mount
  useEffect(() => {
    console.log('🚀 DatabaseDrivenChat initializing...');
    console.log('CompanyData:', companyData);
    
    // Only start if we have basic setup
    const initializeChat = async () => {
      try {
        // Fetch step 101 from database for consistency
        const response = await apiService.getChatFlowStep(101) as ChatFlowResponse;
        addMessage(response.question_text, true, response.question_icon);
        setShowFileUpload(true);
      } catch (error) {
        console.error('❌ Error initializing chat:', error);
        // Fallback to hardcoded message
        addMessage('Välkommen till Raketrapport! Ladda upp din SE-fil så börjar vi analysera din årsredovisning.', true, '👋');
        setShowFileUpload(true);
      }
    };
    
    initializeChat();
  }, []);

  // Auto-scroll when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <div className="flex flex-col h-full">
      {/* Chat Messages */}
      <div 
        ref={chatContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4 font-sans pt-20"
        style={{ fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif' }}
      >
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message.text}
            isBot={message.isBot}
            emoji={message.icon}
          />
        ))}
        
        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t bg-white p-4">
        {showFileUpload ? (
          <div className="space-y-4">
            <div className="text-center text-gray-600 mb-4">
              Ladda upp din SE-fil här:
            </div>
            <FileUpload onFileProcessed={handleFileProcessed} />
          </div>
        ) : showInput ? (
          <div className="flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleInputSubmit()}
              placeholder={inputPlaceholder}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <button
              onClick={handleInputSubmit}
              disabled={!inputValue.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Skicka
            </button>
          </div>
        ) : (
          /* Option Buttons */
          <div className="space-y-2">
            {currentOptions.map((option) => (
              <OptionButton
                key={option.option_order}
                onClick={() => handleOptionSelect(option)}
              >
                {option.option_text || ''}
              </OptionButton>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DatabaseDrivenChat;
