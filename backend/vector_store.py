import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from typing import List, Dict

class VectorStore:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        print(f"[INFO] Initializing Embedding Model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.dimension = 384  # MiniLM-L6-v2 dimension
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []

    def add_documents(self, chunks: List[str]):
        """
        Embed and add document chunks to the FAISS index.
        """
        if not chunks:
            return
        
        self.chunks.extend(chunks)
        embeddings = self.model.encode(chunks)
        
        # FAISS expects float32
        embeddings_np = np.array(embeddings).astype('float32')
        self.index.add(embeddings_np)
        print(f"[OK] Indexed {len(chunks)} document chunks.")

    def search(self, query: str, top_k: int = 5) -> str:
        """
        Retrieve the most relevant chunks for a query.
        """
        if self.index.ntotal == 0:
            return ""

        query_embedding = self.model.encode([query])
        query_embedding_np = np.array(query_embedding).astype('float32')
        
        distances, indices = self.index.search(query_embedding_np, top_k)
        
        relevant_chunks = []
        for idx in indices[0]:
            if idx != -1 and idx < len(self.chunks):
                relevant_chunks.append(self.chunks[idx])
        
        return "\n\n---\n\n".join(relevant_chunks)

    def clear(self):
        """Reset the store."""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []
