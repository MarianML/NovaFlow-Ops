import math


def cosine(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between vectors.
    """
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


def top_k(query_vec: list[float], docs: list[tuple[int, str, str, list[float]]], k: int = 4):
    """
    Return top-k docs by cosine similarity.
    """
    scored = []
    for doc_id, title, content, vec in docs:
        scored.append((cosine(query_vec, vec), doc_id, title, content))
    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[:k]
