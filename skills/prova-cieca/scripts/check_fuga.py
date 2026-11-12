#!/usr/bin/env python3
"""Controllo di fuga di contesto: un messaggio del master può arrivare al tester?
Uso: check_fuga.py <messaggio.txt | -> [--vietate parole.txt] [--json]
parole.txt: una parola o frase per riga (# = commento). Confronto senza maiuscole né accenti, a parola intera.
Alle parole del progetto si aggiungono sempre quelle che rompono la scena (SEMPRE, sotto).
Exit 0 = pulito, 1 = fuga (stampa le parole trovate), 2 = errore d'uso."""
import json, re, sys, unicodedata

# Parole che svelano la prova al tester, qualunque sia il progetto.
SEMPRE = ["simulazione", "simulata", "simulato", "prova cieca", "prove cieche", "tester", "master",
          "note private", "resoconto", "giocatore", "intelligenza artificiale", "modello linguistico",
          "prompt"]


def norma(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace("’", "'")


def carica(percorso):
    if not percorso:
        return []
    righe = [r.split("#", 1)[0].strip() for r in open(percorso, encoding="utf-8")]
    return [r for r in righe if r]


def trova(testo, parole):
    t = norma(testo)
    usate = []
    for p in parole:
        q = norma(p)
        if q and re.search(r"(?<!\w)" + re.escape(q) + r"(?!\w)", t):
            usate.append(p)
    return usate


def segnaposto(testo):
    """[numero di Luca], [nome]…: rompono la scena. Esclusi i link markdown [testo](url)."""
    return ["segnaposto " + m.group(0) for m in re.finditer(r"\[[^\]\n]{1,60}\](?!\()", testo)]


def main(a):
    if not a:
        print(__doc__); return 2
    testo = sys.stdin.read() if a[0] == "-" else open(a[0], encoding="utf-8").read()
    vietate = carica(a[a.index("--vietate") + 1]) if "--vietate" in a else []
    usate = trova(testo, SEMPRE + vietate) + segnaposto(testo)
    if "--json" in a:
        print(json.dumps({"fuga": bool(usate), "parole": usate}, ensure_ascii=False))
    else:
        print("FUGA: " + ", ".join(usate) if usate else "PULITO")
    return 1 if usate else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
