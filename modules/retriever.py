#!/usr/bin/env python3
"""
Module: retriever.py
Handles RAG (Retrieval-Augmented Generation) retrieval.
Takes a user question, finds relevant tables in ChromaDB using local embeddings.
"""

import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the embedding model (the same one we used to index the schema)
print("📥 Loading retrieval model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ Retrieval model loaded!")

# Initialize ChromaDB connection
chroma_client = chromadb.PersistentClient(path="./vector_store")
collection = chroma_client.get_collection("schema_metadata")

def retrieve_context(question: str, top_k: int = 5):
    """
    Retrieve the most relevant table schemas for a given user question.
    
    Args:
        question (str): The user's natural language question.
        top_k (int): Number of top relevant tables to retrieve.
    
    Returns:
        list: A list of table descriptions and names.
    """
    print(f"🔍 Retrieving context for: '{question}'")
    
    # Step 1: Convert the user question into a vector (embedding)
    question_embedding = embedding_model.encode(question).tolist()
    
    # Step 2: Query ChromaDB for the most similar table descriptions
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k
    )
    
    # Step 3: Extract the relevant table names and descriptions
    retrieved_docs = []
    if results and results['documents']:
        for i, doc in enumerate(results['documents'][0]):
            table_name = results['metadatas'][0][i]['table_name']
            retrieved_docs.append({
                "table_name": table_name,
                "description": doc
            })
            print(f"  ✅ Retrieved: {table_name}")
    
    return retrieved_docs

# Simple test block (runs only when you execute this file directly)
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🧪 TESTING RETRIEVER MODULE")
    print("="*50)
    
    test_question = "What were our top 5 products by revenue last quarter?"
    results = retrieve_context(test_question)
    
    print("\n📋 Retrieved Tables:")
    for item in results:
        print(f"  - {item['table_name']}")
    
    print("\n✅ Retriever test complete!")