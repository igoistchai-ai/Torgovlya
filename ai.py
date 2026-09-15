import json
from pathlib import Path
from openai import OpenAI
from config import settings

client=OpenAI(api_key=settings.openai_key)
PROMPT=Path(__file__).resolve().parent/"master_prompt.txt"
SYSTEM=PROMPT.read_text(encoding="utf-8")

def analyze(payload):
    response=client.responses.create(
        model=settings.openai_model,
        instructions=SYSTEM,
        input=("Analyze the supplied verified market package. Return JSON only. "
               "Do not invent missing values. Package:\n"+json.dumps(payload, default=str)),
    )
    text=response.output_text
    try: return json.loads(text)
    except Exception: return {"raw":text}
