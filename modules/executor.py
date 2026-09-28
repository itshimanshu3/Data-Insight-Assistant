#!/usr/bin/env python3
"""
Module: executor.py
Executes validated SQL queries against Supabase (PostgreSQL).
Uses the read-only database connection.
"""

import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the Supabase connection string from .env
DATABASE_URL = os.getenv("SUPABASE_READONLY_URL")

def execute_query(sql: str):
    """
    Execute a SQL query against Supabase and return results as DataFrame.
    
    Args:
        sql (str): The SQL query to execute.
    
    Returns:
        tuple: (df, error)
            - df: pandas DataFrame with results (or None if error)
            - error: error message (or None if success)
    """
    print("⚡ Executing SQL against Supabase...")
    
    if not DATABASE_URL:
        return None, "SUPABASE_READONLY_URL not found in environment variables"
    
    try:
        # Connect to Supabase using the read-only user
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Execute the query
        cur.execute(sql)
        
        # Fetch column names
        colnames = [desc[0] for desc in cur.description] if cur.description else []
        
        # Fetch all rows
        rows = cur.fetchall()
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(rows, columns=colnames)
        
        cur.close()
        conn.close()
        
        print(f"✅ Query executed successfully! {len(df)} rows returned.")
        return df, None
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Query execution failed: {error_msg}")
        return None, error_msg

# Simple test block
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🧪 TESTING EXECUTOR MODULE")
    print("="*50)
    
    # Test query (simple SELECT)
    test_sql = "SELECT product_id, product_name, unit_price FROM products LIMIT 5"
    
    print(f"\n📝 Running: {test_sql}")
    df, error = execute_query(test_sql)
    
    if error:
        print(f"\n❌ Error: {error}")
    else:
        print("\n📊 Results:")
        print(df.to_string(index=False))
        print(f"\n✅ Executor test complete! {len(df)} rows returned.")