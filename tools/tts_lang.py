#!/usr/bin/env python3
"""edge-tts wrapper that tags the text language for multilingual voices.

Sets the SSML document language (TTS_LANG env, default id-ID) so multilingual
voices read the phrase as Indonesian.  Usage:
  tts_lang.py VOICE RATE PITCH VOLUME OUT.mp3 "text"
"""
import asyncio, os, sys
import edge_tts
import edge_tts.communicate as comm

OPEN_EN, CLOSE_EN = "⟦EN⟧", "⟦/EN⟧"   # markers that survive XML escaping


LANG = os.environ.get("TTS_LANG", "id-ID")


def mkssml(tc, escaped_text):
    """Same SSML edge-tts builds, but with the document language set (the service
    rejects inner <lang> tags, so the language applies to the whole phrase)."""
    if isinstance(escaped_text, bytes):
        escaped_text = escaped_text.decode("utf-8")
    return ("<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
            f"xml:lang='{LANG}'><voice name='{tc.voice}'>"
            f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
            f"{escaped_text}</prosody></voice></speak>")


comm.mkssml = mkssml


async def main(voice, rate, pitch, volume, out, text):
    c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume,
                             proxy=os.environ.get("HTTPS_PROXY"))
    await c.save(out)


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:7]))
