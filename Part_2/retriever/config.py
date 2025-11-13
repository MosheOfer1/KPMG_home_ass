from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class RetrieverConfig:
    """
    Represents configuration settings for a retrieval system.

    This class contains configuration parameters necessary for setting up
    a retriever, including paths and deployment settings. These parameters
    are read from environment variables with fallback default values if the
    variables are not defined.

    Attributes:
        kb_dir: A directory path to the knowledge base data. Derived from
            the environment variable 'PHASE2_DATA_DIR' or defaults to
            'Part_2/phase2_data' if not set.
        embeddings_deployment: The deployment name of the Azure OpenAI
            service for embeddings. Derived from the environment variable
            'AZURE_OPENAI_EMBED_DEPLOYMENT' or defaults to
            'text-embedding-ada-002' if not set.
        cache_dir: A directory path for storing retriever cache data.
            Derived from the environment variable 'RETRIEVER_CACHE_DIR'
            or defaults to 'Part_2/.kb_cache' if not set.
    """
    kb_dir: str = os.getenv("PHASE2_DATA_DIR", "Part_2/phase2_data")
    embeddings_deployment: str = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-ada-002")
    cache_dir: str = os.getenv("RETRIEVER_CACHE_DIR", "Part_2/.kb_cache")
