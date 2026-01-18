"""
RAG System for Coach context.
Connects to Pinecone (Vector DB) and uses Local Embeddings (Sentence Transformers).
"""
import os
from pinecone import Pinecone
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pathlib import Path

# Load from backend/.env (sibling directory)
env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

# Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY") 
PINECONE_INDEX_NAME = "coach-memory"

# Initialize Clients
try:
    # Use a small, fast local model (384 dimensions)
    # Note: If your Pinecone index is 1536 dim (OpenAI), this will crash.
    # We will assume you will create a NEW index or we pad the vector.
    # For simplicity, let's use a model that matches or just handle the mismatch check.
    # OpenAI is 1536. 'all-MiniLM-L6-v2' is 384. 
    # To drop OpenAI completely, re-create Pinecone index with dim=384.
    embed_model = SentenceTransformer('all-MiniLM-L6-v2') 
    
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(name=PINECONE_INDEX_NAME) 
except Exception as e:
    print(f"[RAG ERROR] Failed to init clients: {e}")
    index = None
    embed_model = None

# ...existing code...

def get_embedding(text: str):
    """Generates embedding vector utilizing local CPU."""
    if not embed_model: return []
    return embed_model.encode(text).tolist()

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

