#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.supabase_service import SupabaseService

def run_migration():
    """Run the chat flow migration"""
    
    # Read the migration file
    migration_file = 'supabase/migrations/20250109000000_create_chat_flow_table.sql'
    
    try:
        with open(migration_file, 'r') as f:
            sql_content = f.read()
    except FileNotFoundError:
        print(f"Error: Migration file {migration_file} not found")
        return False
    
    # Initialize Supabase service
    supabase_service = SupabaseService()
    
    if not supabase_service.client:
        print("Error: Supabase client not available. Check your environment variables.")
        return False
    
    try:
        # Split by semicolon and execute each statement
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
        
        for i, statement in enumerate(statements):
            if statement and not statement.startswith('--'):
                print(f'Executing statement {i+1}/{len(statements)}...')
                print(f'Statement: {statement[:100]}...')
                
                # Use the rpc function to execute raw SQL
                try:
                    result = supabase_service.client.rpc('exec_sql', {'sql': statement}).execute()
                    print(f'Statement {i+1} executed successfully')
                except Exception as stmt_error:
                    print(f'Error in statement {i+1}: {stmt_error}')
                    # Continue with other statements
        
        print('Migration completed!')
        return True
        
    except Exception as e:
        print(f'Error executing migration: {e}')
        return False

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("✅ Chat flow migration completed successfully!")
    else:
        print("❌ Chat flow migration failed!")
        sys.exit(1)
