import httpx
import pytest

from apps.ai import client


def _transport(handler):
    return httpx.MockTransport(handler)


def _ok_response(request):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"role": "assistant", "content": "Hello."}}]},
    )


def test_chat_returns_content():
    reply = client.chat(
        [{"role": "user", "content": "hi"}], _transport=_transport(_ok_response)
    )
    assert reply == "Hello."


def test_chat_sends_model_and_extra_body(settings):
    settings.LLM_MODEL = "test-model"
    settings.LLM_EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": False}}
    captured = {}

    def handler(request):
        import json

        captured.update(json.loads(request.content))
        return _ok_response(request)

    client.chat([{"role": "user", "content": "hi"}], _transport=_transport(handler))
    assert captured["model"] == "test-model"
    assert captured["chat_template_kwargs"] == {"enable_thinking": False}


def test_chat_sends_bearer_only_when_key_set(settings):
    settings.LLM_API_KEY = "sk-abc"
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return _ok_response(request)

    client.chat([{"role": "user", "content": "hi"}], _transport=_transport(handler))
    assert seen["auth"] == "Bearer sk-abc"


def test_chat_raises_llm_unavailable_on_http_error():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(client.LLMUnavailable):
        client.chat(
            [{"role": "user", "content": "hi"}],
            interactive=True,
            _transport=_transport(handler),
        )


def test_batch_chat_retries_once_then_succeeds(monkeypatch):
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500)
        return _ok_response(request)

    reply = client.chat(
        [{"role": "user", "content": "hi"}], _transport=_transport(handler)
    )
    assert reply == "Hello." and calls["n"] == 2
