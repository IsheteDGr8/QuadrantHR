import os
from typing import List

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class EmbeddingService:
    """
    Central service for the existing text-embedding-3-small deployment
    (GROUP1_TEXT_EMBEDDING_3_SMALL_*). Used only to vectorize knowledge
    queries for hybrid Search - never to make semantic routing decisions;
    that stays GPT-5.2's job via chatbot_agent.decide().
    """

    def __init__(self):
        self.client = None
        self.model = "text-embedding-3-small"

    def _get_client(self) -> OpenAI:
        if self.client is not None:
            return self.client

        api_key = os.getenv("GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY")
        endpoint = os.getenv("GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT")

        if not api_key:
            raise ValueError(
                "GROUP1_TEXT_EMBEDDING_3_SMALL_APIKEY is missing. "
                "Run fetch_secrets.py to populate .env."
            )

        if not endpoint:
            raise ValueError(
                "GROUP1_TEXT_EMBEDDING_3_SMALL_ENDPOINT is missing. "
                "Run fetch_secrets.py to populate .env."
            )

        base_url = endpoint.rstrip("/") + "/openai/v1/"

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        return self.client

    def embed(self, text: str) -> List[float]:
        """Embed a single piece of text (e.g. a knowledge query) for vector search."""

        client = self._get_client()
        response = client.embeddings.create(model=self.model, input=text)
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts in one API call (e.g. chunk migration) - fewer
        live calls than embedding one at a time. Order of results matches
        the order of `texts`.
        """

        if not texts:
            return []
        client = self._get_client()
        response = client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


embedding_service = EmbeddingService()
