import html
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.models_db import User

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logger = logging.getLogger(__name__)

router = APIRouter()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str


@router.post("", response_class=Response, responses={200: {"content": {"audio/mpeg": {}}}})
def synthesize(request: TTSRequest, _: User = Depends(get_current_user)):
    logger.info("Kannada TTS request received: language=%s text_length=%d", request.language, len(request.text))
    if request.language != "kn-IN":
        raise HTTPException(400, "Only Kannada audio is handled by this endpoint.")

    key = os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION")
    if not key or not region:
        logger.info("Azure Kannada TTS is not configured; using server-side Edge Kannada voice")
        try:
            import edge_tts

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
                audio_path = audio_file.name
            try:
                asyncio.run(edge_tts.Communicate(request.text, "kn-IN-SapnaNeural").save(audio_path))
                audio = Path(audio_path).read_bytes()
            finally:
                Path(audio_path).unlink(missing_ok=True)
            if audio:
                logger.info("Kannada TTS audio generated: provider=edge-tts content_type=audio/mpeg bytes=%d", len(audio))
                return Response(content=audio, media_type="audio/mpeg")
        except Exception as error:
            logger.warning("Edge Kannada TTS failed: error_type=%s", type(error).__name__)
        raise HTTPException(503, "Kannada audio is temporarily unavailable.")

    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="kn-IN">'
        '<voice name="kn-IN-SapnaNeural">'
        f"{html.escape(request.text)}"
        "</voice></speak>"
    )
    provider_request = Request(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            "User-Agent": "FoodBridge/2.0",
        },
        method="POST",
    )
    try:
        with urlopen(provider_request, timeout=20) as provider_response:
            logger.info("Azure Kannada TTS provider response: status=%s content_type=%s", provider_response.status, provider_response.headers.get_content_type())
            audio = provider_response.read()
    except HTTPError as error:
        logger.warning("Azure Kannada TTS provider error: status=%s content_type=%s", error.code, error.headers.get_content_type() if error.headers else "unknown")
        raise HTTPException(503, "Kannada audio is temporarily unavailable.") from error
    except (URLError, TimeoutError, OSError) as error:
        logger.warning("Azure Kannada TTS provider request failed: error_type=%s", type(error).__name__)
        raise HTTPException(503, "Kannada audio is temporarily unavailable.") from error

    if not audio:
        raise HTTPException(503, "Kannada audio is temporarily unavailable.")
    logger.info("Kannada TTS audio generated: provider=azure content_type=audio/mpeg bytes=%d", len(audio))
    return Response(content=audio, media_type="audio/mpeg")