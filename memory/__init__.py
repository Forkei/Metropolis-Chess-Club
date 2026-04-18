"""
Memory system components for Chess Master agent.

Includes:
- Weaviate vector database client
- Memory schema definitions
- Memory retrieval and storage
"""

from memory.schemas import Memory, MemoryType

def __getattr__(name):
    if name == "WeaviateClient":
        try:
            from memory.weaviate_client import WeaviateClient
            return WeaviateClient
        except ImportError:
            return None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "WeaviateClient",
    "Memory",
    "MemoryType",
]
