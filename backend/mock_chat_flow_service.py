#!/usr/bin/env python3

"""
Mock Chat Flow Service - demonstrates how database-driven conversation flow would work
"""

class MockChatFlowService:
    def __init__(self):
        # Mock data that would normally come from Supabase
        self.chat_flow_questions = {
            10: {
                "step_number": 10,
                "block_number": 10,
                "question_text": "Vilken typ av utdelning vill du göra?",
                "question_icon": "💰",
                "question_type": "options"
            },
            20: {
                "step_number": 20,
                "block_number": 20,
                "question_text": "Outnyttjat underskott från föregående år är det samlade beloppet av tidigare års skattemässiga förluster som ännu inte har kunnat kvittas mot vinster. Om företaget går med vinst ett senare år kan hela eller delar av det outnyttjade underskottet användas för att minska den beskattningsbara inkomsten och därmed skatten. Denna uppgift går inte att hämta från tidigare årsredovisningar utan behöver tas från årets förtryckta deklaration eller från förra årets inlämnade skattedeklaration. Klicka här för att se läsa mer hur man hämtar denna information. Vill du...",
                "question_icon": "📊",
                "question_type": "options"
            },
            22: {
                "step_number": 22,
                "block_number": 20,
                "question_text": "Ange belopp outnyttjat underskott:",
                "question_icon": "",
                "question_type": "input",
                "input_type": "amount",
                "input_placeholder": "Ange belopp..."
            },
            25: {
                "step_number": 25,
                "block_number": 20,
                "question_text": "Outnyttjat underskott från föregående år har blivit uppdaterat med {unusedTaxLossAmount} kr. Vill du gå vidare?",
                "question_icon": "✅",
                "question_type": "options"
            },
            30: {
                "step_number": 30,
                "block_number": 30,
                "question_text": "Beräknad skatt efter skattemässiga justeringar är {inkBeraknadSkatt} kr. Vill du godkänna denna skatt eller vill du göra manuella ändringar? Eller vill du hellre att vi godkänner och använder den bokförda skatten?",
                "question_icon": "🏛️",
                "question_type": "options"
            }
        }
        
        self.chat_flow_options = {
            10: [
                {"option_order": 1, "option_text": "Ordinarie utdelning", "option_value": "ordinary", "next_step": 20, "action_type": "set_variable", "action_data": {"variable": "dividendType", "value": "ordinary"}},
                {"option_order": 2, "option_text": "Förenklad utdelning", "option_value": "simplified", "next_step": 20, "action_type": "set_variable", "action_data": {"variable": "dividendType", "value": "simplified"}},
                {"option_order": 3, "option_text": "Kvalificerad utdelning", "option_value": "qualified", "next_step": 20, "action_type": "set_variable", "action_data": {"variable": "dividendType", "value": "qualified"}}
            ],
            20: [
                {"option_order": 1, "option_text": "Finns inget outnyttjat underskott kvar", "option_value": "none", "next_step": 30, "action_type": "navigate", "action_data": None},
                {"option_order": 2, "option_text": "Ange belopp outnyttjat underskott", "option_value": "enter_amount", "next_step": 22, "action_type": "show_input", "action_data": {"input_type": "amount", "placeholder": "Ange belopp..."}}
            ],
            22: [
                {"option_order": 1, "option_text": "Skicka", "option_value": "submit", "next_step": 25, "action_type": "process_input", "action_data": {"variable": "unusedTaxLossAmount"}}
            ],
            25: [
                {"option_order": 1, "option_text": "Ja, gå vidare", "option_value": "continue", "next_step": 30, "action_type": "api_call", "action_data": {"endpoint": "recalculate_ink2", "params": {"ink4_16_underskott_adjustment": "{unusedTaxLossAmount}"}}}
            ],
            30: [
                {"option_order": 1, "option_text": "Godkänn och använd beräknad skatt {inkBeraknadSkatt}", "option_value": "approve_calculated", "next_step": 40, "action_type": "set_variable", "action_data": {"variable": "finalTaxChoice", "value": "calculated"}},
                {"option_order": 2, "option_text": "Gör manuella ändringar i skattejusteringarna", "option_value": "manual_changes", "next_step": 35, "action_type": "enable_editing", "action_data": None},
                {"option_order": 3, "option_text": "Godkänn och använd bokförd skatt {inkBokfordSkatt}", "option_value": "approve_booked", "next_step": 40, "action_type": "set_variable", "action_data": {"variable": "finalTaxChoice", "value": "booked"}}
            ]
        }
    
    def get_step(self, step_number: int):
        """Get a specific chat flow step with its options"""
        question = self.chat_flow_questions.get(step_number)
        if not question:
            return None
        
        options = self.chat_flow_options.get(step_number, [])
        
        return {
            "success": True,
            "question": question,
            "options": options
        }
    
    def get_next_step(self, current_step: int):
        """Get the next step in sequence"""
        # Find the next step number greater than current_step
        next_steps = [step for step in self.chat_flow_questions.keys() if step > current_step]
        
        if not next_steps:
            return {"success": True, "next_step": None}  # End of flow
        
        next_step = min(next_steps)
        return self.get_step(next_step)
    
    def process_user_choice(self, step_number: int, option_value: str, context: dict = None):
        """Process user choice and determine next action"""
        options = self.chat_flow_options.get(step_number, [])
        selected_option = next((opt for opt in options if opt["option_value"] == option_value), None)
        
        if not selected_option:
            return {"error": "Invalid option"}
        
        action_type = selected_option.get("action_type")
        action_data = selected_option.get("action_data", {})
        next_step = selected_option.get("next_step")
        
        result = {
            "action_type": action_type,
            "action_data": action_data,
            "next_step": next_step
        }
        
        # Process variable substitution
        if context:
            result = self._substitute_variables(result, context)
        
        return result
    
    def _substitute_variables(self, data, context):
        """Replace {variable} placeholders with actual values"""
        import json
        data_str = json.dumps(data)
        
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if isinstance(value, (int, float)):
                # Format numbers with Swedish locale
                formatted_value = f"{value:,.0f}".replace(',', ' ')
                data_str = data_str.replace(placeholder, formatted_value)
            else:
                data_str = data_str.replace(placeholder, str(value))
        
        return json.loads(data_str)

# Example usage
if __name__ == "__main__":
    service = MockChatFlowService()
    
    # Get step 20 (unused tax loss question)
    step_20 = service.get_step(20)
    print("Step 20:", step_20)
    
    # Process user choosing "enter_amount"
    choice_result = service.process_user_choice(20, "enter_amount")
    print("Choice result:", choice_result)
    
    # Get step 25 with context
    context = {"unusedTaxLossAmount": 50000}
    step_25 = service.get_step(25)
    step_25 = service._substitute_variables(step_25, context)
    print("Step 25 with context:", step_25)
