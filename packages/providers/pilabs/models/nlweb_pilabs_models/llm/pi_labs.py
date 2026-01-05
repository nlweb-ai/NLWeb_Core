import asyncio
import os
import threading
from typing import Any
from dataclasses import dataclass
import httpx
import json

from nlweb_core.llm import LLMProvider


@dataclass
class PiLabsRequest:
    llm_input: str
    llm_output: str
    scoring_spec: list[dict[str, Any]]


class PiLabsClient:
    """PiLabsClient accesses a Pi Labs scoring API.
    It lazily initializes the client it will use to make requests."""

    _client: httpx.AsyncClient

    def __init__(self):
        self._client = httpx.AsyncClient(
            http2=True,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=30),
        )

    async def score(
        self,
        reqs: list[PiLabsRequest],
        endpoint: str,
        api_key: str,
        timeout: float = 30.0,
    ) -> list[float]:
        if not endpoint.endswith("/"):
            endpoint += "/"
        url = f"{endpoint}invocations"
        resp = await self._client.post(
            url=url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=[
                {
                    "llm_input": r.llm_input,
                    "llm_output": r.llm_output,
                    "scoring_spec": r.scoring_spec,
                }
                for r in reqs
            ],
            timeout=timeout,
        )
        resp.raise_for_status()
        return [r.get("total_score", 0) * 100 for r in resp.json()]


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

    async def get_completions(
        self,
        prompts: list[str],
        schema: dict[str, Any],
        kwargs_list: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0,
        max_tokens: int = 0,
        timeout: float = 30.0,
        api_key: str = "",
        endpoint: str = "",
        **kwargs,
    ) -> list[dict[str, Any]]:
        if schema.keys() != {"score", "description"}:
            raise ValueError(
                "PiLabsProvider only supports schema with 'score' and 'description' fields."
            )
        if kwargs_list is None or len(prompts) != len(kwargs_list):
            raise ValueError(
                "PiLabsProvider requires kwargs_list with the same length as prompts."
            )
        for kwargs in kwargs_list or []:
            if {"request.query", "site.itemType", "item.description"} - kwargs.keys():
                raise ValueError(
                    "PiLabsProvider requires 'request.query', 'site.itemType', and 'item.description' in kwargs."
                )
        if not api_key or not endpoint:
            raise ValueError(
                "PiLabsProvider requires 'api_key' and 'endpoint' parameters."
            )
        client = self.get_client()
        scores = await client.score(
            [
                PiLabsRequest(
                    llm_input=kwargs["request.query"],
                    llm_output=json.dumps(kwargs["item.description"]),
                    scoring_spec=[
                        {"question": "Is this item relevant to the query?"},
                    ],
                )
                for kwargs in kwargs_list
            ],
            timeout=timeout,
            api_key=api_key,
            endpoint=endpoint,
        )
        return [
            {"score": score, "description": kwargs["item.description"]}
            for score, kwargs in zip(scores, kwargs_list)
        ]

    async def get_completion(
        self,
        prompt: str,
        schema: dict[str, Any],
        model: str | None = None,
        temperature: float = 0,
        max_tokens: int = 0,
        timeout: float = 30.0,
        api_key: str = "",
        endpoint: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        resp = await self.get_completions(
            prompts=[prompt],
            schema=schema,
            kwargs_list=[kwargs],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            api_key=api_key,
            endpoint=endpoint,
        )
        return resp[0]

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
        endpoint=os.environ.get("PI_LABS_ENDPOINT", ""),
        api_key=os.environ.get("PI_LABS_KEY", ""),
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
