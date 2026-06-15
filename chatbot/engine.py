"""A lightweight, dependency-free retrieval engine for the chatbot.

The engine reads plain-text / Markdown reference files, splits them into
passages and answers questions by ranking passages with a classic TF-IDF
cosine-similarity model. It is intentionally implemented with only the Python
standard library so the chatbot runs anywhere without API keys or heavy ML
dependencies.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Protocol, Sequence, Tuple

# File extensions that are treated as reference documents.
SUPPORTED_EXTENSIONS = (".md", ".markdown", ".txt", ".text")

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A small set of very common English words that add noise to matching.
_STOPWORDS = frozenset(
    """
    a an and are as at be but by for from has have how i in is it its of on or
    that the this to was were what when where which who why will with you your
    do does did can could should would me my we our us
    """.split()
)


def tokenize(text: str) -> List[str]:
    """Lower-case a string and split it into alphanumeric tokens."""
    return _TOKEN_RE.findall(text.lower())


class DocumentSource(Protocol):
    """Anything that can supply ``(name, content)`` reference documents.

    SharePoint is the primary implementation, but any object with a
    ``fetch_documents`` method works, which keeps the engine decoupled from a
    specific backend and easy to test.
    """

    def fetch_documents(self) -> Iterable[Tuple[str, str]]:
        ...


@dataclass
class Document:
    """A single passage extracted from a reference file."""

    text: str
    source: str
    tokens: List[str] = field(default_factory=list)
    term_freq: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tokens:
            self.tokens = tokenize(self.text)
        if not self.term_freq:
            self.term_freq = _term_frequencies(self.tokens)


def _term_frequencies(tokens: Sequence[str]) -> Dict[str, float]:
    """Return normalised term frequencies for a token sequence."""
    counts: Dict[str, float] = {}
    for token in tokens:
        if token in _STOPWORDS:
            continue
        counts[token] = counts.get(token, 0.0) + 1.0
    total = sum(counts.values())
    if total:
        for token in counts:
            counts[token] /= total
    return counts


def split_into_passages(text: str) -> List[str]:
    """Split a document into passages on blank lines.

    Markdown headings are attached to the passage that follows them so a
    heading like ``## Hours`` stays grouped with its answer text.
    """
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text)]
    passages: List[str] = []
    pending_heading = ""
    for block in blocks:
        if not block:
            continue
        # A short line that is only a Markdown heading is treated as context
        # for the following block rather than as its own passage.
        if re.fullmatch(r"#{1,6}\s+.+", block) and "\n" not in block:
            pending_heading = re.sub(r"^#{1,6}\s+", "", block).strip()
            continue
        if pending_heading:
            block = f"{pending_heading}\n{block}"
            pending_heading = ""
        passages.append(block)
    if pending_heading:
        passages.append(pending_heading)
    return passages


@dataclass
class Answer:
    """The result of a query against the engine."""

    text: str
    source: str
    score: float
    found: bool


class ChatbotEngine:
    """Indexes reference files and answers questions from their content."""

    def __init__(
        self,
        reference_dir: str | Path,
        min_score: float = 0.05,
        sources: Sequence["DocumentSource"] | None = None,
    ) -> None:
        self.reference_dir = Path(reference_dir)
        self.min_score = min_score
        self.sources = list(sources or [])
        self.documents: List[Document] = []
        self._idf: Dict[str, float] = {}
        self.reload()

    # -- indexing ---------------------------------------------------------
    def reload(self) -> None:
        """(Re)read every reference file and rebuild the search index."""
        self.documents = []
        if self.reference_dir.is_dir():
            for path in sorted(self.reference_dir.rglob("*")):
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    self._index_file(path)
        for source in self.sources:
            self._index_source(source)
        self._compute_idf()

    def _index_text(self, content: str, source: str) -> None:
        for passage in split_into_passages(content):
            doc = Document(text=passage, source=source)
            if doc.term_freq:
                self.documents.append(doc)

    def _index_file(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        self._index_text(content, path.name)

    def _index_source(self, source: "DocumentSource") -> None:
        """Index documents provided by an external source (e.g. SharePoint).

        Failures are swallowed so a misconfigured or unreachable source never
        takes the whole chatbot down; it simply contributes no documents.
        """
        try:
            documents = source.fetch_documents()
        except Exception:
            return
        for name, content in documents:
            self._index_text(content, name)

    def _compute_idf(self) -> None:
        num_docs = len(self.documents)
        self._idf = {}
        if not num_docs:
            return
        doc_freq: Dict[str, int] = {}
        for doc in self.documents:
            for token in set(doc.term_freq):
                doc_freq[token] = doc_freq.get(token, 0) + 1
        for token, freq in doc_freq.items():
            # Smoothed inverse document frequency.
            self._idf[token] = math.log((1 + num_docs) / (1 + freq)) + 1.0

    # -- querying ---------------------------------------------------------
    def _vector(self, term_freq: Dict[str, float]) -> Dict[str, float]:
        return {
            token: tf * self._idf.get(token, 0.0)
            for token, tf in term_freq.items()
            if self._idf.get(token, 0.0)
        }

    @staticmethod
    def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        # Iterate over the smaller vector for the dot product.
        if len(a) > len(b):
            a, b = b, a
        dot = sum(weight * b.get(token, 0.0) for token, weight in a.items())
        if not dot:
            return 0.0
        norm_a = math.sqrt(sum(w * w for w in a.values()))
        norm_b = math.sqrt(sum(w * w for w in b.values()))
        if not norm_a or not norm_b:
            return 0.0
        return dot / (norm_a * norm_b)

    def query(self, question: str) -> Answer:
        """Return the best matching passage for ``question``."""
        question = (question or "").strip()
        if not question:
            return Answer(
                text="Please ask a question.",
                source="",
                score=0.0,
                found=False,
            )
        if not self.documents:
            return Answer(
                text=(
                    "I don't have any reference material to answer from yet. "
                    "Add documents to the reference folder and try again."
                ),
                source="",
                score=0.0,
                found=False,
            )

        query_vec = self._vector(_term_frequencies(tokenize(question)))
        best_doc: Document | None = None
        best_score = 0.0
        for doc in self.documents:
            score = self._cosine(query_vec, self._vector(doc.term_freq))
            if score > best_score:
                best_score = score
                best_doc = doc

        if best_doc is None or best_score < self.min_score:
            return Answer(
                text=(
                    "Sorry, I couldn't find anything about that in my reference "
                    "material. Try rephrasing your question."
                ),
                source="",
                score=best_score,
                found=False,
            )
        return Answer(
            text=best_doc.text,
            source=best_doc.source,
            score=best_score,
            found=True,
        )
