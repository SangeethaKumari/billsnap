"""
Semantic Matching Layer.

PRODUCTION NOTE (say this out loud in the interview):
This uses TF-IDF + cosine similarity so the whole pipeline runs offline with
no model downloads. The interface (`embed` -> vector -> cosine similarity)
is identical to what you'd get from sentence-transformers or
text-embedding-3-small -- swapping the backend is a one-function change
(see `embed_texts_stub` below for where that swap happens). That's the
point: the matching *architecture* doesn't care which embedding model is
behind it, which is exactly the kind of decoupling you want in a system
that has to survive model upgrades over a multi-year AP product lifecycle.
"""

from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class MatchResult:
    invoice_line: dict
    po_line: dict | None
    similarity: float
    status: str  # "matched" | "no_match"


class POIndex:
    """Vector index over PO line-item descriptions (stand-in for a
    ChromaDB / FAISS collection in production)."""

    def __init__(self, po_lines: list[dict]):
        self.po_lines = po_lines
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2))
        corpus = [self._embed_text(p["description"]) for p in po_lines]
        self.matrix = self.vectorizer.fit_transform(corpus)

    @staticmethod
    def _embed_text(text: str) -> str:
        # Swap point: replace this whole class's vectorizer with a call to
        # sentence-transformers.encode() or an OpenAI embeddings call, and
        # swap TfidfVectorizer.transform -> model.encode(). Everything
        # downstream (cosine_similarity, threshold logic) stays identical.
        return text.lower()

    def best_match(self, query_text: str, threshold: float = 0.25) -> MatchResult | None:
        query_vec = self.vectorizer.transform([self._embed_text(query_text)])
        sims = cosine_similarity(query_vec, self.matrix)[0]
        best_idx = sims.argmax()
        best_score = float(sims[best_idx])
        if best_score < threshold:
            return None
        return self.po_lines[best_idx], best_score


def match_invoice_to_pos(invoice: dict, po_lines: list[dict], index: POIndex) -> list[MatchResult]:
    results = []
    for line in invoice["lines"]:
        match = index.best_match(line["description"])
        if match is None:
            results.append(MatchResult(invoice_line=line, po_line=None, similarity=0.0, status="no_match"))
        else:
            po_line, score = match
            results.append(MatchResult(invoice_line=line, po_line=po_line, similarity=score, status="matched"))
    return results
