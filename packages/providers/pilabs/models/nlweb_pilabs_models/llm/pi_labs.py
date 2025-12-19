import asyncio
import threading
from typing import Any
import httpx
import json

from nlweb_core.llm import LLMProvider


class PiLabsClient:
    """PiLabsClient accesses a Pi Labs scoring API.
    It lazily initializes the client it will use to make requests."""

    _client: httpx.AsyncClient
    _url: str

    def __init__(self, url: str = "http://localhost:8001/invocations"):
        self._url = url
        self._client = httpx.AsyncClient(
            http2=True,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=30),
        )

    async def score(
        self,
        llm_input: str,
        llm_output: str,
        scoring_spec: list[dict[str, Any]],
        timeout: float = 30.0,
    ) -> float:
        resp = await self._client.post(
            url=self._url,
            json={
                "llm_input": llm_input,
                "llm_output": llm_output,
                "scoring_spec": scoring_spec,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("total_score", 0) * 100


class PiLabsProvider(LLMProvider):
    """PiLabsProvider accesses a Pi Labs scoring API."""

    _client_lock = threading.Lock()
    _client: PiLabsClient | None = None

    @classmethod
    def get_client(cls) -> PiLabsClient:
        with cls._client_lock:
            if cls._client is None:
                cls._client = PiLabsClient()
        return cls._client

    async def get_completion(
        self,
        prompt: str,
        schema: dict[str, Any],
        model: str | None = None,
        temperature: float = 0,
        max_tokens: int = 0,
        timeout: float = 30.0,
        **kwargs,
    ) -> dict[str, Any]:
        if schema.keys() != {"score", "description"}:
            raise ValueError(
                "PiLabsProvider only supports schema with 'score' and 'description' fields."
            )
        if {"request.query", "site.itemType", "item.description"} - kwargs.keys():
            raise ValueError(
                "PiLabsProvider requires 'request.query', 'site.itemType', and 'item.description' in kwargs."
            )
        client = self.get_client()
        score = await client.score(
            llm_input=kwargs["request.query"].text,
            llm_output=json.dumps(kwargs["item.description"]),
            scoring_spec=[
                {"question": "Is this item relevant to the query?"},
            ],
            timeout=timeout,
        )
        return {"score": score, "description": kwargs["item.description"]}

    @classmethod
    def clean_response(cls, content: str) -> dict[str, Any]:
        raise NotImplementedError("PiLabsProvider does not support clean_response.")


async def pi_scoring_comparison(file):
    # Generate output filename
    base_name = file.rsplit(".", 1)[0] if "." in file else file
    output_file = f"{base_name}_pi_eval.csv"
    client = PiLabsProvider.get_client()

    with open(file, "r") as f:
        lines = f.readlines()
        data = []
        for line in lines:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    tasks = []
    async with asyncio.TaskGroup() as tg:
        for item in data:
            tasks.append(tg.create_task(process_item(item, client)))

    with open(output_file, "a") as f:
        for task in tasks:
            score, pi_score, csv_line = task.result()
            if score > 64 or pi_score > 30:
                print(csv_line)
            f.write(csv_line + "\n")


async def process_item(item, client):
    item_fields = {
        "url": item.get("url", ""),
        "name": item.get("name", ""),
        "site": item.get("site", ""),
        "siteUrl": item.get("site", ""),
        "score": item.get("ranking", {}).get("score", 0),
        "description": item.get("ranking", {}).get("description", ""),
        "schema_object": item.get("schema_object", {}),
        "query": item.get("query", ""),
    }
    desc = json.dumps(item_fields["schema_object"])
    pi_score, time_taken = await client.score(
        item["query"],
        desc,
        scoring_spec=[
            {"question": "Is the item relevant to the query?"},
        ],
    )
    score = item_fields["score"]

    item["ranking"]["score"] = pi_score
    csv_line = f"O={score},P={pi_score},T={time_taken},Q={item_fields['query']},N={item_fields['name']}"  # ,D={item_fields['description']}"

    if score > 64 or pi_score > 30:
        print(csv_line)
    return score, pi_score, csv_line


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 -m nlweb_models.llm.pi_labs <input_file.jsonl>")
        sys.exit(1)

    input_file = sys.argv[1]
    asyncio.run(pi_scoring_comparison(input_file))
