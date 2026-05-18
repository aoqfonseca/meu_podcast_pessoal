"""Gemini 2.5 native TTS — converts a podcast script into an audio file."""

from __future__ import annotations

import base64
import struct
import wave
from pathlib import Path

from google import genai
from google.genai import types


def _pcm_to_wav(pcm_bytes: bytes, out_path: Path, sample_rate: int = 24000) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)


def synthesize_to_wav(
    api_key: str,
    model: str,
    voice: str,
    script: str,
    out_path: Path,
) -> Path:
    """Send the script to Gemini TTS and write a WAV file. Returns the path written."""
    client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
    )

    response = client.models.generate_content(
        model=model,
        contents=script,
        config=config,
    )

    audio_chunks: list[bytes] = []
    sample_rate = 24000
    for cand in response.candidates or []:
        content = cand.content
        if content is None:
            continue
        for part in content.parts or []:
            inline = getattr(part, "inline_data", None)
            if not inline or not inline.data:
                continue
            data = inline.data
            if isinstance(data, str):
                data = base64.b64decode(data)
            audio_chunks.append(data)
            mime = inline.mime_type or ""
            if "rate=" in mime:
                try:
                    sample_rate = int(mime.split("rate=")[1].split(";")[0])
                except (ValueError, IndexError):
                    pass

    if not audio_chunks:
        raise RuntimeError("Gemini TTS returned no audio data")

    pcm = b"".join(audio_chunks)
    # quick sanity: PCM16 frames are 2 bytes
    if len(pcm) % 2 != 0:
        pcm = pcm + b"\x00"
    _pcm_to_wav(pcm, out_path, sample_rate=sample_rate)
    return out_path


# tiny helper, exported for tests
def _silence_pcm(seconds: float = 0.1, sample_rate: int = 24000) -> bytes:
    n = int(seconds * sample_rate)
    return struct.pack("<" + "h" * n, *([0] * n))
