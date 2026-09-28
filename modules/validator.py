#!/usr/bin/env python3
"""
Module: validator.py
Validates SQL queries for safety before execution.
Uses sqlglot to parse SQL and check for destructive operations.
"""

import sqlglot
from sqlglot import parse_one, exp
import yaml
import os

# Load allowed tables from config file
def load_allowed_tables():
    """Load the list of allowed tables from config file."""
    try:
        with open("config/allowed_tables.yaml", "r") as f:
            config = yaml.safe_load(f)
            return config.get("tables", [])
    except FileNotFoundError:
        # Fallback if config doesn't exist yet
        print("⚠️ Config file not found. Using default allowed tables.")
        return ["categories", "customers", "employees", "order_details", "orders", 
                "products", "suppliers", "shippers", "regions", "territories",
                "employee_territories", "customer_customer_demo", "customer_demographics", "us_states"]

def validate_sql(sql: str):
    """
    Validate that the SQL is safe to execute.
    
    Args:
        sql (str): The SQL query to validate.
    
    Returns:
        tuple: (is_valid, reason, cleaned_sql)
    """
    print("🔍 Validating SQL...")
    
    if not sql:
        return False, "SQL query is empty", None
    
    # Clean the SQL
    sql = sql.strip()
    
    # Step 1: Parse the SQL using sqlglot
    try:
        parsed = parse_one(sql, dialect="postgres")
    except Exception as e:
        return False, f"SQL parsing error: {e}", None
    
    # Step 2: Check if it's a SELECT statement
    if not isinstance(parsed, exp.Select):
        return False, f"Only SELECT queries are allowed. Found: {type(parsed).__name__}", None
    
    # Step 3: Check for destructive keywords (extra safety beyond parsing)
    sql_lower = sql.lower()
    forbidden_keywords = ["drop", "delete", "update", "insert", "alter", "truncate", 
                         "create", "grant", "revoke", "rename", "comment"]
    for keyword in forbidden_keywords:
        if keyword in sql_lower:
            return False, f"Query contains forbidden keyword: {keyword}", None
    
    # Step 4: Extract all table names from the query
    tables = set()
    for table in parsed.find_all(exp.Table):
        table_name = table.this.sql().lower()
        tables.add(table_name)
    
    # Step 5: Check if tables are allowed
    allowed_tables = load_allowed_tables()
    allowed_tables_lower = [t.lower() for t in allowed_tables]
    
    for table in tables:
        if table not in allowed_tables_lower:
            return False, f"Table '{table}' is not in the allowed list", None
    
    # Step 6: Limit the number of JOINs to prevent performance issues
    join_count = len(list(parsed.find_all(exp.Join)))
    if join_count > 8:
        return False, f"Too many JOINs ({join_count}). Maximum is 8.", None
    
    print("✅ SQL validation passed!")
    return True, "SQL is safe to execute", sql

# Simple test block
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🧪 TESTING VALIDATOR MODULE")
    print("="*50)
    
    # Test 1: Safe SELECT
    test_sql = "SELECT product_name, unit_price FROM products WHERE category_id = 1"
    valid, reason, cleaned = validate_sql(test_sql)
    print(f"\nTest 1 - Safe SELECT:")
    print(f"  Valid: {valid}")
    print(f"  Reason: {reason}")
    
    # Test 2: Dangerous DELETE
    test_sql = "DELETE FROM products WHERE product_id = 1"
    valid, reason, cleaned = validate_sql(test_sql)
    print(f"\nTest 2 - Dangerous DELETE:")
    print(f"  Valid: {valid}")
    print(f"  Reason: {reason}")
    
    # Test 3: Unauthorized table
    test_sql = "SELECT * FROM salary_data"
    valid, reason, cleaned = validate_sql(test_sql)
    print(f"\nTest 3 - Unauthorized table:")
    print(f"  Valid: {valid}")
    print(f"  Reason: {reason}")
    
    print("\n✅ Validator test complete!")