#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from services.supabase_service import SupabaseService

def main():
    supabase = SupabaseService()
    
    # Add ib_ub column
    try:
        result1 = supabase.client.rpc('sql', {'query': "ALTER TABLE variable_mapping_noter ADD COLUMN ib_ub TEXT DEFAULT 'UB'"}).execute()
        print('Added ib_ub column successfully')
    except Exception as e:
        print(f'ib_ub column may already exist: {e}')
    
    # Add style column  
    try:
        result2 = supabase.client.rpc('sql', {'query': 'ALTER TABLE variable_mapping_noter ADD COLUMN style TEXT'}).execute()
        print('Added style column successfully')
    except Exception as e:
        print(f'style column may already exist: {e}')
    
    print('Database columns updated')

if __name__ == "__main__":
    main()
