"""
Module: cache.py
Handles caching of query results using SQLite to avoid redundant LLM and database calls.
"""

import hashlib
import json
import sqlite3
import os
import pandas as pd
from datetime import datetime, timedelta

# Path to the cache database
CACHE_DB_PATH = "cache.db"

def get_db_connection():
    """Get a connection to the SQLite cache database."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_cache_table():
    """Create the cache table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_cache (
            query_hash TEXT PRIMARY KEY,
            question TEXT,
            sql TEXT,
            result_json TEXT,
            insight TEXT,
            fig_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def normalize_question(question: str) -> str:
    """Normalize the question to create a consistent cache key."""
    return " ".join(question.lower().strip().split())

def get_cache(question: str):
    """
    Retrieve cached results for a question if available and not expired (24h TTL).
    Returns None if cache miss or expired.
    """
    init_cache_table()
    
    normalized_q = normalize_question(question)
    query_hash = hashlib.md5(normalized_q.encode()).hexdigest()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT question, sql, result_json, insight, fig_json, created_at
        FROM query_cache
        WHERE query_hash = ?
    """, (query_hash,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        # Check TTL (24 hours)
        created_at = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
        if datetime.now() - created_at < timedelta(hours=24):
            # Deserialize the results
            df = pd.read_json(row["result_json"]) if row["result_json"] else None
            fig = None  # For simplicity, we skip fig caching in v1 to avoid plotly issues
            return {
                "question": row["question"],
                "sql": row["sql"],
                "df": df,
                "insight": row["insight"],
                "fig": None
            }
    return None

def set_cache(question: str, sql: str, df: pd.DataFrame, insight: str, fig=None):
    """
    Store the query results in the cache.
    """
    init_cache_table()
    
    normalized_q = normalize_question(question)
    query_hash = hashlib.md5(normalized_q.encode()).hexdigest()
    
    # Serialize DataFrame to JSON
    result_json = df.to_json(orient="records", date_format="iso") if df is not None else None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO query_cache (query_hash, question, sql, result_json, insight, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (query_hash, question, sql, result_json, insight))
    
    conn.commit()
    conn.close()
    print(f"✅ Cached result for question: {question[:30]}...")

# Initialize the cache table when the module is imported
init_cache_table()
