"""Small plain-language Q&A assistant, separate from the intake form's
critical path. A side panel where a member can ask things like "what does
deductible mean?" while filling out the form -- reinforces the brief's
"smart, reassuring first conversation" framing without touching the
autosave/upload/submit flow.

    answer_question(question: str) -> str

Not the main intake mechanism -- if this fails, the form must keep working
on its own.
"""

import os

from google import genai
from google.genai import types

_MODEL = "gemini-flash-latest"

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

_SYSTEM_PROMPT = """
You are a friendly, patient assistant embedded in Emme's health insurance
onboarding form. Members are often anxious or confused about insurance
terminology. Answer their question in plain, jargon-free language, in 2-3
short sentences. Do not give medical advice. Do not ask for or reference
any personal identifying information. If the question is unrelated to
health insurance or this onboarding form, gently redirect them back to
the form.
"""


def answer_question(question: str) -> str:
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
