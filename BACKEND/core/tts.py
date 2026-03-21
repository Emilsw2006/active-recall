"""
Text-to-Speech — prioridad:
  1. Kokoro   (open source, local)   USE_KOKORO_TTS=true en .env
  2. Azure    (neural, 5M gratis)    AZURE_TTS_KEY en .env
  3. ElevenLabs (10k gratis)         ELEVENLABS_API_KEY en .env
  4. OpenAI TTS                      OPENAI_API_KEY en .env
  5. Vacío → frontend usa Web Speech API

Speech-to-Text: Groq Whisper (sin cambios).
"""

import asyncio
import base64
import io
from datetime import datetime

import httpx
from groq import Groq

from config import settings
from core.limits import GROQ_STT_SEM
from utils.logger import get_logger

logger = get_logger(__name__)

groq_client = Groq(api_key=settings.groq_api_key)

# ─── 1. Kokoro (local, open source) ───────────────────────────────────────────

_kokoro_pipeline = None

def _get_kokoro_pipeline():
    """Carga Kokoro una sola vez (lazy)."""
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        from kokoro import KPipeline  # noqa: importado solo si se usa
        _kokoro_pipeline = KPipeline(lang_code='e')  # 'e' = español
        logger.info("Kokoro TTS cargado (español)")
    return _kokoro_pipeline


async def _tts_kokoro(texto: str, voz: str = "") -> bytes:
    """Genera audio WAV con Kokoro en un thread (es síncrono)."""
    import numpy as np
    import soundfile as sf

    voice = voz if voz else settings.kokoro_voice

    def _generate():
        pipeline = _get_kokoro_pipeline()
        chunks = []
        for _, _, audio in pipeline(texto, voice=voice, speed=1.0):
            chunks.append(audio)
        if not chunks:
            raise ValueError("Kokoro no generó audio")
        full_audio = np.concatenate(chunks)
        buf = io.BytesIO()
        sf.write(buf, full_audio, 24000, format='WAV', subtype='PCM_16')
        buf.seek(0)
        return buf.read()

    return await asyncio.to_thread(_generate)


# ─── 2. Azure TTS ─────────────────────────────────────────────────────────────

_AZURE_VOICES = {
    "es": ("es-ES", "es-ES-ElviraNeural"),
    "en": ("en-US", "en-US-SaraNeural"),
    "de": ("de-DE", "de-DE-KatjaNeural"),
}

async def _tts_azure(texto: str, lang: str = "es") -> bytes:
    """Llama a Azure Cognitive Services TTS (neural). Devuelve MP3."""
    xml_lang, voice_name = _AZURE_VOICES.get(lang, _AZURE_VOICES["es"])
    # Allow override from settings for Spanish
    if lang == "es" and settings.azure_tts_voice:
        voice_name = settings.azure_tts_voice
    url = f"https://{settings.azure_tts_region}.tts.speech.microsoft.com/cognitiveservices/v1"
    ssml = (
        f"<speak version='1.0' xml:lang='{xml_lang}'>"
        f"<voice xml:lang='{xml_lang}' name='{voice_name}'>"
        f"{_escape_xml(texto)}"
        f"</voice></speak>"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": settings.azure_tts_key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        "User-Agent": "ActiveRecall",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, content=ssml.encode("utf-8"), headers=headers)
        r.raise_for_status()
        return r.content


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )


# ─── 3. ElevenLabs ────────────────────────────────────────────────────────────

async def _tts_elevenlabs(texto: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    payload = {
        "text": texto,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.80,
            "style": 0.15,
            "use_speaker_boost": True,
        },
    }
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.content


# ─── 4. OpenAI TTS ────────────────────────────────────────────────────────────

async def _tts_openai(texto: str) -> bytes:
    url = "https://api.openai.com/v1/audio/speech"
    payload = {
        "model": "tts-1-hd",
        "input": texto,
        "voice": "nova",
        "response_format": "mp3",
        "speed": 1.0,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.content


# ─── Función pública ───────────────────────────────────────────────────────────

async def texto_a_audio_base64(texto: str, voz: str = "", lang: str = "es") -> str:
    """
    Convierte texto a audio. Devuelve base64 o "" si falla todo.
    lang: 'es' | 'en' | 'de' — selecciona voz TTS correcta.
    """
    inicio = datetime.now()
    logger.info(f"TTS [{lang}]: '{texto[:60]}...' ({len(texto)} chars)")

    audio_bytes: bytes | None = None
    fmt = "mp3"

    # 1. Kokoro local (only Spanish — falls through for EN/DE)
    if settings.use_kokoro_tts and lang == "es" and audio_bytes is None:
        try:
            audio_bytes = await _tts_kokoro(texto, voz)
            fmt = "wav"
            logger.info(f"TTS Kokoro OK en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS Kokoro falló: {e}")

    # 2. Azure (multilingual)
    if settings.azure_tts_key and audio_bytes is None:
        try:
            audio_bytes = await _tts_azure(texto, lang=lang)
            fmt = "mp3"
            logger.info(f"TTS Azure OK [{lang}] en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS Azure falló: {e}")

    # 3. ElevenLabs
    if settings.elevenlabs_api_key and audio_bytes is None:
        try:
            audio_bytes = await _tts_elevenlabs(texto)
            fmt = "mp3"
            logger.info(f"TTS ElevenLabs OK en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS ElevenLabs falló: {e}")

    # 4. OpenAI
    if settings.openai_api_key and audio_bytes is None:
        try:
            audio_bytes = await _tts_openai(texto)
            fmt = "mp3"
            logger.info(f"TTS OpenAI OK en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS OpenAI falló: {e}")

    if audio_bytes is None:
        logger.warning("TTS: sin proveedor disponible — frontend usará Web Speech API")
        return ""

    # El websocket necesita saber el formato para enviar el MIME correcto al cliente
    # Guardamos el formato en el propio base64 con un prefijo ligero que el cliente ignorará
    # (el formato real se manda en audio_format del JSON)
    _last_fmt[0] = fmt
    return base64.b64encode(audio_bytes).decode("utf-8")


# Variable para que websocket.py pueda consultar el último formato generado
_last_fmt: list = ["mp3"]


def get_last_audio_format() -> str:
    return _last_fmt[0]


# ─── STT ──────────────────────────────────────────────────────────────────────

async def transcribir_audio(audio_bytes: bytes, formato: str = "webm", lang: str = "es") -> str:
    """Transcribe audio con Groq Whisper. Devuelve el texto transcrito."""
    inicio = datetime.now()
    whisper_lang = {"es": "es", "en": "en", "de": "de"}.get(lang, "es")
    logger.info(f"STT: transcribiendo {len(audio_bytes)} bytes (formato={formato}, lang={whisper_lang})")

    def _call_stt():
        return groq_client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=(f"audio.{formato}", audio_bytes, f"audio/{formato}"),
            language=whisper_lang,
        )

    async with GROQ_STT_SEM:
        transcription = await asyncio.to_thread(_call_stt)
    texto = transcription.text.strip()
    duracion = (datetime.now() - inicio).total_seconds()
    logger.info(f"STT completado en {duracion:.2f}s: '{texto[:80]}'")
    return texto
