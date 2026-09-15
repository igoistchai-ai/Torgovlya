import json
from pathlib import Path
from openai import OpenAI
from config import settings

client = OpenAI(api_key=settings.openai_key)
PROMPT = Path(__file__).resolve().parent / "master_prompt.txt"
SYSTEM = PROMPT.read_text(encoding="utf-8")

RUSSIAN_INSTRUCTION = """
ОБЯЗАТЕЛЬНОЕ ПРАВИЛО ЯЗЫКА:
Отвечай пользователю только на русском языке.
Не используй английские названия полей, заголовки или пояснения в пользовательском тексте.
Числа, тикеры, названия бирж, индикаторов и стандартные обозначения LONG, SHORT, WAIT, TP1, TP2, TP3 можно сохранять; все остальные пояснения и описания должны быть на русском.
Верни JSON только с данными анализа.
"""


def analyze(payload):
    response = client.responses.create(
        model=settings.openai_model,
        instructions=SYSTEM + "\n\n" + RUSSIAN_INSTRUCTION,
        input=(
            "Проанализируй переданный проверенный пакет рыночных данных. "
            "Верни только JSON. Не выдумывай отсутствующие значения. "
            "Все текстовые значения анализа пиши на русском языке. Пакет:\n"
            + json.dumps(payload, default=str, ensure_ascii=False)
        ),
    )
    text = response.output_text
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}
