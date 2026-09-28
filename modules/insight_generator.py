#!/usr/bin/env python3
"""
Module: insight_generator.py
Generates plain-English insights from query results using Groq.
Uses openai/gpt-oss-20b for faster summarization.
"""

import os
import httpx
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("❌ GROQ_API_KEY not found in environment!")
    exit(1)

client = Groq(
    api_key=GROQ_API_KEY,
    http_client=httpx.Client(timeout=60.0)
)

def generate_insight(question: str, df, sql: str = None):
    if df is None or len(df) == 0:
        return "I couldn't find any data to answer your question."
    
    num_rows = len(df)
    preview = df.head(5).to_string(index=False)
    columns = ", ".join(df.columns.tolist())
    
    prompt = f"""
You are a data analyst. Given the following query results, write a short 2-3 sentence insight summary.

User's question: "{question}"

Data Preview (first 5 rows):
{preview}

Total rows: {num_rows}
Columns: {columns}

Write a concise, natural-language summary that directly answers the user's question. 
Focus on the key numbers, trends, or patterns.
Don't mention SQL or the database.
"""
    
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "You are a data analyst. Provide concise, accurate summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        insight = completion.choices[0].message.content.strip()
        print(f"💡 Insight generated.")
        return insight
        
    except Exception as e:
        print(f"❌ Error generating insight: {e}")
        return f"Found {num_rows} rows matching your question."

if __name__ == "__main__":
    import pandas as pd
    print("\n" + "="*50)
    print("🧪 TESTING INSIGHT GENERATOR MODULE")
    print("="*50)
    
    test_df = pd.DataFrame({
        "product_name": ["Chai", "Chang", "Aniseed Syrup"],
        "total_revenue": [15000, 12000, 8000],
        "units_sold": [120, 90, 60]
    })
    test_question = "What were our top 3 products by revenue?"
    insight = generate_insight(test_question, test_df)
    print(f"\n📝 Insight: {insight}")
    print("\n✅ Insight Generator test complete!")