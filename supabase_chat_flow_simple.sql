-- =====================================================
-- Chat Flow Tables for Raketrapport - CORRECTED VERSION
-- Follows the exact old flow with corrected outnyttjat underskott
-- Run this script in Supabase SQL Editor
-- =====================================================

-- Create chat_flow table for managing conversation steps
CREATE TABLE IF NOT EXISTS public.chat_flow (
    id SERIAL PRIMARY KEY,
    step_number INTEGER NOT NULL UNIQUE,
    block_number INTEGER NOT NULL,
    subblock_number INTEGER, -- For organizing within blocks
    question_text TEXT NOT NULL,
    question_icon TEXT,
    question_type VARCHAR(50) DEFAULT 'options', -- 'options', 'input', 'info', 'message'
    input_type VARCHAR(50), -- 'number', 'text', 'amount' (for input questions)
    input_placeholder TEXT,
    -- Direct option columns for up to 4 options
    option1_text TEXT,
    option1_value TEXT,
    option1_next_step INTEGER,
    option1_action_type VARCHAR(50),
    option1_action_data JSONB,
    option2_text TEXT,
    option2_value TEXT,
    option2_next_step INTEGER,
    option2_action_type VARCHAR(50),
    option2_action_data JSONB,
    option3_text TEXT,
    option3_value TEXT,
    option3_next_step INTEGER,
    option3_action_type VARCHAR(50),
    option3_action_data JSONB,
    option4_text TEXT,
    option4_value TEXT,
    option4_next_step INTEGER,
    option4_action_type VARCHAR(50),
    option4_action_data JSONB,
    -- Conditions for showing this question/message
    show_conditions JSONB, -- Conditions that must be met to show this step
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create chat_flow_options table for backwards compatibility
CREATE TABLE IF NOT EXISTS public.chat_flow_options (
    id SERIAL PRIMARY KEY,
    step_number INTEGER NOT NULL REFERENCES public.chat_flow(step_number),
    option_order INTEGER NOT NULL,
    option_text TEXT NOT NULL,
    option_value TEXT NOT NULL,
    next_step INTEGER,
    action_type VARCHAR(50),
    action_data JSONB,
    conditions JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_chat_flow_step_number ON public.chat_flow(step_number);
CREATE INDEX IF NOT EXISTS idx_chat_flow_block_number ON public.chat_flow(block_number);
CREATE INDEX IF NOT EXISTS idx_chat_flow_subblock_number ON public.chat_flow(subblock_number);
CREATE INDEX IF NOT EXISTS idx_chat_flow_block_subblock ON public.chat_flow(block_number, subblock_number);
CREATE INDEX IF NOT EXISTS idx_chat_flow_options_step ON public.chat_flow_options(step_number);
CREATE INDEX IF NOT EXISTS idx_chat_flow_options_order ON public.chat_flow_options(step_number, option_order);

-- Enable RLS
ALTER TABLE public.chat_flow ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_flow_options ENABLE ROW LEVEL SECURITY;

-- Create policies (allow all for now, can be restricted later)
DROP POLICY IF EXISTS "Allow all operations on chat_flow" ON public.chat_flow;
CREATE POLICY "Allow all operations on chat_flow" ON public.chat_flow
    FOR ALL USING (true);

DROP POLICY IF EXISTS "Allow all operations on chat_flow_options" ON public.chat_flow_options;
CREATE POLICY "Allow all operations on chat_flow_options" ON public.chat_flow_options
    FOR ALL USING (true);

-- =====================================================
-- Insert conversation flow data - ONE ROW AT A TIME
-- =====================================================

-- BLOCK 10: Introduction and SE File Upload
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(101, 10, 'Välkommen till Raketrapport! Jag kommer att guida dig genom att skapa din årsredovisning steg för steg.', '👋', 'message', 'Fortsätt', 'continue', 102, 'navigate');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(102, 10, 'Har du en SE-fil från ditt redovisningsprogram?', '📁', 'options', 'Ja, jag har en SE-fil', 'use_se_file', 103, 'show_file_upload', 'Nej, jag vill ange information manuellt', 'manual_input', 104, 'navigate');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(103, 10, 'Bra! Ladda upp din .SE fil så analyserar jag den åt dig. 📁', '📤', 'file_upload', 'file', NULL, 'Ladda upp SE-fil', 'upload', 105, 'process_se_file');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(104, 10, 'Låt oss börja! Första frågan: Vad blev årets resultat?', '💰', 'message', 'Fortsätt', 'continue', 105, 'navigate');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(105, 10, 'Vad blev årets resultat?', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 201, 'process_input', '{"variable": "result"}');

-- BLOCK 20: Tax Calculations
-- Subblock 30: Pension Tax Check (FIRST)
INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data, option3_text, option3_value, option3_next_step, option3_action_type, option3_action_data, show_conditions) VALUES
(201, 20, 30, 'Innan vi fortsätter med skatteuträkningen vill jag göra dig uppmärksam på att särskild löneskatt på pensionförsäkringspremier inte verkar vara bokförd. Inbetalda pensionförsäkringspremier under året uppgår till {pension_premier} och den särskilda löneskatten borde uppgå till {sarskild_loneskatt_pension_calculated} men endast {sarskild_loneskatt_pension} verkar vara bokfört. Vill du att vi justerar den särskilda löneskatten och därmed årets resultat enligt våra beräkningar?', '⚠️', 'options', 'Justera särskild löneskatt till {sarskild_loneskatt_pension_calculated} kr', 'adjust_calculated', 202, 'set_variable', '{"variable": "justeringSarskildLoneskatt", "value": "calculated"}', 'Behåll nuvarande bokförd särskild löneskatt {sarskild_loneskatt_pension}', 'keep_current', 301, 'set_variable', '{"variable": "justeringSarskildLoneskatt", "value": "current"}', 'Ange belopp för egen särskild löneskatt', 'enter_custom', 203, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}', '{"pension_premier": {"gt": 0}, "sarskild_loneskatt_pension_calculated": {"gt": "sarskild_loneskatt_pension"}}');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(202, 20, 30, 'Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkning till höger.', '✅', 'message', 'Fortsätt', 'continue', 301, 'navigate');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(203, 20, 30, 'Ange belopp för särskild löneskatt:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 202, 'process_input', '{"variable": "sarskildLoneskattCustom"}');

-- Subblock 40: Outnyttjat underskott (SECOND)
INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data) VALUES
(301, 20, 40, 'Outnyttjat underskott från föregående år är det samlade beloppet av tidigare års skattemässiga förluster som ännu inte har kunnat kvittas mot vinster. Om företaget går med vinst ett senare år kan hela eller delar av det outnyttjade underskottet användas för att minska den beskattningsbara inkomsten och därmed skatten. Denna uppgift går inte att hämta från tidigare årsredovisningar utan behöver tas från årets förtryckta deklaration eller från förra årets inlämnade skattedeklaration. Vill du...', '📊', 'options', 'Finns inget outnyttjat underskott kvar', 'none', 401, 'navigate', 'Ange belopp outnyttjat underskott', 'enter_amount', 302, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(302, 20, 40, 'Ange belopp outnyttjat underskott:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 303, 'process_input', '{"variable": "unusedTaxLossAmount"}');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(303, 20, 40, 'Outnyttjat underskott från föregående år har blivit uppdaterat med {unusedTaxLossAmount} kr. Vill du gå vidare?', '✅', 'options', 'Ja, gå vidare', 'continue', 401, 'api_call', '{"endpoint": "recalculate_ink2", "params": {"ink4_14a_outnyttjat_underskott": "{unusedTaxLossAmount}"}}');

-- Subblock 50: Final Tax Approval (THIRD)
INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data, option3_text, option3_value, option3_next_step, option3_action_type, option3_action_data) VALUES
(401, 20, 50, 'Beräknad skatt efter skattemässiga justeringar är {inkBeraknadSkatt} kr. Vill du godkänna denna skatt eller vill du göra manuella ändringar? Eller vill du hellre att vi godkänner och använder den bokförda skatten?', '🧮', 'options', 'Godkänn och använd beräknad skatt {inkBeraknadSkatt}', 'approve_calculated', 501, 'set_variable', '{"variable": "finalTaxChoice", "value": "calculated"}', 'Gör manuella ändringar i skattejusteringarna', 'manual_changes', 402, 'enable_editing', 'Godkänn och använd bokförd skatt {inkBokfordSkatt}', 'approve_booked', 501, 'set_variable', '{"variable": "finalTaxChoice", "value": "booked"}');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(402, 20, 50, 'Du kan nu redigera skattemässiga justeringar. Klicka på "Godkänn och uppdatera skatt" när du är klar.', '✏️', 'message', 'Godkänn och uppdatera skatt', 'update_tax', 501, 'save_manual_tax', 'Ångra ändringar', 'undo_changes', 401, 'reset_tax_edits');

-- BLOCK 30: Dividends
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data, option3_text, option3_value, option3_next_step, option3_action_type, option3_action_data, option4_text, option4_value, option4_next_step, option4_action_type, option4_action_data) VALUES
(501, 30, 'Vill ni göra någon utdelning av vinsten?', '💰', 'options', '0 kr utdelning', '0', 601, 'set_variable', '{"variable": "dividend", "value": "0"}', 'Ordinarie utdelning', 'ordinary', 601, 'set_variable', '{"variable": "dividend", "value": "ordinary"}', 'Förenklad utdelning', 'simplified', 601, 'set_variable', '{"variable": "dividend", "value": "simplified"}', 'Ange eget belopp', 'custom', 502, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(502, 30, 'Ange belopp för utdelning:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 601, 'process_input', '{"variable": "customDividend"}');

-- BLOCK 40: Significant Events
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(601, 40, 'Har något särskilt hänt i verksamheten under året?', '📋', 'options', 'Nej, inget särskilt', 'no_events', 701, 'set_variable', '{"variable": "hasEvents", "value": false}', 'Ja, det har hänt saker', 'has_events', 602, 'show_input', '{"input_type": "text", "placeholder": "Beskriv vad som hänt..."}');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(602, 40, 'Beskriv vad som hänt under året:', '✍️', 'input', 'text', 'Beskriv händelser...', 'Skicka', 'submit', 701, 'process_input', '{"variable": "significantEvents"}');

-- BLOCK 50: Depreciation
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(701, 50, 'Vill du behålla avskrivningarna som de är eller vill du justera dem?', '📉', 'options', 'Behåll som de är', 'keep_depreciation', 801, 'navigate', 'Justera avskrivningar', 'adjust_depreciation', 702, 'show_input', '{"input_type": "text", "placeholder": "Beskriv justeringar..."}');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(702, 50, 'Beskriv vilka justeringar du vill göra:', '✍️', 'input', 'text', 'Beskriv justeringar...', 'Skicka', 'submit', 801, 'process_input', '{"variable": "depreciation"}');

-- BLOCK 60: Employees
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type, option3_text, option3_value, option3_next_step, option3_action_type) VALUES
(801, 60, 'Hur många anställda har företaget?', '👥', 'options', '0 anställda', '0', 901, 'set_variable', '{"variable": "employees", "value": 0}', '1-10 anställda', '1-10', 901, 'set_variable', '{"variable": "employees", "value": "1-10"}', 'Fler än 10 anställda', '10+', 901, 'set_variable', '{"variable": "employees", "value": "10+"}');

-- BLOCK 70: Final Details
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(901, 70, 'Perfekt! Nu går vi vidare. Har något särskilt hänt i verksamheten under året?', '📋', 'message', 'Fortsätt', 'continue', 1001, 'navigate');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(1001, 70, 'Årsredovisningen är nu klar! Vill du ladda ner den som PDF?', '📄', 'options', 'Ja, ladda ner PDF', 'download_pdf', 1002, 'generate_pdf', 'Nej, avsluta', 'finish', 1003, 'complete_session');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(1002, 70, 'PDF har skapats och laddats ner. Tack för att du använde Raketrapport! 🚀', '🎉', 'message', 'Avsluta', 'finish', 1003, 'complete_session');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_action_type) VALUES
(1003, 70, 'Grattis! Din årsredovisning är nu klar. Tack för att du använde Raketrapport! 🚀', '🎉', 'message', 'complete_session');

-- =====================================================
-- Verification queries (uncomment to run after)
-- =====================================================

-- SELECT 'chat_flow table' as table_name, count(*) as rows FROM public.chat_flow;

-- SELECT 
--     block_number,
--     subblock_number,
--     COUNT(*) as steps,
--     CASE block_number
--         WHEN 10 THEN 'Introduction and SE File'
--         WHEN 20 THEN 'Tax Calculations'
--         WHEN 30 THEN 'Dividends'
--         WHEN 40 THEN 'Significant Events'
--         WHEN 50 THEN 'Depreciation'
--         WHEN 60 THEN 'Employees'
--         WHEN 70 THEN 'Final Details'
--         ELSE 'Unknown block'
--     END as block_name
-- FROM public.chat_flow 
-- GROUP BY block_number, subblock_number
-- ORDER BY block_number, subblock_number;
