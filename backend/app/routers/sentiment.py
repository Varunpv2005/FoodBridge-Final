from fastapi import APIRouter
from app.schemas import SentimentRequest, SentimentResponse
from app.utils.model_loader import load_sentiment

router = APIRouter()


@router.post("/predict", response_model=SentimentResponse)
def predict_sentiment(req: SentimentRequest):
    bundle = load_sentiment()
    pipe, le = bundle["pipeline"], bundle["label_encoder"]

    proba = pipe.predict_proba([req.comment_text])[0]
    pred_idx = proba.argmax()
    label = le.inverse_transform([pred_idx])[0]
    probs = {cls: float(p) for cls, p in zip(le.classes_, proba)}

    return SentimentResponse(
        label=label,
        confidence=float(proba[pred_idx]),
        probabilities=probs,
    )
