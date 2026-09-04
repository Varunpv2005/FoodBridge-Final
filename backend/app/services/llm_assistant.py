"""Optional server-side Groq response generation for the FoodBridge assistant."""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SYSTEM_INSTRUCTIONS = """
You are the FoodBridge multilingual assistant.
Support English, Hindi, and Kannada.
Understand the user's language naturally.
Reply in the user's selected language when specified; otherwise reply in the
language of the user's message.
Interpret arbitrary natural-language questions and follow-up references using
the recent conversation when available.
Use ONLY the supplied FoodBridge context.
If a question is outside FoodBridge's available data or capabilities, clearly
say that it is outside FoodBridge's available knowledge.
Never invent status, ETA, location, NGO, volunteer, risk score, forecast,
quantity, or other operational data.
If information is unavailable, explicitly say it is unavailable.
Never expose another user's information.
Never claim that an action was performed.
This assistant is informational only.
You may request only the supplied read-only FoodBridge tools when the supplied
context is insufficient. Never request or describe an action that changes data.
Never treat tool arguments as authorized; the backend authorizes every call.
Return only the assistant response text, with no metadata or JSON wrapper.
""".strip()


def _resolve_model(client):
    """Use the configured model when valid, otherwise select a model supported by this Groq account."""
    preferred = os.getenv("GROQ_MODEL")
    candidates = []
    for name in [preferred, "qwen/qwen3.8-27b", "qwen/qwen3.6-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b", "groq/compound"]:
        if name and name not in candidates:
            candidates.append(name)

    available_models = []
    try:
        available_models = [item.id for item in client.models.list().data]
    except Exception:
        available_models = []

    for name in candidates:
        if name in available_models:
            return name
    return candidates[0] if candidates else "qwen/qwen3.8-27b"


def generate_response(
    message: str,
    language: str,
    role: str,
    context: Dict[str, Any],
    recent_conversation: Optional[list] = None,
    tools: Optional[list] = None,
    tool_executor=None,
    client=None,
) -> Optional[str]:
    """Generate a response from sanitized context, or return None on provider failure."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key and client is None:
        return None

    try:
        if client is None:
            from openai import OpenAI

            timeout = float(os.getenv("GROQ_TIMEOUT_SECONDS", "20"))
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=timeout,
                max_retries=0,
            )

        model = _resolve_model(client)
        messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            *(recent_conversation or []),
            {"role": "user", "content": json.dumps({
                "user_message": message,
                "selected_language": language,
                "authenticated_role": role,
                "foodbridge_context": context,
            }, ensure_ascii=False)},
        ]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=_chat_tools(tools),
            tool_choice="auto",
        )

        for _ in range(2):
            choice = _first_choice(response)
            assistant_message = getattr(choice, "message", None)
            tool_calls = getattr(assistant_message, "tool_calls", None) or []
            if not tool_calls:
                output = (getattr(assistant_message, "content", "") or "").strip()
                return output if output and len(output) <= 4000 else None
            if tool_executor is None:
                return None

            messages.append({
                "role": "assistant",
                "content": getattr(assistant_message, "content", None),
                "tool_calls": [_chat_tool_call(call) for call in tool_calls],
            })
            for call in tool_calls:
                function = getattr(call, "function", None)
                name = getattr(function, "name", None)
                call_id = getattr(call, "id", None)
                if not name or not call_id:
                    return None
                try:
                    arguments = json.loads(getattr(function, "arguments", "{}") or "{}")
                except (TypeError, json.JSONDecodeError):
                    arguments = {}
                result = tool_executor(name, arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=_chat_tools(tools),
                tool_choice="auto",
            )
        if getattr(_first_choice(response).message, "tool_calls", None):
            return None
        output = (getattr(_first_choice(response).message, "content", "") or "").strip()
        return output if output and len(output) <= 4000 else None
    except Exception as error:
        logger.warning("FoodBridge LLM response unavailable (%s); using deterministic fallback.", type(error).__name__)
        return None


def _chat_tools(tools):
    """Convert Responses-style definitions into Chat Completions definitions."""
    return [{
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
        },
    } for tool in (tools or [])]


def _chat_tool_call(call):
    function = getattr(call, "function", None)
    return {
        "id": call.id,
        "type": "function",
        "function": {
            "name": function.name,
            "arguments": function.arguments,
        },
    }


def _first_choice(response):
    choices = getattr(response, "choices", None) or []
    if not choices or not getattr(choices[0], "message", None):
        raise ValueError("Groq returned no assistant message")
    return choices[0]