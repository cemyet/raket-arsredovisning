import React, { useState, useEffect, useRef } from 'react';
import { apiService } from '@/services/api';
import { ChatMessage } from './ChatMessage';
import { OptionButton } from './OptionButton';

interface ChatFlowProps {
  companyData: any;
  onDataUpdate: (updates: Partial<any>) => void;
}

interface ChatStep {
  step_number: number;
  question_text: string;
  question_icon?: string;
  question_type: string;
  input_type?: string;
  input_placeholder?: string;
  show_conditions?: any;
}

interface ChatOption {
  option_order: number;
  option_text: string;
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

const DatabaseDrivenChat: React.FC<ChatFlowProps> = ({ companyData, onDataUpdate }) => {
  const [currentStep, setCurrentStep] = useState<number>(101); // Start with introduction
  const [currentQuestion, setCurrentQuestion] = useState<ChatStep | null>(null);
  const [currentOptions, setCurrentOptions] = useState<ChatOption[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [showInput, setShowInput] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [inputType, setInputType] = useState('text');
  const [inputPlaceholder, setInputPlaceholder] = useState('');
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
    
    // Create context from company data
    const fullContext = {
      ...context,
      ...companyData,
      unusedTaxLossAmount: companyData.unusedTaxLossAmount || 0,
      inkBeraknadSkatt: companyData.inkBeraknadSkatt || 0,
      inkBokfordSkatt: companyData.inkBokfordSkatt || 0,
      SkattAretsResultat: companyData.skattAretsResultat || 0,
      pension_premier: companyData.pensionPremier || 0,
      sarskild_loneskatt_pension: companyData.sarskildLoneskattPension || 0,
      sarskild_loneskatt_pension_calculated: companyData.sarskildLoneskattPensionCalculated || 0
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
  const loadChatStep = async (stepNumber: number) => {
    try {
      setIsLoading(true);
      console.log(`🔄 Loading step ${stepNumber}...`);
      
      const response = await apiService.getChatFlowStep(stepNumber);
      
      if (response.success) {
        setCurrentQuestion(response.question);
        setCurrentOptions(response.options);
        setCurrentStep(stepNumber);

        // Check if we should show this step based on conditions
        if (response.question.show_conditions) {
          const conditionsMet = evaluateConditions(response.question.show_conditions);
          if (!conditionsMet) {
            // Skip to next step
            const nextResponse = await apiService.getNextChatFlowStep(stepNumber);
            if (nextResponse.success && nextResponse.question) {
              return loadChatStep(nextResponse.question.step_number);
            }
            return;
          }
        }

        // Add question to chat
        const questionText = substituteVariables(response.question.question_text);
        addMessage(questionText, true, response.question.question_icon);

        // Handle different question types
        if (response.question.question_type === 'input') {
          setShowInput(true);
          setInputType(response.question.input_type || 'text');
          setInputPlaceholder(response.question.input_placeholder || '');
        } else {
          setShowInput(false);
        }
      } else {
        console.error('Failed to load step:', response);
        addMessage('Något gick fel. Försök igen.', true, '❌');
      }
    } catch (error) {
      console.error('Error loading chat step:', error);
      addMessage('Något gick fel. Försök igen.', true, '❌');
    } finally {
      setIsLoading(false);
    }
  };

  // Evaluate conditions for showing a step
  const evaluateConditions = (conditions: any): boolean => {
    if (!conditions) return true;

    // Simple condition evaluation
    for (const [key, condition] of Object.entries(conditions)) {
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
  };

  // Handle option selection
  const handleOptionSelect = async (option: ChatOption) => {
    try {
      // Add user message
      const optionText = substituteVariables(option.option_text);
      addMessage(optionText, false);

      // Handle special cases first
      if (option.option_value === 'continue_after_underskott') {
        // Navigate directly to the tax question step
        setTimeout(() => loadChatStep(601), 1000); // Step 601 is the tax approval question
        return;
      }

      // Process the choice through the API
      const context = {
        unusedTaxLossAmount: companyData.unusedTaxLossAmount || 0,
        inkBeraknadSkatt: companyData.inkBeraknadSkatt || 0,
        inkBokfordSkatt: companyData.inkBokfordSkatt || 0,
        SkattAretsResultat: companyData.skattAretsResultat || 0
      };

      const response = await apiService.processChatChoice({
        step_number: currentStep,
        option_value: option.option_value,
        context
      });

      if (response.success) {
        const { action_type, action_data, next_step } = response.result;

        // Handle different action types
        switch (action_type) {
          case 'set_variable':
            if (action_data?.variable && action_data?.value) {
              onDataUpdate({ [action_data.variable]: action_data.value });
            }
            break;
            
          case 'show_input':
            setShowInput(true);
            setInputType(action_data?.input_type || 'text');
            setInputPlaceholder(action_data?.placeholder || '');
            return; // Don't navigate to next step yet
            
          case 'api_call':
            await handleApiCall(action_data);
            break;
            
          case 'enable_editing':
            // Enable tax editing mode
            onDataUpdate({ taxEditingEnabled: true });
            break;
        }

        // Navigate to next step
        if (next_step) {
          setTimeout(() => loadChatStep(next_step), 1000);
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
        
        if (companyData.seFileData) {
          const result = await apiService.recalculateInk2({
            current_accounts: companyData.seFileData.current_accounts || {},
            fiscal_year: companyData.fiscalYear,
            rr_data: companyData.seFileData.rr_data || [],
            br_data: companyData.seFileData.br_data || [],
            manual_amounts: {},
            ...params
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

    // Add user message
    const displayValue = inputType === 'amount' 
      ? new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value as number) + ' kr'
      : value;
    addMessage(displayValue, false);

    // Find the submit option for this step
    const submitOption = currentOptions.find(opt => opt.option_value === 'submit');
    if (submitOption) {
      // Store the input value based on action data
      if (submitOption.action_data?.variable) {
        onDataUpdate({ [submitOption.action_data.variable]: value });

        // Special handling for unused tax loss (outnyttjat underskott)
        if (submitOption.action_data.variable === 'unusedTaxLossAmount') {
          await handleUnusedTaxLossSubmission(value as number);
        }
      }

      // Navigate to next step (unless we're handling special cases)
      if (submitOption.next_step && submitOption.action_data?.variable !== 'unusedTaxLossAmount') {
        setShowInput(false);
        setInputValue('');
        setTimeout(() => loadChatStep(submitOption.next_step!), 500);
      }
    }
  };

  // Special handler for unused tax loss submission
  const handleUnusedTaxLossSubmission = async (amount: number) => {
    try {
      console.log('🔥 Handling unused tax loss submission:', amount);
      
      // Update company data with the amount
      onDataUpdate({ unusedTaxLossAmount: amount });

      // Trigger API recalculation to update INK4.14a and all dependent tax calculations
      if (companyData.seFileData) {
        const result = await apiService.recalculateInk2({
          current_accounts: companyData.seFileData.current_accounts || {},
          fiscal_year: companyData.fiscalYear,
          rr_data: companyData.seFileData.rr_data || [],
          br_data: companyData.seFileData.br_data || [],
          manual_amounts: {}, // Keep manual_amounts separate
          ink4_14a_outnyttjat_underskott: amount, // Use the correct parameter
          justering_sarskild_loneskatt: companyData.justeringSarskildLoneskatt || 0
        });
        
        if (result.success) {
          console.log('✅ Tax recalculation successful');
          
          // Update the tax data in company state
          onDataUpdate({
            ink2Data: result.ink2_data,
            inkBeraknadSkatt: result.ink2_data.find((item: any) => 
              item.variable_name === 'INK_beraknad_skatt'
            )?.amount || companyData.inkBeraknadSkatt
          });

          // Show the tax preview by updating a flag
          onDataUpdate({ showTaxPreview: true });
        }
      }

      // Hide input and clear value
      setShowInput(false);
      setInputValue('');

      // Show confirmation message after a short delay
      setTimeout(() => {
        const formattedAmount = new Intl.NumberFormat('sv-SE', { 
          minimumFractionDigits: 0, 
          maximumFractionDigits: 0 
        }).format(amount);
        
        addMessage(
          `Outnyttjat underskott från föregående år har blivit uppdaterat med ${formattedAmount} kr. Vill du gå vidare?`, 
          true, 
          '✅'
        );

        // Set up the "Ja, gå vidare" option
        setCurrentOptions([{
          option_order: 1,
          option_text: 'Ja, gå vidare',
          option_value: 'continue_after_underskott',
          next_step: 601, // Go to tax question step
          action_type: 'navigate',
          action_data: null
        }]);
        
      }, 1000);

    } catch (error) {
      console.error('❌ Error handling unused tax loss:', error);
      addMessage('Något gick fel vid uppdatering av underskottet. Försök igen.', true, '❌');
    }
  };

  // Initialize chat on mount
  useEffect(() => {
    loadChatStep(101); // Start with introduction
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
        className="flex-1 overflow-y-auto p-4 space-y-4"
        style={{ maxHeight: 'calc(100vh - 200px)' }}
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
        {showInput ? (
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
              className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
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
                {substituteVariables(option.option_text)}
              </OptionButton>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DatabaseDrivenChat;
