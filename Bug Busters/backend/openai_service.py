from openai import OpenAI

from settings import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
)


class OpenAIService:
    def __init__(self):
        self.client = None
        self.deployment = AZURE_OPENAI_DEPLOYMENT

        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
            return

        self.client = OpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            base_url=AZURE_OPENAI_ENDPOINT.rstrip("/") + "/openai/v1/",
        )

    def generate_policy(self, prompt: str) -> str:
        if self.client is None:
            raise RuntimeError(
                "Azure OpenAI is not configured. "
                "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."
            )

        if not self.deployment:
            raise RuntimeError(
                "Azure OpenAI deployment is not configured. "
                "Set AZURE_OPENAI_DEPLOYMENT."
            )

        response = self.client.responses.create(
            model=self.deployment,
            input=prompt,
        )

        return response.output_text