from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_model: str = "gemini-1.5-flash"
    gemini_api_key: str = "" # Support for Google AI Studio keys
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    groq_api_key: str
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    secret_key: str = "Hjhdeivacdlfn23"
    
    # TTS — prioridad: Kokoro (local) → Azure → ElevenLabs → OpenAI → browser
    # Kokoro (open source, local, sin coste)
    use_kokoro_tts: bool = True
    kokoro_voice: str = "ef_dora"
    # Piper TTS (local, neural quality)
    use_piper_tts: bool = False
    # Azure TTS (5 millones chars/mes gratis)
    azure_tts_key: str = ""
    azure_tts_region: str = "eastus"
    azure_tts_voice: str = "es-ES-ElviraNeural"
    # ElevenLabs (10k chars/mes gratis)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    # OpenAI TTS
    openai_api_key: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore" # Don't crash if extra variables are in .env
    }




settings = Settings()
