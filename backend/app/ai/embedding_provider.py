import abc
import hashlib
import logging
import math
import re
from typing import List, Optional
import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("docufin.ai.embedding_provider")


class EmbeddingProvider(abc.ABC):
    """Abstract interface decoupling document indexing and vector search from specific embedding models."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        pass

    @abc.abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a batch of text passages."""
        pass

    @abc.abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """Generates embedding vector for a single search query."""
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """
    High-performance, deterministic, zero-cost semantic embedding engine for testing.
    Uses token-frequency hashing and character n-gram projections with L2 normalization
    to compute reproducible semantic similarity vectors.
    """

    def __init__(self, dimension: int = 384):
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def _embed_single_text(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self._dim

        # Tokenize and extract character 3-grams and words
        clean_text = text.lower()
        tokens = re.findall(r"\b[a-z0-9_\$€£₹\-\.]+\b", clean_text)
        vec = [0.0] * self._dim

        if not tokens:
            return [0.0] * self._dim

        for token in tokens:
            # Hash token to primary dimension bucket
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            bucket1 = h % self._dim
            sign1 = 1.0 if ((h >> 8) & 1) else -1.0
            vec[bucket1] += sign1 * 1.5

            # Also project sub-word n-grams for morphological/fuzzy similarity
            if len(token) >= 3:
                for i in range(len(token) - 2):
                    ngram = token[i : i + 3]
                    h_ng = int(hashlib.sha1(ngram.encode("utf-8")).hexdigest(), 16)
                    bucket_ng = h_ng % self._dim
                    sign_ng = 1.0 if ((h_ng >> 4) & 1) else -1.0
                    vec[bucket_ng] += sign_ng * 0.5

        # L2 normalize vector
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            return [round(x / norm, 6) for x in vec]
        return [0.0] * self._dim

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_single_text(t) for t in texts]

    async def embed_query(self, query: str) -> List[float]:
        return self._embed_single_text(query)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI Embeddings provider (e.g. text-embedding-3-small, 1536 dim)."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimension: int = 384,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self._dim = dimension
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": self._dim,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in items]
        except Exception as e:
            logger.error(f"OpenAI embedding call failed: {e}. Falling back to mock embeddings.")
            fallback = MockEmbeddingProvider(dimension=self._dim)
            return await fallback.embed_texts(texts)

    async def embed_query(self, query: str) -> List[float]:
        res = await self.embed_texts([query])
        return res[0] if res else [0.0] * self._dim


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini Embeddings provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-004",
        dimension: int = 384,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self._dim = dimension
        self.timeout = timeout

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents"
            f"?key={self.api_key}"
        )
        requests = [
            {"model": f"models/{self.model}", "content": {"parts": [{"text": t}]}}
            for t in texts
        ]
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json={"requests": requests})
                res.raise_for_status()
                data = res.json()
                embeddings = []
                for item in data.get("embeddings", []):
                    raw_vec = item.get("values", [])
                    # Truncate or pad to expected dimension
                    if len(raw_vec) >= self._dim:
                        vec = raw_vec[: self._dim]
                    else:
                        vec = raw_vec + [0.0] * (self._dim - len(raw_vec))
                    embeddings.append(vec)
                return embeddings
        except Exception as e:
            logger.error(f"Gemini embedding call failed: {e}. Falling back to mock embeddings.")
            fallback = MockEmbeddingProvider(dimension=self._dim)
            return await fallback.embed_texts(texts)

    async def embed_query(self, query: str) -> List[float]:
        res = await self.embed_texts([query])
        return res[0] if res else [0.0] * self._dim


def get_embedding_provider(settings: Optional[Settings] = None) -> EmbeddingProvider:
    """Factory creating configured embedding provider instance."""
    cfg = settings or get_settings()
    provider_name = (cfg.embedding_provider or "mock").lower()

    if provider_name == "openai" and cfg.openai_api_key:
        return OpenAIEmbeddingProvider(
            api_key=cfg.openai_api_key,
            model=cfg.embedding_model or "text-embedding-3-small",
            dimension=cfg.embedding_dimension,
            base_url=cfg.openai_base_url,
            timeout=cfg.rag_timeout_seconds,
        )
    elif provider_name == "gemini" and cfg.gemini_api_key:
        return GeminiEmbeddingProvider(
            api_key=cfg.gemini_api_key,
            model="text-embedding-004",
            dimension=cfg.embedding_dimension,
            timeout=cfg.rag_timeout_seconds,
        )
    else:
        return MockEmbeddingProvider(dimension=cfg.embedding_dimension)
