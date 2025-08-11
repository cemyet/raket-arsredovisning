-- Create chat_flow table for managing conversation steps
CREATE TABLE IF NOT EXISTS public.chat_flow (
    id SERIAL PRIMARY KEY,
    step_number INTEGER NOT NULL UNIQUE,
    block_number INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    question_icon TEXT,
    question_type VARCHAR(50) DEFAULT 'options', -- 'options', 'input', 'info'
    input_type VARCHAR(50), -- 'number', 'text', 'amount' (for input questions)
    input_placeholder TEXT,
    conditions JSONB, -- Conditions for showing this question
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
CREATE INDEX idx_chat_flow_step_number ON public.chat_flow(step_number);
CREATE INDEX idx_chat_flow_block_number ON public.chat_flow(block_number);
CREATE INDEX idx_chat_flow_options_step ON public.chat_flow_options(step_number);
CREATE INDEX idx_chat_flow_options_order ON public.chat_flow_options(step_number, option_order);

-- Enable RLS
ALTER TABLE public.chat_flow ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_flow_options ENABLE ROW LEVEL SECURITY;

-- Create policies (allow all for now, can be restricted later)
CREATE POLICY "Allow all operations on chat_flow" ON public.chat_flow
    FOR ALL USING (true);

CREATE POLICY "Allow all operations on chat_flow_options" ON public.chat_flow_options
    FOR ALL USING (true);

-- Insert initial conversation flow data
INSERT INTO public.chat_flow (step_number, block_number, question_text, question_icon, question_type) VALUES
(10, 10, 'Vilken typ av utdelning vill du göra?', '💰', 'options'),
(20, 20, 'Outnyttjat underskott från föregående år är det samlade beloppet av tidigare års skattemässiga förluster som ännu inte har kunnat kvittas mot vinster. Om företaget går med vinst ett senare år kan hela eller delar av det outnyttjade underskottet användas för att minska den beskattningsbara inkomsten och därmed skatten. Denna uppgift går inte att hämta från tidigare årsredovisningar utan behöver tas från årets förtryckta deklaration eller från förra årets inlämnade skattedeklaration. Klicka här för att se läsa mer hur man hämtar denna information. Vill du...', '📊', 'options'),
(25, 20, 'Outnyttjat underskott från föregående år har blivit uppdaterat med {unusedTaxLossAmount} kr. Vill du gå vidare?', '✅', 'options'),
(30, 30, 'Beräknad skatt efter skattemässiga justeringar är {inkBeraknadSkatt} kr. Vill du godkänna denna skatt eller vill du göra manuella ändringar? Eller vill du hellre att vi godkänner och använder den bokförda skatten?', '🏛️', 'options');

-- Insert options for each question
INSERT INTO public.chat_flow_options (step_number, option_order, option_text, option_value, next_step, action_type, action_data) VALUES
-- Dividend type options (step 10)
(10, 1, 'Ordinarie utdelning', 'ordinary', 20, 'set_variable', '{"variable": "dividendType", "value": "ordinary"}'),
(10, 2, 'Förenklad utdelning', 'simplified', 20, 'set_variable', '{"variable": "dividendType", "value": "simplified"}'),
(10, 3, 'Kvalificerad utdelning', 'qualified', 20, 'set_variable', '{"variable": "dividendType", "value": "qualified"}'),

-- Unused tax loss options (step 20)
(20, 1, 'Finns inget outnyttjat underskott kvar', 'none', 30, 'navigate', NULL),
(20, 2, 'Ange belopp outnyttjat underskott', 'enter_amount', 22, 'show_input', '{"input_type": "amount", "placeholder": "Ange belopp..."}'),

-- Input step for unused tax loss amount (step 22 - will be added dynamically)
-- Continue after unused tax loss (step 25)
(25, 1, 'Ja, gå vidare', 'continue', 30, 'api_call', '{"endpoint": "recalculate_ink2", "params": {"ink4_16_underskott_adjustment": "{unusedTaxLossAmount}"}}'),

-- Final tax question options (step 30)
(30, 1, 'Godkänn och använd beräknad skatt {inkBeraknadSkatt}', 'approve_calculated', 40, 'set_variable', '{"variable": "finalTaxChoice", "value": "calculated"}'),
(30, 2, 'Gör manuella ändringar i skattejusteringarna', 'manual_changes', 35, 'enable_editing', NULL),
(30, 3, 'Godkänn och använd bokförd skatt {inkBokfordSkatt}', 'approve_booked', 40, 'set_variable', '{"variable": "finalTaxChoice", "value": "booked"}');
