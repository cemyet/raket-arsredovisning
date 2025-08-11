-- =====================================================
-- Chat Flow Tables for Raketrapport - SIMPLIFIED VERSION
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

-- BLOCK 10: Introduction
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(101, 10, 'Välkommen till Raketrapport! Jag kommer att guida dig genom att skapa din årsredovisning steg för steg.', '👋', 'message', 'Fortsätt', 'continue', 102, 'navigate');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(102, 10, 'Först behöver jag veta vilket typ av företag det är och vilken typ av utdelning du vill göra.', '📋', 'message', 'Fortsätt', 'continue', 103, 'navigate');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data, option3_text, option3_value, option3_next_step, option3_action_type, option3_action_data) VALUES
(103, 10, 'Vilken typ av utdelning vill du göra?', '💰', 'options', 'Ordinarie utdelning', 'ordinary', 301, 'set_variable', '{"variable": "dividendType", "value": "ordinary"}', 'Förenklad utdelning', 'simplified', 301, 'set_variable', '{"variable": "dividendType", "value": "simplified"}', 'Kvalificerad utdelning', 'qualified', 301, 'set_variable', '{"variable": "dividendType", "value": "qualified"}');

-- BLOCK 20: Tax block - Subblock 30: Särskild löneskatt
INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data, option3_text, option3_value, option3_next_step, option3_action_type, option3_action_data, show_conditions) VALUES
(301, 20, 30, 'Innan vi fortsätter med skatteuträkningen vill jag göra dig uppmärksam på att särskild löneskatt på pensionförsäkringspremier inte verkar vara bokförd. Inbetalda pensionförsäkringspremier under året uppgår till {pension_premier} och den särskilda löneskatten borde uppgå till {sarskild_loneskatt_pension_calculated} men endast {sarskild_loneskatt_pension} verkar vara bokfört. Vill du att vi justerar den särskilda löneskatten och därmed årets resultat enligt våra beräkningar?', '⚠️', 'options', 'Justera särskild löneskatt till {sarskild_loneskatt_pension_calculated} kr', 'adjust_calculated', 302, 'set_variable', '{"variable": "justeringSarskildLoneskatt", "value": "calculated"}', 'Behåll nuvarande bokförd särskild löneskatt {sarskild_loneskatt_pension}', 'keep_current', 401, 'set_variable', '{"variable": "justeringSarskildLoneskatt", "value": "current"}', 'Ange belopp för egen särskild löneskatt', 'enter_custom', 303, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}', '{"pension_premier": {"gt": 0}, "sarskild_loneskatt_pension_calculated": {"gt": "sarskild_loneskatt_pension"}}');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(302, 20, 30, 'Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkning till höger.', '✅', 'message', 'Fortsätt', 'continue', 401, 'navigate');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(303, 20, 30, 'Ange belopp för särskild löneskatt:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 302, 'process_input', '{"variable": "sarskildLoneskattCustom"}');

-- Subblock 40: Outnyttjat underskott
INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data) VALUES
(401, 20, 40, 'Outnyttjat underskott från föregående år är det samlade beloppet av tidigare års skattemässiga förluster som ännu inte har kunnat kvittas mot vinster. Om företaget går med vinst ett senare år kan hela eller delar av det outnyttjade underskottet användas för att minska den beskattningsbara inkomsten och därmed skatten. Denna uppgift går inte att hämta från tidigare årsredovisningar utan behöver tas från årets förtryckta deklaration eller från förra årets inlämnade skattedeklaration. Klicka här för att se läsa mer hur man hämtar denna information. Vill du...', '📊', 'options', 'Finns inget outnyttjat underskott kvar', 'none', 501, 'navigate', 'Ange belopp outnyttjat underskott', 'enter_amount', 402, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(402, 20, 40, 'Ange belopp outnyttjat underskott:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 403, 'process_input', '{"variable": "unusedTaxLossAmount"}');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(403, 20, 40, 'Outnyttjat underskott från föregående år har blivit uppdaterat med {unusedTaxLossAmount} kr. Vill du gå vidare?', '✅', 'options', 'Ja, gå vidare', 'continue', 501, 'api_call', '{"endpoint": "recalculate_ink2", "params": {"ink4_16_underskott_adjustment": "{unusedTaxLossAmount}"}}');

-- Subblock 50: Periodiseringsfond
INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type, option2_action_data) VALUES
(501, 20, 50, 'Har företaget någon periodiseringsfond från tidigare år?', '🏦', 'options', 'Nej, ingen periodiseringsfond', 'none', 601, 'navigate', 'Ja, ange belopp', 'enter_amount', 502, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(502, 20, 50, 'Ange belopp för periodiseringsfond:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 601, 'process_input', '{"variable": "periodiseringsfond"}');

-- Subblock 60: Manuell justering
INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(601, 20, 60, 'Den bokförda skatten är {SkattAretsResultat}. Vill du godkänna den eller vill du se över de skattemässiga justeringarna?', '🏛️', 'options', 'Godkänn bokförd skatt', 'approve_booked', 701, 'set_variable', '{"variable": "finalTaxChoice", "value": "booked"}', 'Se över skattemässiga justeringar', 'review_adjustments', 602, 'show_tax_preview');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data, option2_text, option2_value, option2_next_step, option2_action_type, option3_text, option3_value, option3_next_step, option3_action_type, option3_action_data) VALUES
(602, 20, 60, 'Beräknad skatt efter skattemässiga justeringar är {inkBeraknadSkatt} kr. Vill du godkänna denna skatt eller vill du göra manuella ändringar? Eller vill du hellre att vi godkänner och använder den bokförda skatten?', '🧮', 'options', 'Godkänn och använd beräknad skatt {inkBeraknadSkatt}', 'approve_calculated', 701, 'set_variable', '{"variable": "finalTaxChoice", "value": "calculated"}', 'Gör manuella ändringar i skattejusteringarna', 'manual_changes', 603, 'enable_editing', 'Godkänn och använd bokförd skatt {inkBokfordSkatt}', 'approve_booked', 701, 'set_variable', '{"variable": "finalTaxChoice", "value": "booked"}');

INSERT INTO public.chat_flow (step_number, block_number, subblock_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(603, 20, 60, 'Du kan nu redigera skattemässiga justeringar. Klicka på "Godkänn och uppdatera skatt" när du är klar.', '✏️', 'message', 'Godkänn och uppdatera skatt', 'update_tax', 701, 'save_manual_tax', 'Ångra ändringar', 'undo_changes', 602, 'reset_tax_edits');

-- BLOCK 70: RR block
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(701, 70, 'Nu ska vi gå igenom resultaträkningen (RR). Här visas företagets intäkter och kostnader för året.', '📊', 'message', 'Fortsätt till resultaträkning', 'continue', 801, 'navigate');

-- BLOCK 80: BR block  
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(801, 80, 'Nu ska vi gå igenom balansräkningen (BR). Här visas företagets tillgångar, skulder och eget kapital.', '⚖️', 'message', 'Fortsätt till balansräkning', 'continue', 901, 'navigate');

-- BLOCK 90: FB block
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(901, 90, 'Nu ska vi gå igenom förändringar i eget kapital (FB).', '💼', 'message', 'Fortsätt till förändringar i eget kapital', 'continue', 1001, 'navigate');

-- BLOCK 100: Noter block
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(1001, 100, 'Vill du lägga till några noter till årsredovisningen?', '📝', 'options', 'Nej, inga noter', 'no_notes', 1201, 'navigate', 'Ja, lägg till noter', 'add_notes', 1002, 'show_notes_editor');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, input_type, input_placeholder, option1_text, option1_value, option1_next_step, option1_action_type, option1_action_data) VALUES
(1002, 100, 'Skriv dina noter här:', '✍️', 'input', 'text', 'Skriv noter...', 'Spara noter', 'save', 1201, 'process_input', '{"variable": "notes"}');

-- BLOCK 120: Signaturer block
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(1201, 120, 'Nu behöver vi signaturerna för årsredovisningen.', '✍️', 'message', 'Fortsätt till signaturer', 'continue', 1301, 'navigate');

-- BLOCK 130: Fastställelseintyg block
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type) VALUES
(1301, 130, 'Skapar fastställelseintyg för årsredovisningen.', '📋', 'message', 'Fortsätt till fastställelseintyg', 'continue', 1401, 'navigate');

-- BLOCK 140: Lämna in block
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(1401, 140, 'Årsredovisningen är nu klar! Vill du lämna in den direkt till Bolagsverket?', '📮', 'options', 'Ja, lämna in nu', 'submit_now', 1501, 'submit_to_bolagsverket', 'Nej, ladda ner PDF först', 'download_first', 1402, 'download_pdf');

INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_next_step, option1_action_type, option2_text, option2_value, option2_next_step, option2_action_type) VALUES
(1402, 140, 'PDF har skapats och laddats ner. Vill du lämna in årsredovisningen nu?', '📄', 'options', 'Ja, lämna in nu', 'submit_now', 1501, 'submit_to_bolagsverket', 'Nej, jag gör det senare', 'later', 1501, 'navigate');

-- BLOCK 150: Avslutning block
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type, option1_text, option1_value, option1_action_type) VALUES
(1501, 150, 'Grattis! Din årsredovisning är nu klar och inlämnad. Tack för att du använde Raketrapport! 🚀', '🎉', 'message', 'Avsluta', 'finish', 'complete_session');

-- =====================================================
-- Verification queries (uncomment to run after)
-- =====================================================

-- SELECT 'chat_flow table' as table_name, count(*) as rows FROM public.chat_flow;

-- SELECT 
--     block_number,
--     subblock_number,
--     COUNT(*) as steps,
--     CASE block_number
--         WHEN 10 THEN 'Introduction'
--         WHEN 20 THEN 'Tax block'
--         WHEN 70 THEN 'RR block'
--         WHEN 80 THEN 'BR block'
--         WHEN 90 THEN 'FB block'
--         WHEN 100 THEN 'Noter block'
--         WHEN 120 THEN 'Signaturer block'
--         WHEN 130 THEN 'Fastställelseintyg block'
--         WHEN 140 THEN 'Lämna in block'
--         WHEN 150 THEN 'Avslutning block'
--         ELSE 'Unknown block'
--     END as block_name
-- FROM public.chat_flow 
-- GROUP BY block_number, subblock_number
-- ORDER BY block_number, subblock_number;
