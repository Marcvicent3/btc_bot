from transformers import pipeline

# Cargar el modelo de traducción inglés → español
translator = pipeline("translation_en_to_es", model="Helsinki-NLP/opus-mt-en-es")


def translate_to_spanish(texts: list[str]) -> list[str]:
    if not texts:
        return []

    # Traduce en lotes
    results = translator(texts, max_length=512)
    return [r["translation_text"] for r in results]
