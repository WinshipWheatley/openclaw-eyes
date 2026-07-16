#!/usr/bin/env bash
# Master -> operator VOICE on the Maestro Telegram channel.
# Kokoro-82M neural TTS — clean American English (intelligible, high quality), no reverb.
if [ "${OPENCLAW_SKIP_CHIEF_ENV:-0}" != "1" ]; then
  set -a; source /home/openclaw/.chief.env 2>/dev/null || true; set +a
fi
# Ollama owns the 6 GB card. Voice always uses the warm CPU service or a local CPU fallback.
export CUDA_VISIBLE_DEVICES=""
TXT="$(cat)"

# --- voice-layer leak guard (redesign change 1/5, 2026-06-22) ---
# Operator surfaces are PROSE ONLY (agent_voice_response_layer policy: NO_JARGON_IN_ELIWINSHIP —
# no raw JSON keys, file paths, hashes, class names, rail jargon). master_voice previously piped
# raw stdin straight to TTS+Telegram, bypassing the voice layer. Refuse machine-contract so a
# receipt/JSON/stack-trace can never reach the operator's ear or eye through this script.
if ! printf '%s' "$TXT" | "${PYGUARD:-/home/openclaw/chief_env/bin/python}" -c '
import sys, re
t = sys.stdin.read(); s = t.strip()
keyhits = len(re.findall(r"\"[A-Za-z_][A-Za-z0-9_]*\"\s*:", t))
bad = (
    s.startswith(("{", "[")) or
    keyhits >= 2 or
    "Traceback (most recent call last)" in t or
    re.search(r"OpenClawResponseForMac\(|content_hash=|request_id=|source_request_id=|internal_status=", t) is not None
)
sys.exit(1 if bad else 0)
' 2>/dev/null; then
  echo "REFUSED: master_voice received machine-contract content (raw JSON / receipt / stack trace). Operator surfaces are prose-only — route it through the voice layer first. Not sent." >&2
  exit 6
fi
# --- end voice-layer leak guard ---

WAV="${WAV:-/mnt/c/OpenClaw/logs/master_voice.wav}"
OGG="${OGG:-/mnt/c/OpenClaw/logs/master_voice.ogg}"
PYV="${PYV:-/home/openclaw/chief_env/bin/python}"; [ -x "$PYV" ] || PYV=python3
CURL_BIN="${CURL_BIN:-curl}"
redact_with_python() {
  "$PYV" -c 'import sys; sys.path.insert(0, "/home/openclaw"); from secret_log_redaction import redact_secrets; sys.stdout.write(redact_secrets(sys.stdin.read()))' 2>/dev/null \
    || printf '<redaction unavailable>'
}
AGENT="${KOKORO_AGENT:-${OPENCLAW_AGENT:-${AGENT:-maestro}}}"
VOICE="${KOKORO_VOICE:-}"
if [ -z "$VOICE" ]; then
  VOICE="$(OPENCLAW_VOICE_AGENT="$AGENT" "$PYV" -c 'import os; from agent_kokoro_voice import voice_for_agent; print(voice_for_agent(os.environ["OPENCLAW_VOICE_AGENT"]))')" \
    || { echo "KOKORO VOICE RESOLUTION FAILED for agent=$AGENT"; exit 2; }
fi
SPEED="${KOKORO_SPEED:-1.05}"

# Provenance label so the operator can tell this is the Orchestrator relayed THROUGH
# Maestro's lane — not Maestro talking about himself. Override via RELAY_LABEL.
# Moved above the synth step (task 128) so it's available to the text-only fallback too.
PROV="${RELAY_LABEL:-🎼 Orchestrator · relayed through Maestro}"
export API="https://api.telegram.org/bot${MAESTRO_BOT_TOKEN}"
export CHAT="${TELEGRAM_AUTHORIZED_USER_ID}"

# Telegram limits: media caption <= 1024 chars, text message <= 4096. Never silently
# truncate (operator caught a cut-off brief 2026-06-20). Chunked under 4096 preferring
# paragraph/line/word breaks. Shared by the long-brief voice followup AND the text-only
# fallback (task 128) — one chunking implementation, both callers.
send_chunked_text() {
  printf '%s' "$1" | "$PYV" -c '
import sys, os, json, urllib.request, urllib.parse
sys.path.insert(0, "/home/openclaw")
from secret_log_redaction import redact_secrets
txt=sys.stdin.read().strip(); api=os.environ["API"]; chat=os.environ["CHAT"]; LIM=3900
chunks=[]
while txt:
    if len(txt)<=LIM: chunks.append(txt); break
    cut=txt.rfind("\n\n",0,LIM)
    if cut<400: cut=txt.rfind("\n",0,LIM)
    if cut<400: cut=txt.rfind(" ",0,LIM)
    if cut<400: cut=LIM
    chunks.append(txt[:cut].rstrip()); txt=txt[cut:].lstrip()
for i,c in enumerate(chunks):
    data=urllib.parse.urlencode({"chat_id":chat,"text":c}).encode()
    try:
        r=urllib.request.urlopen(api+"/sendMessage",data=data,timeout=20)
        d=json.load(r); print(f"text {i+1}/{len(chunks)} ok:",d.get("ok"),"| err:",d.get("description"))
    except Exception as e:
        print(f"text {i+1} FAILED:",redact_secrets(str(e)))
'
}

# Task 128: words > silence, always. If Kokoro synth fails on both GPU and CPU, the
# operator must still get the message — as text, with an honest note that voice wasn't
# available — never total silence.
send_text_only_fallback() {
  echo "text sent ok: true (voice unavailable fallback)"
  send_chunked_text "$(printf '%s\n%s\n\n(voice unavailable)' "$PROV" "$TXT")"
}

KOKORO_SYNTH_PY="$(mktemp --suffix=.py)"
cat > "$KOKORO_SYNTH_PY" <<'PYEOF'
import sys, os, numpy as np, soundfile as sf
sys.path.insert(0, "/home/openclaw")
from kokoro import KPipeline
from agent_kokoro_voice import apply_pronunciation_lexicon, normalize_loudness
text = sys.stdin.read()
try:  # speech-tailor for the ear (emoji-free, symbols spoken) — same render as every agent
    from speech_render import to_speech_text
    text = to_speech_text(text)
except Exception:
    pass
text = apply_pronunciation_lexicon(text)
pipe = KPipeline(lang_code="a")
chunks=[a for _,_,a in pipe(text, voice=os.environ["VOICE"], speed=float(os.environ["SPEED"]))]
if not chunks: sys.exit(3)
sf.write(os.environ["WAV"], normalize_loudness(np.concatenate(chunks)), 24000)
print("[kokoro] ok agent=", os.environ["AGENT"], "voice=", os.environ["VOICE"], flush=True)
PYEOF

WARM_AUDIO="$({
  printf '%s' "$TXT" | AGENT="$AGENT" "$PYV" -c '
import os, sys
sys.path.insert(0, "/home/openclaw")
from kokoro_voice_client import synthesize_remote
path = synthesize_remote(sys.stdin.read(), agent=os.environ["AGENT"], timeout=15.0)
sys.stdout.write(str(path or ""))
';
} 2>/dev/null)"

SYNTH_INPUT=""
if [ -n "$WARM_AUDIO" ] && [ -s "$WARM_AUDIO" ]; then
  SYNTH_INPUT="$WARM_AUDIO"
else
  echo "WARM KOKORO SERVICE UNAVAILABLE — using local CPU synth" >&2
  printf '%s' "$TXT" | OPENCLAW_KOKORO_SYNTH_ATTEMPT=fallback AGENT="$AGENT" VOICE="$VOICE" SPEED="$SPEED" WAV="$WAV" "$PYV" "$KOKORO_SYNTH_PY"
  SYNTH_STATUS=$?
  if [ "$SYNTH_STATUS" -eq 0 ] && [ -s "$WAV" ]; then
    SYNTH_INPUT="$WAV"
  fi
fi
rm -f "$KOKORO_SYNTH_PY"
if [ -z "$SYNTH_INPUT" ]; then
  send_text_only_fallback
  exit 0
fi

# pure vowels / crisp consonants: light presence + warmth, NO reverb, NO pitch tricks
ffmpeg -y -loglevel error -i "$SYNTH_INPUT" -af "equalizer=f=3000:t=q:w=2:g=1.5,equalizer=f=180:t=q:w=1:g=1" -c:a libopus -b:a 64k "$OGG" || { echo "FFMPEG FAILED"; send_text_only_fallback; exit 0; }

FULL="$(printf '%s\n%s' "$PROV" "$TXT")"
if [ "${#FULL}" -le 950 ]; then
  CAP="$FULL"; LONG=0
else
  CAP="$(printf '%s\n%s' "$PROV" "🎧 voice note — full text below ⬇️")"; LONG=1
fi

VOICE_RESPONSE="$(mktemp)"
VOICE_CURL_ERR="$(
  "$CURL_BIN" -sS "${API}/sendVoice" \
    -F chat_id="$CHAT" \
    -F voice="@${OGG};type=audio/ogg" \
    --form-string caption="$CAP" \
    --output "$VOICE_RESPONSE" \
    2>&1
)"
VOICE_CURL_STATUS=$?
if [ "$VOICE_CURL_STATUS" -ne 0 ]; then
  printf 'voice send FAILED: ' >&2
  printf '%s' "$VOICE_CURL_ERR" | redact_with_python >&2
  printf '\n' >&2
  rm -f "$VOICE_RESPONSE"
  exit 7
fi
"$PYV" -c 'import json,sys; d=json.load(sys.stdin); print("voice sent ok:", d.get("ok"), "| msg:", (d.get("result") or {}).get("message_id"), "| err:", d.get("description"))' < "$VOICE_RESPONSE"
rm -f "$VOICE_RESPONSE"

if [ "$LONG" = "1" ]; then
  send_chunked_text "$TXT"
fi
