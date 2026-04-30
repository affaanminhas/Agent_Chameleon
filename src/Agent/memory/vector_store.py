"""
Step 1: Persistent Memory with ChromaDB
Field: Vector Databases, Embeddings
Purpose: Store and retrieve conversations semantically for any persona
"""

import chromadb
from chromadb.config import Settings
import os
from datetime import datetime
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import uuid


class Memory:
    """
    A persistent memory system for any persona using vector search.
    """
    
    def __init__(self, persist_directory: str, persona: str = None):
        """
        Initialize the memory system.
        
        Args:
            persist_directory: Where ChromaDB stores data on disk
            persona: Persona identifier for metadata (optional)
        """
        self.persona = persona or "agent"
        
        # 1. Initialize embedding model
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # 2. Initialize ChromaDB with persistence
        print(f"Initializing ChromaDB with persistence at: {persist_directory}")
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 3. Create or get collection for memories
        self.collection = self.client.get_or_create_collection(
            name="agent_memories",
            metadata={"hnsw:space": "cosine"}
        )
        
        print(f"Memory initialized. Current memory count: {self.collection.count()}")
    
    def store_interaction(self, 
                          user_input: str, 
                          agent_response: str,
                          topic: Optional[str] = None,
                          metadata: Optional[Dict] = None) -> str:
        """
        Store a conversation interaction in memory.
        """
        memory_id = str(uuid.uuid4())
        
        text_to_embed = f"User: {user_input}\n{self.persona}: {agent_response}"
        embedding = self.embedding_model.encode(text_to_embed).tolist()
        
        memory_metadata = {
            "timestamp": datetime.now().isoformat(),
            "topic": topic or "general",
            "user_input_preview": user_input[:100],
            "response_preview": agent_response[:100],
            "persona": self.persona
        }
        
        if metadata:
            memory_metadata.update(metadata)
        
        self.collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            metadatas=[memory_metadata],
            documents=[text_to_embed]
        )
        
        print(f"📝 Stored memory {memory_id} about: {topic or 'general'}")
        return memory_id
    
    def recall_similar(self, 
                       query: str, 
                       n_results: int = 5,
                       similarity_threshold: float = 0.3,
                       topic_filter: Optional[str] = None) -> List[Dict]:
        """
        Find memories semantically similar to the query.
        """

        count = self.collection.count()
        if count == 0:
            return []
        n_results = min(n_results, count)  # can't request more than exists

        query_embedding = self.embedding_model.encode(query).tolist()
        where_filter = {"topic": topic_filter} if topic_filter else None
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter
        )
        
        memories = []
        if results['ids'][0]:
            for i in range(len(results['ids'][0])):
                similarity = 1 - results["distances"][0][i]
                if similarity >= similarity_threshold:
                    memories.append({
                        'id': results['ids'][0][i],
                        'text': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'similarity': similarity
                    })
        
        return memories
    
    def get_recent_memories(self, limit: int = 10) -> List[Dict]:
        """Get most recent memories."""
        results = self.collection.get(limit=limit)
        
        memories = []
        if results['ids']:
            for i in range(len(results['ids'])):
                memories.append({
                    'id': results['ids'][i],
                    'text': results['documents'][i],
                    'metadata': results['metadatas'][i]
                })
            
            memories.sort(
                key=lambda x: x['metadata'].get('timestamp', ''),
                reverse=True
            )
        
        return memories
    
    def delete_memory(self, memory_id: str):
        self.collection.delete(ids=[memory_id])
        print(f"Deleted memory {memory_id}")
    
    def count_memories(self) -> int:
        return self.collection.count()