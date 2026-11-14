#!/usr/bin/env python3
"""Scrive <out>/risposta.txt da <out>/transcript.jsonl (stream-json di un turno del tester). Lo chiama run_blind.sh.

Di base è il testo del primo evento result. Se quel testo non ha la risposta nel formato (COSA FACCIO / DECISIONE / A CHE
CONCLUSIONE SONO ARRIVATO) ma un messaggio precedente dello stesso turno sì, si prende quel messaggio: il tester può
scrivere la risposta e poi fare un'ultima azione (prova CASA 14/11: risposta scritta, poi «Ho chiuso la scheda del
browser» come ultimo testo → risposta persa, campagna ferma al turno 1)."""
import json
import os
import re
import sys

FORMATO = re.compile(r"(?:^|\n)[ \t>#*_]*(?:COSA FACCIO|DECISIONE|A CHE CONCLUSIONE SONO ARRIVATO)[ \t*_]*(?::|(?=\n))")


def ha_formato(t):
    return bool(t and FORMATO.search(t))


def estrai(o):
    res, esito, ultimo, col_formato = None, "", "", ""
    for l in open(os.path.join(o, "transcript.jsonl"), errors="ignore"):
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if e.get("type") == "result" and res is None:  # solo il primo turno
            res, esito = e.get("result") or "", e.get("subtype", "")
        if e.get("type") == "assistant" and res is None:
            t = "".join(c.get("text", "") for c in (e.get("message") or {}).get("content", []) if c.get("type") == "text")
            if t.strip():
                ultimo = t
                if ha_formato(t):
                    col_formato = t
    if col_formato and not ha_formato(ultimo):
        ultimo = col_formato  # risposta scritta, poi un'altra azione con un testo senza formato
    if res is not None and not ha_formato(res) and col_formato:
        res = col_formato
    if os.path.exists(os.path.join(o, "INTERROTTO")):
        res = "[INTERROTTO: " + open(os.path.join(o, "INTERROTTO")).read().strip() + "]\n\n" + ultimo
    elif esito and esito != "success":
        res = "[FERMATO dalla CLI: " + esito + "]\n\n" + (res or ultimo)
    elif res is None:
        res = "[NESSUN RISULTATO: claude uscito senza evento result]\n\n" + ultimo
    with open(os.path.join(o, "risposta.txt"), "w") as f:
        f.write(res)
    return res


if __name__ == "__main__":
    estrai(sys.argv[1])
