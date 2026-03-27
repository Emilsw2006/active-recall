"""
Text-to-Speech — prioridad:
  1. Kokoro     (open source, local)        USE_KOKORO_TTS=true en .env  [EN/ES]
  2. Piper TTS  (local, neural quality)     USE_PIPER_TTS=true en .env   [DE/EN/ES]
  3. Edge TTS   (gratis, sin API key)       siempre activo, voces Neural multilingual
  4. gTTS       (Google, sin API key)       siempre activo, endpoint distinto a Bing
  5. Azure      (neural, 5M gratis)         AZURE_TTS_KEY en .env
  6. ElevenLabs (10k gratis)                ELEVENLABS_API_KEY en .env
  7. OpenAI TTS                             OPENAI_API_KEY en .env
  8. Kokoro fallback                        last resort para EN/ES
  9. Vacío → frontend usa Web Speech API

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
# Supported lang_codes: 'a'=American EN, 'b'=British EN, 'e'=ES,
#   'f'=FR, 'h'=HI, 'i'=IT, 'p'=PT-BR, 'j'=JA, 'z'=ZH
# Voice prefix → lang_code mapping:
_VOICE_LANGCODE = {
    'af': 'a', 'am': 'a',  # American English
    'bf': 'b', 'bm': 'b',  # British English
    'ef': 'e', 'em': 'e',  # Spanish
    'ff': 'f', 'fm': 'f',  # French
    'hf': 'h', 'hm': 'h',  # Hindi
    'if': 'i', 'im': 'i',  # Italian
    'pf': 'p', 'pm': 'p',  # Portuguese
    'jf': 'j', 'jm': 'j',  # Japanese
    'zf': 'z', 'zm': 'z',  # Mandarin
}

_kokoro_pipelines: dict = {}  # lang_code → KPipeline

def _get_kokoro_pipeline(lang_code: str = 'e'):
    """Carga la pipeline Kokoro para el lang_code dado (lazy, una vez por idioma)."""
    if lang_code not in _kokoro_pipelines:
        from kokoro import KPipeline
        _kokoro_pipelines[lang_code] = KPipeline(lang_code=lang_code)
        logger.info(f"Kokoro TTS cargado (lang_code='{lang_code}')")
    return _kokoro_pipelines[lang_code]


def _lang_code_for_voice(voz: str) -> str:
    prefix = voz[:2] if len(voz) >= 2 else ''
    return _VOICE_LANGCODE.get(prefix, 'e')


async def _tts_kokoro(texto: str, voz: str = "") -> bytes:
    """Genera audio WAV con Kokoro en un thread (es síncrono)."""
    import numpy as np
    import soundfile as sf

    voice = voz if voz else settings.kokoro_voice
    lang_code = _lang_code_for_voice(voice)

    def _generate():
        pipeline = _get_kokoro_pipeline(lang_code)
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


# ─── 2. Edge TTS (free, no API key, same voices as Azure Neural) ──────────────

_EDGE_DEFAULT_VOICES = {
    "es": "es-ES-ElviraNeural",
    "en": "en-US-SaraNeural",
    "de": "de-DE-KatjaNeural",
}

async def _tts_edge(texto: str, voice_name: str = "", lang: str = "es") -> bytes:
    """Microsoft Edge TTS — free, no API key, supports all Azure Neural voices."""
    import edge_tts
    voice = voice_name if voice_name else _EDGE_DEFAULT_VOICES.get(lang, "es-ES-ElviraNeural")
    communicate = edge_tts.Communicate(texto, voice)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    if not chunks:
        raise ValueError("edge-tts no generó audio")
    return b"".join(chunks)


# ─── 2b. Piper TTS (local, neural quality — needs piper-tts + model files) ────
# Models dir: BACKEND/.piper_models/
# German: de_DE-thorsten-high.onnx + .onnx.json  (~60 MB, download once)
# Download: https://huggingface.co/rhasspy/piper-voices/tree/main/de/de_DE/thorsten/high

from pathlib import Path as _Path

_PIPER_MODELS_DIR = _Path(__file__).parent.parent / ".piper_models"
_PIPER_VOICES = {
    "de": "de_DE-thorsten-high",
    "en": "en_US-lessac-high",
    "es": "es_ES-carlfm-x_low",
}
_piper_voice_cache: dict = {}


async def _tts_piper(texto: str, lang: str = "de") -> bytes:
    """Piper TTS — local neural quality, no internet needed after first download."""
    import wave, io

    voice_name = _PIPER_VOICES.get(lang)
    if not voice_name:
        raise ValueError(f"Piper: no voice configured for lang={lang}")

    onnx_path = _PIPER_MODELS_DIR / f"{voice_name}.onnx"
    json_path = _PIPER_MODELS_DIR / f"{voice_name}.onnx.json"
    if not onnx_path.exists() or not json_path.exists():
        raise FileNotFoundError(f"Piper model not found: {onnx_path}")

    def _generate():
        from piper import PiperVoice
        if voice_name not in _piper_voice_cache:
            _piper_voice_cache[voice_name] = PiperVoice.load(str(onnx_path), config_path=str(json_path))
        voice = _piper_voice_cache[voice_name]
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            voice.synthesize(texto, wav_file)
        buf.seek(0)
        return buf.read()

    return await asyncio.to_thread(_generate)


# ─── 2c. gTTS (Google Translate TTS — free, no API key, different endpoint than Edge) ──

async def _tts_gtts(texto: str, lang: str = "de") -> bytes:
    """Google Translate TTS — uses translate.google.com, works when Bing DNS fails."""
    import io
    from gtts import gTTS

    gtts_lang = {"es": "es", "en": "en", "de": "de"}.get(lang, "de")

    def _generate():
        tts = gTTS(text=texto, lang=gtts_lang, slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()

    return await asyncio.to_thread(_generate)


# ─── 3. Azure TTS ─────────────────────────────────────────────────────────────

_AZURE_VOICES = {
    "es": ("es-ES", "es-ES-ElviraNeural"),
    "en": ("en-US", "en-US-SaraNeural"),
    "de": ("de-DE", "de-DE-KatjaNeural"),
}

async def _tts_azure(texto: str, lang: str = "es", voice_name: str = "") -> bytes:
    """Llama a Azure Cognitive Services TTS (neural). Devuelve MP3."""
    xml_lang, default_voice = _AZURE_VOICES.get(lang, _AZURE_VOICES["es"])
    if not voice_name:
        # Allow override from settings for Spanish when no explicit voice
        if lang == "es" and settings.azure_tts_voice:
            voice_name = settings.azure_tts_voice
        else:
            voice_name = default_voice
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

    # Detect if voice ID is an Azure Neural voice
    is_azure_voice = "Neural" in voz if voz else False

    # 1. Kokoro local — any supported lang (EN, ES, FR…) via voice prefix; skip Azure/Edge voices
    is_kokoro_voice = voz[:2] in _VOICE_LANGCODE if voz else False
    if settings.use_kokoro_tts and (is_kokoro_voice or (lang == "es" and not is_azure_voice)) and audio_bytes is None:
        try:
            audio_bytes = await _tts_kokoro(texto, voz)
            fmt = "wav"
            logger.info(f"TTS Kokoro OK en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS Kokoro falló: {e}")

    # 2. Piper TTS (local, neural quality — no internet needed)
    if settings.use_piper_tts and audio_bytes is None:
        try:
            audio_bytes = await _tts_piper(texto, lang=lang)
            fmt = "wav"
            logger.info(f"TTS Piper OK [{lang}] en {(datetime.now()-inicio).total_seconds():.2f}s")
        except FileNotFoundError:
            pass  # Model not downloaded yet — skip silently
        except Exception as e:
            logger.warning(f"TTS Piper falló: {e}")

    # 3. Edge TTS (free, no API key — multilingual, same Neural voices as Azure)
    if audio_bytes is None:
        try:
            edge_voice = voz if is_azure_voice else ""
            audio_bytes = await _tts_edge(texto, voice_name=edge_voice, lang=lang)
            fmt = "mp3"
            logger.info(f"TTS Edge OK [{lang}] en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS Edge falló: {e}")

    # 4. gTTS (Google Translate TTS — different endpoint than Edge, works when Bing DNS fails)
    if audio_bytes is None:
        try:
            audio_bytes = await _tts_gtts(texto, lang=lang)
            fmt = "mp3"
            logger.info(f"TTS gTTS OK [{lang}] en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS gTTS falló: {e}")

    # 5. Azure (multilingual — pass voice_name if it's an Azure voice ID)  # noqa: E265
    if settings.azure_tts_key and audio_bytes is None:
        try:
            azure_voice = voz if is_azure_voice else ""
            audio_bytes = await _tts_azure(texto, lang=lang, voice_name=azure_voice)
            fmt = "mp3"
            logger.info(f"TTS Azure OK [{lang}] en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS Azure falló: {e}")

    # 4. ElevenLabs
    if settings.elevenlabs_api_key and audio_bytes is None:
        try:
            audio_bytes = await _tts_elevenlabs(texto)
            fmt = "mp3"
            logger.info(f"TTS ElevenLabs OK en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS ElevenLabs falló: {e}")

    # 5. OpenAI
    if settings.openai_api_key and audio_bytes is None:
        try:
            audio_bytes = await _tts_openai(texto)
            fmt = "mp3"
            logger.info(f"TTS OpenAI OK en {(datetime.now()-inicio).total_seconds():.2f}s")
        except Exception as e:
            logger.warning(f"TTS OpenAI falló: {e}")

    # Last resort: Kokoro fallback for supported languages when cloud providers fail
    _KOKORO_FALLBACK = {'en': 'af_sarah', 'es': 'ef_dora'}
    if settings.use_kokoro_tts and audio_bytes is None and lang in _KOKORO_FALLBACK:
        try:
            audio_bytes = await _tts_kokoro(texto, _KOKORO_FALLBACK[lang])
            fmt = "wav"
            logger.info(f"TTS Kokoro fallback OK [{lang}]")
        except Exception as e:
            logger.warning(f"TTS Kokoro fallback falló: {e}")

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
