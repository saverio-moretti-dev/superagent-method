#!/usr/bin/env python3
"""Controlla i prompt dei tester ciechi contro le trappole già incontrate, PRIMA di spendere token.
Uso: controlla_prompt.py <prompt.txt|input.jsonl> [...]   (un .jsonl stream-json: legge le parti di testo)
     controlla_prompt.py --prova                          (autoverifica)
Esce 1 se c'è almeno un ERRORE. Gli AVVISI non bloccano. Trappole: ../references/trappole-prove-cieche.md
"""
import json, re, sys

STRANIERO = re.compile(r"\b(je bent|jullie|you are|your family|du bist|sie sind|ihr|wij|we are)\b", re.I)
SPIA = re.compile(r"\b(claude|anthropic|prova cieca|test cieco|tester cieco|esito atteso|dovresti trovare|generat[oa] (con|dall)'?\s*(ia|ai))\b", re.I)

def testo(path):
    raw = open(path, encoding="utf-8").read()
    if not path.endswith(".jsonl"):
        return raw, 0
    parti, img = [], 0
    for riga in raw.splitlines():
        try: m = json.loads(riga)
        except ValueError: continue
        for c in (m.get("message") or {}).get("content", []):
            if c.get("type") == "text": parti.append(c["text"])
            elif c.get("type") == "image": img += 1
    return "\n".join(parti), img

def controlla(t, img=0):
    err, avv = [], []
    if m := re.search(r"__[A-Z_]+__|<\.\.\.>|<[a-z][^<>\n]{2,40}>", t):
        err.append(f"segnaposto non riempito: {m.group(0)!r}")
    if not re.search(r"rispondi in italiano", t, re.I):
        err.append("manca «Rispondi in italiano»")
    elif STRANIERO.search(t[:600]) and not re.search(r"rispondi in italiano", t[:600], re.I):
        err.append("ruolo in lingua straniera: «Rispondi in italiano» va anche IN TESTA (ospiti 6/11: 3 su 6 in olandese)")
    if not re.search(r"file local[ei]", t, re.I):
        err.append("manca il divieto di leggere file locali")
    if not re.search(r"email", t, re.I):
        avv.append("manca la regola sull'email/nome dell'account da ignorare")
    if m := SPIA.search(t):
        err.append(f"il prompt svela il test o l'esito atteso: {m.group(0)!r}")
    if not re.search(r"verdetto", t, re.I):
        err.append("manca il formato di decisione fisso (Verdetto …)")
    if not re.search(r"copiat|tra virgolette", t, re.I):
        avv.append("manca la regola anti-invenzione (ogni critica = indirizzo + testo copiato)")
    if not re.search(r"errori nuovi|cose sbagliate|contraddittori", t, re.I):
        avv.append("manca la domanda separata sugli errori concreti (sbagliato/contraddittorio), distinta dalle obiezioni")
    if re.search(r"tabs_create_mcp|navigate|schermat", t, re.I) and re.search(r"chrome|browser", t, re.I):
        if not re.search(r"tabs_context_mcp", t):
            err.append("Chrome: manca tabs_context_mcp prima di aprire schede (dal 11/2026 è obbligatorio)")
        if not re.search(r"tabs_close_mcp|chiudi la scheda", t, re.I):
            avv.append("Chrome: manca «chiudi la scheda alla fine»")
        if re.search(r"resize_window", t) and not re.search(r"non usare resize_window", t, re.I):
            err.append("Chrome: resize_window non restringe sotto ~500 px; il telefono si dà con schermate 390 nel messaggio")
    if re.search(r"telefono", t, re.I) and re.search(r"schermate qui sotto|schermate telefono", t, re.I) and img == 0 and t:
        avv.append("il testo parla di schermate del telefono ma il file non contiene immagini (va bene solo se le aggiunge lo script di lancio)")
    return err, avv

def prova():
    buono = ("Sei Anna, 40 anni. Rispondi in italiano.\nMATERIALE: http://localhost:8977/\nVerdetto: SI | FORSE | NO\n"
             "Ogni critica: indirizzo + testo copiato. Cose sbagliate o contraddittorie: elencale.\n"
             "Non leggere file locali. Email dell'account: ignorala.")
    assert controlla(buono) == ([], []), controlla(buono)
    e, _ = controlla("Je bent Femke. " + buono.replace("Rispondi in italiano.", "") + "x" * 600 + "\nRispondi in italiano.")
    assert any("IN TESTA" in x for x in e), e
    e, _ = controlla(buono + " Apri __URL__")
    assert any("segnaposto" in x for x in e), e
    e, _ = controlla(buono + " Questa è una prova cieca.")
    assert any("svela" in x for x in e), e
    e, _ = controlla(buono + " Hai un browser Chrome: apri con navigate, fai schermate.")
    assert any("tabs_context_mcp" in x for x in e), e
    print("autoverifica ok")

if __name__ == "__main__":
    if sys.argv[1:] == ["--prova"]:
        prova(); sys.exit(0)
    if not sys.argv[1:]:
        print(__doc__); sys.exit(2)
    male = False
    for p in sys.argv[1:]:
        e, a = controlla(*testo(p))
        print(f"{'ERRORI' if e else 'OK'}  {p}")
        for x in e: print("  ERRORE:", x)
        for x in a: print("  avviso:", x)
        male |= bool(e)
    sys.exit(1 if male else 0)
