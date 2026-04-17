from langchain_huggingface import HuggingFaceEmbeddings

def get_mobile_context_analyzer():
    """
    Lightweight embedding model for mobile context analyzer.
    Per user request, this expects the 'EmbeddingGemma-300M' architecture.
    """
    # Note: Using the exact string provided by the user. If this repository isn't public, it will attempt to fetch it from huggingface.
    return HuggingFaceEmbeddings(model_name="EmbeddingGemma-300M")

def get_laptop_context_analyzer():
    """
    Standard embedded tier for laptop context analyzer.
    """
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
