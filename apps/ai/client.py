"""OpenAI-compatible chat-completions client. The only place the app talks
to an LLM. Works against Ollama (/v1), vLLM, or any hospital gateway that
speaks the protocol — selected purely by env vars (spec §2)."""

import time

import httpx
from django.conf import settings


class LLMUnavailable(Exception):
    pass


def chat(messages, *, interactive=False, _transport=None) -> str:
    """One chat-completion round trip; returns the assistant text.

    interactive=True → short timeout, no retry (fail fast for the UI).
    Batch (default)  → full timeout, one internal retry with a short pause;
    Procrastinate-level retries on the task supply the patience beyond that.
    """
    timeout = (
        settings.LLM_INTERACTIVE_TIMEOUT_SECONDS
        if interactive
        else settings.LLM_TIMEOUT_SECONDS
    )
    body = {"model": settings.LLM_MODEL, "messages": messages}
    body.update(settings.LLM_EXTRA_BODY)
    headers = {}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

    attempts = 1 if interactive else 2
    last_error = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(2)
        try:
            with httpx.Client(
                base_url=settings.LLM_BASE_URL,
                timeout=timeout,
                transport=_transport,
            ) as http:
                response = http.post("/chat/completions", json=body, headers=headers)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            last_error = exc
    raise LLMUnavailable(str(last_error))
