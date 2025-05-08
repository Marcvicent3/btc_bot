from transformers import pipeline

classifier = pipeline("sentiment-analysis")


def get_sentiment(text: str) -> str:
    result = classifier(text)[0]
    label = result["label"]
    score = result["score"]
    emoji = "😃" if label == "POSITIVE" else "😐" if score < 0.85 else "😠"
    return f"{label} {emoji} ({score:.2f})"
