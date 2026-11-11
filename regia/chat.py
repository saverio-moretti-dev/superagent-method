#!/usr/bin/env python3
"""Regia — chat di una sessione, a 0 token. SOLA LETTURA: nessun modello viene chiamato, si leggono file che esistono già.

Voci, in ordine di ora:
  tu → (Regia)     coda.jsonl, sessione = NOME (con lo stato: letto/girato/risposto)
  SUP              risposte.jsonl, sessione = NOME (righe scritte dal SUP con sup.py risposta)
  <da> → sessione  messaggi tra sessioni ricevuti (<cross-session-message from-name=…>) nella trascrizione
  sessione → <a>   SendMessage mandati dalla sessione (trascrizione, tool_use)
  sessione         testi dell'agente (trascrizione, blocchi «text» dell'assistente)
  tu (terminale)   quello che l'utente scrive direttamente nella scheda della sessione

Uso: python3 regia/chat.py NOME SESSION_ID  → JSON su stdout.
"""
import datetime, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attesa import trattenute  # noqa: E402
from modifiche import unisci  # noqa: E402

QUI = os.path.dirname(os.path.abspath(__file__))
DATI = os.environ.get("PLANCIA_DATI", QUI)
CASA = os.path.expanduser("~")
CODA_BYTE = 1_500_000      # coda della trascrizione letta: basta per le ultime ore anche nelle sessioni lunghe
MAX_VOCI = 40
MAX_TESTO = 4000           # il taglio a ~400 caratteri con «apri tutto» lo fa la pagina
MSG = re.compile(r'<cross-session-message[^>]*?from-name="([^"]*)"[^>]*>\s*(.*?)\s*</cross-session-message>', re.S)
SOCK = re.compile(r'<cross-session-message[^>]*?from="([^"]*)"[^>]*?from-name="([^"]*)"')


def _file(sid):
    if not sid or not re.fullmatch(r"[0-9a-f-]{8,64}", sid):
        return None
    f = glob.glob(os.path.join(CASA, f".claude/projects/*/{sid}.jsonl"))
    return f[0] if f else None


def firma(sid):
    """ETag: dimensione e data della trascrizione e dei file messaggi, senza leggerli."""
    parti = []
    for p in [_file(sid)] + [os.path.join(DATI, n) for n in ("coda.jsonl", "richieste.json", "risposte.jsonl", "attesa.jsonl")]:
        try:
            st = os.stat(p)
            parti.append(f"{st.st_size}-{st.st_mtime_ns}")
        except (OSError, TypeError):
            parti.append("0")
    return '"c' + sid[:8] + "." + ".".join(parti) + '"'


def _locale(ts):
    """ISO UTC della trascrizione → «AAAA-MM-GG HH:MM:SS» locale, come coda.jsonl e risposte.jsonl."""
    try:
        t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return t.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return ""


def _jsonl(p):
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


def _taglia(t):
    t = (t or "").strip()
    return t if len(t) <= MAX_TESTO else t[:MAX_TESTO] + "…"


def trascrizione(sid):
    """Voci della sessione lette dalla sua trascrizione."""
    f = _file(sid)
    if not f:
        return []
    voci, visti, socket_nome = [], set(), {}
    with open(f, "rb") as h:
        h.seek(max(0, os.path.getsize(f) - CODA_BYTE))
        righe = h.read().decode("utf-8", "ignore").splitlines()
    for l in righe:
        try:
            d = json.loads(l)
        except ValueError:
            continue
        tipo, ora = d.get("type"), _locale(d.get("timestamp", ""))
        testi_in = []
        if tipo == "attachment" and (d.get("attachment") or {}).get("type") == "queued_command":
            testi_in.append(str(d["attachment"].get("prompt") or ""))
        m = d.get("message") if isinstance(d.get("message"), dict) else None
        # i messaggi fra sessioni ora arrivano con isMeta=true e origin.kind="peer": vanno tenuti
        if tipo == "user" and m and (not d.get("isMeta") or (d.get("origin") or {}).get("kind") == "peer"):
            c = m.get("content")
            if isinstance(c, str):
                testi_in.append(c)
            elif isinstance(c, list) and not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                testi_in.append("\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"))
        for t in testi_in:
            for so, nome in SOCK.findall(t):
                socket_nome[so] = nome
            trovati = MSG.findall(t)
            for da, corpo in trovati:  # messaggio da un'altra sessione (arriva due volte: in coda e nel turno)
                chiave = ("in", corpo[:200])
                if chiave in visti:
                    continue
                visti.add(chiave)
                voci.append({"ora": ora, "chi": "in", "da": da or "?", "testo": _taglia(corpo)})
            if not trovati and tipo == "user":
                s = t.strip()
                # quello che l'utente scrive nel terminale: niente comandi, avvisi di sistema, interruzioni
                if s and not s.startswith(("<", "[Request interrupted", "Caveat:", "Base directory")):
                    voci.append({"ora": ora, "chi": "terminale", "testo": _taglia(s)})
        if tipo == "assistant" and m and isinstance(m.get("content"), list):
            for b in m["content"]:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text", "").strip():
                    voci.append({"ora": ora, "chi": "sessione", "testo": _taglia(b["text"])})
                elif b.get("type") == "tool_use" and b.get("name") == "SendMessage":
                    inp = b.get("input") or {}
                    if inp.get("message"):
                        voci.append({"ora": ora, "chi": "out", "a": str(inp.get("to") or "?"), "testo": _taglia(str(inp["message"]))})
    for v in voci:  # «uds:/tmp/cc-socks/48440.sock» → «SUPERAGENTE» quando il nome è noto
        if v["chi"] == "out":
            v["a"] = socket_nome.get(v["a"], v["a"])
    return voci


def chat(nome, sid):
    nome = (nome or "").upper()
    richieste = {}
    try:
        with open(os.path.join(DATI, "richieste.json"), encoding="utf-8") as f:
            richieste = json.load(f)
    except (OSError, ValueError):
        pass
    voci = trascrizione(sid)
    for r in unisci(_jsonl(os.path.join(DATI, "coda.jsonl")) + [dict(r, attesa=True) for r in trattenute(DATI)]):
        if str(r.get("sessione", "")).upper() == nome:
            s = richieste.get(r.get("id"), {})
            voci.append({"ora": r.get("ora", ""), "chi": "tu", "testo": _taglia(r.get("testo")), "id": r.get("id"),
                         "stato": "attesa" if r.get("attesa") else s.get("stato", "nuova"), "ora_stato": s.get("ora"), "storia": s.get("storia", []), "a": s.get("a"),
                         "prima": r.get("prima", []), "modificata": r.get("modificata"), "mod_vista": s.get("mod_vista")})
    for r in _jsonl(os.path.join(DATI, "risposte.jsonl")):
        if str(r.get("sessione", "")).upper() == nome:
            voci.append({"ora": r.get("ora", ""), "chi": "sup", "testo": _taglia(r.get("testo"))})
    voci.sort(key=lambda v: v["ora"])  # stabile: a parità d'ora resta l'ordine della trascrizione
    # testi consecutivi della sessione («ora provo…», «fatto, ora…»): resta l'ultimo, con quanti passi copre;
    # altrimenti la cronaca del lavoro copre i messaggi veri
    unite = []
    for v in voci:
        if v["chi"] == "sessione" and unite and unite[-1]["chi"] == "sessione":
            v = dict(v, passi=unite[-1].get("passi", 1) + 1)
            unite[-1] = v
        else:
            unite.append(v)
    return {"nome": nome, "voci": unite[-MAX_VOCI:]}


FILO_SUP_MAX = 30


def firma_sup(sid):
    """ETag del filo unico del SUP: trascrizione del SUP + file dei messaggi (solo stat, nessuna lettura)."""
    return firma(sid or "00000000").replace('"c', '"f', 1)


def filo_sup(sid):
    """Filo unico del SUP. Solo le voci che NON sono già nel filo del SUP, in ordine di tempo:
      tu → NOME     coda.jsonl con sessione ≠ SUP (scritte nel filo di una sessione), con lo stato
      SUP → NOME    risposte.jsonl con sessione ≠ SUP (risposte del SUP nel filo di una sessione)
      NOME → SUP    messaggi degli agenti al SUP: dalla SOLA trascrizione del SUP (cross-session «in»)
    Le trascrizioni degli altri agenti non si leggono (costo): i loro testi restano nella chat della sessione."""
    richieste = {}
    try:
        with open(os.path.join(DATI, "richieste.json"), encoding="utf-8") as f:
            richieste = json.load(f)
    except (OSError, ValueError):
        pass
    voci = [dict(v, chi="agente") for v in trascrizione(sid) if v["chi"] == "in"] if sid else []
    for r in unisci(_jsonl(os.path.join(DATI, "coda.jsonl")) + [dict(r, attesa=True) for r in trattenute(DATI)]):
        nome = str(r.get("sessione", "")).upper()
        if nome and nome != "SUP":
            s = richieste.get(r.get("id"), {})
            voci.append({"ora": r.get("ora", ""), "chi": "tu-s", "sessione": nome, "testo": _taglia(r.get("testo")), "id": r.get("id"),
                         "stato": "attesa" if r.get("attesa") else s.get("stato", "nuova"), "ora_stato": s.get("ora"), "storia": s.get("storia", []),
                         "a": s.get("a"), "prima": r.get("prima", []), "modificata": r.get("modificata"), "mod_vista": s.get("mod_vista")})
    for r in _jsonl(os.path.join(DATI, "risposte.jsonl")):
        nome = str(r.get("sessione", "")).upper()
        if nome and nome != "SUP":
            voci.append({"ora": r.get("ora", ""), "chi": "sup-s", "sessione": nome, "testo": _taglia(r.get("testo"))})
    voci.sort(key=lambda v: v["ora"])
    return {"voci": voci[-FILO_SUP_MAX:]}


if __name__ == "__main__":
    json.dump(chat(sys.argv[1], sys.argv[2]), sys.stdout, ensure_ascii=False, indent=1)
    print()
