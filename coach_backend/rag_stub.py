"""
RAG System for Coach context.
Connects to Pinecone (Vector DB) and OpenAI (Embeddings).
"""
import os
import openai
from pinecone import Pinecone

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Ensure this is set in environment
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY") 
PINECONE_INDEX_NAME = "coach-memory"

# Initialize Clients
try:
    openai.api_key = OPENAI_API_KEY
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)
except Exception as e:
    print(f"[RAG ERROR] Failed to init clients: {e}")
    index = None

def get_embedding(text: str):
    """Generates embedding vector for query."""
    response = openai.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def get_rag_context(user_id: str, query: str = "current focus") -> list:
    """
    Retrieves relevant memories from Pinecone based on user_id and query.
    """
    if not index or not OPENAI_API_KEY:
        print("[RAG] Missing API Keys or Index. Returning empty.")
        return []

    print(f"[RAG] Querying vector DB for user {user_id} with intent '{query}'...")
    
    try:
        # 1. Embed the query
        vector = get_embedding(query)
        
        # 2. Query Pinecone
        results = index.query(
            vector=vector,
            top_k=3,
            include_metadata=True,
            filter={
                "user_id": {"$eq": user_id}
            }
        )
        
        # 3. Extract text
        memories = []
        for match in results.matches:
            if match.metadata and "text" in match.metadata:
                memories.append(match.metadata["text"])
                
        return memories

    except Exception as e:
        print(f"[RAG ERROR] Retrieval failed: {e}")
        return []

