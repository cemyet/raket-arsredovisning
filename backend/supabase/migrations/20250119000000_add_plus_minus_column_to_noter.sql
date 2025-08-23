-- Add plus_minus column to variable_mapping_noter table
-- This column stores the +/- sign override for display formatting

ALTER TABLE variable_mapping_noter 
ADD COLUMN plus_minus TEXT;

-- Add comment to explain the column
COMMENT ON COLUMN variable_mapping_noter.plus_minus IS 'Sign override for display: "+" for positive, "-" for negative values';
