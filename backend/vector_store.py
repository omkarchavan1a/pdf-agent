import numpy as np
from typing import List

# Optional dependencies are loaded lazily to avoid import-time failures in environments
# that do not have all heavy ML libraries installed (eg. torchvision for some transformers models).
HAS_SENTENCE_TRANSFORMERS = False
HAS_FAISS = False
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    HAS_SENTENCE_TRANSFORMERS = True
except Exception:
    SentenceTransformer = None  # type: ignore
try:
    import faiss  # type: ignore
    HAS_FAISS = True
except Exception:
    faiss = None  # type: ignore

class VectorStore:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        print(f"[INFO] Initializing Embedding Model: {model_name}...")
        self.use_fallback = True
        self.dimension = 128  # fallback embedding size
        self.chunks: List[str] = []

        # Try to initialize real embedding stack if available
        if HAS_SENTENCE_TRANSFORMERS and SentenceTransformer is not None:
            try:
                self.model = SentenceTransformer(model_name)  # type: ignore
                self.dimension = self.model.get_sentence_embedding_dimension()
                self.use_fallback = False
                # Prefer FAISS if available for fast similarity search
                if HAS_FAISS and faiss is not None:
                    self.index = faiss.IndexFlatL2(self.dimension)
                else:
                    self.index = None
            except Exception:
                # Fall back to deterministic lightweight embeddings
                self.model = None  # type: ignore
                self.use_fallback = True
                self.index = None
        else:
            self.model = None  # type: ignore
            self.index = None
            self.use_fallback = True

        # In fallback mode we keep lightweight in-memory embeddings
        self._fallback_embeddings = []  # type: List[List[float]]

    def _simple_embedding(self, texts: List[str]) -> np.ndarray:
        """A tiny, deterministic embedding for environments without dependencies.
        This is a lightweight fallback and is not semantic, but keeps the flow working.
        """
        import numpy as _np
        dim = self.dimension
        vecs = []
        for t in texts:
            # deterministic seed from text content
            seed = sum(ord(ch) for ch in t) % (2**32)
            rng = _np.random.default_rng(seed)
            v = rng.normal(size=(dim,)).astype('float32')
            norm = (_np.linalg.norm(v) + 1e-9)
            vecs.append((v / norm).tolist())
        return _np.array(vecs, dtype='float32')

    def add_documents(self, chunks: List[str]):
        """Embed and add document chunks to the index (real or fallback)."""
        if not chunks:
            return
        self.chunks.extend(chunks)
        if not self.use_fallback and getattr(self, 'model', None) is not None:
            embeddings = self.model.encode(chunks)  # type: ignore
            embeddings_np = np.array(embeddings).astype('float32')
            if self.index is not None:
                self.index.add(embeddings_np)
            else:
                # Fallback to in-memory storage if FAISS index isn't available
                self._fallback_embeddings.extend(embeddings_np.tolist())
        else:
            # Fallback path: lightweight embedding per chunk
            emb = self._simple_embedding(chunks)
            self._fallback_embeddings.extend(emb.tolist())
        print(f"[OK] Indexed {len(chunks)} document chunks.")

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        dot = float(np.dot(a, b))
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)

    def search(self, query: str, top_k: int = 5) -> str:
        """Retrieve the most relevant chunks for a query."""
        if not self.chunks:
            return ""

        if not self.use_fallback and self.index is not None:
            # Real embedding path
            query_embedding = self.model.encode([query])  # type: ignore
            query_embedding_np = np.array(query_embedding).astype('float32')
            distances, indices = self.index.search(query_embedding_np, top_k)
            relevant_chunks: List[str] = []
            for idx in indices[0]:
                if idx != -1 and idx < len(self.chunks):
                    relevant_chunks.append(self.chunks[idx])
            return "\n\n---\n\n".join(relevant_chunks)

        # Fallback path: simple cosine similarity over lightweight embeddings
        # Ensure we have embeddings for all chunks
        if not self._fallback_embeddings:
            # If no embeddings stored yet, fall back to the first chunk
            return self.chunks[:top_k] and "\n\n---\n\n".join(self.chunks[:top_k]) or ""

        # Build embeddings for current query (fallback path)
        q_emb = self._simple_embedding([query])[0]
        # Compare against stored chunk embeddings linearly
        candidates = []  # (score, chunk)
        for i, chunk in enumerate(self.chunks):
            if self.use_fallback:
                # Align with how embeddings are stored in fallback: list of vectors
                # _fallback_embeddings may be a list of arrays in order; infer index
                if i < len(self._fallback_embeddings):
                    c_emb = self._fallback_embeddings[i]
                    c_emb = np.asarray(c_emb, dtype='float32')
                else:
                    # Compute on the fly if missing
                    c_emb = self._simple_embedding([chunk])[0]
            else:
                c_emb = None
            if c_emb is None:
                continue
            score = self._cosine_similarity(q_emb, c_emb)
            candidates.append((score, chunk))
        # Sort by score desc and return top_k chunks
        candidates.sort(key=lambda x: x[0], reverse=True)
        top = [c for _, c in candidates[:top_k]]
        return "\n\n---\n\n".join(top)

    def clear(self):
        """Reset the store."""
        self.index = faiss.IndexFlatL2(self.dimension) if (HAS_FAISS and faiss is not None) else None  # type: ignore
        self.chunks = []
        self._fallback_embeddings = []
