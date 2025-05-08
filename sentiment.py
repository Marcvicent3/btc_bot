from transformers import pipeline, logging

# 1) Silenciar warnings de Transformers
logging.set_verbosity_error()

sentiment_analyzer = pipeline(
    "sentiment-analysis",
    model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    revision="714eb0f",
)


def get_sentiment(text: str) -> str:
    """
    Devuelve algo como 'POSITIVE (0.97)' o 'NEGATIVE (0.65)'.
    """
    res = sentiment_analyzer(text, max_length=512)[0]
    label = res["label"]
    score = res["score"]
    # Formateamos con dos decimales
    return f"{label} ({score:.2f})"
