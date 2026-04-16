"""
WebSocket /ws/sesion/{sesion_id}

Estados: IDLE → SPEAKING_AI → LISTENING_USER → PROCESSING → WAITING_NEXT → (loop)

Mensajes cliente → servidor:
  - bytes: chunk de audio (webm/opus)
  - {"type": "barge_in"}       ← interrumpe a la IA mientras habla
  - {"type": "next"}           ← avanza a la siguiente pregunta (tras resultado)
  - {"type": "pista"}          ← pide pista sutil sin revelar respuesta
  - {"type": "skip"}           ← salta pregunta (marca rojo silencioso)
  - {"type": "pausar"}         ← guarda progreso y cierra sesión gracefully
  - {"type": "switch_mode",
     "mode": "chat"|"voice"}   ← activa/desactiva TTS

Mensajes servidor → cliente:
  - {"type": "pregunta", pregunta, audio_base64, audio_format, progreso, modo}
  - {"type": "resultado", ruta, respuesta_voz, respuesta_usuario, texto_completo, audio_base64, audio_format, flashcard, similitud, progreso, es_ultima, segundo_intento}
  - {"type": "feynman", texto, audio_base64, audio_format}  ← pide analogía (ruta amarilla)
  - {"type": "pista", texto, audio_base64, audio_format}
  - {"type": "skip_ok", progreso}
  - {"type": "pausa_ok", mensaje}
  - {"type": "modo_cambiado", modo}
  - {"type": "sesion_completa", sesion_id}
  - {"type": "error", mensaje}
"""

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from core.session_manager import get_sesion, eliminar_sesion, cargar_sesion
from core.question_generator import generar_pregunta, generar_pregunta_cached, generar_pista
from core.tts import texto_a_audio_base64, transcribir_audio, get_last_audio_format
from core.evaluator import evaluar_respuesta
from core.flashcard_generator import generar_flashcard
from core.limits import GROQ_LLM_SEM, GROQ_STT_SEM
from core.prefetch import PrefetchManager
from utils.logger import get_logger
from utils.supabase_client import get_service_client

logger = get_logger(__name__)
router = APIRouter(tags=["websocket"])

SILENCIO_RAPIDO = 3.0   # tras 3s: transcribe y mira si hay trigger phrase
SILENCIO_LARGO  = 12.0  # tras 12s sin chunks: evalúa (da tiempo para respuestas largas)
MIN_PALABRAS_AUTO = 5   # mínimo de palabras para evaluar en el check rápido

# Frases que el usuario puede decir para indicar que ha terminado de responder.
# Se detectan en la transcripción y se eliminan antes de evaluar.
TRIGGER_PHRASES = [
    "evalúame esto", "evalúame", "ya he terminado", "he terminado",
    "ya terminé", "terminé", "eso es todo", "ya está", "listo",
]

def _limpiar_trigger(texto: str) -> tuple[str, bool]:
    """
    Elimina trigger phrases del final de la transcripción.
    Devuelve (texto_limpio, se_detectó_trigger).
    Solo elimina si el trigger aparece en los últimos 40 caracteres.
    """
    texto_strip = texto.strip()
    texto_lower = texto_strip.lower().rstrip(" .,!¡?¿")
    # Ordenar por longitud desc para matchear primero las más específicas
    for trigger in sorted(TRIGGER_PHRASES, key=len, reverse=True):
        if texto_lower.endswith(trigger):
            # Calcular dónde empieza el trigger en el texto original
            idx = len(texto_strip) - len(texto_strip.lower().rstrip(" .,!¡?¿")) + len(texto_lower) - len(trigger)
            # Buscar hacia atrás en el texto original
            idx_real = texto_strip.lower().rfind(trigger)
            if idx_real != -1 and idx_real >= len(texto_strip) - len(trigger) - 40:
                limpio = texto_strip[:idx_real].strip(" .,!¡?¿")
                return limpio, True
    return texto_strip, False

def _feynman_prompt(atomo_titulo: str) -> str:
    """Genera un prompt Feynman con contexto del átomo específico."""
    return (
        f"Vas bien con '{atomo_titulo}', lo tienes casi. "
        f"Pero para asegurarme de que lo entiendes de verdad: "
        f"explícame con tus propias palabras qué es exactamente, "
        f"como si se lo contaras a alguien que no sabe nada del tema. "
        f"Usa una analogía con algo cotidiano si te ayuda."
    )


@router.websocket("/ws/sesion/{sesion_id}")
async def websocket_sesion(
    websocket: WebSocket,
    sesion_id: str,
    voice: str = Query(default="ef_dora"),
    lang: str = Query(default="es"),
):
    await websocket.accept()
    logger.info(f"[{sesion_id}] WebSocket conectado")
    await websocket.send_json({"type": "estado", "estado": "loading_session"})

    db = get_service_client()
    sesion = get_sesion(sesion_id)

    if not sesion:
        # Intentar reanudar desde DB
        sesion_db = await asyncio.to_thread(
            lambda: db.table("sesiones").select(
                "usuario_id, temas_elegidos, fecha_fin, status, duration_type, current_question_index, n_preguntas"
            ).eq("id", sesion_id).execute()
        )

        if not sesion_db.data:
            await websocket.send_json({"type": "error", "mensaje": "Sesión no encontrada"})
            await websocket.close()
            return

        row = sesion_db.data[0]
        if row.get("fecha_fin") or row.get("status") == "completada":
            await websocket.send_json({"type": "error", "mensaje": "Sesión ya completada"})
            await websocket.close()
            return

        logger.info(f"[{sesion_id}] Reanudando sesión desde DB (status={row.get('status')})")
        sesion = await cargar_sesion(
            sesion_id=sesion_id,
            usuario_id=row["usuario_id"],
            temas_elegidos=row["temas_elegidos"],
            duration_type=row.get("duration_type", "corta"),
            start_index=row.get("current_question_index", 0),
            max_atomos=row.get("n_preguntas"),  # respetar límite de la parte
        )

        if not sesion.atomos:
            await websocket.send_json({
                "type": "sesion_completa",
                "mensaje": "¡Todos los átomos ya respondidos!",
                "sesion_id": sesion_id,
            })
            await websocket.close()
            return

    # Aplicar voz recibida por query param (Kokoro — cualquier prefijo de 2 letras — o Neural)
    _KOKORO_PREFIXES = ('af_','am_','bf_','bm_','ef_','em_','ff_','fm_','hf_','hm_','if_','im_','pf_','pm_','jf_','jm_','zf_','zm_')
    if voice.startswith(_KOKORO_PREFIXES) or "Neural" in voice:
        sesion.kokoro_voice = voice
        logger.info(f"[{sesion_id}] Voz: {voice}")

    # Marcar sesión como empezada en DB
    await asyncio.to_thread(
        lambda: db.table("sesiones").update({"status": "empezada"}).eq("id", sesion_id).execute()
    )

    audio_chunks = []
    silencio_task = None
    ws_connected = True

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _tts(texto: str) -> tuple[str, str]:
        """TTS solo si el modo voz está activo. Devuelve (base64, formato)."""
        if sesion.tts_enabled:
            b64 = await texto_a_audio_base64(texto, sesion.kokoro_voice, lang=lang)
            fmt = get_last_audio_format()
            return b64, fmt
        return "", "mp3"

    # ── Prefetch Manager ──────────────────────────────────────────────────
    async def _generar_pregunta_prefetch(atomo_id, texto_completo, titulo_corto):
        """Wrapper que lee lang en el momento de la llamada (puede cambiar mid-session)."""
        return await generar_pregunta_cached(atomo_id, texto_completo, titulo_corto, lang=lang)

    prefetch_mgr = PrefetchManager(
        sesion=sesion,
        generar_pregunta_fn=_generar_pregunta_prefetch,
        tts_fn=_tts,
    )

    async def enviar_pregunta_actual():
        atomo = sesion.atomo_actual
        if not atomo:
            return
        sesion.estado = "SPEAKING_AI"
        sesion.en_segundo_intento = False

        # Intentar obtener pregunta del prefetch buffer
        prefetched = prefetch_mgr.get_if_ready(sesion.indice_actual)

        if prefetched:
            # Pregunta ya pre-generada — envío instantáneo
            pregunta = prefetched.pregunta_texto
            audio_b64 = prefetched.audio_base64
            audio_fmt = prefetched.audio_format
            atomo.pregunta = pregunta
            logger.info(f"[{sesion_id}] Prefetch HIT — pregunta {sesion.indice_actual}")
        else:
            # Fallback: generar en tiempo real
            if ws_connected:
                await websocket.send_json({"type": "estado", "estado": "generating_question"})
            if not atomo.pregunta:
                atomo.pregunta = await generar_pregunta_cached(atomo.id, atomo.texto_completo, atomo.titulo_corto, lang=lang)
            pregunta = atomo.pregunta
            audio_b64, audio_fmt = await _tts(pregunta)
            logger.info(f"[{sesion_id}] Prefetch MISS — generada en real-time")

        await websocket.send_json({
            "type": "pregunta",
            "pregunta": pregunta,
            "audio_base64": audio_b64,
            "audio_format": audio_fmt,
            "progreso": sesion.progreso,
            "modo": "voz" if sesion.tts_enabled else "chat",
        })
        sesion.estado = "LISTENING_USER"
        logger.info(f"[{sesion_id}] Pregunta enviada — {sesion.progreso}")

        # Lanzar prefetch de la siguiente pregunta en background
        asyncio.create_task(prefetch_mgr.prefetch_next(sesion.indice_actual + 1))

    async def _guardar_resultado(atomo_id: str, ruta: str, texto_usuario: str, similitud: float, pregunta: str = ""):
        await asyncio.to_thread(lambda: db.table("resultados").insert({
            "sesion_id": sesion_id,
            "atomo_id": atomo_id,
            "estado": ruta,
            "respuesta_usuario": texto_usuario,
            "similitud_coseno": similitud,
            "pregunta": pregunta,
        }).execute())
        # Actualizar índice en DB para soporte de pausa
        await asyncio.to_thread(lambda: db.table("sesiones").update({
            "current_question_index": sesion.indice_actual + 1,
        }).eq("id", sesion_id).execute())

    async def _guardar_flashcard_history(atomo_id: str, flashcard: dict):
        await asyncio.to_thread(lambda: db.table("flashcards_history").insert({
            "session_id": sesion_id,
            "atomo_id": atomo_id,
            "concepto": flashcard.get("paso_1_concepto_base", ""),
            "error_cometido": flashcard.get("paso_2_error_cometido", ""),
            "analogia_generada": flashcard.get("paso_3_analogia", ""),
        }).execute())

    # ── Silencio ────────────────────────────────────────────────────────────

    async def detectar_silencio():
        nonlocal audio_chunks

        # ── Fase 1: 2s — transcripción rápida para detectar trigger phrase ──
        await asyncio.sleep(SILENCIO_RAPIDO)
        if sesion.estado != "LISTENING_USER" or not audio_chunks:
            return

        audio_check = b"".join(audio_chunks)
        if len(audio_check) >= 10_000:
            try:
                texto_check = await transcribir_audio(audio_check, lang=lang)
                texto_limpio, trigger_ok = _limpiar_trigger(texto_check)
                if trigger_ok:
                    logger.info(f"[{sesion_id}] Trigger phrase detectada tras {SILENCIO_RAPIDO}s — procesando")
                    await procesar_respuesta()
                    return
                # Si hay pocas palabras, notificar al frontend para que el usuario decida
                palabras = len(texto_limpio.split())
                if palabras < MIN_PALABRAS_AUTO:
                    logger.info(f"[{sesion_id}] Respuesta corta ({palabras} palabras) — notificando al frontend")
                    if ws_connected:
                        await websocket.send_json({
                            "type": "respuesta_corta",
                            "transcript": texto_limpio,
                        })
            except Exception:
                pass  # Si falla la transcripción rápida, seguimos al timeout largo

        # Fase 2: auto-evaluar tras silencio largo (fallback si el usuario no pulsa Enviar)
        await asyncio.sleep(SILENCIO_LARGO - SILENCIO_RAPIDO)
        if sesion.estado == "LISTENING_USER" and audio_chunks:
            logger.info(f"[{sesion_id}] Silencio {SILENCIO_LARGO}s — auto-evaluando")
            await procesar_respuesta()

    # ── Procesar respuesta ──────────────────────────────────────────────────

    async def procesar_respuesta():
        nonlocal audio_chunks, silencio_task
        if sesion.estado != "LISTENING_USER" or not ws_connected:
            return

        sesion.estado = "PROCESSING"
        audio_buffer = b"".join(audio_chunks)
        audio_chunks = []

        # Audio demasiado pequeño = sin respuesta real (solo header WebM o ruido)
        MIN_AUDIO_BYTES = 10_000
        if len(audio_buffer) < MIN_AUDIO_BYTES:
            logger.info(f"[{sesion_id}] Audio muy corto ({len(audio_buffer)} bytes) — volviendo a escuchar")
            sesion.estado = "LISTENING_USER"
            return

        atomo = sesion.atomo_actual
        if not atomo:
            return

        try:
            # Notify client if server is busy (semaphore at capacity)
            if GROQ_STT_SEM.locked():
                await websocket.send_json({"type": "estado", "estado": "servidor_ocupado"})

            try:
                texto_usuario = await transcribir_audio(audio_buffer, lang=lang)
            except Exception as stt_err:
                err_str = str(stt_err).lower()
                if any(k in err_str for k in ("could not process", "invalid", "400", "is it a valid")):
                    logger.warning(f"[{sesion_id}] Audio inválido (STT rechazado), volviendo a escuchar: {stt_err}")
                    sesion.estado = "LISTENING_USER"
                    if ws_connected:
                        await websocket.send_json({"type": "stt_error", "mensaje": "No te he entendido bien, ¿lo repites?"})
                    return
                raise  # Error inesperado → propagar
            logger.info(f"[{sesion_id}] Transcripción: '{texto_usuario[:80]}'")
            if not texto_usuario.strip():
                texto_usuario = "Sin respuesta"
            else:
                texto_usuario, trigger_detectado = _limpiar_trigger(texto_usuario)
                if trigger_detectado:
                    logger.info(f"[{sesion_id}] Trigger phrase detectada — texto limpio: '{texto_usuario[:80]}'")
                if not texto_usuario:
                    texto_usuario = "Sin respuesta"

            ruta, similitud, feedback, detalle = await evaluar_respuesta(
                respuesta_usuario=texto_usuario,
                atomo_texto=atomo.texto_completo,
                atomo_embedding=atomo.embedding,
                pregunta=atomo.pregunta,
                uso_pista=atomo.uso_pista,
                lang=lang,
                en_segundo_intento=sesion.en_segundo_intento,
                tema_analogia=sesion.usuario_mundo_analogias,
            )
            logger.info(f"[{sesion_id}] Ruta={ruta} similitud={similitud:.3f} intento2={sesion.en_segundo_intento}")

            # ── RUTA AMARILLA (Método Feynman) ──
            # Primer intento amarillo: pedir transformación antes de guardar
            if ruta == "amarillo" and not sesion.en_segundo_intento:
                sesion.en_segundo_intento = True
                # Use the evaluator's transformation message (already in correct lang)
                feynman_text = feedback if feedback else _feynman_prompt(atomo.titulo_corto)
                audio_feynman, fmt_feynman = await _tts(feynman_text)
                sesion.estado = "LISTENING_USER"
                await websocket.send_json({
                    "type": "feynman",
                    "texto": feynman_text,
                    "audio_base64": audio_feynman,
                    "audio_format": fmt_feynman,
                })
                return  # No avanzar índice — esperar segundo intento

            # En segundo intento o cualquier otra ruta: guardar y avanzar
            sesion.en_segundo_intento = False
            await _guardar_resultado(atomo.id, ruta, texto_usuario, similitud, atomo.pregunta or "")

            # Build flashcard from evaluator detalle (rojo) — avoids separate LLM call
            flashcard = None
            if ruta == "rojo" and detalle:
                flashcard = {
                    "paso_1_concepto_base":  detalle.get("error", ""),
                    "paso_2_error_cometido": detalle.get("micro_explicacion", ""),
                    "paso_3_analogia":       detalle.get("analogia", ""),
                }
                await _guardar_flashcard_history(atomo.id, flashcard)
                audio_feedback_b64, fmt_feedback = await _tts(feedback)
            elif ruta in ("rojo", "amarillo"):
                # Fallback: generate flashcard separately (detalle was None)
                _is_review_sess = sesion.duration_type == "repaso"
                async def _gen_flashcard():
                    fc = await generar_flashcard(
                        atomo_id=atomo.id,
                        usuario_id=sesion.usuario_id,
                        atomo_texto=atomo.texto_completo,
                        respuesta_usuario=texto_usuario,
                        mundo_analogias=sesion.usuario_mundo_analogias,
                        lang=lang,
                        is_review=_is_review_sess,
                    )
                    await _guardar_flashcard_history(atomo.id, fc)
                    return fc

                flashcard, (audio_feedback_b64, fmt_feedback) = await asyncio.gather(
                    _gen_flashcard(),
                    _tts(feedback),
                )
            else:
                audio_feedback_b64, fmt_feedback = await _tts(feedback)

            if not ws_connected:
                return

            sesion.indice_actual += 1
            es_ultima = sesion.completada

            payload = {
                "type": "resultado",
                "ruta": ruta,
                "respuesta_voz": feedback,
                "respuesta_usuario": texto_usuario,
                "texto_completo": atomo.texto_completo,
                "audio_base64": audio_feedback_b64,
                "audio_format": fmt_feedback,
                "flashcard": flashcard,
                "detalle": detalle,
                "similitud": round(similitud, 3),
                "progreso": sesion.progreso,
                "es_ultima": es_ultima,
                "segundo_intento": True if ruta == "amarillo" else False,
            }
            await websocket.send_json(payload)

            if es_ultima:
                fecha_fin = datetime.utcnow().isoformat()
                await asyncio.to_thread(lambda: db.table("sesiones").update({
                    "fecha_fin": fecha_fin,
                    "status": "completada",
                }).eq("id", sesion_id).execute())
                await websocket.send_json({
                    "type": "sesion_completa",
                    "mensaje": "¡Sesión completada!",
                    "sesion_id": sesion_id,
                })
                eliminar_sesion(sesion_id)
            else:
                sesion.estado = "WAITING_NEXT"

        except Exception as e:
            logger.error(f"[{sesion_id}] Error procesando respuesta: {e}", exc_info=True)
            if ws_connected:
                await websocket.send_json({"type": "error", "mensaje": str(e)})
            sesion.estado = "LISTENING_USER"

    # ── Enviar primera pregunta ─────────────────────────────────────────────

    try:
        await enviar_pregunta_actual()
    except Exception as e:
        logger.error(f"[{sesion_id}] Error primera pregunta: {e}", exc_info=True)
        await websocket.send_json({"type": "error", "mensaje": str(e)})
        await websocket.close()
        return

    # ── Loop principal ──────────────────────────────────────────────────────

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive(), timeout=120.0)
            except asyncio.TimeoutError:
                logger.warning(f"[{sesion_id}] Timeout 120s")
                break

            # ── Audio binario ──
            if "bytes" in data and data["bytes"]:
                chunk = data["bytes"]

                if sesion.estado == "SPEAKING_AI":
                    audio_chunks.append(chunk)
                    if len(audio_chunks) > 20:
                        logger.info(f"[{sesion_id}] Barge-in por audio")
                        sesion.estado = "LISTENING_USER"
                        audio_chunks = audio_chunks[-5:]
                    continue

                if sesion.estado == "LISTENING_USER":
                    audio_chunks.append(chunk)
                    if silencio_task and not silencio_task.done():
                        silencio_task.cancel()
                    silencio_task = asyncio.create_task(detectar_silencio())

            # ── Mensajes JSON ──
            elif "text" in data and data["text"]:
                try:
                    msg = json.loads(data["text"])
                except json.JSONDecodeError:
                    continue

                t = msg.get("type")

                # Barge-in manual
                if t == "barge_in" and sesion.estado == "SPEAKING_AI":
                    logger.info(f"[{sesion_id}] Barge-in manual")
                    sesion.estado = "LISTENING_USER"

                # Siguiente pregunta
                elif t == "next" and sesion.estado == "WAITING_NEXT":
                    await enviar_pregunta_actual()

                # Pista sutil
                elif t == "pista" and sesion.estado in ("LISTENING_USER", "WAITING_NEXT"):
                    if silencio_task and not silencio_task.done():
                        silencio_task.cancel()
                    audio_chunks = []
                    atomo = sesion.atomo_actual
                    if atomo and atomo.pregunta:
                        # Marcar que se usó pista → cap amarillo en evaluación
                        atomo.uso_pista = True
                        logger.info(f"[{sesion_id}] Pista solicitada — átomo {atomo.id[:8]}... penalización activa")
                        pista_texto = await generar_pista(atomo.texto_completo, atomo.pregunta, lang=lang)
                        pista_audio, fmt_pista = await _tts(pista_texto)
                        if silencio_task and not silencio_task.done():
                            silencio_task.cancel()
                        audio_chunks = []
                        silencio_task = None
                        sesion.estado = "LISTENING_USER"
                        await websocket.send_json({
                            "type": "pista",
                            "texto": pista_texto,
                            "audio_base64": pista_audio,
                            "audio_format": fmt_pista,
                        })

                # Skip — salta la pregunta (rojo silencioso)
                elif t == "skip":
                    if silencio_task and not silencio_task.done():
                        silencio_task.cancel()
                    audio_chunks = []
                    atomo = sesion.atomo_actual
                    if atomo:
                        logger.info(f"[{sesion_id}] Skip átomo {atomo.id}")
                        await _guardar_resultado(atomo.id, "rojo", "[saltado]", 0.0)
                        # Guardar en flashcards_history
                        await asyncio.to_thread(lambda: db.table("flashcards_history").insert({
                            "session_id": sesion_id,
                            "atomo_id": atomo.id,
                            "concepto": atomo.titulo_corto,
                            "error_cometido": "Pregunta saltada",
                            "analogia_generada": atomo.texto_completo[:300],
                        }).execute())
                        sesion.indice_actual += 1
                        if sesion.completada:
                            fecha_fin = datetime.utcnow().isoformat()
                            await asyncio.to_thread(lambda: db.table("sesiones").update({
                                "fecha_fin": fecha_fin,
                                "status": "completada",
                            }).eq("id", sesion_id).execute())
                            await websocket.send_json({
                                "type": "sesion_completa",
                                "mensaje": "¡Sesión completada!",
                                "sesion_id": sesion_id,
                            })
                            eliminar_sesion(sesion_id)
                            break
                        else:
                            await websocket.send_json({
                                "type": "skip_ok",
                                "progreso": sesion.progreso,
                            })
                            await enviar_pregunta_actual()

                # Repetir pregunta (tras error con flashcard panel)
                elif t == "repetir" and sesion.estado == "WAITING_NEXT":
                    if silencio_task and not silencio_task.done():
                        silencio_task.cancel()
                    audio_chunks = []
                    # Deshacer el avance del índice para repetir la misma pregunta
                    if sesion.indice_actual > 0:
                        sesion.indice_actual -= 1
                    sesion.en_segundo_intento = False
                    logger.info(f"[{sesion_id}] Repitiendo pregunta {sesion.indice_actual}")
                    await enviar_pregunta_actual()

                # Pausar sesión — guardar progreso y cerrar
                elif t == "pausar":
                    if silencio_task and not silencio_task.done():
                        silencio_task.cancel()
                    audio_chunks = []
                    await asyncio.to_thread(lambda: db.table("sesiones").update({
                        "status": "empezada",
                        "current_question_index": sesion.indice_actual,
                    }).eq("id", sesion_id).execute())
                    logger.info(f"[{sesion_id}] Sesión pausada en índice {sesion.indice_actual}")
                    await websocket.send_json({
                        "type": "pausa_ok",
                        "mensaje": "Sesión guardada. Puedes retomar cuando quieras.",
                        "current_question_index": sesion.indice_actual,
                    })
                    break  # Cerrar conexión gracefully

                # Usuario pulsó Enviar — evaluar ahora (llega tras el último chunk de audio)
                elif t == "enviar" and sesion.estado == "LISTENING_USER":
                    if silencio_task and not silencio_task.done():
                        silencio_task.cancel()
                    logger.info(f"[{sesion_id}] Enviar recibido — evaluando")
                    await procesar_respuesta()

                # Cambiar voz (Kokoro o Azure Neural)
                elif t == "set_voice":
                    voz = msg.get("voice", "ef_dora")
                    if voz[:2] in ('af','am','bf','bm','ef','em','ff','fm','hf','hm','if','im','pf','pm','jf','jm','zf','zm') or "Neural" in voz:
                        sesion.kokoro_voice = voz
                        logger.info(f"[{sesion_id}] Voz cambiada a '{voz}'")

                # Cambiar idioma de la sesión en tiempo real
                elif t == "set_lang":
                    new_lang = msg.get("lang", "es")
                    if new_lang in ("es", "en", "de"):
                        lang = new_lang
                        prefetch_mgr.invalidate()  # Preguntas cacheadas en idioma anterior
                        logger.info(f"[{sesion_id}] Idioma cambiado a '{new_lang}'")

                # Toggle modo voz/chat
                elif t == "switch_mode":
                    modo = msg.get("mode", "voice")
                    sesion.tts_enabled = (modo == "voice")
                    prefetch_mgr.invalidate()  # TTS mode changed, invalidate buffer
                    logger.info(f"[{sesion_id}] Modo cambiado a '{modo}' tts={sesion.tts_enabled}")
                    await websocket.send_json({
                        "type": "modo_cambiado",
                        "modo": modo,
                    })

    except WebSocketDisconnect:
        logger.info(f"[{sesion_id}] WebSocket desconectado")
    except Exception as e:
        logger.error(f"[{sesion_id}] Error WebSocket: {e}", exc_info=True)
    finally:
        ws_connected = False
        if silencio_task and not silencio_task.done():
            silencio_task.cancel()
        await prefetch_mgr.stop()
        eliminar_sesion(sesion_id)
        logger.info(f"[{sesion_id}] Conexión cerrada")
