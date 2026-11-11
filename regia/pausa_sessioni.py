#!/usr/bin/env python3
"""Sessioni «in pausa»: «quando ti dico di mettere una sessione in pausa mettila in pausa.
viene sostanzialmente bypassata da tutto finché io o te non gli richiediamo qualcosa e rientrano negli stati attuali».

Stato in `sessioni-pausa.json` (cartella dati della plancia): {NOME: {"ora", "motivo", "vista_ferma"}}.
- La mette e la toglie il SUP: `sup.py sessione pausa NOME ["motivo"]` / `sup.py sessione via NOME`.
- Esce da sola (`aggiorna`): (a) l'utente le scrive dalla Regia (richiesta in coda con sessione=NOME, più nuova
  della pausa); (b) la sessione torna a lavorare (busy) dopo essere stata vista ferma: un SendMessage del SUP, un cron,
  una sveglia la svegliano, ed è giusto così. `sup.py rispondi --a NOME` la toglie subito.
- Quando esce da sola lo scrive nel filo della sessione (risposte.jsonl), così l'utente lo vede.
È la sola scrittura che fa raccogli.py: piccola, atomica, solo se qualcosa cambia.
"""
import json, os, time

FILE = "sessioni-pausa.json"
ORA = lambda: time.strftime("%Y-%m-%d %H:%M:%S")


def _p(dati):
    return os.path.join(dati, FILE)


def leggi(dati):
    try:
        with open(_p(dati), encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _scrivi(dati, v):
    tmp = _p(dati) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _p(dati))


def metti(dati, nome, motivo="", busy=False):
    v = leggi(dati)
    v[nome.upper()] = {"ora": ORA(), "motivo": motivo, "vista_ferma": not busy}
    _scrivi(dati, v)
    return v[nome.upper()]


def togli(dati, nome, perche=None):
    """Toglie la pausa; con `perche` scrive una riga nel filo della sessione. True se era in pausa."""
    v = leggi(dati)
    if v.pop(nome.upper(), None) is None:
        return False
    _scrivi(dati, v)
    if perche:
        with open(os.path.join(dati, "risposte.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessione": nome.upper(), "testo": f"Regia: uscita dalla pausa, {perche}.",
                                "ora": ORA(), "pausa": "uscita"}, ensure_ascii=False) + "\n")
    return True


def aggiorna(dati, stati, coda):
    """stati = {NOME: "busy"|"idle"…} delle sessioni vive; coda = richieste dell'utente (con "sessione", "ora").
    Toglie le pause scadute, segna «vista ferma». Restituisce il dizionario delle pause rimaste."""
    v = leggi(dati)
    if not v:
        return v
    cambiato, uscite = False, []
    for nome, p in list(v.items()):
        scritta = any((r.get("sessione") or "").upper() == nome and (r.get("ora") or "") > p.get("ora", "") for r in coda)
        st = stati.get(nome)
        if scritta:
            uscite.append((nome, "le hai scritto dalla Regia"))
        elif st == "busy" and p.get("vista_ferma"):
            uscite.append((nome, "ha ripreso a lavorare"))
        elif st is not None and st != "busy" and not p.get("vista_ferma"):
            p["vista_ferma"] = True  # messa in pausa mentre finiva il turno: da qui in poi «busy» = svegliata
            cambiato = True
    if cambiato:
        _scrivi(dati, v)
    for nome, perche in uscite:
        togli(dati, nome, perche)
        v.pop(nome, None)
    return v
