#!/usr/bin/env python3
"""Controlla un transcript stream-json di un tester cieco.
Uso: check_blind.py <cartella-output | transcript.jsonl>
Esito CIECO se: solo WebSearch/WebFetch usati, nessuno strumento disponibile oltre a quelli (a parte ToolSearch/consegna),
nessun connettore mcp__. Riporta ricerche, fetch, token, costo. Exit 0 = cieco, 1 = sospetto."""
import json, sys, os
p = sys.argv[1] if len(sys.argv) > 1 else sys.exit("uso: check_blind.py <cartella|file>")
if os.path.isdir(p): p = os.path.join(p, "transcript.jsonl")
ALLOWED = {"WebSearch", "WebFetch"}
IGNORED = {"ToolSearch", "SubagentHandback"}
used, queries, fetches, init_tools, model, res = [], [], [], [], None, {}
for line in open(p):
    try: e = json.loads(line)
    except Exception: continue
    if e.get("type") == "system" and e.get("subtype") == "init":
        init_tools = e.get("tools", []); model = e.get("model")
    elif e.get("type") == "assistant":
        for b in e.get("message", {}).get("content", []):
            if b.get("type") == "tool_use":
                n = b["name"]; used.append(n); i = b.get("input", {})
                if n == "WebSearch": queries.append(i.get("query"))
                if n == "WebFetch": fetches.append(i.get("url"))
    elif e.get("type") == "result":
        res = e
bad_used = sorted({u for u in used if u not in ALLOWED | IGNORED})
extra_avail = sorted({t for t in init_tools if t not in ALLOWED | IGNORED})
u = res.get("usage", {}) or {}
tok_in = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
print(f"modello: {model}")
print(f"strumenti disponibili all'avvio: {init_tools}")
print(f"ricerche web: {len(queries)}  fetch: {len(fetches)}  turni: {res.get('num_turns')}")
for q in queries: print("  Q:", q)
for f in fetches: print("  F:", f)
print(f"token ingresso (incl. cache): {tok_in}  uscita: {u.get('output_tokens')}  costo listino: ${res.get('total_cost_usd')}")
ok = not bad_used and not extra_avail and not res.get("is_error", False)
if not queries: print("ATTENZIONE: zero ricerche -> test da considerare NON valido (punto 2 della checklist)")
if bad_used: print("SOSPETTO: strumenti usati non ammessi:", bad_used)
if extra_avail: print("SOSPETTO: strumenti disponibili oltre ai web:", extra_avail)
print("ESITO:", "CIECO" if ok else "SOSPETTO")
sys.exit(0 if ok else 1)
