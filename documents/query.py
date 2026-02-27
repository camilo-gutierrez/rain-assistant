"""Query expansion and multi-hop retrieval for Rain RAG system (Phase 4).

Provides simple NLP-based query expansion (no LLM required) and
key term extraction for multi-hop search.
"""

import re
from collections import Counter
from typing import Optional

# Common English + Spanish stop words
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "but", "and", "or", "if", "about", "it", "its", "i", "me", "my",
    "we", "our", "you", "your", "he", "him", "his", "she", "her", "they",
    "them", "their", "this", "that", "these", "those", "what", "which",
    "who", "whom", "up", "don", "t", "s",
    # Spanish
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "en", "con", "por", "para", "es", "son", "fue", "ser", "estar",
    "como", "que", "qué", "se", "su", "sus", "al", "lo", "le", "les",
    "más", "pero", "ya", "si", "sí", "no", "muy", "también", "entre",
    "hay", "tiene", "puede", "cuando", "donde", "sin", "sobre", "este",
    "esta", "estos", "estas", "ese", "esa", "esos", "esas", "yo", "tú",
    "él", "ella", "nosotros", "ellos", "ellas",
})

# Patterns for technical terms
_CAMEL_CASE = re.compile(r"[a-z][A-Z]")
_SNAKE_CASE = re.compile(r"\w+_\w+")
_WORD_RE = re.compile(r"\b\w+\b")


def expand_query_simple(query: str) -> list[str]:
    """Expand a query into multiple search variants using simple NLP.

    Always includes the original query. Adds a "core terms" variant
    (stop words removed) if it differs meaningfully from the original.

    Args:
        query: Original user query.

    Returns:
        List of 1-3 query variants, always starting with the original.
    """
    if not query or not query.strip():
        return [query] if query else []

    variants = [query]

    # Variant 1: core terms (remove stop words)
    words = _WORD_RE.findall(query.lower())
    core = [w for w in words if w not in _STOP_WORDS and len(w) > 1]
    if core and len(core) < len(words):
        core_query = " ".join(core)
        if core_query != query.lower().strip():
            variants.append(core_query)

    # Variant 2: extract quoted phrases and technical terms
    quoted = re.findall(r'"([^"]+)"', query)
    tech_terms = _extract_technical_terms(query)
    extra_terms = quoted + tech_terms
    if extra_terms:
        extra_query = " ".join(extra_terms)
        if extra_query not in variants:
            variants.append(extra_query)

    return variants[:3]


def extract_key_terms(text: str, max_terms: int = 5) -> list[str]:
    """Extract key terms/entities from text for multi-hop search.

    Uses a combination of:
    - TF-IDF-like importance (uncommon words weighted higher)
    - Capitalized phrases (likely named entities)
    - Technical terms (camelCase, snake_case)

    Args:
        text: Text to extract terms from.
        max_terms: Maximum number of terms to extract.

    Returns:
        List of key terms sorted by estimated importance.
    """
    if not text:
        return []

    words = _WORD_RE.findall(text)
    if not words:
        return []

    # Find capitalized words (potential named entities), excluding sentence starts
    sentences = re.split(r"[.!?]\s+", text)
    named_entities = set()
    for sentence in sentences:
        sentence_words = sentence.split()
        for w in sentence_words[1:]:  # Skip first word (sentence start)
            clean = w.strip(".,;:!?\"'()[]{}")
            if clean and clean[0].isupper() and len(clean) > 1 and clean.lower() not in _STOP_WORDS:
                named_entities.add(clean)

    # Find technical terms
    tech_terms = set(_extract_technical_terms(text))

    # TF scoring (prefer less common words)
    lower_words = [w.lower() for w in words if w.lower() not in _STOP_WORDS and len(w) > 2]
    tf = Counter(lower_words)
    total = len(lower_words) if lower_words else 1

    scored: list[tuple[float, str]] = []
    seen = set()

    # Named entities get a boost
    for term in named_entities:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            freq = tf.get(key, 1) / total
            scored.append((freq + 0.5, term))  # +0.5 boost for named entities

    # Technical terms get a boost
    for term in tech_terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            freq = tf.get(key, 1) / total
            scored.append((freq + 0.3, term))  # +0.3 boost for tech terms

    # Top TF words
    for word, count in tf.most_common(max_terms * 2):
        if word not in seen and len(word) > 3:
            seen.add(word)
            scored.append((count / total, word))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [term for _, term in scored[:max_terms]]


def deduplicate_results(results: list[dict], key: str = "id") -> list[dict]:
    """Deduplicate search results, keeping the highest-scored entry.

    Args:
        results: Combined results from multiple searches.
        key: Dict key to use for deduplication (default "id").

    Returns:
        Deduplicated list sorted by _score descending.
    """
    best: dict[str, dict] = {}
    for r in results:
        rid = r.get(key, "")
        if not rid:
            continue
        existing = best.get(rid)
        if existing is None or r.get("_score", 0) > existing.get("_score", 0):
            best[rid] = r

    deduped = list(best.values())
    deduped.sort(key=lambda x: x.get("_score", 0), reverse=True)
    return deduped


def _extract_technical_terms(text: str) -> list[str]:
    """Extract camelCase and snake_case terms from text."""
    terms = []
    # camelCase: split and join
    for match in _CAMEL_CASE.finditer(text):
        start = text.rfind(" ", 0, match.start()) + 1
        end = text.find(" ", match.end())
        if end == -1:
            end = len(text)
        term = text[start:end].strip(".,;:!?\"'()[]{}")
        if len(term) > 2:
            terms.append(term)

    # snake_case
    for match in _SNAKE_CASE.finditer(text):
        term = match.group()
        if len(term) > 3:
            terms.append(term)

    return terms
