from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth import get_current_user
from app.models_db import User, Donation, Feedback
from app.schemas_v2 import FeedbackCreate, FeedbackOut
from app.utils.model_loader import load_sentiment

router = APIRouter()


@router.post("", response_model=FeedbackOut)
def submit_feedback(req: FeedbackCreate, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    donation = db.query(Donation).filter(Donation.id == req.donation_id).first()
    if not donation:
        raise HTTPException(404, "Donation not found.")

    bundle = load_sentiment()
    pipe, le = bundle["pipeline"], bundle["label_encoder"]
    label, confidence = None, None
    if req.comment_text.strip():
        proba = pipe.predict_proba([req.comment_text])[0]
        idx = proba.argmax()
        label = le.inverse_transform([idx])[0]
        confidence = float(proba[idx])

    fb = Feedback(
        donation_id=req.donation_id, from_user_id=user.id, target_type=req.target_type,
        target_id=req.target_id, rating=req.rating, comment_text=req.comment_text,
        sentiment_label=label, sentiment_confidence=confidence,
    )
    db.add(fb)

    target = db.query(User).filter(User.id == req.target_id).first()
    if target:
        # Rolling exponential-moving-average trust/rating update -- this is the
        # feedback loop that keeps the NGO matcher and future assignments honest.
        if req.target_type == "donor":
            target.trust_score = round(0.8 * target.trust_score + 0.2 * (req.rating / 5 * 100), 2)
        else:
            target.volunteer_rating = round(0.8 * target.volunteer_rating + 0.2 * req.rating, 2)
        db.add(target)

    db.commit()
    db.refresh(fb)
    return fb


@router.get("/for/{target_id}", response_model=List[FeedbackOut])
def feedback_for(target_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (db.query(Feedback).filter(Feedback.target_id == target_id)
            .order_by(Feedback.created_at.desc()).all())
