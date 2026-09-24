import re
from typing import List, Sequence, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9]+")


def normalize(text: str) -> str:
    if not text:
        return ""
    return " ".join(_TOKEN_RE.findall(text.lower()))


def _safe_vectorizer(texts: Sequence[str]) -> Tuple[TfidfVectorizer, np.ndarray]:
    cleaned = [normalize(t) or " " for t in texts]
    vec = TfidfVectorizer(
        min_df=1,
        ngram_range=(1, 2),
        stop_words="english",
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9]+\b",
    )
    matrix = vec.fit_transform(cleaned)
    return vec, matrix


def cosine_scores(query: str, corpus: Sequence[str]) -> List[float]:
    if not corpus:
        return []
    all_texts = [query] + list(corpus)
    _, matrix = _safe_vectorizer(all_texts)
    if matrix.shape[0] < 2:
        return [0.0] * len(corpus)
    sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    return sims.tolist()


def pairwise_matrix(texts: Sequence[str]) -> np.ndarray:
    if len(texts) < 2:
        return np.zeros((len(texts), len(texts)))
    _, matrix = _safe_vectorizer(texts)
    return cosine_similarity(matrix)


def keyword_overlap(a: str, b: str) -> float:
    ta = set(normalize(a).split())
    tb = set(normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def max_score_against(query: str, corpus: Sequence[str]) -> Tuple[int, float]:
    scores = cosine_scores(query, corpus)
    if not scores:
        return -1, 0.0
    idx = int(np.argmax(scores))
    return idx, float(scores[idx])


def duplicates(texts: Sequence[str], threshold: float = 0.85) -> List[Tuple[int, int, float]]:
    if len(texts) < 2:
        return []
    matrix = pairwise_matrix(texts)
    pairs: List[Tuple[int, int, float]] = []
    n = matrix.shape[0]
    for i in range(n):
        for j in range(i + 1, n):
            score = float(matrix[i, j])
            if score >= threshold:
                pairs.append((i, j, score))
    return pairs


NEGATION_TERMS = (
    " not ",
    " never ",
    " no ",
    " without ",
    "must not",
    "cannot",
    "can't",
    "won't",
    "should not",
    "shouldn't",
    "do not",
    "don't",
    "forbidden",
    "prohibited",
    "disallow",
)


def has_negation(text: str) -> bool:
    if not text:
        return False
    lower = " " + text.lower() + " "
    return any(term in lower for term in NEGATION_TERMS)
