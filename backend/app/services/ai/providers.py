"""Model provider adapters. Only this file knows a provider's API; everything else uses ai/service.py.

The provider is an open owner decision (AI_PROVIDER). The Anthropic adapter uses the official SDK.
"""
import json
import logging

from app.services.ai.schemas import ChatOutcome, ToolSpec

log = logging.getLogger("app.ai")


class ProviderError(Exception):
    """The provider failed or declined; callers fall back to basic mode."""


class AnthropicAdapter:
    name = "anthropic"
    DEFAULT_MODEL = "claude-opus-5-5"
    BETAS = ["server-side-fallback-2026-07-01"]   # on a policy decline, the API retries on a fallback model

    def __init__(self, api_key: str, chat_model: str | None, vision_model: str | None, client=None):
        import anthropic
        self._anthropic = anthropic
        self.client = client or anthropic.AsyncAnthropic(api_key=api_key, max_retries=2, timeout=60)
        self.chat_model = chat_model or self.DEFAULT_MODEL
        self.vision_model = vision_model or self.chat_model

    async def _create(self, **kwargs):
        try:
            return await self.client.beta.messages.create(betas=self.BETAS, fallbacks="default", **kwargs)
        except self._anthropic.RateLimitError as e:
            raise ProviderError("rate_limited") from e
        except self._anthropic.APIStatusError as e:
            log.warning("AI provider error status=%s", e.status_code)
            raise ProviderError(f"status_{e.status_code}") from e
        except self._anthropic.APIConnectionError as e:
            raise ProviderError("connection") from e

    async def run_tools(self, system: str, messages: list[dict], tools: list[ToolSpec], max_rounds: int = 6) -> ChatOutcome:
        """Manual tool loop (we need to see every tool result to check the final answer)."""
        defs = [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]
        handlers = {t.name: t.handler for t in tools}
        convo = list(messages)
        out = ChatOutcome(text="", model=self.chat_model)
        for _ in range(max_rounds):
            resp = await self._create(model=self.chat_model, max_tokens=4000, system=system, tools=defs, messages=convo,
                                      output_config={"effort": "low"})
            out.input_tokens += resp.usage.input_tokens
            out.output_tokens += resp.usage.output_tokens
            if resp.stop_reason == "refusal":
                out.refused = True
                return out
            calls = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason != "tool_use" or not calls:
                out.text = "".join(b.text for b in resp.content if b.type == "text").strip()
                return out
            convo.append({"role": "assistant", "content": resp.content})
            results = []
            for call in calls:   # all results go back in one user message
                try:
                    data = await handlers[call.name](dict(call.input or {}))
                    out.tool_results.append(data)
                    results.append({"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(data, default=str)})
                except Exception as e:  # a failed tool is reported, never dropped
                    log.warning("tool %s failed: %s", call.name, type(e).__name__)
                    results.append({"type": "tool_result", "tool_use_id": call.id, "is_error": True,
                                    "content": "That lookup failed."})
            convo.append({"role": "user", "content": results})
        out.text = ""
        return out

    async def extract_json(self, system: str, content: list[dict], schema: dict) -> tuple[dict | None, int, int]:
        resp = await self._create(model=self.vision_model, max_tokens=16000, system=system,
                                  messages=[{"role": "user", "content": content}],
                                  output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}})
        if resp.stop_reason in ("refusal", "max_tokens"):
            return None, resp.usage.input_tokens, resp.usage.output_tokens
        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            return json.loads(text), resp.usage.input_tokens, resp.usage.output_tokens
        except json.JSONDecodeError:
            return None, resp.usage.input_tokens, resp.usage.output_tokens


def build(provider: str | None, api_key: str | None, chat_model: str | None, vision_model: str | None):
    if not provider or not api_key:
        return None
    if provider.lower() == "anthropic":
        return AnthropicAdapter(api_key, chat_model, vision_model)
    raise ValueError(f"AI provider {provider!r} has no adapter yet")
