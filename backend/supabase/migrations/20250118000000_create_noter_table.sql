-- Create Noter (Notes) table for annual report notes section
-- This follows the same pattern as RR/BR but with toggle functionality

-- Table: Variable Mapping for Noter
CREATE TABLE variable_mapping_noter (
  id SERIAL PRIMARY KEY,
  row_id INTEGER NOT NULL,
  row_title TEXT NOT NULL,
  accounts_included TEXT, -- Account numbers to sum (e.g., "6072;6992" or "6000-6999")
  calculation_formula TEXT, -- Formula for calculated values, may reference variables
  always_show BOOLEAN NOT NULL DEFAULT FALSE, -- Show row regardless of amount
  toggle_show BOOLEAN NOT NULL DEFAULT FALSE, -- Show only when block toggle is enabled
  show_tag BOOLEAN NOT NULL DEFAULT FALSE, -- Show SHOW tag for account details popup
  variable_name TEXT NOT NULL, -- Variable name for the amount
  block TEXT, -- Block/section grouping (e.g., "ANLAGGNINGAR", "OMSATTNING")
  calculated BOOLEAN NOT NULL DEFAULT FALSE, -- Whether to use formula instead of accounts
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  
  UNIQUE(row_id)
);

-- Enable RLS
ALTER TABLE variable_mapping_noter ENABLE ROW LEVEL SECURITY;

-- Create policies (following same pattern as other mapping tables)
CREATE POLICY "Anyone can view Noter mappings" ON variable_mapping_noter FOR SELECT USING (true);
CREATE POLICY "Anyone can insert Noter mappings" ON variable_mapping_noter FOR INSERT WITH CHECK (true);
CREATE POLICY "Anyone can update Noter mappings" ON variable_mapping_noter FOR UPDATE USING (true);
CREATE POLICY "Anyone can delete Noter mappings" ON variable_mapping_noter FOR DELETE USING (true);
