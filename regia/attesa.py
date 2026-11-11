"""Messaggi trattenuti mentre il SUP si riavvia (il messaggio non parte finché il SUP non è ripartito).

Con pausa.json presente il server scrive la richiesta in attesa.jsonl invece che in coda.jsonl: il SUP vecchio
(che sta per fare /clear) non la vede e non la perde. rilascia() la sposta in coda.jsonl con lo stesso id quando
la pausa è finita: la chiamano `sup.py riprendi`, `sup.py nuove` e il server a ogni invio (rete di sicurezza se
la pausa viene tolta in un altro modo). L'app le mostra con stato «aspetta il SUP».
"""
import json, os, threading

_lock = threading.Lock()


def file_pausa(cartella):
    return os.path.join(cartella, "pausa.json")


def file_attesa(cartella):
    return os.path.join(cartella, "attesa.jsonl")


def in_pausa(cartella):
    return os.path.exists(file_pausa(cartella))


def _righe(p):
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            for l in f:
                try:
                    out.append(json.loads(l))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def trattenute(cartella):
    return _righe(file_attesa(cartella))


def trattieni(cartella, riga):
    with _lock, open(file_attesa(cartella), "a", encoding="utf-8") as f:
        f.write(json.dumps(riga, ensure_ascii=False) + "\n")


def rilascia(cartella):
    """Pausa finita: le trattenute passano in coda.jsonl (stesso id, nell'ordine). Restituisce quante."""
    if in_pausa(cartella):
        return 0
    p = file_attesa(cartella)
    with _lock:
        righe = _righe(p)
        if not righe:
            return 0
        gia = {r.get("id") for r in _righe(os.path.join(cartella, "coda.jsonl"))}
        with open(os.path.join(cartella, "coda.jsonl"), "a", encoding="utf-8") as f:
            for r in righe:
                if r.get("modifica") or r.get("id") not in gia:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(p, p + ".rilasciate")  # copia dell'ultimo rilascio, per controllo
    return len(righe)
