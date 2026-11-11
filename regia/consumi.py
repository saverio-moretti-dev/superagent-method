#!/usr/bin/env python3
"""Plancia — scheda Token.

Non rifà il Token Manager: importa IN SOLA LETTURA i calcoli di dont-waste-your-token (ctm.limits, ctm.usage)
e li impacchetta per /api/token. Fonti: ~/.claude/consumo/limiti.csv (5 h, 7 g) e le trascrizioni
~/.claude/projects/**/*.jsonl (solo i numeri `usage`, mai il testo). Unico file scritto: la cache di ctm
in DATI/.cache-token.json (in .gitignore).

  python3 regia/consumi.py      → stampa il JSON (prova a mano)
Variabili per i test: PLANCIA_CTM (cartella di dont-waste-your-token), PLANCIA_LIMITI (csv),
PLANCIA_TRASCRIZIONI (cartella delle trascrizioni), PLANCIA_DATI (cache).
"""
import json, os, sys, time
from datetime import datetime

CASA = os.path.expanduser("~")
CTM = os.environ.get("PLANCIA_CTM", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "dont-waste-your-token"))  # predefinito: cartella accanto a questa repo
LIMITI = os.environ.get("PLANCIA_LIMITI", os.path.join(CASA, ".claude/consumo/limiti.csv"))
TRASCRIZIONI = os.environ.get("PLANCIA_TRASCRIZIONI", os.path.join(CASA, ".claude/projects"))
DATI = os.environ.get("PLANCIA_DATI", os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(DATI, ".cache-token.json")
SOGLIA_GIORNO = 14  # % della settimana al giorno: tetto consigliato (~1/7 della settimana)


def _ctm():
    if CTM not in sys.path:
        sys.path.insert(0, CTM)
    from ctm import limits, usage  # noqa: E402  (sola lettura: nessuna funzione che scrive nella sua repo)
    return limits, usage


def _progetto(cartella):
    """«-Users-x-Desktop-progetti-superagent-method» → «progetti-superagent-method»."""
    n = cartella
    pref = "-" + CASA.strip("/").replace("/", "-").replace(" ", "-") + "-"
    if n + "-" == pref:
        return "~ (cartella home)"
    if n.startswith(pref):
        n = n[len(pref):]
    for p in ("Desktop-", "Documents-"):
        if n.startswith(p):
            n = n[len(p):]
    return n or "~"


def _diradare(punti, passo):
    """Un punto ogni `passo` secondi (l'ultimo sempre): il csv ha una lettura al minuto."""
    out, ultimo = [], None
    for p in punti:
        if ultimo is None or p[0] - ultimo >= passo:
            out.append(p); ultimo = p[0]
    if punti and out[-1] is not punti[-1]:
        out.append(punti[-1])
    return out


def senza_letture_vecchie(rows):
    """Più sessioni scrivono limiti.csv insieme e alcune riportano letture vecchie (es. 21:15:30: 73/54 e 79/55):
    dentro una stessa finestra (stessa ora di ripristino) il consumo non può scendere → massimo progressivo.
    Il cambio di finestra (ripristino diverso di oltre 1 h, o assente) riparte da capo."""
    out, mx = [], {"p5": (None, None), "p7": (None, None)}
    for r in rows:
        r = dict(r)
        for p, rk in (("p5", "r5"), ("p7", "r7")):
            if r[p] is None:
                continue
            fin, val = mx[p]
            if r[rk] and fin and abs(r[rk] - fin) < 3600 and val is not None and r[p] < val:
                r[p] = val
            elif r[rk]:
                mx[p] = (r[rk], r[p]) if not (fin and abs(r[rk] - fin) < 3600) else (fin, max(val or 0, r[p]))
        out.append(r)
    return out


def settimana(rows, now):
    """Consumo di oggi, ritmo ideale, margine al giorno, serie della finestra settimanale."""
    ult = next((r for r in reversed(rows) if r["p7"] is not None and r["r7"]), None)
    if not ult or ult["r7"] < now:
        return None
    inizio = ult["r7"] - 168 * 3600
    mezzanotte = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    base_t = max(mezzanotte, inizio)
    prima = next((r for r in reversed(rows) if r["t"] <= base_t and r["p7"] is not None), None)
    base = prima["p7"] if prima and (not prima["r7"] or abs(prima["r7"] - ult["r7"]) < 3600) else 0
    trascorsa = min(1.0, max(0.0, (now - inizio) / (168 * 3600)))
    giorni_rimasti = max(0.0, (ult["r7"] - now) / 86400)
    serie = [(r["t"], r["p7"]) for r in rows if r["t"] >= inizio and r["p7"] is not None]
    return {
        "oggi_pct": max(0, ult["p7"] - base),
        "ideale_pct": round(trascorsa * 100, 1),  # dove saresti a ritmo costante
        "giorni_rimasti": round(giorni_rimasti, 1),
        "margine_giorno": round((100 - ult["p7"]) / giorni_rimasti, 1) if giorni_rimasti >= 0.5 else None,
        "inizio": inizio,
        "serie": _diradare(serie, 3600),
    }


def raccogli_token(sessioni=None, now=None):
    """sessioni: [{nome, session_id}] delle sessioni vive (da raccogli), per i token per agente."""
    now = time.time() if now is None else now
    try:
        limits, usage = _ctm()
    except Exception as e:  # repo assente o cambiata: la scheda lo dice, la Plancia resta in piedi
        return {"errore": f"dont-waste-your-token non importabile ({type(e).__name__}): {CTM}"}
    rows = senza_letture_vecchie(limits.parse_csv(LIMITI))
    som = limits.summary(rows, now=now)
    out = {"letture": len(rows), "ultima": som["last"] and som["last"]["time"], "soglia_giorno": SOGLIA_GIORNO,
           "cinque": som["five_hour"], "sette": som["seven_day"], "settimana": settimana(rows, now),
           "serie48": _diradare([(r["t"], r["p5"], r["p7"]) for r in limits.series(rows, 48, now)], 900)}

    # token dalle trascrizioni (solo questo Mac: cloud e altri PC non ci sono)
    dati = usage.load(TRASCRIZIONI, CACHE, now=now)
    giorni, progetti, per_sessione = {}, {}, {}
    sette_fa = now - 7 * 86400
    for path, ent in dati.items():
        rel = os.path.relpath(path, TRASCRIZIONI).split(os.sep)
        prog = _progetto(rel[0]) if rel else "?"
        for h, vals in ent.get("hours", {}).items():
            if int(h) < sette_fa:
                continue
            g = datetime.fromtimestamp(int(h)).strftime("%Y-%m-%d")
            w = usage.weigh(vals)
            giorni[g] = giorni.get(g, 0) + w
            progetti[prog] = progetti.get(prog, 0) + w
        for sid, vals in ent.get("sessions", {}).items():
            per_sessione[sid] = per_sessione.get(sid, 0) + usage.weigh(vals)
    out["giorni"] = [{"giorno": g, "pesati": round(v)} for g, v in sorted(giorni.items())]
    out["progetti"] = [{"nome": k, "pesati": round(v)} for k, v in sorted(progetti.items(), key=lambda x: -x[1])[:10]]
    out["agenti"] = sorted(({"nome": s["nome"], "pesati": round(per_sessione.get(s.get("session_id") or "", 0))}
                            for s in (sessioni or []) if s.get("session_id")), key=lambda x: -x["pesati"])
    out["agenti"] = [a for a in out["agenti"] if a["pesati"] > 0]
    out["per_pct"] = usage.tokens_per_pct(rows, dati, now=now)
    out["pesi"] = "token pesati come i prezzi API: input 1, output 5, scrittura cache 1,25, lettura cache 0,1 (convenzione per confrontare, non la formula dei limiti)"
    return out


if __name__ == "__main__":
    t = time.time()
    d = raccogli_token()
    d["_secondi"] = round(time.time() - t, 2)
    for k in ("serie48",):
        d[k] = f"{len(d.get(k) or [])} punti"
    if d.get("settimana"):
        d["settimana"]["serie"] = f"{len(d['settimana']['serie'])} punti"
    print(json.dumps(d, ensure_ascii=False, indent=1, default=str))
