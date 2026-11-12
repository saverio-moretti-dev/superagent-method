#!/usr/bin/env python3
"""Controlla un transcript stream-json di un tester cieco.
Uso: check_blind.py <cartella-output | transcript.jsonl> [--siti host1,host2]
Con --siti (prova con Chrome): ammessi anche gli strumenti Chrome di run_blind.sh, ma ogni navigate deve
restare su quegli host; vietati gli strumenti che leggono le altre schede o il browser.
Esito CIECO se: solo WebSearch/WebFetch usati, nessuno strumento disponibile oltre a quelli (a parte ToolSearch/consegna),
nessun connettore mcp__, nessun messaggio di altre sessioni entrato. Riporta ricerche, fetch, token, costo. Exit 0 = cieco, 1 = sospetto."""
import json, sys, os
from urllib.parse import urlparse
a = sys.argv[1:]
p = a[0] if a else sys.exit("uso: check_blind.py <cartella|file> [--siti host1,host2]")
siti = a[a.index("--siti") + 1].split(",") if "--siti" in a else []
if os.path.isdir(p): p = os.path.join(p, "transcript.jsonl")
ALLOWED = {"WebSearch", "WebFetch"}
C = "mcp__claude-in-chrome__"
if siti: ALLOWED |= {C + t for t in "tabs_context_mcp tabs_create_mcp tabs_close_mcp navigate computer read_page get_page_text find form_input resize_window".split()}
IGNORED = {"ToolSearch", "SubagentHandback"}
ids, blocked, used, navs, queries, fetches, init_tools, model, res, intrusi = {}, [], [], [], [], [], [], None, {}, []
for line in open(p):
    try: e = json.loads(line)
    except Exception: continue
    if e.get("type") == "system" and e.get("subtype") == "init":
        init_tools = e.get("tools", []); model = e.get("model")
    elif e.get("type") == "assistant":
        for b in e.get("message", {}).get("content", []):
            if b.get("type") == "tool_use":
                n = b["name"]; ids[b["id"]] = n; used.append(n); i = b.get("input", {})
                if n == "WebSearch": queries.append(i.get("query"))
                if n == "WebFetch": fetches.append(i.get("url"))
                if n == C + "navigate": navs.append(i.get("url", ""))
    elif e.get("type") == "user" and isinstance(e.get("message", {}).get("content"), list):
        for b in e["message"]["content"]:  # strumento vietato chiamato ma rifiutato: non ha visto niente
            if b.get("type") == "tool_result" and "No such tool available" in str(b.get("content")):
                n = ids.get(b.get("tool_use_id")); used.remove(n); blocked.append(n)
    elif e.get("type") == "result":
        if (e.get("origin") or {}).get("kind") == "peer": intrusi.append((e["origin"].get("name"), e["origin"].get("body", "")[:80]))
        if not res: res = e  # il primo turno è quello del tester
    if "cross-session-message" in line or '"kind": "peer"' in line or '"kind":"peer"' in line:
        if not intrusi: intrusi.append(("?", "messaggio fra sessioni nel transcript"))
bad_used = sorted({u for u in used if u not in ALLOWED | IGNORED})
extra_avail = sorted({t for t in init_tools if t not in ALLOWED | IGNORED})
u = res.get("usage", {}) or {}
tok_in = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
print(f"modello: {model}")
print(f"strumenti disponibili all'avvio: {init_tools}")
print(f"ricerche web: {len(queries)}  fetch: {len(fetches)}  turni: {res.get('num_turns')}")
for q in queries: print("  Q:", q)
for f in fetches: print("  F:", f)
for n in navs: print("  N:", n)
host = lambda u: urlparse(u if "://" in u else "https://" + u).hostname or u
fuori = [n for n in navs if n not in ("back", "forward") and host(n) not in siti]
print(f"token ingresso (incl. cache): {tok_in}  uscita: {u.get('output_tokens')}  costo listino: ${res.get('total_cost_usd')}")
if siti and fuori: print("SOSPETTO: Chrome fuori dai siti ammessi:", fuori)
if siti and not navs: print("ATTENZIONE: prova con Chrome ma nessuna pagina aperta")
ok = not bad_used and not extra_avail and not (siti and fuori) and not intrusi
if intrusi: print("SOSPETTO: messaggio di un'altra sessione entrato nel tester:", intrusi)
interrotto = os.path.join(os.path.dirname(p), "INTERROTTO")
if os.path.exists(interrotto): print("ATTENZIONE: giro INTERROTTO dal tetto di run_blind.sh ->", open(interrotto).read().strip(), "-> risposta incompleta")
elif res.get("is_error", False) or not res: print("ATTENZIONE: giro troncato o senza esito (", res.get("subtype"), ") -> risposta incompleta, non vale come giudizio pieno")
if not queries and not navs: print("ATTENZIONE: zero ricerche -> test da considerare NON valido (punto 2 della checklist)")
if blocked: print("tentativi rifiutati (nessun dato ricevuto):", sorted(set(blocked)))
if bad_used: print("SOSPETTO: strumenti usati non ammessi:", bad_used)
if extra_avail: print("SOSPETTO: strumenti disponibili oltre ai web:", extra_avail)
print("ESITO:", "CIECO" if ok else "SOSPETTO")
sys.exit(0 if ok else 1)
