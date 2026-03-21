"""
Global API rate limiters (asyncio.Semaphore).

Prevent 429 errors and protect external APIs under concurrent load.
Tune values based on your API tier:
  - Groq free tier:  ~30 RPM  → Semaphore(8) is safe
  - Groq paid tier:  ~240 RPM → raise to Semaphore(30)
  - Gemini Vertex:   depends on quota → Semaphore(5) is conservative

Usage in any async function:
    from core.limits import GROQ_LLM_SEM
    async with GROQ_LLM_SEM:
        response = await asyncio.to_thread(_call_api)
"""

import asyncio

# Groq LLM — evaluation + feedback generation
GROQ_LLM_SEM = asyncio.Semaphore(8)

# Groq Whisper — speech-to-text transcription
GROQ_STT_SEM = asyncio.Semaphore(10)

# Gemini / Vertex AI — flashcard generation
GEMINI_SEM = asyncio.Semaphore(5)
