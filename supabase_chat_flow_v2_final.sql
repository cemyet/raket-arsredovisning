-- Chat Flow V2 - Final Create Script
-- Based on chat_flow v2.csv structure with no_option support

-- Create the new table with the correct v2 structure
CREATE TABLE public.chat_flow (
    id SERIAL PRIMARY KEY,
    step_number INTEGER UNIQUE NOT NULL,
    block VARCHAR(50),
    question_text TEXT NOT NULL,
    question_icon VARCHAR(10),
    question_type VARCHAR(20) NOT NULL,
    input_type VARCHAR(20),
    input_placeholder TEXT,
    no_option_value VARCHAR(100),
    no_option_next_step INTEGER,
    no_option_action_type VARCHAR(50),
    no_option_action_data JSONB,
    option1_text TEXT,
    option1_value VARCHAR(100),
    option1_next_step INTEGER,
    option1_action_type VARCHAR(50),
    option1_action_data JSONB,
    option2_text TEXT,
    option2_value VARCHAR(100),
    option2_next_step INTEGER,
    option2_action_type VARCHAR(50),
    option2_action_data JSONB,
    option3_text TEXT,
    option3_value VARCHAR(100),
    option3_next_step INTEGER,
    option3_action_type VARCHAR(50),
    option3_action_data JSONB,
    option4_text TEXT,
    option4_value VARCHAR(100),
    option4_next_step INTEGER,
    option4_action_type VARCHAR(50),
    option4_action_data JSONB,
    show_conditions JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert data from chat_flow v2.csv
INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, no_option_value, no_option_next_step, no_option_action_type) VALUES
(101, 'INTRO', '🚀 Hej! Välkommen till RaketRapport! Jag hjälper dig att skapa och ladda upp din årsredovisning på bara ett par minuter.📁 Ladda upp din .SE fil från bokföringsprogrammet för att automatiskt skapa din årsredovisning.', '', 'message', 'upload_se_file', 102, 'show_file_upload');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, no_option_value, no_option_next_step, no_option_action_type) VALUES
(102, 'INTRO', 'Perfekt! Resultatrapport och balansräkning är nu skapad från SE-filen.', '✅', 'message', 'continue', 103, 'navigate');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, no_option_value, no_option_next_step, no_option_action_type) VALUES
(103, 'INTRO', 'Årets resultat är: {SumAretsResultat}. Se fullständig resultat- och balans rapport i preview fönstret till höger.', '💰', 'message', 'continue', 104, 'navigate');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(104, 'INTRO', 'Den bokförda skatten är {SkattAretsResultat} kr. Vill du godkänna den eller vill du se över de skattemässiga justeringarna?', '🏛️', 'options', 'Ja, godkänn den bokförda skatten.', 'continue', 501, 'navigate', 'Låt mig se över justeringarna!', 'continue', 201, 'navigate');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data, option3_text, option3_value, option3_next_step, option3_action_type, option3_action_data, show_conditions) VALUES
(201, 'PENSION', 'Det verkar som att särskild löneskatt på pensionförsäkringspremier inte verkar vara bokförd. Inbetalda pensionförsäkringspremier under året uppgår till {pension_premier} och den särskilda löneskatten borde uppgå till {sarskild_loneskatt_pension_calculated}, men endast {sarskild_loneskatt_pension} verkar vara bokfört. Vill du att vi justerar den särskilda löneskatten och därmed årets resultat enligt våra beräkningar?', '⚠️', 'options', 'Justera särskild löneskatt till {sarskild_loneskatt_pension_calculated} kr', 'adjust_calculated', 202, 'set_variable', '{"variable": "justeringSarskildLoneskatt", "value": "calculated"}', 'Behåll nuvarande bokförd särskild löneskatt {sarskild_loneskatt_pension}', 'keep_current', 301, 'set_variable', '{"variable": "justeringSarskildLoneskatt", "value": "current"}', 'Ange belopp för egen särskild löneskatt', 'enter_custom', 203, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}', '{"pension_premier": {"gt": 0}, "sarskild_loneskatt_pension_calculated": {"gt": "sarskild_loneskatt_pension"}}');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, no_option_value, no_option_next_step, no_option_action_type) VALUES
(202, 'PENSION', 'Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkningen till höger.', '✅', 'message', 'continue', 301, 'navigate');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(203, 'PENSION', 'Ange belopp för särskild löneskatt:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 202, 'process_input', '{"variable": "sarskildLoneskattCustom"}');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data) VALUES
(301, 'UNDERSKOTT', 'Outnyttjat underskott från föregående år är det samlade beloppet av tidigare års skattemässiga förluster som ännu inte har kunnat kvittas mot vinster. Om företaget går med vinst ett senare år kan hela eller delar av det outnyttjade underskottet användas för att minska den beskattningsbara inkomsten och därmed skatten. Denna uppgift går inte att hämta från tidigare årsredovisningar utan behöver tas från årets förtryckta deklaration eller från förra årets inlämnade skattedeklaration. Vill du...', '📊', 'options', 'Finns inget outnyttjat underskott kvar', 'none', 401, 'navigate', 'Ange belopp outnyttjat underskott', 'enter_amount', 302, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(302, 'UNDERSKOTT', 'Ange belopp outnyttjat underskott:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 303, 'process_input', '{"variable": "unusedTaxLossAmount"}');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(303, 'UNDERSKOTT', 'Outnyttjat underskott från föregående år har blivit uppdaterat med {unusedTaxLossAmount} kr, som du kan se i skatteuträkningen till höger.', '✅', 'options', 'continue', 401, 'api_call', '{"params": {"ink4_14a_outnyttjat_underskott": "{unusedTaxLossAmount}"}, "endpoint": "recalculate_ink2"}');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option3_text, option3_value, option3_next_step, option3_action_type, option3_action_data) VALUES
(401, 'SLUTSKATT', 'Beräknad skatt efter skattemässiga justeringar är {inkBeraknadSkatt} kr. Vill du godkänna denna skatt eller vill du göra manuella justeringar? Eller vill du hellre att vi godkänner och använder den bokförda skatten?', '🧮', 'options', 'Godkänn och använd beräknad skatt {inkBeraknadSkatt}', 'approve_calculated', 405, 'set_variable', '{"variable": "finalTaxChoice", "value": "calculated"}', 'Gör manuella ändringar i skattejusteringarna', 'manual_changes', 402, 'enable_editing', 'Godkänn och använd bokförd skatt {inkBokfordSkatt}', 'approve_booked', 405, 'set_variable', '{"variable": "finalTaxChoice", "value": "booked"}');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(402, 'SLUTSKATT', 'Du kan nu redigera skattemässiga justeringar. Klicka på "Godkänn och uppdatera skatt" när du är klar.', '✏️', 'message', 'Godkänn och uppdatera skatt', 'update_tax', 405, 'save_manual_tax', 'Ångra ändringar', 'undo_changes', 401, 'reset_tax_edits');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, no_option_value, no_option_next_step, no_option_action_type) VALUES
(405, 'SLUTSKATT', 'Perfekt! Nu är årets skatt beräknat och vi har även ett slutgiltigt årets resultat och vi kan gå vidare!', '✅', 'message', 'continue', 501, 'navigate');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data, option3_text, option3_value, option3_next_step, option3_action_type, option3_action_data) VALUES
(501, 'UTDELNING', 'Perfekt! Vill ni göra någon utdelning av vinsten?', '💰', 'options', '0 kr utdelning', '0', 505, 'set_variable', '{"variable": "dividend", "value": "0"}', 'Hela årets vinst {SumAretsResultat}', 'full_profit', 505, 'set_variable', '{"variable": "dividend", "value": "full_profit"}', 'Ange eget belopp', 'custom', 502, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(502, 'UTDELNING', 'Ange belopp för utdelning:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 505, 'process_input', '{"variable": "customDividend"}');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, no_option_value, no_option_next_step, no_option_action_type) VALUES
(505, 'UTDELNING', 'Perfekt! Då har vi bestämt hur utdelningsbara medel ska disponeras och kan gå vidare med att färdigställa förvaltningsberättelsen.', '✅', 'message', 'continue', 601, 'navigate');

INSERT INTO public.chat_flow (step_number, block, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data) VALUES
(601, 'FB', 'Har något särskilt hänt i verksamheten under året?', '📋', 'options', 'Nej, inget särskilt', 'no_events', 701, 'set_variable', '{"variable": "hasEvents", "value": false}', 'Ja, det har hänt saker', 'has_events', 602, 'show_input', '{"input_type": "text", "placeholder": "Beskriv vad som hänt..."}');

-- Create indexes for better performance
CREATE INDEX idx_chat_flow_step_number ON public.chat_flow(step_number);
CREATE INDEX idx_chat_flow_block ON public.chat_flow(block);

-- Enable Row Level Security (RLS)
ALTER TABLE public.chat_flow ENABLE ROW LEVEL SECURITY;

-- Create policy to allow all operations
CREATE POLICY "Allow all operations on chat_flow" ON public.chat_flow
    FOR ALL USING (true);
