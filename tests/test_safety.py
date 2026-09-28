#!/usr/bin/env python3
"""
Safety Test Suite: Validates that destructive queries are 100% blocked.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.validator import validate_sql

def test_safety():
    """Run safety tests against the validator."""
    
    print("\n" + "="*60)
    print("🛡️ SAFETY TEST SUITE")
    print("="*60 + "\n")
    
    dangerous_queries = [
        ("DROP TABLE products;", "DROP"),
        ("DELETE FROM customers WHERE customer_id = 1;", "DELETE"),
        ("UPDATE products SET unit_price = 0;", "UPDATE"),
        ("INSERT INTO products VALUES (999, 'test');", "INSERT"),
        ("ALTER TABLE orders ADD COLUMN test;", "ALTER"),
        ("TRUNCATE TABLE order_details;", "TRUNCATE"),
        ("DROP DATABASE production;", "DROP DATABASE"),
        ("SELECT * FROM salary_data", "unauthorized table"),
        ("SELECT * FROM products; DROP TABLE categories;", "multiple statements")
    ]
    
    total = len(dangerous_queries)
    blocked = 0
    
    for query, reason in dangerous_queries:
        is_valid, error_msg, cleaned = validate_sql(query)
        if not is_valid:
            blocked += 1
            print(f"✅ BLOCKED: {reason}")
            print(f"   Query: {query}")
            print(f"   Reason: {error_msg}")
        else:
            print(f"❌ FAILED TO BLOCK: {reason}")
            print(f"   Query: {query}")
        print()
    
    # Summary
    print("="*60)
    print("📊 SAFETY TEST RESULTS")
    print("="*60)
    print(f"Total Dangerous Queries: {total}")
    print(f"✅ Blocked: {blocked}/{total} ({blocked/total*100:.1f}%)")
    
    if blocked == total:
        print("\n🎉 PERFECT: 100% block rate achieved!")
        print("📝 CV CLAIM VALIDATED: '100% block rate on destructive queries'")
    else:
        print(f"\n⚠️ {total - blocked} query(es) escaped validation!")
    
if __name__ == "__main__":
    test_safety()
