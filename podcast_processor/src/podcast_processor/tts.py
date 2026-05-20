"""TTS backends — convert a podcast script into an audio file.

Two providers are supported:
- `gemini`: Gemini 2.5 native TTS (paid). Writes PCM-to-MP3 via lameenc.
- `edge`:   Microsoft Edge TTS (free, no API key). Writes MP3 directly.

Both providers accept an optional `voice_map` dict that maps speaker names
(e.g. ``{"André": "pt-BR-AntonioNeural", "Marina": "pt-BR-FranciscaNeural"}``)
to their respective voices. When supplied the script is split on ``[Speaker]:``
tags and each segment is rendered with the correct voice, producing natural
two-host dialogue audio.
"""

from __future__ import annotations

import asyncio
import base64
import re
from pathlib import Path

import edge_tts
import lameenc
from google import genai
from google.genai import types

# Matches lines like "[André]: some text" or "[Marina]: other text".
# re.split on this pattern (with capture group) produces alternating
# [pre_text, speaker, text, speaker, text, ...] chunks.
_SPEAKER_TAG = re.compile(r"^\[([^\]]+)\]:\s*", re.MULTILINE)


def _parse_speaker_turns(script: str) -> list[tuple[str, str]]:
    """Split a script on [Speaker]: tags into (speaker, text) pairs."""
    parts = _SPEAKER_TAG.split(script)
    # parts[0] is any text before the first tag (preamble); skip it.
    turns: list[tuple[str, str]] = []
    it = iter(parts[1:])
    for speaker in it:
        text = next(it, "").strip()
        if text:
            turns.append((speaker.strip(), text))
    return turns


# ---------------------------------------------------------------------------
# MP3 helper
# ---------------------------------------------------------------------------


def _pcm_to_mp3(pcm_bytes: bytes, out_path: Path, sample_rate: int = 24000) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(1)
    encoder.set_quality(2)
    mp3_data = encoder.encode(pcm_bytes) + encoder.flush()
    out_path.write_bytes(mp3_data)


# ---------------------------------------------------------------------------
# Gemini TTS
# ---------------------------------------------------------------------------


def _extract_pcm(response: object) -> tuple[bytes, int]:
    """Pull raw PCM bytes and sample rate out of a Gemini generate_content response."""
    audio_chunks: list[bytes] = []
    sample_rate = 24000
    for cand in getattr(response, "candidates", None) or []:
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
    return b"".join(audio_chunks), sample_rate


def synthesize_to_mp3(
    api_key: str,
    model: str,
    voice: str,
    script: str,
    out_path: Path,
    voice_map: dict[str, str] | None = None,
) -> Path:
    """Send the script to Gemini TTS and write an MP3 file. Returns the path written.

    When `voice_map` is provided and the script contains ``[Speaker]:`` tags,
    uses Gemini's multi-speaker TTS in a single API call so the model can
    produce naturally varied voices for each host.
    """
    client = genai.Client(api_key=api_key)

    turns = _parse_speaker_turns(script) if voice_map else []
    if turns and voice_map:
        speaker_configs = [
            types.SpeakerVoiceConfig(
                speaker=speaker,
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_map.get(speaker, voice)
                    )
                ),
            )
            for speaker in dict.fromkeys(s for s, _ in turns)  # preserve order, deduplicate
        ]
        speech_cfg = types.SpeechConfig(
            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=speaker_configs
            )
        )
    else:
        speech_cfg = types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        )

    response = client.models.generate_content(
        model=model,
        contents=script,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=speech_cfg,
        ),
    )

    pcm, sample_rate = _extract_pcm(response)
    if not pcm:
        raise RuntimeError("Gemini TTS returned no audio data")
    if len(pcm) % 2 != 0:
        pcm += b"\x00"
    _pcm_to_mp3(pcm, out_path, sample_rate=sample_rate)
    return out_path


# ---------------------------------------------------------------------------
# Edge TTS
# ---------------------------------------------------------------------------


async def _edge_stream_to_mp3(text: str, voice: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice=voice)
    with open(out_path, "wb") as fp:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])


async def _edge_multispeaker_to_mp3(
    turns: list[tuple[str, str]],
    voice_map: dict[str, str],
    fallback_voice: str,
    out_path: Path,
) -> None:
    """Render each speaker turn with its own voice and stream all into one MP3."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fp:
        for speaker, text in turns:
            voice = voice_map.get(speaker, fallback_voice)
            communicate = edge_tts.Communicate(text, voice=voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    fp.write(chunk["data"])


def synthesize_edge_to_mp3(
    voice: str,
    script: str,
    out_path: Path,
    voice_map: dict[str, str] | None = None,
) -> Path:
    """Synthesize `script` with Microsoft Edge TTS, writing an MP3.

    Voice names follow Edge format, e.g. ``pt-BR-FranciscaNeural``,
    ``pt-BR-AntonioNeural``. No API key needed.

    When `voice_map` is provided and the script contains ``[Speaker]:`` tags,
    each speaker's lines are rendered with their mapped voice so the hosts
    sound distinct.
    """
    turns = _parse_speaker_turns(script) if voice_map else []
    if turns and voice_map:
        asyncio.run(_edge_multispeaker_to_mp3(turns, voice_map, voice, out_path))
    else:
        asyncio.run(_edge_stream_to_mp3(script, voice, out_path))
    return out_path
