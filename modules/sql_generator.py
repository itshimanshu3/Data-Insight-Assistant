#!/usr/bin/env python3
"""
Module: sql_generator.py
Handles SQL generation using Groq.
Uses openai/gpt-oss-120b for SQL generation.
"""

import os
import httpx
from groq import Groq
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY not found in environment!")
    exit(1)

client = Groq(
    api_key=GROQ_API_KEY,
    http_client=httpx.Client(timeout=60.0)
)

def generate_sql(question: str, context: list, history: list = None):
    """
    Generate SQL from natural language using Groq.
    
    Args:
        question (str): The user's natural language question.
        context (list): List of relevant table descriptions from retriever.
        history (list, optional): Previous conversation turns.
    
    Returns:
        str: The generated SQL query.
    """
    print("🤖 Generating SQL...")
    
    # Build context string
    context_str = ""
    for item in context:
        context_str += f"- {item['description']}\n"
    
    # Build history string
    history_str = ""
    if history:
        for turn in history[-3:]:
            history_str += f"User: {turn.get('question', '')}\n"
    
    # Build prompt
    prompt = f"""
You are an expert PostgreSQL SQL assistant. Given the following schema, write a valid PostgreSQL SELECT query.

## Schema:
{context_str}

## History:
{history_str if history_str else "No previous conversation."}

## Question:
{question}

## Instructions:
- Return ONLY the SQL query.
- No explanations, no markdown.
- Use exact table and column names from the schema.
- Add LIMIT if needed.

SQL:
"""
    
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are a PostgreSQL expert. Return only the SQL query."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        sql = completion.choices[0].message.content.strip()
        
        # Clean markdown
        if sql.startswith("```sql"):
            sql = sql[6:]
        if sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        
        sql = sql.strip()
        print(f"✅ SQL Generated")
        return sql
        
    except Exception as e:
        print(f"❌ Error generating SQL: {e}")
        return None

if __name__ == "__main__":
    test_context = [
        {"table_name": "products", "description": "Products table with product_name, unit_price, category_id"},
        {"table_name": "order_details", "description": "Order details with order_id, product_id, quantity, unit_price"}
    ]
    sql = generate_sql("top 5 products by revenue", test_context)
    print("\n📝 Generated SQL:")
    print(sql)