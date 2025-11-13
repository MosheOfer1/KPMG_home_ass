from __future__ import annotations
from typing import Iterable, List, Protocol, Optional, Dict


class ILLMClient(Protocol):
    """
    Interface for an LLM (Large Language Model) Client.

    Defines the protocol for interacting with a language model by providing a
    method to facilitate chat-like interactions.

    """
    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """Return assistant text (JSON string if json_mode=True)."""
        ...


class IEmbeddingsClient(Protocol):
    def embed_texts(
        self,
        texts: Iterable[str],
        *,
        model: Optional[str] = None,
        batch_size: int = 64,
    ) -> List[List[float]]:
        """
        Generate embeddings for a given set of texts using a specified model. The function processes
        texts in batches to optimize performance. It returns a list of embeddings where each embedding
        is a vector of float values corresponding to a text input. Default model and batch size values
        can be customized if needed.

        :param texts:
            An iterable containing text strings for which embeddings need to be generated.
        :param model:
            The name of the model to use for embedding. Default is None, which implies using
            the preconfigured or default model.
        :param batch_size:
            An integer specifying the size of each batch of texts to process. Default is 64.
        :return:
            A list of lists, where each inner list represents the embedding of the corresponding
            text in the input iterable.
        """
        ...
