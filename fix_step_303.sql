-- Fix step 303 to prevent API call that resets injected values
-- The issue is that step 303 tries to make an API call with variable substitution,
-- but the substitution fails and resets the values to 0

UPDATE public.chat_flow 
SET 
    option1_action_type = 'navigate',
    option1_action_data = NULL
WHERE step_number = 303;

-- Verify the change
SELECT 
    step_number,
    question_text,
    option1_text,
    option1_value,
    option1_next_step,
    option1_action_type,
    option1_action_data
FROM public.chat_flow 
WHERE step_number = 303;
