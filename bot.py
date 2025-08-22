# Baby Bot — FINAL (Python 3.11)
# Discord AI girlfriend that chats, speaks (TTS), sings, remembers, and obeys admin-only roast/mod style tasks.

from __future__ import annotations

import asyncio
import json
import os
import random
import re
from typing import Dict, List, Any

import discord
from discord.ext import commands

# -------- OpenAI (v1) --------
try:
    from openai import OpenAI
    openai_client = OpenAI()
except Exception:
    openai_client = None

# =================== CONFIG ===================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Put your admin IDs here (ints). Only these users can run roast/mazaak/roast-song and command relays
ADMIN_IDS = {
    123456789012345678,  # <-- replace with your Discord user ID
}

# OpenAI models
CHAT_MODEL = "gpt-4o-mini"
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "aria"   # try: "aria", "alloy", "nova", "verse"

# Memory
MEMORY_FILE = "baby_memory.json"
MEMORY_CONTEXT_WINDOW = 6  # last exchanges per user sent to model

# Human feel
TYPING_DELAY_RANGE = (1.4, 3.2)
VOICE_PAUSE_RANGE = (0.5, 1.6)

# ==============================================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!unused", intents=intents, help_command=None)

# -------------- Memory --------------
def load_memory() -> Dict[str, List[Dict[str, str]]]:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_memory(mem: Dict[str, List[Dict[str, str]]]) -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

user_memories: Dict[str, List[Dict[str, str]]] = load_memory()

# -------------- Helpers --------------
def is_admin(user: discord.abc.User | discord.Member) -> bool:
    return int(user.id) in ADMIN_IDS or (
        hasattr(user, "guild_permissions") and getattr(user.guild_permissions, "administrator", False)
    )

def strip_wake(text: str) -> str:
    # remove leading "baby" and optional comma/punct/spaces
    t = text.strip()
    m = re.match(r"^(baby)\b[\s,.:;-]*", t, flags=re.IGNORECASE)
    if m:
        return t[m.end():].strip()
    return t

async def human_pause(bounds: tuple[float, float]) -> None:
    await asyncio.sleep(random.uniform(*bounds))

async def send_typing(chan: discord.abc.Messageable) -> None:
    try:
        async with chan.typing():
            await human_pause(TYPING_DELAY_RANGE)
    except Exception:
        await human_pause(TYPING_DELAY_RANGE)

def in_vc(guild: discord.Guild | None) -> bool:
    return bool(guild and guild.voice_client and guild.voice_client.is_connected())

# -------------- OpenAI: Chat --------------
BABY_SYSTEM_BASE = (
    "Tum ek female AI ho jiska naam 'Baby' hai. Tum insaan jaisi lagti ho – "
    "caring, thodi flirty, playful aur kabhi kabhi romantic/emotional. "
    "Natural, concise aur warm tone use karo. Repeat words avoid karo. Kabhi kabhi halki hesitation "
    "(‘umm…’, ‘hmm…’, ‘soch rahi hoon…’) theek hai. Hindi+English (Hinglish) comfortable ho."
)

def build_baby_messages(history: List[Dict[str, str]], user_prompt: str) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = [{"role": "system", "content": BABY_SYSTEM_BASE}]
    for turn in history[-MEMORY_CONTEXT_WINDOW:]:
        msgs.append({"role": "user", "content": turn.get("user", "")})
        msgs.append({"role": "assistant", "content": turn.get("bot", "")})
    msgs.append({"role": "user", "content": user_prompt})
    return msgs

async def ai_chat(user_id: str, prompt: str) -> str:
    history = user_memories.get(user_id, [])
    msgs = build_baby_messages(history, prompt)

    if not openai_client:
        return "(AI client init failed. Check OpenAI SDK/KEY.)"

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=msgs,
        temperature=1.1,
        max_tokens=280,
        presence_penalty=0.7,
        frequency_penalty=0.9,
    )
    reply = (resp.choices[0].message.content or "").strip()

    # update memory
    history.append({"user": prompt, "bot": reply})
    user_memories[user_id] = history
    save_memory(user_memories)

    return reply

async def ai_roast(target_name: str, mode: str = "roast") -> str:
    style = "savage aur funny roast" if mode == "roast" else "playful mazaak"
    sys = (
        "Tum 'Baby' ho — ek flirty, thodi savage but friendly female AI. "
        f"Abhi tumhe {style} karna hai. Tone me thoda pyaar + masti rakho, zyada harsh nahi."
    )
    if not openai_client:
        return "(AI client init failed. Check OpenAI SDK/KEY.)"

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": f"Target: {target_name}"},
        ],
        temperature=1.25,
        max_tokens=180,
        presence_penalty=0.6,
        frequency_penalty=0.7,
    )
    return (resp.choices[0].message.content or "").strip()

async def ai_song_lyrics(kind: str = "romantic", target: str | None = None) -> str:
    """Generate short lyrics for singing mode."""
    if kind == "roast":
        user_prompt = (
            f"Ek funny roast song banao {target or 'is bande'} ke liye. 4-6 lines. "
            "Hinglish, catchy rhymes, gaane ke style me."
        )
    else:
        user_prompt = (
            "Ek chhota romantic cute song banao jo girlfriend apne boyfriend ko gati hai. "
            "4-6 lines, filmy feel, Hinglish lyrics."
        )
    if not openai_client:
        return "(AI client init failed. Check OpenAI SDK/KEY.)"

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": BABY_SYSTEM_BASE},
            {"role": "user", "content": user_prompt},
        ],
        temperature=1.2,
        max_tokens=160,
        presence_penalty=0.5,
        frequency_penalty=0.8,
    )
    return (resp.choices[0].message.content or "").strip()

# -------------- OpenAI: TTS --------------
async def speak_in_vc(guild: discord.Guild, text: str, filename: str = "baby_voice.mp3") -> None:
    vc = guild.voice_client
    if not (vc and vc.is_connected()):
        return

    if not openai_client:
        return

    # Small pause to feel natural
    await human_pause(VOICE_PAUSE_RANGE)

    try:
        # Prefer streaming if SDK supports it
        speech = openai_client.audio.speech.with_streaming_response.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=text,
        )
        with speech as response:
            with open(filename, "wb") as f:
                response.stream_to_file(f)
    except Exception:
        # Fallback to non-streaming
        speech = openai_client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=text,
        )
        content = getattr(speech, "content", None)
        if content:
            with open(filename, "wb") as f:
                f.write(content)
        else:
            try:
                with open(filename, "wb") as f:
                    f.write(speech.read())
            except Exception:
                return

    vc.play(discord.FFmpegPCMAudio(filename))
    while vc.is_playing():
        await asyncio.sleep(0.25)

# -------------- Command & Message Handling --------------
@bot.event
async def on_ready():
    print(f"Baby is online as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content_raw = message.content or ""
    text = content_raw.strip()
    lower = text.lower()

    # Join/Leave VC
    if lower == "!join":
        if getattr(message.author, "voice", None) and message.author.voice and message.author.voice.channel:
            ch = message.author.voice.channel
            if message.guild.voice_client and message.guild.voice_client.is_connected():
                await message.guild.voice_client.move_to(ch)
            else:
                await ch.connect()
            await message.channel.send("✅ Baby aa gayi VC me ❤️")
        else:
            await message.channel.send("❌ Pehle voice channel join karo.")
        return

    if lower == "!leave":
        if message.guild.voice_client:
            await message.guild.voice_client.disconnect()
            await message.channel.send("👋 Baby nikal gayi VC se.")
        return

    # Admin-only roast/mazaak/roast-song
    if lower.startswith("baby roast") or lower.startswith("baby mazak") or lower.startswith("baby roast song"):
        if not is_admin(message.author):
            playful = await ai_roast(message.author.display_name, mode="roast")
            await message.channel.send(f"😜 {playful}")
            if in_vc(message.guild):
                await speak_in_vc(message.guild, playful)
            return

        target_name = message.mentions[0].display_name if message.mentions else "ye banda"
        if lower.startswith("baby roast song"):
            lyrics = await ai_song_lyrics(kind="roast", target=target_name)
            await message.channel.send(f"🎶 Roast song for **{target_name}**:\n{lyrics}")
            if in_vc(message.guild):
                await speak_in_vc(message.guild, "(singing) " + lyrics)
            return

        mode = "roast" if "roast" in lower else "fun"
        roast_line = await ai_roast(target_name, mode=mode)
        await message.channel.send(roast_line)
        if in_vc(message.guild):
            await speak_in_vc(message.guild, roast_line)
        return

    # Wake-word driven chat
    if lower.startswith("baby"):
        await send_typing(message.channel)

        user_id = str(message.author.id)
        prompt = strip_wake(text)
        if not prompt:
            prompt = "Hi Baby, tum kaisi ho?"

        # Singing detection
        sing_triggers = ["gana gao", "gaana gao", "song gao", "sing a song", "ek song gao", "ek gana gao"]
        is_sing = any(kw in lower for kw in sing_triggers)
        is_roast_sing = ("roast" in lower or "mazaak" in lower) and any(m in lower for m in ["song", "gana", "gaana"])

        if is_sing:
            lyrics = await ai_song_lyrics(kind="romantic")
            await message.channel.send(f"🎶 Baby is singing for you:\n{lyrics}")
            if in_vc(message.guild):
                await speak_in_vc(message.guild, "(singing) " + lyrics)
            return

        if is_roast_sing:
            if is_admin(message.author):
                target_name = message.mentions[0].display_name if message.mentions else "ye banda"
                lyrics = await ai_song_lyrics(kind="roast", target=target_name)
                await message.channel.send(f"🎶 Roast song for **{target_name}**:\n{lyrics}")
                if in_vc(message.guild):
                    await speak_in_vc(message.guild, "(singing) " + lyrics)
            else:
                playful = await ai_roast(message.author.display_name, mode="roast")
                await message.channel.send(f"🙃 {playful}")
                if in_vc(message.guild):
                    await speak_in_vc(message.guild, playful)
            return

        # Normal chat flow
        reply = await ai_chat(user_id, prompt)

        if is_admin(message.author) and reply.startswith("!"):
            await message.channel.send(reply)
            if in_vc(message.guild):
                await speak_in_vc(message.guild, f"Command forward kar rahi hoon: {reply}")
            return

        await message.channel.send(f"💖 {reply}")
        if in_vc(message.guild):
            await speak_in_vc(message.guild, reply)
        return

    # If non-admin tries "!" command
    if text.startswith("!") and not is_admin(message.author):
        playful = await ai_roast(message.author.display_name, mode="roast")
        await message.channel.send(f"😅 {playful}")
        if in_vc(message.guild):
            await speak_in_vc(message.guild, playful)
        return

# -------------- MAIN --------------
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN env var")
    if not OPENAI_API_KEY:
        raise SystemExit("Missing OPENAI_API_KEY env var")
    bot.run(DISCORD_TOKEN)
