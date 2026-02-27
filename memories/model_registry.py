"""Pluggable embedding model registry for Rain (Phase 6).

Supports multiple embedding models with auto-selection based on content type.
Models are lazy-loaded on first use. Falls back gracefully when models
or dependencies are unavailable.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a registered embedding model."""
    name: str
    model_id: str
    dim: int
    content_types: list[str] = field(default_factory=lambda: ["*"])
    priority: int = 0  # higher = preferred when multiple match
    requires: str = "sentence-transformers"


# Default registry
_REGISTRY: dict[str, ModelConfig] = {
    "default": ModelConfig(
        name="default",
        model_id="all-MiniLM-L6-v2",
        dim=384,
        content_types=["*"],
        priority=0,
    ),
    "code": ModelConfig(
        name="code",
        model_id="microsoft/codebert-base",
        dim=768,
        content_types=["code"],
        priority=10,
    ),
}

# Loaded model instances (lazy)
_loaded_models: dict[str, object] = {}

# Source code extensions (for auto content type detection)
_CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".c", ".cpp",
    ".h", ".hpp", ".rb", ".php", ".swift", ".kt", ".scala", ".sh", ".bash",
    ".zsh", ".ps1", ".sql", ".r", ".m", ".lua",
})


def register_model(config: ModelConfig) -> None:
    """Register a new embedding model configuration."""
    _REGISTRY[config.name] = config
    logger.info("Registered embedding model '%s' (%s)", config.name, config.model_id)


def get_model_for_content(
    content_type: str = "text",
    preferred: Optional[str] = None,
) -> tuple[str, ModelConfig]:
    """Select the best model for a content type.

    Args:
        content_type: "text", "code", etc.
        preferred: Override model name. If available, use it.

    Returns:
        (model_name, ModelConfig) tuple.
    """
    # Preferred override
    if preferred and preferred in _REGISTRY:
        return preferred, _REGISTRY[preferred]

    # Find best matching model
    candidates = []
    for name, config in _REGISTRY.items():
        if "*" in config.content_types or content_type in config.content_types:
            candidates.append((config.priority, name, config))

    if not candidates:
        return "default", _REGISTRY["default"]

    candidates.sort(key=lambda x: x[0], reverse=True)
    # Among highest-priority matches, prefer the content-specific one
    best = candidates[0]
    return best[1], best[2]


def get_embedding_batch(
    texts: list[str],
    model_name: str = "default",
) -> list[Optional[list[float]]]:
    """Generate embeddings for a batch of texts.

    Uses the specified model (lazy-loaded). Returns None entries
    for texts that fail to embed.

    Args:
        texts: List of text strings to embed.
        model_name: Name from the registry (default: "default").

    Returns:
        List of embedding vectors (or None for failures).
    """
    if not texts:
        return []

    config = _REGISTRY.get(model_name, _REGISTRY.get("default"))
    if config is None:
        return [None] * len(texts)

    model = _load_model(config)
    if model is None:
        # Fall back to individual embedding via the legacy function
        from .embeddings import get_embedding
        return [get_embedding(t) for t in texts]

    try:
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        logger.error("Batch embedding failed with model '%s': %s", model_name, e)
        return [None] * len(texts)


def content_type_from_extension(ext: str) -> str:
    """Map file extension to content type for model selection."""
    return "code" if ext.lower() in _CODE_EXTENSIONS else "text"


def _load_model(config: ModelConfig):
    """Lazy-load a sentence-transformers model."""
    if config.model_id in _loaded_models:
        return _loaded_models[config.model_id]

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model '%s' (%s)...", config.name, config.model_id)
        model = SentenceTransformer(config.model_id)
        _loaded_models[config.model_id] = model
        logger.info("Model '%s' loaded successfully.", config.name)
        return model
    except ImportError:
        logger.warning("sentence-transformers not installed for model '%s'", config.name)
        return None
    except Exception as e:
        logger.error("Failed to load model '%s': %s", config.name, e)
        return None
