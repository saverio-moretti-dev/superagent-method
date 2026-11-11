#!/usr/bin/env python3
"""Regia — server locale, solo stdlib, solo 127.0.0.1.

  GET  /              → web/index.html (e i file statici di web/, elenco chiuso)
  GET  /api/stato     → istantanea di raccogli.py (cache 5 s)
  GET  /api/messaggi  → solo messaggi + battito del SUP, ETag (304 se nulla è cambiato): giro di 2 s
  GET  /api/chat?s=NOME → chat della sessione (chat.py: trascrizione + coda + risposte, 0 token), ETag/304
  GET  /api/token     → scheda Token: consumi.py (calcoli di dont-waste-your-token in sola lettura, cache 60 s)
  POST /api/modifica  → {"id": "...", "testo": "..."} → richiesta modificata prima della risposta (modifiche.py)
  POST /api/richiesta → {"sessione": "NOME"|"SUP", "testo": "..."} → una riga in coda.jsonl (per il SUP);
                       con pausa.json (SUP in riavvio) va in attesa.jsonl e parte alla ripresa (attesa.py)

Scrive SOLO in regia/coda.jsonl e regia/attesa.jsonl. Non tocca schede, ~/.claude, regole. Avvio a mano:
  python3 regia/server.py [porta]      (default 8765)  →  http://127.0.0.1:8765
"""
import json, os, re, secrets, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from raccogli import raccogli, messaggi, firma_messaggi, QUI, DATI  # noqa: E402
from consumi import raccogli_token  # noqa: E402
import chat as chat_  # noqa: E402
from attesa import in_pausa, trattieni, rilascia, trattenute  # noqa: E402
from modifiche import unisci, ha_risposta  # noqa: E402
from raccogli import _json, _jsonl  # noqa: E402
from urllib.parse import urlparse, parse_qs  # noqa: E402

PORTA = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
CODA = os.path.join(DATI, "coda.jsonl")
WEB = os.path.join(QUI, "web")
STATICI = {"/": ("index.html", "text/html"), "/index.html": ("index.html", "text/html"),
           "/app.js": ("app.js", "text/javascript"), "/token.js": ("token.js", "text/javascript"), "/style.css": ("style.css", "text/css"),
           "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"), "/sw.js": ("sw.js", "text/javascript"),
           "/favicon.ico": ("icone/favicon-32.png", "image/png")}
for _n in ("regia-192.png", "regia-512.png", "regia-maskable-512.png", "apple-touch-180.png", "favicon-32.png", "regia.svg"):
    STATICI[f"/icone/{_n}"] = (f"icone/{_n}", "image/svg+xml" if _n.endswith(".svg") else "image/png")
HOST_OK = {f"127.0.0.1:{PORTA}", f"localhost:{PORTA}"}
PROVA = os.path.realpath(DATI) != os.path.realpath(QUI)  # dati finti: server di prova
CODA_VERA = os.path.join(QUI, "coda.jsonl")
PROVA_MIN = int(os.environ.get("PLANCIA_PROVA_MIN", "30"))  # il server di prova si spegne da solo


# Aggiornamento da solo (senza, il server restava con il vecchio raccogli.py in memoria). Codice Python cambiato → il server si rilancia (execv, stessa porta, stesso
# ambiente: launchd non se ne accorge). File della pagina cambiati → la versione in X-Regia-Versione cambia e app.js ricarica.
PY = [os.path.join(QUI, n) for n in ("server.py", "raccogli.py", "consumi.py", "chat.py")]


def _firma(file):
    tot = []
    for f in file:
        try:
            tot.append(os.stat(f).st_mtime_ns)
        except OSError:
            tot.append(0)
    return tot


def versione_web():
    return str(max(_firma([os.path.join(WEB, n) for n, _ in STATICI.values()])))


def _sorveglia(prima):
    while True:
        time.sleep(3)
        ora = _firma(PY)
        if ora != prima:
            time.sleep(1)  # salvataggio a metà: si aspetta che finisca
            # file rotto → niente rilancio (altrimenti la Regia vera si spegne e launchd la rilancia a vuoto)
            prova = subprocess.run([sys.executable, "-m", "py_compile"] + PY, capture_output=True, text=True)
            if prova.returncode:
                print("codice cambiato ma non compila: resto col vecchio\n" + prova.stderr[-500:], flush=True)
                prima = _firma(PY)
                continue
            print("codice cambiato: il server si rilancia", flush=True)
            os.execv(sys.executable, [sys.executable] + sys.argv)
PROVA_FASCIA = ('<body><div role="alert" class="fascia-prova">SERVER DI PROVA (dati finti): i messaggi '
                'scritti qui vanno anche al SUP solo se non cominciano con «prova». La Regia vera è su 127.0.0.1:8765.</div>').encode()
NOME_OK = re.compile(r"^[A-Z0-9_-]{1,40}$")
ID_OK = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
# stato finto (prove cieche, prove a schermo): /api/stato, /api/chat e /api/token dal file, riletto a ogni richiesta;
# solo col server di prova, così un tester non vede mai le sessioni vere. Chiavi: stato, chat {NOME: voci}, token
FINTO = os.environ.get("PLANCIA_STATO_FINTO") if PROVA else None


def finto(chiave, base=None):
    with open(FINTO, encoding="utf-8") as f:
        d = json.load(f)
    v = d.get(chiave, base)
    if chiave == "stato" and isinstance(v, dict):
        v = {**v, "ora": int(time.time())}
    return v


_cache, _cache_t, _lock = None, 0.0, threading.Lock()
_tok, _tok_t, _tok_lock = None, 0.0, threading.Lock()


def stato():
    global _cache, _cache_t
    with _lock:
        if _cache is None or time.time() - _cache_t > 5:
            _cache, _cache_t = raccogli(), time.time()
        return _cache


def token():
    global _tok, _tok_t
    with _tok_lock:
        if _tok is None or time.time() - _tok_t > 60:
            # elenco sessioni: quello già in memoria anche se vecchio (serve solo ai nomi degli agenti); stato() a freddo
            # chiama `claude agents` e costava 4-6 s di scheda vuota
            base = _cache if _cache is not None else stato()
            sessioni = [{"nome": s["nome"], "session_id": s.get("session_id")} for s in base.get("sessioni", [])]
            _tok, _tok_t = raccogli_token(sessioni), time.time()
        return _tok


def apri_terminale(nome):
    """Porta in primo piano la scheda di Terminal della sessione: pid (claude agents) → tty (ps) → scheda con quel tty."""
    base = _cache if _cache is not None else stato()
    pid = next((x.get("pid") for x in base.get("sessioni", []) if x["nome"] == nome), None)
    if not isinstance(pid, int):
        return {"ok": False, "errore": f"{nome}: sessione non trovata"}
    try:
        tty = subprocess.run(["ps", "-o", "tty=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        tty = ""
    if not re.fullmatch(r"ttys\d{1,4}", tty):
        return {"ok": False, "errore": f"{nome}: terminale non trovato (non è in una scheda di Terminal?)"}
    script = ['tell application "Terminal"', "repeat with w in windows", "repeat with t in tabs of w",
              f'if tty of t is "/dev/{tty}" then', "set selected of t to true", "set index of w to 1", "activate",
              'return "ok"', "end if", "end repeat", "end repeat", 'return "manca"', "end tell"]
    try:
        r = subprocess.run(["osascript"] + sum([["-e", s] for s in script], []), capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return {"ok": False, "errore": "Terminal non risponde"}
    if r.stdout.strip() == "ok":
        return {"ok": True}
    if "-1743" in r.stderr:
        return {"ok": False, "errore": "manca il permesso: Impostazioni di Sistema › Privacy e sicurezza › Automazione › consenti a Python di controllare Terminal"}
    return {"ok": False, "errore": f"{nome}: scheda con /dev/{tty} non trovata in Terminal" if r.stdout.strip() == "manca" else (r.stderr.strip()[:200] or "errore osascript")}



def scrivi(cartella, r):
    """Una riga per il SUP. SUP in riavvio (pausa.json): trattenuta in attesa.jsonl, parte quando riparte."""
    rilascia(cartella)
    if in_pausa(cartella):
        trattieni(cartella, r)
        return True
    with open(os.path.join(cartella, "coda.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return False


class Plancia(BaseHTTPRequestHandler):
    server_version = "Regia"

    def log_message(self, fmt, *args):  # niente testo dell'utente nel log; i giri regolari riusciti non si scrivono
        if self.path.split("?")[0] in ("/api/messaggi", "/api/stato", "/api/token", "/api/chat") and str(args[1] if len(args) > 1 else "")[:1] in "23":
            return
        sys.stderr.write(f"{time.strftime('%H:%M:%S')} {self.command} {self.path.split('?')[0]} {args[1] if len(args) > 1 else ''}\n")

    def _manda(self, codice, corpo, tipo="application/json"):
        dati = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(codice)
        self.send_header("Content-Type", tipo if tipo.startswith("image/") else f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(dati)))
        self.send_header("Cache-Control", "no-cache" if tipo.startswith("image/") else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Regia-Versione", versione_web())
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com")
        self.end_headers()
        self.wfile.write(dati)

    def _json_etag(self, etag, fai):
        """Risposta JSON con ETag: 304 senza calcolare niente se il client ha già quella versione."""
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return
        dati = json.dumps(fai(), ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dati)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(dati)

    def _host_ok(self):  # contro DNS rebinding: solo Host locale
        return self.headers.get("Host", "") in HOST_OK

    def do_GET(self):
        if not self._host_ok():
            return self._manda(403, {"errore": "host non ammesso"})
        p = self.path.split("?")[0]
        if FINTO and p in ("/api/stato", "/api/token", "/api/chat"):
            if p == "/api/chat":
                nome = (parse_qs(urlparse(self.path).query).get("s") or [""])[0].upper()
                return self._manda(200, {"nome": nome, "voci": (finto("chat", {}) or {}).get(nome, [])})
            return self._manda(200, finto("stato" if p == "/api/stato" else "token", {}))
        if p == "/api/stato":
            return self._manda(200, stato())
        if p == "/api/chat":
            nome = (parse_qs(urlparse(self.path).query).get("s") or [""])[0].upper()
            if not NOME_OK.match(nome):
                return self._manda(400, {"errore": "nome non valido"})
            base = _cache if _cache is not None else stato()  # l'elenco sessioni basta anche se vecchio di qualche secondo
            sid = next((x.get("session_id") for x in base.get("sessioni", []) if x["nome"] == nome), None)
            if not sid:
                return self._manda(404, {"errore": "sessione non viva"})
            return self._json_etag(chat_.firma(sid), lambda: chat_.chat(nome, sid))
        if p == "/api/messaggi":
            return self._json_etag(firma_messaggi(), messaggi)
        if p == "/api/token":
            return self._manda(200, token())
        if p in STATICI:
            nome, tipo = STATICI[p]
            try:
                with open(os.path.join(WEB, nome), "rb") as f:
                    corpo = f.read()
                if PROVA and nome == "index.html":  # server di prova: impossibile scambiarlo per la Regia vera
                    corpo = corpo.replace(b"<title>", b"<title>PROVA ", 1).replace(b"<body>", PROVA_FASCIA, 1)
                return self._manda(200, corpo, tipo)
            except OSError:
                return self._manda(404, {"errore": "file mancante"})
        self._manda(404, {"errore": "non trovato"})

    def _modifica(self, n):
        """Richiesta modificata dopo l'invio. Prima della risposta del SUP sì,
        dopo no (409: si manda di nuovo). Una riga «modifica» in coda.jsonl sveglia il Monitor del SUP."""
        global _cache
        try:
            d = json.loads(self.rfile.read(n))
            rid = str(d.get("id", "")).strip()
            testo = str(d.get("testo", "")).strip()
        except (ValueError, AttributeError):
            return self._manda(400, {"errore": "JSON non valido"})
        if not ID_OK.match(rid):
            return self._manda(400, {"errore": "id non valido"})
        if not testo or len(testo) > 4000:
            return self._manda(400, {"errore": "testo vuoto o oltre 4000 caratteri"})
        with _lock:
            righe = unisci(_jsonl(CODA) + trattenute(DATI))
            base = next((q for q in righe if q.get("id") == rid), None)
            if base is None:
                return self._manda(404, {"errore": "richiesta non trovata"})
            if ha_risposta(_json(os.path.join(DATI, "richieste.json"), {}).get(rid, {})):
                return self._manda(409, {"errore": "il SUP ha già risposto: mandala di nuovo come richiesta nuova"})
            if testo == base.get("testo"):
                return self._manda(200, {"ok": True, "uguale": True})
            riga = {"id": rid, "sessione": base.get("sessione"), "modifica": True, "testo": testo,
                    "ora": time.strftime("%Y-%m-%d %H:%M:%S")}
            trattenuta = scrivi(DATI, riga)
            originale = (base.get("prima") or [base.get("testo", "")])[0]
            if PROVA and not originale.lower().startswith("prova"):  # la richiesta era andata anche nella coda vera
                scrivi(QUI, dict(riga, da_prova=True))
            _cache = None
        return self._manda(201, dict(riga, trattenuta=trattenuta))

    def do_POST(self):
        global _cache
        # contro richieste da altri siti: Host locale, Origin (se c'è) locale, corpo JSON
        origine = self.headers.get("Origin")
        if not self._host_ok() or (origine and origine.split("://", 1)[-1] not in HOST_OK):
            return self._manda(403, {"errore": "origine non ammessa"})
        if self.path not in ("/api/richiesta", "/api/terminale", "/api/modifica"):
            return self._manda(404, {"errore": "non trovato"})
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._manda(415, {"errore": "serve application/json"})
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 < n <= 20_000:
            return self._manda(413, {"errore": "corpo vuoto o troppo grande"})
        if self.path == "/api/terminale":
            try:
                nome = str(json.loads(self.rfile.read(n)).get("nome", "")).strip().upper()
            except (ValueError, AttributeError):
                return self._manda(400, {"errore": "JSON non valido"})
            if not NOME_OK.match(nome):
                return self._manda(400, {"errore": "nome non valido"})
            if FINTO:
                return self._manda(200, {"ok": True, "prova": f"server di prova: scheda di {nome} non aperta"})
            esito = apri_terminale(nome)
            return self._manda(200 if esito.get("ok") else 409, esito)
        if self.path == "/api/modifica":
            return self._modifica(n)
        try:
            d = json.loads(self.rfile.read(n))
            sessione = str(d.get("sessione", "")).strip().upper()
            testo = str(d.get("testo", "")).strip()
        except (ValueError, AttributeError):
            return self._manda(400, {"errore": "JSON non valido"})
        if not NOME_OK.match(sessione):
            return self._manda(400, {"errore": "sessione non valida"})
        if not testo or len(testo) > 4000:
            return self._manda(400, {"errore": "testo vuoto o oltre 4000 caratteri"})
        riga = {"id": time.strftime("%m%d-%H%M%S") + "-" + secrets.token_hex(2), "sessione": sessione,
                "testo": testo, "ora": time.strftime("%Y-%m-%d %H:%M:%S")}
        with _lock:
            trattenuta = scrivi(DATI, riga)
            # server di prova: un messaggio vero (non comincia con «prova») va ANCHE nella coda vera, stesso id:
            # l'utente aveva scritto 4 messaggi nella scheda di prova credendola la Regia
            if PROVA and not testo.lower().startswith("prova"):
                scrivi(QUI, dict(riga, da_prova=True))
            _cache = None
        self._manda(201, dict(riga, trattenuta=trattenuta))


if __name__ == "__main__":
    if PROVA:
        print(f"SERVER DI PROVA (dati in {DATI}): si spegne da solo fra {PROVA_MIN} min", flush=True)
        t = threading.Timer(PROVA_MIN * 60, lambda: os._exit(0))
        t.daemon = True
        t.start()
    threading.Thread(target=_sorveglia, args=(_firma(PY),), daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORTA), Plancia)
    print(f"Regia su http://127.0.0.1:{PORTA}  (ctrl+C per fermare)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
