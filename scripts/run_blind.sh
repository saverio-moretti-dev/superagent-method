#!/bin/bash
# Lancia UN tester cieco: claude -p --safe-mode, solo strumenti web, da cartella vuota temporanea.
# Uso: run_blind.sh <prompt.txt> <cartella-output> [modello=sonnet] [max-turni=30]
# Produce <cartella-output>/transcript.jsonl (stream-json) e <cartella-output>/risposta.txt
set -euo pipefail
PROMPT="${1:?prompt file}"; OUT="${2:?output dir}"; MODEL="${3:-sonnet}"; TURNS="${4:-30}"
[ -f "$PROMPT" ] || { echo "prompt non trovato: $PROMPT" >&2; exit 2; }
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"; PROMPT="$(cd "$(dirname "$PROMPT")" && pwd)/$(basename "$PROMPT")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/cieco.XXXXXX")"   # cartella vuota: nessun contesto locale
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
claude -p --safe-mode \
  --tools "WebSearch,WebFetch" --allowedTools "WebSearch,WebFetch" --disallowedTools "mcp__*" \
  --model "$MODEL" --max-turns "$TURNS" --no-session-persistence \
  --output-format stream-json --verbose < "$PROMPT" > "$OUT/transcript.jsonl"
python3 -I - "$OUT" <<'PY'
import json,sys
o=sys.argv[1]; res=""
for l in open(o+"/transcript.jsonl"):
    try: e=json.loads(l)
    except Exception: continue
    if e.get("type")=="result": res=e.get("result","")
open(o+"/risposta.txt","w").write(res)
PY
echo "fatto: $OUT"
