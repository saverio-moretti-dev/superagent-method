#!/usr/bin/env python3
"""Prove VERE di tools/riavvia.py --sup su sessioni claude usa e getta (tester indipendente, ordine SUP 11/11 19:42).

NON parte con `unittest discover` (il nome non comincia con test_): apre schede di Terminal e spende token.
Ogni caso apre una finestra di Terminal sua con `claude --safe-mode --model haiku --tools "" -n PROVA-PUB-<caso>`
in una cartella temporanea (niente skill, CLAUDE.md, strumenti: «/riparti superagente» non fa niente di vero),
crea la condizione, lancia riavvia.py e MISURA l'esito sulle trascrizioni, non sul log:
  svuotato = dopo il lancio nasce una trascrizione nuova (session id diverso) nella cartella del progetto
             E la trascrizione vecchia non ha ricevuto come prompt un testo che contiene «/clear».
Alla fine chiude la sessione e la finestra, cancella la nota finta. Mai tty di sessioni vive.

Uso:  python3 tests/e2e_riavvia.py [C1 C2 …]      (senza argomenti: tutti)
      RIAVVIA=<percorso di riavvia.py da provare>   (predefinito: tools/riavvia.py di questa repo)
"""
import fcntl, glob, json, os, re, subprocess, sys, tempfile, termios, threading, time

QUI = os.path.dirname(os.path.abspath(__file__))
RIAVVIA = os.environ.get("RIAVVIA", os.path.join(QUI, "..", "tools", "riavvia.py"))
CASA = os.path.expanduser("~")
PASSAGGI = os.path.join(CASA, ".claude", "passaggi")
PROGETTI = os.path.join(CASA, ".claude", "projects")
BASE = os.environ.get("E2E_BASE", "/private/tmp/prova-riavvio")
VIVI_VIETATI = {"ttys001", "ttys002", "ttys003", "ttys025"}
ENV_CORTO = {"RIAVVIA_BLOCCO_S": "1", "RIAVVIA_NOTA_MAX_S": "600", "RIAVVIA_PROVA": "1"}


def osa(*righe, args=()):
    if args:
        righe = ("on run argv", *righe, "end run")
    r = subprocess.run(["osascript", *[x for l in righe for x in ("-e", l)], *args], capture_output=True, text=True, timeout=30)
    return r.stdout.strip(), r.stderr.strip()


def agenti():
    try:
        out = subprocess.run(["claude", "agents", "--json"], capture_output=True, text=True, timeout=30).stdout
        d = json.loads(out)
    except Exception:  # noqa: BLE001
        return []
    return d if isinstance(d, list) else d.get("agents") or d.get("sessions") or []


def voce(nome):
    for a in agenti():
        if (a.get("name") or a.get("nome")) == nome:
            return a
    return None


def trascrizioni(cartella):
    """file .jsonl del progetto della cartella (nome cartella con / e spazi → -)."""
    chiave = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(cartella))
    return {os.path.basename(p)[:-6]: p for p in glob.glob(os.path.join(PROGETTI, chiave, "*.jsonl"))}


def prompt_utente(p):
    out = []
    try:
        for riga in open(p, encoding="utf-8"):
            try:
                d = json.loads(riga)
            except ValueError:
                continue
            if d.get("type") == "user":
                c = (d.get("message") or {}).get("content")
                if isinstance(c, str):
                    out.append(c)
                elif isinstance(c, list):
                    out += [x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"]
    except OSError:
        pass
    return out


def inietta(tty, testo, invio=False):
    """Testo nella casella della sessione come se l'utente lo digitasse (TIOCSTI sulla tty della scheda)."""
    fd = os.open("/dev/" + tty, os.O_RDWR | os.O_NOCTTY)
    try:
        for ch in (testo + ("\r" if invio else "")).encode():
            fcntl.ioctl(fd, termios.TIOCSTI, bytes([ch]))
    finally:
        os.close(fd)


class Sessione:
    def __init__(self, caso, primo="rispondi solo: ok"):
        self.nome = f"PROVA-PUB-{caso}"
        # cartella FISSA sotto quella già fidata (SUP 11/11): una cartella nuova fa uscire «ti fidi della cartella?»
        self.dir = os.path.join(BASE, "pub")
        os.makedirs(self.dir, exist_ok=True)
        cmd = f"cd '{self.dir}' && claude --safe-mode --model haiku --tools '' -n {self.nome} '{primo}'"
        out, err = osa('tell application "Terminal"', "set t to do script (item 1 of argv)",
                       'return (tty of t) & "|" & (id of (first window whose tabs contains t))', "end tell", args=(cmd,))
        if "|" not in out:
            raise RuntimeError(f"scheda non aperta: {err}")
        self.tty, self.win = out.split("|")[0].replace("/dev/", ""), out.split("|")[1]
        assert self.tty not in VIVI_VIETATI, self.tty

    def aspetta_ferma(self, max_s=120):
        fine = time.time() + max_s
        while time.time() < fine:
            v = voce(self.nome)
            if v and v.get("status") == "idle" and trascrizioni(self.dir):
                return True
            time.sleep(3)
        return False

    def nota(self, eta_s=0):
        os.makedirs(PASSAGGI, exist_ok=True)
        p = os.path.join(PASSAGGI, f"{self.nome}.md")
        with open(p, "w") as f:
            f.write(f"nome: {self.nome}\nnota finta di prova (tests/e2e_riavvia.py)\n")
        t = time.time() - eta_s
        os.utime(p, (t, t))

    def riavvia(self, *extra, attendi=None, env=None):
        a = [sys.executable, RIAVVIA, self.nome, self.tty, "--sup", *extra]
        if attendi:
            a += ["--attendi", str(attendi)]
        e = dict(os.environ, **ENV_CORTO, **(env or {}))
        r = subprocess.run(a, capture_output=True, text=True, timeout=60 * (attendi or 1) + 120, env=e)
        return r.returncode, (r.stdout + r.stderr).strip()

    def chiudi(self):
        subprocess.run(["pkill", "-f", f"-n {self.nome}( |$)"], capture_output=True)
        for _ in range(10):
            if not voce(self.nome):
                break
            time.sleep(1)
        osa('tell application "Terminal"', f"close (every window whose id is {self.win}) saving no", "end tell")
        for p in glob.glob(os.path.join(PASSAGGI, f"{self.nome}*.md")):
            os.remove(p)


def misura(s, prima):
    """(svuotato, dettagli): trascrizione nuova + nessun «…/clear» entrato come prompt nella vecchia."""
    time.sleep(8)
    dopo = trascrizioni(s.dir)
    nuove = [k for k in dopo if k not in prima]
    sporchi = [t for k, p in prima.items() for t in prompt_utente(p) if "/clear" in t and "<command-name>" not in t]
    riparti_nuova = any("/riparti" in t for k in nuove for t in prompt_utente(dopo[k]))
    return bool(nuove) and not sporchi, f"nuove={len(nuove)} riparti_in_nuova={riparti_nuova} prompt_sporchi={sporchi[:2]}"


# ---------- casi ----------
def c1(s):
    s.nota(); prima = trascrizioni(s.dir)
    rc, out = s.riavvia()
    ok, det = misura(s, prima)
    return ok and rc == 0, f"rc={rc} {det} | {out[-160:]}"


def c2(s):
    """testo lasciato nella casella prima del /clear (il caso reale «rit/clear»)."""
    s.nota(); prima = trascrizioni(s.dir)
    inietta(s.tty, "rit"); time.sleep(1)
    rc, out = s.riavvia()
    ok, det = misura(s, prima)
    return (ok or rc == 2) and not misura_sporco(prima), f"rc={rc} {det} | {out[-160:]}"


def misura_sporco(prima):
    return [t for p in prima.values() for t in prompt_utente(p) if "/clear" in t and "<command-name>" not in t]


def c3(s):
    """prompt che arriva nello stesso istante del /clear (cron / messaggio)."""
    s.nota(); prima = trascrizioni(s.dir)
    th = threading.Thread(target=lambda: (time.sleep(0.3), inietta(s.tty, "sveglia cron: rispondi ok", invio=True)))
    th.start(); rc, out = s.riavvia(); th.join()
    ok, det = misura(s, prima)
    return (ok or rc == 2) and not misura_sporco(prima), f"rc={rc} {det} | {out[-160:]}"


def c4(s):
    """sessione busy (turno lungo in corso): niente svuotamento."""
    s.nota(); inietta(s.tty, "scrivi una poesia di 60 righe sul mare, lentamente", invio=True); time.sleep(4)
    prima = trascrizioni(s.dir)
    rc, out = s.riavvia()
    dopo = trascrizioni(s.dir)
    return rc == 2 and set(dopo) == set(prima), f"rc={rc} nuove={len(set(dopo) - set(prima))} | {out[-160:]}"


def c5(s):
    """messaggio in arrivo durante l'attesa (prompt a metà --attendi)."""
    s.nota(); prima = trascrizioni(s.dir)
    th = threading.Thread(target=lambda: (time.sleep(5), inietta(s.tty, "messaggio da un'altra sessione: rispondi ok", invio=True)))
    th.start(); rc, out = s.riavvia(attendi=3); th.join()
    ok, det = misura(s, prima)
    return ok and not misura_sporco(prima), f"rc={rc} {det} | {out[-160:]}"


def c6(s):
    """10 riavvii di fila sulla stessa scheda (blocco ridotto a 1 s)."""
    esiti = []
    for i in range(10):
        s.nota(); prima = trascrizioni(s.dir)
        rc, out = s.riavvia(attendi=2)
        ok, det = misura(s, prima)
        esiti.append(ok and rc == 0)
        s.aspetta_ferma(90)
    return all(esiti), f"{sum(esiti)}/10 svuotati"


def c7(s):
    s.nota(eta_s=3600); prima = trascrizioni(s.dir)
    rc, out = s.riavvia()
    return rc == 2 and set(trascrizioni(s.dir)) == set(prima), f"rc={rc} | {out[-160:]}"


def c8(s):
    prima = trascrizioni(s.dir)
    rc, out = s.riavvia()
    return rc == 2 and set(trascrizioni(s.dir)) == set(prima), f"rc={rc} | {out[-160:]}"


CASI = {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5, "C6": c6, "C7": c7, "C8": c8}

if __name__ == "__main__":
    scelti = sys.argv[1:] or list(CASI)
    print(f"riavvia.py provato: {os.path.realpath(RIAVVIA)}")
    for c in scelti:
        s = None
        try:
            s = Sessione(c)
            if not s.aspetta_ferma():
                schermo, _ = osa('tell application "Terminal"', f"return contents of selected tab of (first window whose id is {s.win})", "end tell")
                v = voce(s.nome)
                print(f"{c} · NON VALIDO: sessione di prova non ferma · agents={v and v.get('status')} trascr={len(trascrizioni(s.dir))} · schermo: {' | '.join(l for l in schermo.splitlines() if l.strip())[-400:]}"); continue
            ok, det = CASI[c](s)
            print(f"{c} · {'PASSA' if ok else 'FALLISCE'} · {det}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"{c} · ERRORE PROVA · {type(e).__name__}: {e}", flush=True)
        finally:
            if s:
                s.chiudi()
