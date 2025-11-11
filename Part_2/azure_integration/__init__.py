from .interfaces import ILLMClient, IEmbeddingsClient
from .config import AzureOpenAIConfig, load_config
from .clients import AzureChatClient, AzureEmbeddingsClient
from dotenv import load_dotenv

# Load .env once when the module is imported
load_dotenv()

__all__ = [
    "ILLMClient",
    "IEmbeddingsClient",
    "AzureOpenAIConfig",
    "load_config",
    "AzureChatClient",
    "AzureEmbeddingsClient",
]
