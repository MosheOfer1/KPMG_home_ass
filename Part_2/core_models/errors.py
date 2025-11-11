class CoreModelsError(Exception):
    """Base error for core-models."""


class ValidationProblem(CoreModelsError):
    """Input did not satisfy schema constraints."""


class RateLimitError(CoreModelsError):
    """Provider or service rate-limited the request."""


class KbEmptyError(CoreModelsError):
    """Retrieval produced no useful knowledge base snippets."""


class SafetyBlockError(CoreModelsError):
    """Intent or content violates safety/policy constraints."""
