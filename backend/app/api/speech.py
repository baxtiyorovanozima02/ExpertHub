from pydantic import BaseModel, field_validator


class SpeechToTextOut(BaseModel):
    """STT natijasi: tan olingan matn."""
    text: str


class TextToSpeechIn(BaseModel):
    text: str
    lang: str = "uz-UZ"
    voice: str = "nigora"
    format: str = "oggopus"
    speed: float = 1.0

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Matn bo'sh bo'lishi mumkin emas")
        if len(v) > 5000:
            raise ValueError("Matn juda uzun (maksimum 5000 belgi)")
        return v

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        allowed = {"oggopus", "lpcm", "mp3"}
        if v not in allowed:
            raise ValueError(f"Noto'g'ri format: {v}. Ruxsat etilganlar: {sorted(allowed)}")
        return v

    @field_validator("speed")
    @classmethod
    def validate_speed(cls, v: float) -> float:
        if not (0.1 <= v <= 3.0):
            raise ValueError("Tezlik 0.1 dan 3.0 gacha bo'lishi kerak")
        return v