#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.supabase_service import SupabaseService

def create_tables():
    """Create chat flow tables manually"""
    
    # Initialize Supabase service
    supabase_service = SupabaseService()
    
    if not supabase_service.client:
        print("Error: Supabase client not available. Check your environment variables.")
        return False
    
    client = supabase_service.client
    
    try:
        # Insert chat flow questions
        chat_flow_data = [
            {
                "step_number": 10,
                "block_number": 10,
                "question_text": "Vilken typ av utdelning vill du göra?",
                "question_icon": "💰",
                "question_type": "options"
            },
            {
                "step_number": 20,
                "block_number": 20,
                "question_text": "Outnyttjat underskott från föregående år är det samlade beloppet av tidigare års skattemässiga förluster som ännu inte har kunnat kvittas mot vinster. Om företaget går med vinst ett senare år kan hela eller delar av det outnyttjade underskottet användas för att minska den beskattningsbara inkomsten och därmed skatten. Denna uppgift går inte att hämta från tidigare årsredovisningar utan behöver tas från årets förtryckta deklaration eller från förra årets inlämnade skattedeklaration. Klicka här för att se läsa mer hur man hämtar denna information. Vill du...",
                "question_icon": "📊",
                "question_type": "options"
            },
            {
                "step_number": 25,
                "block_number": 20,
                "question_text": "Outnyttjat underskott från föregående år har blivit uppdaterat med {unusedTaxLossAmount} kr. Vill du gå vidare?",
                "question_icon": "✅",
                "question_type": "options"
            },
            {
                "step_number": 30,
                "block_number": 30,
                "question_text": "Beräknad skatt efter skattemässiga justeringar är {inkBeraknadSkatt} kr. Vill du godkänna denna skatt eller vill du göra manuella ändringar? Eller vill du hellre att vi godkänner och använder den bokförda skatten?",
                "question_icon": "🏛️",
                "question_type": "options"
            }
        ]
        
        print("Inserting chat flow questions...")
        for question in chat_flow_data:
            try:
                result = client.table('chat_flow').upsert(question).execute()
                print(f"✅ Inserted question step {question['step_number']}")
            except Exception as e:
                print(f"❌ Error inserting question step {question['step_number']}: {e}")
        
        # Insert chat flow options
        options_data = [
            # Dividend type options (step 10)
            {"step_number": 10, "option_order": 1, "option_text": "Ordinarie utdelning", "option_value": "ordinary", "next_step": 20, "action_type": "set_variable", "action_data": {"variable": "dividendType", "value": "ordinary"}},
            {"step_number": 10, "option_order": 2, "option_text": "Förenklad utdelning", "option_value": "simplified", "next_step": 20, "action_type": "set_variable", "action_data": {"variable": "dividendType", "value": "simplified"}},
            {"step_number": 10, "option_order": 3, "option_text": "Kvalificerad utdelning", "option_value": "qualified", "next_step": 20, "action_type": "set_variable", "action_data": {"variable": "dividendType", "value": "qualified"}},
            
            # Unused tax loss options (step 20)
            {"step_number": 20, "option_order": 1, "option_text": "Finns inget outnyttjat underskott kvar", "option_value": "none", "next_step": 30, "action_type": "navigate", "action_data": None},
            {"step_number": 20, "option_order": 2, "option_text": "Ange belopp outnyttjat underskott", "option_value": "enter_amount", "next_step": 22, "action_type": "show_input", "action_data": {"input_type": "amount", "placeholder": "Ange belopp..."}},
            
            # Continue after unused tax loss (step 25)
            {"step_number": 25, "option_order": 1, "option_text": "Ja, gå vidare", "option_value": "continue", "next_step": 30, "action_type": "api_call", "action_data": {"endpoint": "recalculate_ink2", "params": {"ink4_16_underskott_adjustment": "{unusedTaxLossAmount}"}}},
            
            # Final tax question options (step 30)
            {"step_number": 30, "option_order": 1, "option_text": "Godkänn och använd beräknad skatt {inkBeraknadSkatt}", "option_value": "approve_calculated", "next_step": 40, "action_type": "set_variable", "action_data": {"variable": "finalTaxChoice", "value": "calculated"}},
            {"step_number": 30, "option_order": 2, "option_text": "Gör manuella ändringar i skattejusteringarna", "option_value": "manual_changes", "next_step": 35, "action_type": "enable_editing", "action_data": None},
            {"step_number": 30, "option_order": 3, "option_text": "Godkänn och använd bokförd skatt {inkBokfordSkatt}", "option_value": "approve_booked", "next_step": 40, "action_type": "set_variable", "action_data": {"variable": "finalTaxChoice", "value": "booked"}}
        ]
        
        print("\nInserting chat flow options...")
        for option in options_data:
            try:
                result = client.table('chat_flow_options').upsert(option).execute()
                print(f"✅ Inserted option for step {option['step_number']}: {option['option_text']}")
            except Exception as e:
                print(f"❌ Error inserting option for step {option['step_number']}: {e}")
        
        print("\n✅ All data inserted successfully!")
        return True
        
    except Exception as e:
        print(f'Error creating tables: {e}')
        return False

if __name__ == "__main__":
    success = create_tables()
    if success:
        print("\n🎉 Chat flow tables created and populated successfully!")
    else:
        print("\n💥 Failed to create chat flow tables!")
        sys.exit(1)
