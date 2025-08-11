-- =====================================================
-- Chat Flow Tables for Raketrapport
-- Run this script in Supabase SQL Editor
-- =====================================================

-- Create chat_flow table for managing conversation steps
CREATE TABLE IF NOT EXISTS public.chat_flow (
    id SERIAL PRIMARY KEY,
    step_number INTEGER NOT NULL UNIQUE,
    block_number INTEGER NOT NULL,
    subblock_number INTEGER, -- For organizing within blocks (e.g., 30, 40, 50, 60 within Tax block 20)
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

-- Create chat_flow_options table for question options
CREATE TABLE IF NOT EXISTS public.chat_flow_options (
    id SERIAL PRIMARY KEY,
    step_number INTEGER NOT NULL REFERENCES public.chat_flow(step_number),
    option_order INTEGER NOT NULL,
    option_text TEXT NOT NULL,
    option_value TEXT NOT NULL,
    next_step INTEGER, -- Next step to go to, NULL means continue to next in sequence
    action_type VARCHAR(50), -- 'navigate', 'api_call', 'set_variable', 'calculate'
    action_data JSONB, -- Additional data for the action
    conditions JSONB, -- Conditions for showing this option
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
-- Insert conversation flow data
-- =====================================================

-- Insert chat flow questions with new block structure
INSERT INTO public.chat_flow (
    step_number, 
    block_number, 
    subblock_number, 
    question_text, 
    question_icon, 
    question_type,
    input_type,
    input_placeholder,
    option1_text,
    option1_value,
    option1_next_step,
    option1_action_type,
    option1_action_data,
    option2_text,
    option2_value,
    option2_next_step,
    option2_action_type,
    option2_action_data,
    option3_text,
    option3_value,
    option3_next_step,
    option3_action_type,
    option3_action_data,
    option4_text,
    option4_value,
    option4_next_step,
    option4_action_type,
    option4_action_data,
    show_conditions
) VALUES

-- =====================================================
-- BLOCK 10: Introduction
-- =====================================================
(101, 10, NULL, 'Välkommen till Raketrapport! Jag kommer att guida dig genom att skapa din årsredovisning steg för steg.', '👋', 'message', NULL, NULL, 'Fortsätt', 'continue', 102, 'navigate', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(102, 10, NULL, 'Först behöver jag veta vilket typ av företag det är och vilken typ av utdelning du vill göra.', '📋', 'message', NULL, NULL, 'Fortsätt', 'continue', 103, 'navigate', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(103, 10, NULL, 'Vilken typ av utdelning vill du göra?', '💰', 'options', NULL, NULL, 'Ordinarie utdelning', 'ordinary', 301, 'set_variable', '{"variable": "dividendType", "value": "ordinary"}', 'Förenklad utdelning', 'simplified', 301, 'set_variable', '{"variable": "dividendType", "value": "simplified"}', 'Kvalificerad utdelning', 'qualified', 301, 'set_variable', '{"variable": "dividendType", "value": "qualified"}', NULL, NULL, NULL, NULL, NULL, NULL),

-- =====================================================
-- BLOCK 20: Tax block
-- =====================================================

-- Subblock 30: Särskild löneskatt
(301, 20, 30, 'Innan vi fortsätter med skatteuträkningen vill jag göra dig uppmärksam på att särskild löneskatt på pensionförsäkringspremier inte verkar vara bokförd. Inbetalda pensionförsäkringspremier under året uppgår till {pension_premier} och den särskilda löneskatten borde uppgå till {sarskild_loneskatt_pension_calculated} men endast {sarskild_loneskatt_pension} verkar vara bokfört. Vill du att vi justerar den särskilda löneskatten och därmed årets resultat enligt våra beräkningar?', '⚠️', 'options', NULL, NULL, 'Justera särskild löneskatt till {sarskild_loneskatt_pension_calculated} kr', 'adjust_calculated', 302, 'set_variable', '{"variable": "justeringSarskildLoneskatt", "value": "calculated"}', 'Behåll nuvarande bokförd särskild löneskatt {sarskild_loneskatt_pension}', 'keep_current', 401, 'set_variable', '{"variable": "justeringSarskildLoneskatt", "value": "current"}', 'Ange belopp för egen särskild löneskatt', 'enter_custom', 303, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}', NULL, NULL, NULL, NULL, NULL, '{"pension_premier": {"gt": 0}, "sarskild_loneskatt_pension_calculated": {"gt": "sarskild_loneskatt_pension"}}'),

(302, 20, 30, 'Perfekt, nu är den särskilda löneskatten justerad som du kan se i skatteuträkning till höger.', '✅', 'message', NULL, NULL, 'Fortsätt', 'continue', 401, 'navigate', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(303, 20, 30, 'Ange belopp för särskild löneskatt:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 302, 'process_input', '{"variable": "sarskildLoneskattCustom"}', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- Subblock 40: Outnyttjat underskott
(401, 20, 40, 'Outnyttjat underskott från föregående år är det samlade beloppet av tidigare års skattemässiga förluster som ännu inte har kunnat kvittas mot vinster. Om företaget går med vinst ett senare år kan hela eller delar av det outnyttjade underskottet användas för att minska den beskattningsbara inkomsten och därmed skatten. Denna uppgift går inte att hämta från tidigare årsredovisningar utan behöver tas från årets förtryckta deklaration eller från förra årets inlämnade skattedeklaration. Klicka här för att se läsa mer hur man hämtar denna information. Vill du...', '📊', 'options', NULL, NULL, 'Finns inget outnyttjat underskott kvar', 'none', 501, 'navigate', NULL, 'Ange belopp outnyttjat underskott', 'enter_amount', 402, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(402, 20, 40, 'Ange belopp outnyttjat underskott:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 403, 'process_input', '{"variable": "unusedTaxLossAmount"}', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(403, 20, 40, 'Outnyttjat underskott från föregående år har blivit uppdaterat med {unusedTaxLossAmount} kr. Vill du gå vidare?', '✅', 'options', NULL, NULL, 'Ja, gå vidare', 'continue', 501, 'api_call', '{"endpoint": "recalculate_ink2", "params": {"ink4_16_underskott_adjustment": "{unusedTaxLossAmount}"}}', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- Subblock 50: Periodiseringsfond
(501, 20, 50, 'Har företaget någon periodiseringsfond från tidigare år?', '🏦', 'options', NULL, NULL, 'Nej, ingen periodiseringsfond', 'none', 601, 'navigate', NULL, 'Ja, ange belopp', 'enter_amount', 502, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(502, 20, 50, 'Ange belopp för periodiseringsfond:', '💰', 'input', 'amount', 'Ange belopp...', 'Skicka', 'submit', 601, 'process_input', '{"variable": "periodiseringsfond"}', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- Subblock 60: Manuell justering
(601, 20, 60, 'Den bokförda skatten är {SkattAretsResultat}. Vill du godkänna den eller vill du se över de skattemässiga justeringarna?', '🏛️', 'options', NULL, NULL, 'Godkänn bokförd skatt', 'approve_booked', 701, 'set_variable', '{"variable": "finalTaxChoice", "value": "booked"}', 'Se över skattemässiga justeringar', 'review_adjustments', 602, 'show_tax_preview', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(602, 20, 60, 'Beräknad skatt efter skattemässiga justeringar är {inkBeraknadSkatt} kr. Vill du godkänna denna skatt eller vill du göra manuella ändringar? Eller vill du hellre att vi godkänner och använder den bokförda skatten?', '🧮', 'options', NULL, NULL, 'Godkänn och använd beräknad skatt {inkBeraknadSkatt}', 'approve_calculated', 701, 'set_variable', '{"variable": "finalTaxChoice", "value": "calculated"}', 'Gör manuella ändringar i skattejusteringarna', 'manual_changes', 603, 'enable_editing', NULL, 'Godkänn och använd bokförd skatt {inkBokfordSkatt}', 'approve_booked', 701, 'set_variable', '{"variable": "finalTaxChoice", "value": "booked"}', NULL),

(603, 20, 60, 'Du kan nu redigera skattemässiga justeringar. Klicka på "Godkänn och uppdatera skatt" när du är klar.', '✏️', 'message', NULL, NULL, 'Godkänn och uppdatera skatt', 'update_tax', 701, 'save_manual_tax', NULL, 'Ångra ändringar', 'undo_changes', 602, 'reset_tax_edits', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- =====================================================
-- BLOCK 70: RR block
-- =====================================================
(701, 70, NULL, 'Nu ska vi gå igenom resultaträkningen (RR). Här visas företagets intäkter och kostnader för året.', '📊', 'message', NULL, NULL, 'Fortsätt till resultaträkning', 'continue', 801, 'navigate', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- =====================================================
-- BLOCK 80: BR block  
-- =====================================================
(801, 80, NULL, 'Nu ska vi gå igenom balansräkningen (BR). Här visas företagets tillgångar, skulder och eget kapital.', '⚖️', 'message', NULL, NULL, 'Fortsätt till balansräkning', 'continue', 901, 'navigate', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- =====================================================
-- BLOCK 90: FB block
-- =====================================================
(901, 90, NULL, 'Nu ska vi gå igenom förändringar i eget kapital (FB).', '💼', 'message', NULL, NULL, 'Fortsätt till förändringar i eget kapital', 'continue', 1001, 'navigate', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- =====================================================
-- BLOCK 100: Noter block
-- =====================================================
(1001, 100, NULL, 'Vill du lägga till några noter till årsredovisningen?', '📝', 'options', NULL, NULL, 'Nej, inga noter', 'no_notes', 1201, 'navigate', NULL, 'Ja, lägg till noter', 'add_notes', 1002, 'show_notes_editor', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(1002, 100, NULL, 'Skriv dina noter här:', '✍️', 'input', 'text', 'Skriv noter...', 'Spara noter', 'save', 1201, 'process_input', '{"variable": "notes"}', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- =====================================================
-- BLOCK 120: Signaturer block
-- =====================================================
(1201, 120, NULL, 'Nu behöver vi signaturerna för årsredovisningen.', '✍️', 'message', NULL, NULL, 'Fortsätt till signaturer', 'continue', 1301, 'navigate', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- =====================================================
-- BLOCK 130: Fastställelseintyg block
-- =====================================================
(1301, 130, NULL, 'Skapar fastställelseintyg för årsredovisningen.', '📋', 'message', NULL, NULL, 'Fortsätt till fastställelseintyg', 'continue', 1401, 'navigate', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- =====================================================
-- BLOCK 140: Lämna in block
-- =====================================================
(1401, 140, NULL, 'Årsredovisningen är nu klar! Vill du lämna in den direkt till Bolagsverket?', '📮', 'options', NULL, NULL, 'Ja, lämna in nu', 'submit_now', 1501, 'submit_to_bolagsverket', NULL, 'Nej, ladda ner PDF först', 'download_first', 1402, 'download_pdf', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

(1402, 140, NULL, 'PDF har skapats och laddats ner. Vill du lämna in årsredovisningen nu?', '📄', 'options', NULL, NULL, 'Ja, lämna in nu', 'submit_now', 1501, 'submit_to_bolagsverket', NULL, 'Nej, jag gör det senare', 'later', 1501, 'navigate', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),

-- =====================================================
-- BLOCK 150: Avslutning block
-- =====================================================
(1501, 150, NULL, 'Grattis! Din årsredovisning är nu klar och inlämnad. Tack för att du använde Raketrapport! 🚀', '🎉', 'message', NULL, NULL, 'Avsluta', 'finish', NULL, 'complete_session', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)

ON CONFLICT (step_number) DO UPDATE SET
    block_number = EXCLUDED.block_number,
    subblock_number = EXCLUDED.subblock_number,
    question_text = EXCLUDED.question_text,
    question_icon = EXCLUDED.question_icon,
    question_type = EXCLUDED.question_type,
    input_type = EXCLUDED.input_type,
    input_placeholder = EXCLUDED.input_placeholder,
    option1_text = EXCLUDED.option1_text,
    option1_value = EXCLUDED.option1_value,
    option1_next_step = EXCLUDED.option1_next_step,
    option1_action_type = EXCLUDED.option1_action_type,
    option1_action_data = EXCLUDED.option1_action_data,
    option2_text = EXCLUDED.option2_text,
    option2_value = EXCLUDED.option2_value,
    option2_next_step = EXCLUDED.option2_next_step,
    option2_action_type = EXCLUDED.option2_action_type,
    option2_action_data = EXCLUDED.option2_action_data,
    option3_text = EXCLUDED.option3_text,
    option3_value = EXCLUDED.option3_value,
    option3_next_step = EXCLUDED.option3_next_step,
    option3_action_type = EXCLUDED.option3_action_type,
    option3_action_data = EXCLUDED.option3_action_data,
    option4_text = EXCLUDED.option4_text,
    option4_value = EXCLUDED.option4_value,
    option4_next_step = EXCLUDED.option4_next_step,
    option4_action_type = EXCLUDED.option4_action_type,
    option4_action_data = EXCLUDED.option4_action_data,
    show_conditions = EXCLUDED.show_conditions,
    updated_at = NOW();

-- NOTE: chat_flow_options table is kept for backwards compatibility,
-- but options are now stored directly in the chat_flow table (option1_text, option2_text, etc.)
-- This table can be used for complex scenarios that need more than 4 options.

-- =====================================================
-- Verification queries (optional - you can run these after)
-- =====================================================

-- Check that tables were created successfully
-- SELECT 'chat_flow table' as table_name, count(*) as rows FROM public.chat_flow;

-- View all blocks and their steps
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
--     END as block_name,
--     CASE 
--         WHEN block_number = 20 AND subblock_number = 30 THEN 'Särskild löneskatt subblock'
--         WHEN block_number = 20 AND subblock_number = 40 THEN 'Outnyttjat underskott subblock'
--         WHEN block_number = 20 AND subblock_number = 50 THEN 'Periodiseringsfond subblock'
--         WHEN block_number = 20 AND subblock_number = 60 THEN 'Manuell justering subblock'
--         ELSE ''
--     END as subblock_name
-- FROM public.chat_flow 
-- GROUP BY block_number, subblock_number
-- ORDER BY block_number, subblock_number;

-- View the conversation flow structure with options
-- SELECT 
--     cf.step_number,
--     cf.block_number,
--     cf.subblock_number,
--     LEFT(cf.question_text, 60) || '...' as question_preview,
--     cf.question_type,
--     cf.option1_text,
--     cf.option1_next_step,
--     cf.option2_text,
--     cf.option2_next_step,
--     cf.show_conditions
-- FROM public.chat_flow cf
-- ORDER BY cf.step_number;

-- Check for any broken next_step references
-- SELECT 
--     cf.step_number as current_step,
--     cf.option1_next_step as next_step,
--     CASE WHEN next_flow.step_number IS NULL AND cf.option1_next_step IS NOT NULL 
--          THEN 'BROKEN REFERENCE' 
--          ELSE 'OK' 
--     END as link_status
-- FROM public.chat_flow cf
-- LEFT JOIN public.chat_flow next_flow ON cf.option1_next_step = next_flow.step_number
-- WHERE cf.option1_next_step IS NOT NULL
-- UNION ALL
-- SELECT 
--     cf.step_number,
--     cf.option2_next_step,
--     CASE WHEN next_flow.step_number IS NULL AND cf.option2_next_step IS NOT NULL 
--          THEN 'BROKEN REFERENCE' 
--          ELSE 'OK' 
--     END
-- FROM public.chat_flow cf
-- LEFT JOIN public.chat_flow next_flow ON cf.option2_next_step = next_flow.step_number
-- WHERE cf.option2_next_step IS NOT NULL
-- ORDER BY current_step;
