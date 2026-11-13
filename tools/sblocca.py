#!/usr/bin/env python3
"""Rilevatore di sessioni Claude Code bloccate su un dialogo, nelle schede di Terminal (macOS).

Una sessione che resta ferma su un dialogo (uscita con lavoro in sottofondo, cartella da approvare, permesso, menu di
scelta) aspetta un tasto che nessuno premerà: il coordinatore e l'utente usano un'altra finestra. Questo script, lanciato
ogni ~2 minuti (launchd o giro del coordinatore), legge lo schermo visibile di ogni sessione e:

  - dialogo noto, fermo da almeno SOGLIA_S  → risponde con l'opzione nota (tabella DIALOGHI), mai concedendo permessi:
        uscita con lavoro in sottofondo → «Stay»        (nessun lavoro perso; chi voleva uscire riprova a lavoro finito)
        permesso «Do you want to …»     → «No …»        (la sessione riprende e chiede per la via giusta)
        cartella da approvare           → «Yes, I trust this folder» solo sotto le radici date con --radice, altrimenti «No»
        impostazioni gestite            → nessun tasto, solo avviso (una sessione nuova troverebbe lo stesso dialogo)
  - dialogo sconosciuto, o 2 risposte che non lo hanno chiuso → doppia.py NOME (sessione NOME-2 al posto della prima)
  - ogni azione → avviso al coordinatore (comando dato con --avvisa, che riceve il testo come ultimo argomento).

Uso:
  sblocca.py [--prova] [--soglia S] [--radice DIR]... [--avvisa CMD...] [--apri CMD...] [--no-doppia NOME]...
             [--solo NOME]...
  sblocca.py --leggi TTY        stampa lo schermo visibile di una scheda e la classificazione (per capire un caso)

  --prova       legge e dice cosa farebbe, senza scrivere niente nelle schede
  --soglia S    secondi di dialogo fermo (stessa firma in due giri) prima di agire; predefinito 100
  --avvisa CMD  comando per l'avviso (ripetibile = più parole, es. --avvisa python3 --avvisa sup.py --avvisa risposta)
  --apri CMD    passato a doppia.py (comando che apre una scheda: riceve NOME CARTELLA COMANDO)
  --no-doppia   nomi per cui non si apre mai la copia (es. il coordinatore, che ha la sua procedura): solo avviso
  --solo        controlla solo questi nomi (prove su sessioni usa e getta)

Ogni osascript ha un tetto di 10 s (Terminal con molte finestre si è appeso per minuti su un comando solo).
Stato fra un giro e l'altro: ~/.claude/sblocca/stato.json · log: ~/.claude/sblocca/sblocca.log
Uscita: 0 nessun blocco o tutto risolto, 1 errore, 2 almeno un blocco non risolto (avvisato).
"""
import json
import os
import re
import subprocess
import sys
import time

CASA = os.path.expanduser("~")
DIR = os.environ.get("SBLOCCA_DIR") or os.path.join(CASA, ".claude", "sblocca")
STATO = os.path.join(DIR, "stato.json")
LOG = os.path.join(DIR, "sblocca.log")
TETTO_S = 10
TENTATIVI_MAX = 2
QUI = os.path.dirname(os.path.abspath(__file__))
CLAUDE = os.environ.get("CLAUDE_BIN") or next(
    (p for p in (os.path.join(CASA, ".local", "bin", "claude"), "/opt/homebrew/bin/claude", "/usr/local/bin/claude")
     if os.path.exists(p)), "claude")

# Dialoghi noti: (chiave, testo che lo riconosce, regola di scelta). La regola riceve la cartella della sessione e le
# radici fidate e restituisce la regex dell'etichetta da scegliere, oppure None = non toccare (solo avviso).
DIALOGHI = [
    ("uscita", re.compile(r"Background work is running"), lambda cwd, radici: r"^Stay\b"),
    ("impostazioni", re.compile(r"Yes, I trust these settings"), lambda cwd, radici: None),
    ("fiducia", re.compile(r"Yes, I trust this folder"),
     lambda cwd, radici: r"^Yes, I trust this folder" if sotto(cwd, radici) else r"^No\b"),
    ("permesso", re.compile(r"Do you want to (proceed|make this edit|create|allow|run)"), lambda cwd, radici: r"^No\b"),
]
SOLO_AVVISO = {"impostazioni"}
OPZIONE = re.compile(r"^[\s│|]*(❯|>)?\s*(\d{1,2})\.\s+(.*?)[\s│|]*$")
BORDO = re.compile(r"^[\s╭╰│]*[─━]{8,}")
PIEDE_MENU = re.compile(r"Enter to (select|confirm)|Esc to (cancel|go back|exit)|to navigate", re.I)


def sotto(cwd, radici):
    c = os.path.realpath(cwd or "/nessuna")
    return any(c == os.path.realpath(r) or c.startswith(os.path.realpath(r).rstrip("/") + "/") for r in radici)


def ora():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def registra(msg):
    os.makedirs(DIR, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{ora()} {msg}\n")


def osa(righe, *argomenti):
    """osascript con tetto di TETTO_S; None se Terminal non risponde."""
    try:
        r = subprocess.run(["osascript", *[x for l in righe for x in ("-e", l)], *argomenti],
                           capture_output=True, text=True, timeout=TETTO_S)
    except subprocess.TimeoutExpired:
        registra(f"Terminal non risponde da {TETTO_S} s")
        return None
    return r.stdout


SCHERMO = ["on run argv", 'tell application "Terminal"', "repeat with w in windows", "repeat with t in tabs of w",
           "if tty of t is (item 1 of argv) then", "return contents of t", "end if", "end repeat", "end repeat",
           "end tell", 'return ""', "end run"]
SCRIVI = ["on run argv", 'tell application "Terminal"', "repeat with w in windows", "repeat with t in tabs of w",
          "if tty of t is (item 1 of argv) then", "do script (item 2 of argv) in t", 'return "ok"', "end if",
          "end repeat", "end repeat", "end tell", 'return "scheda non trovata"', "end run"]


def schermo(tty):
    out = osa(SCHERMO, "/dev/" + tty.replace("/dev/", ""))
    return None if out is None else out.rstrip("\n").splitlines()


def scrivi(tty, testo):
    return (osa(SCRIVI, "/dev/" + tty.replace("/dev/", ""), testo) or "").strip() == "ok"


def casella_aperta(righe):
    """True se in fondo allo schermo c'è la casella d'ingresso (bordo, «❯ testo», bordo): nessun dialogo aperto."""
    coda = [l for l in righe if l.strip()][-10:]
    for i in range(1, len(coda) - 1):
        l = coda[i].lstrip(" │")
        if l.startswith(("❯", ">")) and not OPZIONE.match(coda[i]) and BORDO.match(coda[i - 1]) and BORDO.match(coda[i + 1]):
            return True
    return False


def classifica(righe, cwd="", radici=()):
    """Dallo schermo visibile → None (nessun dialogo) oppure dict(chiave, opzioni, scelta, firma).
    chiave «sconosciuto» = menu aperto che nessuna regola conosce; scelta None = non premere niente."""
    if not righe or casella_aperta(righe):
        return None
    coda = righe[-40:]
    testo = "\n".join(coda)
    opzioni = []
    for l in coda:
        m = OPZIONE.match(l)
        if m and m.group(3):
            n = int(m.group(2))
            if opzioni and n != opzioni[-1][0] + 1:
                opzioni = []          # lista numerata del discorso, non il menu: ricomincia
            if n == 1 or opzioni:
                opzioni.append((n, m.group(3).strip()))
    for chiave, segno, regola in DIALOGHI:
        if segno.search(testo):
            voluta = regola(cwd, radici)
            scelta = None
            if voluta:
                scelta = next((n for n, et in opzioni if re.search(voluta, et)), None)
                if scelta is None:
                    chiave = chiave + "-senza-opzione"
            return {"chiave": chiave, "opzioni": opzioni, "scelta": scelta,
                    "firma": chiave + "|" + "|".join(et for _, et in opzioni)}
    if len(opzioni) >= 2 and PIEDE_MENU.search(testo):
        return {"chiave": "sconosciuto", "opzioni": opzioni, "scelta": None,
                "firma": "sconosciuto|" + "|".join(et for _, et in opzioni)}
    return None


def sessioni():
    out = subprocess.run([CLAUDE, "agents", "--json"], capture_output=True, text=True, timeout=30).stdout
    return json.loads(out or "[]")


def tty_di(pid):
    try:
        return subprocess.run(["ps", "-o", "tty=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
    except subprocess.SubprocessError:
        return ""


def leggi_stato():
    try:
        with open(STATO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def scrivi_stato(s):
    os.makedirs(DIR, exist_ok=True)
    tmp = STATO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATO)


def avvisa(cmd, testo, prova):
    registra("AVVISO " + testo)
    if prova or not cmd:
        print("  avviso:", testo)
        return
    try:
        subprocess.run([*cmd, testo], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        registra(f"avviso non partito: {e}")


def doppia(nome, a, prova):
    cmd = [sys.executable, os.path.join(QUI, "doppia.py"), nome]
    for x in a["apri"]:
        cmd += ["--apri", x]
    if prova:
        cmd.append("--prova")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout + r.stderr).strip()


def giro(a):
    stato = leggi_stato()
    nuovo, bloccati, adesso = {}, 0, time.time()
    try:
        lista = sessioni()
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print(f"claude agents non risponde: {e}", file=sys.stderr)
        return 1
    for s in lista:
        nome, pid = s.get("name") or "", s.get("pid")
        if s.get("kind") != "interactive" or not pid or (a["solo"] and nome.upper() not in a["solo"]):
            continue
        tty = tty_di(pid)
        if not tty or tty == "??":
            continue
        righe = schermo(tty)
        if righe is None:
            print("Terminal non risponde: giro interrotto", file=sys.stderr)
            scrivi_stato({**stato, **nuovo})
            return 1
        d = classifica(righe, s.get("cwd") or "", a["radici"])
        if not d:
            continue
        prima = stato.get(tty) or {}
        if prima.get("firma") != d["firma"] or prima.get("pid") != pid:
            prima = {"firma": d["firma"], "pid": pid, "nome": nome, "primo": adesso, "tentativi": 0}
        nuovo[tty] = prima
        fermo = adesso - prima["primo"]
        print(f"{nome} ({tty}): {d['chiave']} da {int(fermo)} s, opzioni {[et for _, et in d['opzioni']]}")
        if fermo < a["soglia"]:
            continue
        bloccati += 1
        if d["scelta"] is not None and prima["tentativi"] < TENTATIVI_MAX:
            etichetta = dict(d["opzioni"])[d["scelta"]]
            if a["prova"]:
                print(f"  (prova) premerei {d['scelta']} = «{etichetta}»")
                continue
            prima["tentativi"] += 1
            ok = scrivi(tty, str(d["scelta"]))
            time.sleep(4)
            dopo = classifica(schermo(tty) or [], s.get("cwd") or "", a["radici"])
            chiuso = ok and (not dopo or dopo["firma"] != d["firma"])
            registra(f"{nome} {tty} {d['chiave']}: premuto {d['scelta']} «{etichetta}» → {'chiuso' if chiuso else 'ancora aperto'}")
            if chiuso:
                del nuovo[tty]
                bloccati -= 1
                avvisa(a["avvisa"], f"Sblocco: {nome} era fermo su «{d['chiave']}» da {int(fermo / 60)} min, "
                                    f"scelto «{etichetta}». Sessione di nuovo libera.", False)
            continue
        # Solo avviso: dialogo noto senza risposta prevista (una copia lo ritroverebbe) o nome escluso dalla copia.
        # Copia: dialogo sconosciuto, opzione voluta non trovata, o TENTATIVI_MAX risposte che non lo hanno chiuso.
        if d["chiave"] in SOLO_AVVISO or nome.upper() in a["no_doppia"]:
            if not prima.get("avvisato"):
                avvisa(a["avvisa"], f"Sblocco: {nome} fermo su «{d['chiave']}» da {int(fermo / 60)} min; "
                                    f"nessuna risposta automatica prevista, serve il coordinatore.", a["prova"])
                prima["avvisato"] = True
            continue
        codice, uscita = doppia(nome, a, a["prova"])
        registra(f"{nome} {tty} {d['chiave']}: doppia.py → {codice} {uscita[-200:]!r}")
        if not a["prova"]:
            nuovo.pop(tty, None)
            avvisa(a["avvisa"], f"Sblocco: {nome} fermo su «{d['chiave']}» da {int(fermo / 60)} min "
                                f"(tentativi {prima['tentativi']}): copia {nome}-2. Esito: {uscita.splitlines()[-1] if uscita else codice}", False)
        else:
            print("  " + uscita.replace("\n", "\n  "))
    if not a["prova"]:
        scrivi_stato(nuovo)
    return 2 if bloccati else 0


def argomenti(argv):
    a = {"prova": False, "soglia": 100, "radici": [], "avvisa": [], "apri": [], "no_doppia": set(), "solo": set(),
         "leggi": None}
    i = 0
    while i < len(argv):
        x = argv[i]
        if x == "--prova":
            a["prova"] = True
        elif x in ("--soglia", "--radice", "--avvisa", "--apri", "--no-doppia", "--solo", "--leggi") and i + 1 < len(argv):
            i += 1
            v = argv[i]
            if x == "--soglia":
                a["soglia"] = float(v)
            elif x == "--radice":
                a["radici"].append(os.path.expanduser(v))
            elif x == "--avvisa":
                a["avvisa"].append(v)
            elif x == "--apri":
                a["apri"].append(v)
            elif x == "--no-doppia":
                a["no_doppia"].add(v.upper())
            elif x == "--solo":
                a["solo"].add(v.upper())
            else:
                a["leggi"] = v
        else:
            print(__doc__)
            sys.exit(1)
        i += 1
    return a


def main(argv):
    a = argomenti(argv)
    if a["leggi"]:
        righe = schermo(a["leggi"])
        if righe is None:
            print("Terminal non risponde")
            return 1
        print("\n".join(righe[-40:]))
        print("---\n", classifica(righe, "", a["radici"]))
        return 0
    return giro(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
