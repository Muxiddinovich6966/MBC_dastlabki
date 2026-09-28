"""
Ovozli xabarni matnga aylantirish — Groq Whisper (large-v3) orqali.

Tekin API: https://console.groq.com  →  .env: GROQ_API_KEY=...
O'zbek tili yaxshi tanilishi uchun language='uz' beriladi.
"""
import asyncio
import io

import requests
from django.conf import settings

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"


def _post_groq(audio_bytes: bytes):
    """Audio baytlarini Groq'ga yuborib matn oladi. Qaytadi: (ok, matn_yoki_xato)."""
    token = getattr(settings, 'GROQ_API_KEY', '')
    if not token:
        return False, "GROQ_API_KEY yo'q (.env ga qo'shing)"
    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("voice.ogg", audio_bytes, "audio/ogg")},
            data={
                "model": GROQ_MODEL,
                "language": "uz",
                "response_format": "json",
                "temperature": "0",
                # Prompt modelni o'zbek tili va vazifa kontekstiga moslaydi (aniqlikni oshiradi)
                "prompt": "Bu o'zbek tilidagi ish topshirig'i. Masalan: "
                          "ertaga soat uchda hisobotni tayyorla, jadval tuz, mijozga qo'ng'iroq qil.",
            },
            timeout=60,
        )
        try:
            data = r.json()
        except Exception:
            return False, f"HTTP {r.status_code}"
        if r.status_code == 200:
            text = (data.get("text") or "").strip()
            return (True, text) if text else (False, "bo'sh natija")
        return False, (data.get("error", {}) or {}).get("message", f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


async def transcribe_voice(bot, file_id: str):
    """Telegram voice/audio file_id ni matnga aylantiradi.

    Qaytadi: (ok, matn_yoki_xato). Event loop bloklanmasligi uchun
    Groq so'rovi alohida thread'da bajariladi.
    """
    buf = io.BytesIO()
    try:
        await bot.download(file_id, destination=buf)
    except Exception as e:
        return False, f"faylni yuklab bo'lmadi: {e}"
    audio = buf.getvalue()
    if not audio:
        return False, "audio bo'sh"
    return await asyncio.to_thread(_post_groq, audio)
