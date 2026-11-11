#!/usr/bin/env python3
"""Plancia T1 — istantanea dello stato di sessioni e agenti, in JSON. SOLA LETTURA.

Fonti: `claude agents --json` (vive, busy/idle), trascrizioni ~/.claude/projects/*/<id>.jsonl (contesto K,
ultima scrittura, ultimo testo, attesa permesso), SESSIONI.md (§ Aperte), agende/<NOME>.md
(§ 3 prossimi passi, § 10 cronologia), passaggi.py elenco, ~/.claude/consumo/limiti.csv, file della plancia
(insospeso.json, richieste.json, risposte.jsonl: scritti da server.py e sup.py).
Unica scrittura: le pause delle sessioni che scadono (pausa_sessioni.aggiorna → sessioni-pausa.json, riga nel filo).

Uso: python3 regia/raccogli.py  → JSON su stdout.  Da codice: `from raccogli import raccogli`.
"""
import datetime, glob, json, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attesa import trattenute  # noqa: E402
from modifiche import unisci  # noqa: E402
import pausa_sessioni  # noqa: E402

QUI = os.path.dirname(os.path.abspath(__file__))
HUB = os.environ.get("PLANCIA_HUB", os.path.dirname(QUI))  # cartella con SESSIONI.md e agende/
DATI = os.environ.get("PLANCIA_DATI", QUI)  # cartella dei file dati (coda, richieste, risposte…): diversa solo nei test
CASA = os.path.expanduser("~")
PASSAGGI = os.environ.get("PLANCIA_PASSAGGI", os.path.join(os.path.dirname(QUI), "tools", "passaggi.py"))
LIMITI = os.environ.get("PLANCIA_LIMITI", os.path.join(CASA, ".claude/consumo/limiti.csv"))
# Soglie cumulative elastiche della settimana (piano elastico: più margine a inizio settimana): weekday() -> % 7d.
# Stessa tabella e stessa regola di ~/.claude/statusline-consumo.py (SOGLIE_7D, soglia_oggi): se cambiano, cambiare tutte e due.
SOGLIE_7D = {4: 8, 5: 35, 6: 63, 0: 71, 1: 79, 2: 92, 3: 100}
ATTESA_MIN = 2  # busy + ultima voce = chiamata a strumento senza risposta da più di N min → probabile permesso


def _leggi(p, default=""):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


def _json(p, default):
    try:
        return json.loads(_leggi(p)) if os.path.exists(p) else default
    except ValueError:
        return default


def _jsonl(p):
    righe = []
    for l in _leggi(p).splitlines():
        try:
            righe.append(json.loads(l))
        except ValueError:
            pass
    return righe


def vive():
    try:
        out = subprocess.run(["claude", "agents", "--json"], capture_output=True, text=True, timeout=30).stdout
        return [a for a in json.loads(out) if a.get("kind") == "interactive"
                and not (a.get("name") or "").upper().startswith("CIECO")], None
    except Exception as e:  # noqa: BLE001 — la plancia mostra l'errore invece di cadere
        return [], f"claude agents --json non leggibile: {e}"


def trascrizione(session_id):
    """Dalla coda della trascrizione: minuti dall'ultima scrittura, contesto K, ultimo testo dell'agente,
    True se l'ultima voce è una chiamata a strumento ancora senza risultato."""
    file = glob.glob(os.path.join(CASA, f".claude/projects/*/{session_id}.jsonl"))
    if not file:
        return {}
    f = file[0]
    # ultima attività vera = ultima voce assistente/utente; la data del file cambia anche per voci di servizio
    # (es. un messaggio del SUP a tutti «ringiovaniva» sessioni ferme da ore)
    ultima = os.path.getmtime(f)
    visto = None
    k, testo, tool_aperto = None, "", False
    with open(f, "rb") as h:
        h.seek(max(0, os.path.getsize(f) - 400_000))
        for l in h.read().decode("utf-8", "ignore").splitlines():
            try:
                d = json.loads(l)
            except ValueError:
                continue
            m = d.get("message")
            if not isinstance(m, dict):
                continue
            if d.get("type") in ("assistant", "user") and d.get("timestamp"):
                visto = d["timestamp"]
            u = m.get("usage")
            if u:
                tot = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                       + u.get("cache_creation_input_tokens", 0))
                if tot > 0:  # usage tutta a zero in coda alla trascrizione non azzera il contesto
                    k = tot // 1000
            c = m.get("content")
            if not isinstance(c, list):
                continue
            tipi = {b.get("type") for b in c if isinstance(b, dict)}
            if d.get("type") == "assistant":
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip():
                        testo = b["text"].strip()
                if "tool_use" in tipi:
                    tool_aperto = True
                elif tipi & {"text"}:
                    tool_aperto = False
            elif d.get("type") == "user" and "tool_result" in tipi:
                tool_aperto = False
    if visto:
        try:
            ultima = datetime.datetime.fromisoformat(visto.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    minuti = max(0, int((time.time() - ultima) // 60))
    livello = None if k is None else "riavvio" if k >= 200 else "passaggio" if k >= 150 else "ok"
    return {"minuti": minuti, "ultima": int(ultima), "contesto_k": k, "livello": livello, "ultimo_testo": testo[:600],
            "tool_aperto": tool_aperto}


def registro():
    """{NOME: compito} dalla tabella «Aperte» di SESSIONI.md.

    Le voci in sospeso NON si leggono da SESSIONI.md § In sospeso (blocchi per sessione vecchi e mai
    ripuliti). Fonte unica: insospeso.json,
    mostrato una volta sola nel riquadro in testata."""
    testo = _leggi(os.path.join(HUB, "SESSIONI.md"))
    compiti = {}
    aperte = testo.split("## Aperte", 1)[-1].split("\n## ", 1)[0]
    for riga in aperte.splitlines():
        celle = [c.strip() for c in riga.strip().strip("|").split("|")]
        if len(celle) >= 4 and celle[0] and celle[0] != "nome" and not set(celle[0]) <= set("-"):
            compiti[celle[0].upper()] = {"testo": celle[3], "data": celle[5] if len(celle) > 5 else ""}
    return compiti


def agenda(nome):
    testo = _leggi(os.path.join(HUB, "agende", f"{nome}.md"))
    if not testo:
        return None

    def sezione(n):
        m = re.search(rf"^## {n}\..*?$(.*?)(?=^## \d+\.|\Z)", testo, re.M | re.S)
        return [r.strip() for r in m.group(1).splitlines() if r.strip().startswith("- ")] if m else []
    breve = re.search(r"^In breve:\s*(.+)$", testo[:3000], re.M)  # riga scritta apposta: vince su tutto
    return {"breve": breve.group(1).strip() if breve else None, "scopo": sezione(1)[:1],
            "prossimi": sezione(3)[:8], "cronologia": sezione(10)[:4]}


def _frase(t, lung=170):
    """Una frase in parole semplici: via etichette [AG]/[SUP], grassetti, apici; tagliata alla prima frase."""
    t = re.sub(r"^-\s*", "", t or "")
    t = re.sub(r"\[(AG|SUP|MET|UT|[A-Z]{2,4})\]\s*", "", t)
    t = re.sub(r"^(Scopo|Obiettivo)\s*:\s*", "", t.replace("**", "").replace("`", ""), flags=re.I).strip()
    t = re.sub(r"^[\d/-]+(\s+~?[\d:x]+)?\s*(notte|mattina|sera)?\s*[,:·]?\s*(utente( al SUP)?\s*:?\s*)?", "", t).strip(" ·:")
    m = re.search(r"(?<=.{30})(\. |; | → )", t)
    if m:
        t = t[:m.start()]
    return t if len(t) <= lung else t[:lung - 1].rsplit(" ", 1)[0] + "…"


COMPITI = os.path.join(os.environ.get("SB_CONSUMO_DIR") or os.path.join(CASA, ".claude", "consumo"), "compiti")


def adesso(sid):
    """Il lavoro ATTUALE della sessione: la frase che l'agente riscrive a ogni cambio di compito
    (compiti/<sid>.adesso.txt, chiesta dall'hook dell'etichetta); se manca, l'etichetta della barra (2-4 parole)."""
    for nome, fonte in ((f"{sid}.adesso.txt", "frase"), (f"{sid}.txt", "etichetta")):
        p = os.path.join(COMPITI, nome)
        try:
            testo = " ".join(open(p, encoding="utf-8").read().split())[:200]
            if testo:
                return {"testo": testo, "fonte": fonte, "minuti": int((time.time() - os.path.getmtime(p)) // 60)}
        except OSError:
            continue
    return None


def contesto(ag, reg):
    """Le 2 righe fisse del dettaglio.
    Fonte: agenda (§ 1 scopo, § 10 ultima voce), che è aggiornata; il registro SESSIONI.md solo se manca
    l'agenda, e segnato «vecchia» se ha più di 24 h."""
    occupa, punto, ora, vecchia = None, None, None, False
    if ag:
        if ag.get("breve"):
            occupa = _frase(ag["breve"], 200)
        else:
            voce = (ag.get("scopo") or ag.get("prossimi") or [None])[0]
            occupa = _frase(voce) if voce else None
            if occupa and occupa.startswith("«"):  # § 1 è una citazione dell'utente, non un riassunto
                occupa = None
        if ag.get("cronologia"):
            c = ag["cronologia"][0]
            m = re.match(r"-\s*(\d{4})-(\d\d)-(\d\d)\s+~?([\dx:]+)?\s*(.*)$", c)
            if m:
                ora = f"{m.group(3)}/{m.group(2)} {m.group(4) or ''}".strip()
                punto = _frase(m.group(5), 200)
            else:
                punto = _frase(c, 200)
    if not occupa and reg:
        occupa = _frase(reg.get("testo"))
        try:
            vecchia = (time.time() - time.mktime(time.strptime(reg.get("data", "")[:10], "%Y-%m-%d"))) > 86400 * 2
        except ValueError:
            vecchia = False
    if not occupa and ag and ag.get("prossimi"):
        occupa = _frase(re.sub(r"^-?\s*[A-Z][A-Z-]+ · ", "", ag["prossimi"][0]))
    return {"occupa": occupa, "punto": punto, "ora": ora, "fonte": "agenda" if ag else ("registro" if reg else None),
            "vecchia": vecchia}


def passaggi():
    """{NOME: {'quando':..., 'ore':..., 'nota':...}} delle note da leggere."""
    try:
        out = subprocess.run([sys.executable, PASSAGGI, "elenco"], capture_output=True, text=True, timeout=20).stdout
    except Exception:  # noqa: BLE001
        return {}
    note = {}
    for riga in out.splitlines():
        m = re.match(r"(\S+)\s+nome: .*?(\d\d/\d\d \d\d:\d\d)\s+(\d+) h(.*)$", riga)
        if m:
            note[m.group(1).upper()] = {"quando": m.group(2), "ore": int(m.group(3)), "nota": m.group(4).strip()}
    return note


def comandi_in_corso():
    """{pid sessione: età in secondi del comando Bash più giovane}. Claude Code lancia ogni comando come figlio
    «/bin/zsh -c source ~/.claude/shell-snapshots/…»; un permesso in attesa non ha ancora lanciato niente.
    I comandi in background (Monitor, server) sono figli anche loro, ma più vecchi della chiamata aperta: li esclude
    il confronto con l'età della chiamata (vedi sotto)."""
    try:
        out = subprocess.run(["ps", "-A", "-o", "ppid=,etime=,command="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    eta = {}
    for riga in out.splitlines():
        parti = riga.strip().split(None, 2)
        if len(parti) == 3 and parti[0].isdigit() and "/.claude/shell-snapshots/" in parti[2]:
            g, _, hms = parti[1].rpartition("-")
            s = 0
            for x in hms.split(":"):
                s = s * 60 + int(x or 0)
            s += int(g or 0) * 86400
            p = int(parti[0])
            eta[p] = min(s, eta.get(p, s))
    return eta


def consumo():
    """Consumo per la testata. Più sessioni scrivono limiti.csv nello stesso secondo e alcune riportano letture vecchie
   : l'ultima riga non basta. Dentro una finestra (stessa ora di
    ripristino) il consumo non scende → massimo delle ultime righe di quella finestra; 5 ore scaduta → nessun valore."""
    def n(x):
        try:
            return int(x)
        except ValueError:
            return None
    righe = [r.split(",") for r in _leggi(LIMITI).strip().splitlines()[1:][-300:]]
    righe = [r + [""] * (5 - len(r)) for r in righe if len(r) >= 3]
    ult = next((r for r in reversed(righe) if r[2]), None)
    if not ult:
        return None
    r7 = next((n(r[4]) for r in reversed(righe) if n(r[4])), None)
    p7 = max((n(r[2]) for r in righe if n(r[2]) is not None and (r7 is None or n(r[4]) == r7)), default=n(ult[2]))
    r5 = next((n(r[3]) for r in reversed(righe) if n(r[3])), None)
    p5 = None
    if r5 and r5 > time.time():
        p5 = max((n(r[1]) for r in righe if n(r[1]) is not None and n(r[3]) == r5), default=None)
    return {"ora": ult[0], "sessione_5h": p5, "settimana_7d": p7, "ripristino_5h": r5 if p5 is not None else None,
            "ripristino_7d": r7, "soglia_7d": soglia_oggi(r7)}


def soglia_oggi(r7, ora=None):
    """Soglia cumulativa 7d di oggi; il giorno d'inizio settimana (reset) usa già la soglia del giorno dopo."""
    ora = time.time() if ora is None else ora
    oggi = datetime.datetime.fromtimestamp(ora)
    if r7:
        inizio = datetime.datetime.fromtimestamp(r7 - 7 * 86400)
        if inizio.date() == oggi.date() and ora >= inizio.timestamp():
            return SOGLIE_7D[(inizio.weekday() + 1) % 7]
    return SOGLIE_7D[oggi.weekday()]



def taglia_sup(rich, n=30):
    """Richieste al SUP per la lista sotto la casella: tutte le aperte (né risposta né consegnata) + le ultime n
   ."""
    fatta = lambda q: q.get("stato") == "grigio" or any(x.get("stato") == "risposta" for x in q.get("storia") or [])
    ultime = rich[-n:]
    return [q for q in rich[:-n] if not fatta(q)] + ultime if len(rich) > n else rich

def raccogli():
    agenti, errore = vive()
    compiti = registro()
    note = passaggi()
    richieste = _json(os.path.join(DATI, "richieste.json"), {})
    risposte = _jsonl(os.path.join(DATI, "risposte.jsonl"))
    coda = unisci(_jsonl(os.path.join(DATI, "coda.jsonl")) + [dict(r, attesa=True) for r in trattenute(DATI)])  # riavvio; modifiche

    def con_stato(r):  # in coda e non ancora presa dal SUP: «nuova»; l'ora dello stato non copre quella della richiesta
        s = richieste.get(r["id"], {})
        return dict(r, stato="attesa" if r.get("attesa") else s.get("stato", "nuova"), nota=s.get("nota", ""), ora_stato=s.get("ora"),
                    storia=s.get("storia", []), a=s.get("a"), mod_vista=s.get("mod_vista"))
    sessioni = []
    lunghi = comandi_in_corso()
    # sessioni in pausa: escono da sole se l'utente scrive loro o tornano a lavorare; l'uscita va nel filo
    stati = {}
    for a in agenti:
        n = (a.get("name") or "").upper()
        if n:
            stati[n] = "busy" if a.get("status") == "busy" or stati.get(n) == "busy" else a.get("status")
    prima = len(pausa_sessioni.leggi(DATI))
    pause = pausa_sessioni.aggiorna(DATI, stati, coda) if not errore else pausa_sessioni.leggi(DATI)
    if len(pause) < prima:  # qualcuna è uscita: la riga nuova del filo deve esserci già in questa istantanea
        risposte = _jsonl(os.path.join(DATI, "risposte.jsonl"))
    for a in agenti:
        nome = (a.get("name") or "?").upper()
        t = trascrizione(a.get("sessionId", ""))
        stato = "al lavoro" if a.get("status") == "busy" else "ferma"
        if stato == "al lavoro" and t.get("tool_aperto") and (t.get("minuti") or 0) >= ATTESA_MIN:
            # comando Bash ancora in esecuzione (figlio zsh della sessione) = lavora, non aspetta un permesso
            #
            e = lunghi.get(a.get("pid"))
            stato = "al lavoro" if e is not None and e <= (t.get("minuti") or 0) * 60 + 90 else "in attesa"
        p = pause.get(nome)
        if p:  # vince su ferma e in attesa: niente banner permesso, niente avvisi, sempre in fondo
            stato = "in pausa"
        sessioni.append({
            "nome": nome, "session_id": a.get("sessionId"), "pid": a.get("pid"), "cwd": a.get("cwd"),
            "avviata": a.get("startedAt"), "stato": stato, **t,
            "pausa": {"ora": p.get("ora"), "motivo": p.get("motivo", "")} if p else None,
            "compito": (compiti.get(nome) or {}).get("testo"), "agenda": (ag := agenda(nome)),
            "contesto": contesto(ag, compiti.get(nome)), "adesso": adesso(a.get("sessionId", "")) if a.get("sessionId") else None,
            "passaggio": note.get(nome),
            "richieste": [con_stato(r) for r in coda if r.get("sessione", "").upper() == nome][-6:],
            "risposte": [r for r in risposte if r.get("sessione", "").upper() == nome][-10:],
        })
    vivi = {s["nome"] for s in sessioni}
    return {
        "ora": int(time.time()),
        "errore": errore,
        "consumo": consumo(),
        "insospeso": _json(os.path.join(DATI, "insospeso.json"), None),
        "pausa": _json(os.path.join(DATI, "pausa.json"), None),
        "ascolto": _json(os.path.join(DATI, "sup-ascolto.json"), None),
        "sup": {
            "richieste": taglia_sup([con_stato(r) for r in coda if r.get("sessione", "").upper() == "SUP"]),
            "risposte": [r for r in risposte if r.get("sessione", "").upper() == "SUP"][-20:],
            "aspetta_permesso": _json(os.path.join(DATI, "permesso.json"), None),
        },
        "sessioni": sessioni,
        "registro_non_vive": sorted(n for n in compiti if n not in vivi),
        "passaggi_da_leggere": note,
    }


if __name__ == "__main__":
    json.dump(raccogli(), sys.stdout, ensure_ascii=False, indent=1)
    print()


FILE_MESSAGGI = ("coda.jsonl", "richieste.json", "risposte.jsonl", "sup-ascolto.json", "attesa.jsonl", "pausa.json", "sessioni-pausa.json")


def firma_messaggi():
    """ETag di /api/messaggi: dimensione e data dei soli file dei messaggi (nessuna lettura)."""
    parti = []
    for n in FILE_MESSAGGI:
        try:
            st = os.stat(os.path.join(DATI, n))
            parti.append(f"{st.st_size}-{st.st_mtime_ns}")
        except OSError:
            parti.append("0")
    return '"' + ".".join(parti) + '"'


def messaggi():
    """Solo i messaggi (richieste con stato, risposte, battito del SUP): leggero, per il giro di 2 s."""
    richieste = _json(os.path.join(DATI, "richieste.json"), {})
    risposte = _jsonl(os.path.join(DATI, "risposte.jsonl"))
    coda = unisci(_jsonl(os.path.join(DATI, "coda.jsonl")) + [dict(r, attesa=True) for r in trattenute(DATI)])  # riavvio; modifiche

    def con_stato(r):
        s = richieste.get(r["id"], {})
        return dict(r, stato="attesa" if r.get("attesa") else s.get("stato", "nuova"), nota=s.get("nota", ""), ora_stato=s.get("ora"),
                    storia=s.get("storia", []), a=s.get("a"), mod_vista=s.get("mod_vista"))
    per = {}
    for r in coda:
        per.setdefault(r.get("sessione", "").upper(), {"richieste": [], "risposte": []})["richieste"].append(con_stato(r))
    for r in risposte:
        per.setdefault(r.get("sessione", "").upper(), {"richieste": [], "risposte": []})["risposte"].append(r)
    for nome, v in per.items():
        v["richieste"] = taglia_sup(v["richieste"]) if nome == "SUP" else v["richieste"][-6:]
        v["risposte"] = v["risposte"][-(20 if nome == "SUP" else 10):]
    return {"per": per, "ascolto": _json(os.path.join(DATI, "sup-ascolto.json"), None),
            "pausa": _json(os.path.join(DATI, "pausa.json"), None)}
