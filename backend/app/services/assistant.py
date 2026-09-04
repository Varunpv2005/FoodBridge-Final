"""Read-only, deterministic FoodBridge assistant responses."""
import re
import threading
import time
from collections import OrderedDict
from typing import Optional

from sqlalchemy.orm import Session

from app.models_db import Delivery, DeliveryStop, Donation, User
from app.services.assistant_tools import TOOL_DEFINITIONS, execute_tool
from app.services.demand_forecasting import forecast_demand
from app.services.llm_assistant import generate_response

ID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
HI_STATUS = "\u0938\u094d\u0925\u093f\u0924\u093f"
HI_DONATION = "\u0926\u093e\u0928"
KN_STOP = "\u0ca8\u0cbf\u0cb2\u094d\u0926\u0cbe\u0ca3"
KN_NEXT = "\u0cae\u0cc1\u0c82\u0ca6\u0cbf\u0ca8"
KN_STATUS = "\u0cb8\u094d\u0925\u0cbf\u0ca4\u0cbf"
KN_DONATION = "\u0ca6\u0cbe\u0ca8"

TEXT = {
    "en": {
        "no_donation": "I could not find a donation available to your account.",
        "no_delivery": "I could not find a delivery assigned to your account.",
        "status": "Donation {id} is {status}. Food: {food}, quantity: {quantity} plates. NGO: {ngo}. Volunteer: {volunteer}.",
        "delivery": "Delivery {id} is {status}. Route: {stops} stops, {distance} km, estimated travel time: {duration}.",
        "stop": "Current stop: {current}. Next pending stop: {next_stop}.",
        "stop_none": "There are no pending stops on this delivery.",
        "risk": "Estimated food risk for donation {id}: {risk}. Score: {score}. {recommendation}",
        "risk_unavailable": "An estimated food-risk result is unavailable for donation {id}.",
        "demand": "The aggregate demand forecast for {date} is {demand} requested plates. It is not an NGO-specific forecast.",
        "demand_unavailable": "The demand forecast is currently unavailable.",
        "unknown": "That question is outside FoodBridge's available information. I can help with donation status, delivery status, current or next stop, route ETA, food risk, and demand forecast questions.",
    },
    "hi": {
        "no_donation": "मुझे आपके खाते के लिए कोई उपलब्ध दान नहीं मिला।",
        "no_delivery": "मुझे आपके खाते के लिए कोई असाइन की गई डिलीवरी नहीं मिली।",
        "status": "दान {id} की स्थिति {status} है। भोजन: {food}, मात्रा: {quantity} प्लेट। NGO: {ngo}। स्वयंसेवक: {volunteer}।",
        "delivery": "डिलीवरी {id} की स्थिति {status} है। मार्ग: {stops} स्टॉप, {distance} किमी, अनुमानित समय: {duration}।",
        "stop": "वर्तमान स्टॉप: {current}। अगला लंबित स्टॉप: {next_stop}।",
        "stop_none": "इस डिलीवरी पर कोई लंबित स्टॉप नहीं है।",
        "risk": "दान {id} का अनुमानित खाद्य जोखिम: {risk}। स्कोर: {score}। {recommendation}",
        "risk_unavailable": "दान {id} के लिए अनुमानित खाद्य जोखिम उपलब्ध नहीं है।",
        "demand": "{date} के लिए कुल मांग पूर्वानुमान {demand} अनुरोधित प्लेट है। यह किसी एक NGO का पूर्वानुमान नहीं है।",
        "demand_unavailable": "मांग पूर्वानुमान अभी उपलब्ध नहीं है।",
        "unknown": "यह सवाल FoodBridge की उपलब्ध जानकारी के बाहर है। मैं दान स्थिति, डिलीवरी स्थिति, वर्तमान या अगले स्टॉप, मार्ग ETA, खाद्य जोखिम और मांग पूर्वानुमान में मदद कर सकता हूँ।",
    },
    "kn": {
        "no_donation": "ನಿಮ್ಮ ಖಾತೆಗೆ ಲಭ್ಯವಿರುವ ದಾನ ಸಿಗಲಿಲ್ಲ.",
        "no_delivery": "ನಿಮ್ಮ ಖಾತೆಗೆ ನಿಯೋಜಿಸಲಾದ ವಿತರಣೆ ಸಿಗಲಿಲ್ಲ.",
        "status": "ದಾನ {id} ಸ್ಥಿತಿ {status} ಆಗಿದೆ. ಆಹಾರ: {food}, ಪ್ರಮಾಣ: {quantity} ಪ್ಲೇಟ್. NGO: {ngo}. ಸ್ವಯಂಸೇವಕ: {volunteer}.",
        "delivery": "ವಿತರಣೆ {id} ಸ್ಥಿತಿ {status} ಆಗಿದೆ. ಮಾರ್ಗ: {stops} ನಿಲ್ದಾಣ, {distance} ಕಿಮೀ, ಅಂದಾಜು ಸಮಯ: {duration}.",
        "stop": "ಪ್ರಸ್ತುತ ನಿಲ್ದಾಣ: {current}. ಮುಂದಿನ ಬಾಕಿ ನಿಲ್ದಾಣ: {next_stop}.",
        "stop_none": "ಈ ವಿತರಣೆಯಲ್ಲಿ ಬಾಕಿ ನಿಲ್ದಾಣಗಳಿಲ್ಲ.",
        "risk": "ದಾನ {id} ಅಂದಾಜು ಆಹಾರ ಅಪಾಯ: {risk}. ಸ್ಕೋರ್: {score}. {recommendation}",
        "risk_unavailable": "ದಾನ {id} ಗೆ ಅಂದಾಜು ಆಹಾರ ಅಪಾಯ ಲಭ್ಯವಿಲ್ಲ.",
        "demand": "{date} ರ ಒಟ್ಟು ಬೇಡಿಕೆ ಮುನ್ಸೂಚನೆ {demand} ಬೇಡಿಕೆಯ ಪ್ಲೇಟ್. ಇದು ನಿರ್ದಿಷ್ಟ NGO ಮುನ್ಸೂಚನೆ ಅಲ್ಲ.",
        "demand_unavailable": "ಬೇಡಿಕೆ ಮುನ್ಸೂಚನೆ ಈಗ ಲಭ್ಯವಿಲ್ಲ.",
        "unknown": "ಈ ಪ್ರಶ್ನೆ FoodBridge ಲಭ್ಯವಿರುವ ಮಾಹಿತಿಯ ಹೊರಗಿದೆ. ದಾನ ಸ್ಥಿತಿ, ವಿತರಣೆ ಸ್ಥಿತಿ, ಪ್ರಸ್ತುತ ಅಥವಾ ಮುಂದಿನ ನಿಲ್ದಾಣ, ಮಾರ್ಗ ETA, ಆಹಾರ ಅಪಾಯ ಮತ್ತು ಬೇಡಿಕೆ ಮುನ್ಸೂಚನೆ ಕುರಿತು ನಾನು ಸಹಾಯ ಮಾಡಬಹುದು.",
    },
}


class _ConversationMemory:
    """Bounded process-local memory keyed by authenticated user ID."""

    def __init__(self, max_messages=12, max_conversations=1000, ttl_seconds=1800):
        self.max_messages = max_messages
        self.max_conversations = max_conversations
        self.ttl_seconds = ttl_seconds
        self._items = OrderedDict()
        self._lock = threading.Lock()

    def get(self, user_id):
        now = time.monotonic()
        with self._lock:
            item = self._items.get(user_id)
            if item is None:
                return []
            if now - item["touched"] > self.ttl_seconds:
                del self._items[user_id]
                return []
            item["touched"] = now
            self._items.move_to_end(user_id)
            return [dict(message) for message in item["messages"]]

    def add_turn(self, user_id, user_message, assistant_message):
        now = time.monotonic()
        with self._lock:
            item = self._items.setdefault(user_id, {"touched": now, "messages": []})
            item["messages"].extend([
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ])
            item["messages"] = item["messages"][-self.max_messages:]
            item["touched"] = now
            self._items.move_to_end(user_id)
            while len(self._items) > self.max_conversations:
                self._items.popitem(last=False)

    def clear(self):
        with self._lock:
            self._items.clear()


_conversation_memory = _ConversationMemory()


def _role(user):
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def _donation(db: Session, user: User, identifier: Optional[str] = None):
    query = db.query(Donation)
    role = _role(user)
    if role == "donor":
        query = query.filter(Donation.donor_id == user.id)
    elif role == "ngo":
        query = query.filter(Donation.matched_ngo_id == user.id)
    elif role == "volunteer":
        query = query.join(DeliveryStop, DeliveryStop.donation_id == Donation.id).join(Delivery, Delivery.id == DeliveryStop.delivery_id).filter(Delivery.volunteer_id == user.id)
    if identifier:
        query = query.filter(Donation.id == identifier)
    return query.order_by(Donation.created_at.desc()).first()


def _delivery(db: Session, user: User, identifier: Optional[str] = None):
    query = db.query(Delivery)
    role = _role(user)
    if role == "volunteer":
        query = query.filter(Delivery.volunteer_id == user.id)
    elif role in ("donor", "ngo"):
        query = query.join(DeliveryStop, DeliveryStop.delivery_id == Delivery.id).join(Donation, Donation.id == DeliveryStop.donation_id)
        query = query.filter(Donation.donor_id == user.id if role == "donor" else Donation.matched_ngo_id == user.id)
    if identifier:
        query = query.filter(Delivery.id == identifier)
    return query.order_by(Delivery.created_at.desc()).first()


def _intent(message: str) -> str:
    text = message.lower()
    if not text.strip():
        return "general"

    greeting_phrases = (
        "hello", "hey", "good morning", "good afternoon", "good evening",
        "thanks", "thank you", "thx"
    )
    if re.search(r"\bhi\b", text) or any(phrase in text for phrase in greeting_phrases):
        return "general"

    general_phrases = (
        "how does", "what is", "what does", "explain", "food redistribution",
        "food waste", "how can i reduce", "what is an ngo", "what is foodbridge",
        "how does foodbridge", "foodbridge", "redistribution", "ngo"
    )
    if any(phrase in text for phrase in general_phrases):
        return "general"

    demand_terms = ("demand", "मांग", "पूर्वानुमान", "ಬೇಡಿಕೆ", "ಮುನ್ಸೂಚನೆ")
    weather_terms = ("weather", "मौसम", "हवा", "ಹವಾಮಾನ")
    if any(item in text for item in demand_terms) or ("forecast" in text and not any(item in text for item in weather_terms)):
        return "demand"
    if any(item in text for item in ("risk", "spoil", "expiry", "खतरा", "जोखिम", "ಅಪಾಯ", "ಹಾಳಾಗ")):
        return "risk"
    if any(item in text for item in ("stop", "next", "current", "स्टॉप", "अगला", "वर्तमान", KN_STOP, KN_NEXT)):
        return "stop"
    if any(item in text for item in ("route", "eta", "distance", "मार्ग", "समय", "ಮಾರ್ಗ", "ದೂರ")):
        return "route"
    if any(item in text for item in ("delivery", "status", "donation", HI_STATUS, HI_DONATION, "वितरण", "दान", KN_STATUS, KN_DONATION)):
        return "status"
    return "unknown"


def _status_value(value):
    return value.value if hasattr(value, "value") else value


def _sanitized_context(db: Session, user: User, message: str, language: str, intent: str):
    """Build only the already-authorized operational context sent to the LLM."""
    match = ID_PATTERN.search(message)
    identifier = match.group(0) if match else None
    context = {"language": language, "intent": intent}

    if intent == "demand":
        try:
            point = forecast_demand(horizon=1)["forecasts"][0]
            context["demand_forecast"] = {
                "forecast_date": point["forecast_date"],
                "predicted_demand": point["predicted_demand"],
                "scope": "aggregate across all regions and food types",
            }
        except (FileNotFoundError, KeyError, ValueError):
            context["demand_forecast"] = {"unavailable": True}
        return context

    donation = _donation(db, user, identifier)
    delivery = _delivery(db, user, identifier)
    if delivery is None and donation is not None and intent in ("route", "stop"):
        delivery = (db.query(Delivery).join(DeliveryStop, DeliveryStop.delivery_id == Delivery.id)
                    .filter(DeliveryStop.donation_id == donation.id).first())

    if donation is not None:
        ngo = db.query(User).filter(User.id == donation.matched_ngo_id).first() if donation.matched_ngo_id else None
        volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first() if delivery else None
        context["donation"] = {
            "id": donation.id,
            "status": _status_value(donation.status),
            "food_type": donation.food_type,
            "quantity_plates": donation.quantity_plates,
            "ngo": ngo.name if ngo else None,
            "volunteer": volunteer.name if volunteer else None,
            "risk_level": getattr(donation, "risk_level", None),
            "risk_score": getattr(donation, "risk_score", None),
            "risk_recommendation": getattr(donation, "risk_recommendation", None),
        }
    if delivery is not None:
        context["delivery"] = {
            "id": delivery.id,
            "status": _status_value(delivery.status),
            "total_stops": len(delivery.stops),
            "distance_km": delivery.total_distance_km,
            "estimated_travel_minutes": getattr(delivery, "estimated_travel_minutes", None),
            "route_error": getattr(delivery, "route_error", None),
            "stops": [],
        }
        for stop in sorted(delivery.stops, key=lambda item: item.sequence):
            stop_donation = db.query(Donation).filter(Donation.id == stop.donation_id).first()
            context["delivery"]["stops"].append({
                "sequence": stop.sequence,
                "type": stop.stop_type,
                "status": stop.status,
                "food_type": stop_donation.food_type if stop_donation else None,
                "quantity_plates": stop_donation.quantity_plates if stop_donation else None,
                "donor": (db.query(User).filter(User.id == stop_donation.donor_id).first().name
                          if stop_donation and db.query(User).filter(User.id == stop_donation.donor_id).first() else None),
                "ngo": (db.query(User).filter(User.id == stop.ngo_id).first().name
                        if db.query(User).filter(User.id == stop.ngo_id).first() else None),
                "eta_minutes": stop.eta_minutes,
                "estimated_arrival": getattr(stop, "estimated_arrival", None),
                "remaining_food_window_minutes": getattr(stop, "remaining_food_window_minutes", None),
                "lateness_minutes": getattr(stop, "lateness_minutes", None),
                "urgency": getattr(stop, "urgency", None),
                "risk_score": getattr(stop, "risk_score", None),
            })
    return context


def _deterministic_answer(db: Session, user: User, message: str, language: str):
    language = language if language in TEXT else "en"
    text = TEXT[language]
    intent = _intent(message)
    if intent == "general":
        lower = message.strip().lower()
        if any(term in lower for term in ("thanks", "thank you", "thx")):
            return {"language": language, "intent": "general", "reply": "You're welcome! 😊" if language == "en" else ("स्वागत है! 😊" if language == "hi" else "ಸ್ವಾಗತ! 😊")}
        if any(term in lower for term in ("hi", "hello", "hey", "good morning", "good afternoon", "good evening")):
            return {"language": language, "intent": "general", "reply": "Hi! 👋 I'm your FoodBridge Assistant. How can I help you today?" if language == "en" else ("नमस्ते! 👋 मैं आपका FoodBridge Assistant हूँ। आज मैं आपकी कैसे मदद कर सकता हूँ?" if language == "hi" else "ಹೈ! 👋 ನಾನು ನಿಮ್ಮ FoodBridge ಸಹಾಯಕ. ನಾನು ಇಂದು ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?")}
        return {"language": language, "intent": "general", "reply": "I can help with FoodBridge updates, donations, delivery progress, food risk, and general food redistribution questions. What would you like to know?" if language == "en" else ("मैं FoodBridge अपडेट, दान, डिलीवरी प्रगति, खाद्य जोखिम और सामान्य खाद्य पुनर्वितरण सवालों में मदद कर सकता हूँ। आप क्या जानना चाहते हैं?" if language == "hi" else "ನಾನು FoodBridge ನವೀಕರಣಗಳು, ದಾನ, ವಿತರಣೆ ಪ್ರಗತಿ, ಆಹಾರ ಅಪಾಯ ಮತ್ತು ಸಾಮಾನ್ಯ ಆಹಾರ ಪುನರ್ವಿತರಣೆಯ ಪ್ರಶ್ನೆಗಳಲ್ಲಿ ಸಹಾಯ ಮಾಡಬಹುದು. ನೀವು ಏನು ತಿಳಿಯಲು ಬಯಸುತ್ತೀರಿ?")}
    if intent == "unknown" and language == "hi":
        intent = "status"
    if intent == "unknown" and language == "kn":
        intent = "stop"
    match = ID_PATTERN.search(message)
    identifier = match.group(0) if match else None
    if intent == "demand":
        try:
            point = forecast_demand(horizon=1)["forecasts"][0]
            return {"language": language, "intent": intent, "reply": text["demand"].format(date=point["forecast_date"], demand=point["predicted_demand"])}
        except (FileNotFoundError, KeyError, ValueError):
            return {"language": language, "intent": intent, "reply": text["demand_unavailable"]}
    donation = _donation(db, user, identifier)
    delivery = _delivery(db, user, identifier)
    if delivery is None and donation is not None and intent in ("route", "stop"):
        delivery = db.query(Delivery).join(DeliveryStop, DeliveryStop.delivery_id == Delivery.id).filter(DeliveryStop.donation_id == donation.id).first()
    if intent in ("status", "risk") and donation is None:
        return {"language": language, "intent": intent, "reply": text["no_donation"]}
    if intent in ("route", "stop") and delivery is None:
        return {"language": language, "intent": intent, "reply": text["no_delivery"]}
    if intent == "unknown":
        return {"language": language, "intent": intent, "reply": text["unknown"]}
    if intent == "risk":
        risk = getattr(donation, "risk_level", None)
        score = getattr(donation, "risk_score", None)
        if risk is None and score is None:
            return {"language": language, "intent": intent, "reply": text["risk_unavailable"].format(id=donation.id[:8])}
        return {"language": language, "intent": intent, "reply": text["risk"].format(id=donation.id[:8], risk=risk or "unavailable", score=score or "unavailable", recommendation=getattr(donation, "risk_recommendation", None) or "")}
    if intent == "status":
        ngo = db.query(User).filter(User.id == donation.matched_ngo_id).first() if donation.matched_ngo_id else None
        volunteer = db.query(User).filter(User.id == delivery.volunteer_id).first() if delivery else None
        status = donation.status.value if hasattr(donation.status, "value") else donation.status
        return {"language": language, "intent": intent, "reply": text["status"].format(id=donation.id[:8], status=status, food=donation.food_type, quantity=donation.quantity_plates, ngo=ngo.name if ngo else "unavailable", volunteer=volunteer.name if volunteer else "unavailable")}
    if intent == "stop":
        stops = sorted(delivery.stops, key=lambda item: item.sequence)
        pending = [item for item in stops if item.status != "completed"]
        return {"language": language, "intent": intent, "reply": text["stop_none"] if not pending else text["stop"].format(current=pending[0].stop_type, next_stop=pending[0].stop_type)}
    status = delivery.status.value if hasattr(delivery.status, "value") else delivery.status
    duration = getattr(delivery, "estimated_travel_minutes", None)
    return {"language": language, "intent": intent, "reply": text["delivery"].format(id=delivery.id[:8], status=status, stops=len(delivery.stops), distance=delivery.total_distance_km, duration=f"{duration} minutes" if duration is not None else "unavailable")}


def answer(db: Session, user: User, message: str, language: str):
    fallback = _deterministic_answer(db, user, message, language)
    context = _sanitized_context(db, user, message, language, fallback["intent"])
    recent_conversation = _conversation_memory.get(user.id)
    generated = generate_response(
        message=message,
        language=language,
        role=_role(user),
        context=context,
        recent_conversation=recent_conversation,
        tools=TOOL_DEFINITIONS,
        tool_executor=lambda name, arguments: execute_tool(name, arguments, db, user),
    )
    reply = generated.strip() if generated else fallback["reply"]
    _conversation_memory.add_turn(user.id, message, reply)
    return {**fallback, "reply": reply}
