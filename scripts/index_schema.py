#!/usr/bin/env python3
"""
Schema Indexer for ChromaDB

This script connects to Supabase (PostgreSQL), reads the database schema,
creates embeddings for table descriptions, and stores them in ChromaDB
for RAG retrieval.
"""

import os

import chromadb
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer


# ============================================================
# Load environment variables
# ============================================================

load_dotenv()

DATABASE_URL = os.getenv("SUPABASE_READONLY_URL")

if not DATABASE_URL:
    raise ValueError(
        "SUPABASE_READONLY_URL is not set in the .env file."
    )


# ============================================================
# Initialize embedding model
# ============================================================

print("📥 Loading embedding model...")

model = SentenceTransformer("all-MiniLM-L6-v2")

print("✅ Model loaded!")


# ============================================================
# Initialize ChromaDB
# ============================================================

print("📂 Initializing ChromaDB...")

chroma_client = chromadb.PersistentClient(
    path="./vector_store"
)

collection = chroma_client.get_or_create_collection(
    name="schema_metadata",
    metadata={"hnsw:space": "cosine"}
)

print("✅ ChromaDB initialized!")


# ============================================================
# Fetch schema from Supabase
# ============================================================

def get_schema_from_supabase():
    """Fetch table and column metadata from Supabase."""

    print("🔌 Connecting to Supabase...")

    conn = None
    cur = None

    try:
        # Connect to Supabase using the read-only user
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        print("✅ Connected to Supabase!")

        # --------------------------------------------------------
        # Get all tables in the public schema
        # --------------------------------------------------------

        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
            """
        )

        tables = cur.fetchall()

        print(f"📊 Found {len(tables)} tables.")

        schema_data = []

        # --------------------------------------------------------
        # Process each table
        # --------------------------------------------------------

        for table in tables:

            table_name = table[0]

            # Get columns for this table
            cur.execute(
                """
                SELECT
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position;
                """,
                (table_name,)
            )

            columns = cur.fetchall()

            # ----------------------------------------------------
            # Create human-readable column descriptions
            # ----------------------------------------------------

            col_descriptions = []

            for col in columns:

                col_name = col[0]
                col_type = col[1]
                nullable = (
                    "NULL"
                    if col[2] == "YES"
                    else "NOT NULL"
                )

                col_descriptions.append(
                    f"{col_name} ({col_type}, {nullable})"
                )

            # ----------------------------------------------------
            # Add business context for important tables
            # ----------------------------------------------------

            business_hint = ""

            if table_name == "order_details":

                business_hint = (
                    "This table tracks sales revenue "
                    "(unit_price * quantity), order line items, "
                    "discounts, and product sales. "
                )

            elif table_name == "orders":

                business_hint = (
                    "This table tracks customer purchases, "
                    "order dates, shipping details, and order totals. "
                )

            elif table_name == "products":

                business_hint = (
                    "This table tracks product inventory, "
                    "pricing, supplier information, and stock levels. "
                )

            elif table_name == "customers":

                business_hint = (
                    "This table tracks customer information, "
                    "company names, contact details, and country locations. "
                )

            elif table_name == "employees":

                business_hint = (
                    "This table tracks employee information, "
                    "reporting structure, and sales territories. "
                )

            # ----------------------------------------------------
            # Create complete table description
            # ----------------------------------------------------

            description = (
                f"{business_hint}"
                f"Table '{table_name}' contains columns: "
                + ", ".join(col_descriptions)
            )

            # ----------------------------------------------------
            # Store schema information
            # ----------------------------------------------------

            schema_data.append(
                {
                    "table_name": table_name,
                    "description": description,
                    "columns": [col[0] for col in columns],
                }
            )

            print(
                f"  ✅ {table_name}: {len(columns)} columns"
            )

        return schema_data

    except Exception as e:

        print(f"❌ Error connecting to Supabase: {e}")

        return None

    finally:

        if cur is not None:
            cur.close()

        if conn is not None:
            conn.close()

        print("🔌 Supabase connection closed.")


# ============================================================
# Index schema into ChromaDB
# ============================================================

def index_schema(schema_data):
    """Generate embeddings and store schema data in ChromaDB."""

    if not schema_data:

        print("❌ No schema data to index.")

        return

    print(
        f"\n🔄 Indexing {len(schema_data)} tables into ChromaDB..."
    )

    for table_info in schema_data:

        table_name = table_info["table_name"]
        description = table_info["description"]

        # --------------------------------------------------------
        # Generate embedding
        # --------------------------------------------------------

        embedding = model.encode(description).tolist()

        # --------------------------------------------------------
        # Store / update document in ChromaDB
        # --------------------------------------------------------

        collection.upsert(
            ids=[f"table_{table_name}"],
            documents=[description],
            embeddings=[embedding],
            metadatas=[
                {
                    "table_name": table_name,
                    "type": "table",
                }
            ],
        )

        print(f"  ✅ Indexed: {table_name}")

    print(
        f"\n✅ Successfully indexed "
        f"{len(schema_data)} tables in ChromaDB!"
    )

    print("📂 Vector store saved at: ./vector_store")


# ============================================================
# Main function
# ============================================================

def main():
    """Main execution function."""

    print("\n" + "=" * 60)
    print("🚀 STARTING SCHEMA INDEXING")
    print("=" * 60 + "\n")

    # --------------------------------------------------------
    # Step 1: Fetch schema from Supabase
    # --------------------------------------------------------

    schema_data = get_schema_from_supabase()

    if not schema_data:

        print("❌ Failed to fetch schema. Exiting.")

        return

    # --------------------------------------------------------
    # Step 2: Index schema into ChromaDB
    # --------------------------------------------------------

    index_schema(schema_data)

    print("\n" + "=" * 60)
    print("✅ SCHEMA INDEXING COMPLETE!")
    print("=" * 60)


# ============================================================
# Script entry point
# ============================================================

if __name__ == "__main__":
    main()