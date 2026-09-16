from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from domain.interfaces import ILLMClient


class AzureOpenAIClient(ILLMClient):
    def __init__(self, endpoint: str, deployment: str):
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default"
        )
        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
        )
        self._deployment = deployment

    def complete(self, prompt: str, context: list[str]) -> str:
        system = "Rispondi solo usando il contesto fornito. Se non basta, dillo esplicitamente."
        messages = [
            {"role": "system",
                "content": f"{system}\n\nContesto:\n{chr(10).join(context)}"},
            {"role": "user", "content": prompt},
        ]
        result = self._client.chat.completions.create(
            model=self._deployment, messages=messages)
        return result.choices[0].message.content
