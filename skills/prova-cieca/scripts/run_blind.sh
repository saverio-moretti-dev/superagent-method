#!/bin/bash
# Lancia UN tester cieco: claude -p --safe-mode, solo strumenti web, da cartella vuota temporanea.
# Uso: run_blind.sh <prompt.txt> <cartella-output> [modello=sonnet] [max-turni=30]
# Produce <cartella-output>/transcript.jsonl (stream-json) e <cartella-output>/risposta.txt
# CHROME=1: il tester usa anche il Chrome vero dell'utente, con i soli strumenti di CHROME_OK (niente altre schede,
# niente javascript, niente upload; tabs_context_mcp serve: dal 11/2026 tabs_create lo vuole prima). Un tester Chrome alla volta: le schede sono condivise. Poi check_blind.py --siti.
# TETTO VERO: max-turni = numero massimo di CHIAMATE a strumenti. --max-turns della CLI conta le risposte del modello,
# e una risposta può contenere più chiamate in parallelo (8/11/2026, prova Chrome «scettico»: 23 risposte, 57 chiamate,
# num_turns 58, nessuno stop con max 25, costo oltre il tetto). Un sorvegliante legge il transcript mentre gira e ferma
# il tester alla chiamata max-turni+1; allora scrive <cartella-output>/INTERROTTO e risposta.txt riporta l'ultimo testo
# con la nota del tetto. --max-turns resta passato alla CLI come rete in più (scatta solo dopo).
# Messaggi fra sessioni: un claude -p può riceverli come una sessione qualunque. Il sorvegliante chiude il processo al
# primo evento result; check_blind.py segna SOSPETTO ogni transcript in cui ne è entrato uno.
# CLI_TURNS=N (solo per le prove del sorvegliante) alza il --max-turns passato alla CLI.
# Campagne (livelli 2-3, campagna.py): SESSIONE=<uuid> apre una sessione che resta salvata, RIPRENDI=<uuid> la riprende
# (stessi strumenti: --safe-mode + --resume verificato il 12/11/2026), CARTELLA=<dir> usa quella cartella vuota invece di
# una temporanea e non la cancella (la ripresa vuole la stessa cartella). Senza queste variabili: come sempre.
set -euo pipefail
PROMPT="${1:?prompt file}"; OUT="${2:?output dir}"; MODEL="${3:-sonnet}"; TURNS="${4:-30}"
[ -f "$PROMPT" ] || { echo "prompt non trovato: $PROMPT" >&2; exit 2; }
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"; PROMPT="$(cd "$(dirname "$PROMPT")" && pwd)/$(basename "$PROMPT")"
if [ -n "${CARTELLA:-}" ]; then mkdir -p "$CARTELLA"; WORK="$(cd "$CARTELLA" && pwd)"
else WORK="$(mktemp -d "${TMPDIR:-/tmp}/cieco.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT; fi   # cartella vuota: nessun contesto locale
if [ -n "${RIPRENDI:-}" ]; then SESS=(--resume "$RIPRENDI")
elif [ -n "${SESSIONE:-}" ]; then SESS=(--session-id "$SESSIONE")
else SESS=(--no-session-persistence); fi
cd "$WORK"
C=mcp__claude-in-chrome__
CHROME_OK="${C}tabs_context_mcp,${C}tabs_create_mcp,${C}tabs_close_mcp,${C}navigate,${C}computer,${C}read_page,${C}get_page_text,${C}find,${C}form_input,${C}resize_window"
CHROME_NO="${C}list_connected_browsers,${C}select_browser,${C}switch_browser,${C}javascript_tool,${C}read_network_requests,${C}read_console_messages,${C}file_upload,${C}upload_image,${C}shortcuts_execute,${C}shortcuts_list,${C}gif_creator,${C}browser_batch"
if [ "${CHROME:-0}" = 1 ]; then
  MCP=(--chrome --allowedTools "WebSearch,WebFetch,$CHROME_OK" --disallowedTools "$CHROME_NO")
else
  MCP=(--no-chrome --allowedTools "WebSearch,WebFetch" --disallowedTools "mcp__*")
fi
rm -f "$OUT/INTERROTTO"; : > "$OUT/transcript.jsonl"
# ENABLE_CLAUDEAI_MCP_SERVERS=false: connettori claude.ai mai caricati. Oggi --safe-mode li esclude già (8/11/2026:
# stessi server e stessi token con e senza, web e Chrome); resta come garanzia se --safe-mode cambia.
ENABLE_CLAUDEAI_MCP_SERVERS=false claude -p --safe-mode \
  --tools "WebSearch,WebFetch" "${MCP[@]}" \
  --model "$MODEL" --max-turns "${CLI_TURNS:-$TURNS}" "${SESS[@]}" \
  --output-format stream-json --verbose < "$PROMPT" > "$OUT/transcript.jsonl" &
CPID=$!
# Sorvegliante: conta le chiamate a strumenti (id distinti dei blocchi tool_use) e ferma claude oltre il tetto.
python3 -I - "$OUT/transcript.jsonl" "$CPID" "$TURNS" <<'PY' &
import json, os, signal, sys, time
f, pid, lim = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ids, pos, buf = set(), 0, ""
def vivo():
    try: os.kill(pid, 0); return True
    except OSError: return False
while vivo():
    with open(f) as h:
        h.seek(pos); buf += h.read(); pos = h.tell()
    *righe, buf = buf.split("\n")
    for l in righe:
        try: e = json.loads(l)
        except Exception: continue
        m = e.get("message") or {}
        if e.get("type") == "assistant":
            ids.update(c.get("id") for c in m.get("content", []) if c.get("type") == "tool_use")
        if e.get("type") == "result":  # turno finito: chiudere subito, prima che arrivi un messaggio di un'altra
            time.sleep(1)               # sessione (12/11/2026: un claude -p ha ricevuto un messaggio del coordinatore
            if vivo(): os.kill(pid, signal.SIGTERM)  # dopo il risultato e ha fatto un secondo turno)
            sys.exit(0)
    if len(ids) > lim:
        os.kill(pid, signal.SIGTERM); time.sleep(5)
        if vivo(): os.kill(pid, signal.SIGKILL)
        open(os.path.join(os.path.dirname(f), "INTERROTTO"), "w").write(
            f"fermato dal sorvegliante: {len(ids)} chiamate a strumenti, tetto {lim}\n")
        break
    time.sleep(0.5)
PY
WPID=$!
RC=0; wait "$CPID" || RC=$?
# chiuso dal sorvegliante dopo un turno finito (SIGTERM = 143): non è un errore
if [ "$RC" = 143 ] && [ ! -f "$OUT/INTERROTTO" ] && grep -q '"type": *"result"' "$OUT/transcript.jsonl"; then RC=0; fi
wait "$WPID" 2>/dev/null || true
python3 -I "$(dirname "$0")/risposta.py" "$OUT"  # risposta.txt: primo result, o il testo col formato se dopo c'è un'altra azione
if [ -f "$OUT/INTERROTTO" ]; then echo "interrotto (tetto $TURNS chiamate a strumenti): $OUT"; exit 3; fi
[ "$RC" = 0 ] || { echo "claude uscito con codice $RC (es. tetto --max-turns della CLI): $OUT"; exit "$RC"; }
echo "fatto: $OUT"
