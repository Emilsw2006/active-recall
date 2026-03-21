from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_model: str = "gemini-3-pro-preview"
    google_cloud_project: str
    google_cloud_location: str = "us-central1"
    groq_api_key: str
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    secret_key: str = "cambia_esto_por_un_secreto_largo_y_aleatorio"
    # TTS — prioridad: Kokoro (local) → Azure → ElevenLabs → OpenAI → browser
    # Kokoro (open source, local, sin coste)
    use_kokoro_tts: bool = False
    kokoro_voice: str = "ef_dora"           # Voz española femenina de Kokoro
    # Azure TTS (5 millones chars/mes gratis, voces neurales excelentes)
    azure_tts_key: str = ""
    azure_tts_region: str = "eastus"
    azure_tts_voice: str = "es-ES-ElviraNeural"  # Elvira — la mejor voz española
    # ElevenLabs (10k chars/mes gratis)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # Sarah — multilingual
    # OpenAI TTS
    openai_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
