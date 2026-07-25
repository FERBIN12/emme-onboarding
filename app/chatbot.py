"""Plain-language Q&A assistant ("Ask Emme"), used both as a side panel
during onboarding (single question) and as a persistent chat widget on
the compare page (multi-turn, aware of the member's own plan data).

    answer_question(question: str) -> str
    answer_chat(messages: list[dict], plan_fields: dict | None) -> str

Not the main intake/compare mechanism -- if this fails, the surrounding
page must keep working on its own.
"""

import os

from google import genai
from google.genai import types

_MODEL = "gemini-flash-latest"

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

_SYSTEM_PROMPT = """
You are Emme's insurance explainer. Members are often anxious or confused
about insurance terminology. Rules:
- Plain language. No jargon unless you immediately define it.
- Short answers: two or three sentences unless asked for more.
- When the member's own plan data is provided below, answer using THEIR
  numbers, not generic examples.
- You explain and compare. You never tell someone which plan to buy, and
  you never estimate whether a specific treatment will be covered --
  coverage depends on medical necessity and the specific claim.
- If you don't know or the data doesn't say, say so and point them at
  their insurer's member services line.
- You are not a doctor, an insurance broker, or a lawyer.
- Do not ask for or reference any personal identifying information.
"""


def answer_question(question: str) -> str:
    """Single-turn Q&A, used by the onboarding side panel."""
    response = _client.models.generate_content(
        model=_MODEL,
        contents=[question],
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=1024,
        ),
    )
    return response.text.strip()


def answer_chat(messages: list[dict], plan_fields: dict | None = None) -> str:
    """Multi-turn chat, used by the compare page's "Ask Emme" widget.

    messages: [{"role": "user"|"assistant", "content": "..."}, ...]
    plan_fields: the member's known plan.json fields dict (value/confidence/
    source per field), if a plan has been collected yet.
    """
    system = _SYSTEM_PROMPT
    if plan_fields:
        known = {k: v.get("value") for k, v in plan_fields.items() if v.get("value") is not None}
        if known:
            system += "\n\nThis member's plan so far:\n" + str(known)

    contents = [
        types.Content(
            role="model" if m.get("role") == "assistant" else "user",
            parts=[types.Part.from_text(text=m.get("content", ""))],
        )
        for m in messages[-12:]  # cap context, matches the reference server.py
    ]

    response = _client.models.generate_content(
        model=_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.3,
            max_output_tokens=1024,
        ),
    )
    return response.text.strip()
