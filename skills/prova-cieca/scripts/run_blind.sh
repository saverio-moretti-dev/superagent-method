#!/bin/bash
# Lancia UN tester cieco: claude -p --safe-mode, solo strumenti web, da cartella vuota temporanea.
# Uso: run_blind.sh <prompt.txt> <cartella-output> [modello=sonnet] [max-turni=30]
# Produce <cartella-output>/transcript.jsonl (stream-json) e <cartella-output>/risposta.txt
# CHROME=1: il tester usa anche il Chrome vero dell'utente, con i soli strumenti di CHROME_OK (niente altre schede,
# niente javascript, niente upload; tabs_context_mcp serve: dal 11/2026 tabs_create lo vuole prima). Un tester Chrome alla volta: le schede sono condivise. Poi check_blind.py --siti.
set -euo pipefail
PROMPT="${1:?prompt file}"; OUT="${2:?output dir}"; MODEL="${3:-sonnet}"; TURNS="${4:-30}"
[ -f "$PROMPT" ] || { echo "prompt non trovato: $PROMPT" >&2; exit 2; }
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"; PROMPT="$(cd "$(dirname "$PROMPT")" && pwd)/$(basename "$PROMPT")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/cieco.XXXXXX")"   # cartella vuota: nessun contesto locale
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
C=mcp__claude-in-chrome__
CHROME_OK="${C}tabs_context_mcp,${C}tabs_create_mcp,${C}tabs_close_mcp,${C}navigate,${C}computer,${C}read_page,${C}get_page_text,${C}find,${C}form_input,${C}resize_window"
CHROME_NO="${C}list_connected_browsers,${C}select_browser,${C}switch_browser,${C}javascript_tool,${C}read_network_requests,${C}read_console_messages,${C}file_upload,${C}upload_image,${C}shortcuts_execute,${C}shortcuts_list,${C}gif_creator,${C}browser_batch"
if [ "${CHROME:-0}" = 1 ]; then
  MCP=(--chrome --allowedTools "WebSearch,WebFetch,$CHROME_OK" --disallowedTools "$CHROME_NO")
else
  MCP=(--no-chrome --allowedTools "WebSearch,WebFetch" --disallowedTools "mcp__*")
fi
claude -p --safe-mode \
  --tools "WebSearch,WebFetch" "${MCP[@]}" \
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
