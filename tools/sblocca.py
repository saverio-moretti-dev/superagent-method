#!/usr/bin/env python3
"""Rilevatore di sessioni Claude Code bloccate su un dialogo, nelle schede di Terminal (macOS).

Una sessione che resta ferma su un dialogo (uscita con lavoro in sottofondo, cartella da approvare, permesso, menu di
scelta) aspetta un tasto che nessuno premerà: il coordinatore e l'utente usano un'altra finestra. Questo script, lanciato
ogni ~2 minuti (launchd o giro del coordinatore), legge lo schermo visibile di ogni sessione e:

  - dialogo noto, fermo da almeno SOGLIA_S  → risponde con l'opzione nota (tabella DIALOGHI), mai concedendo permessi:
        uscita con lavoro in sottofondo → «Stay»        (nessun lavoro perso; chi voleva uscire riprova a lavoro finito)
        permesso «Do you want to …»     → «No …»        (la sessione riprende e chiede per la via giusta)
        cartella da approvare           → «Yes, I trust this folder» solo sotto le radici date con --radice, altrimenti
                                          solo avviso («No, exit» chiuderebbe la sessione)
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
  --avvio-copia primo messaggio della copia al posto di «/riparti NOME» (prove: la copia non deve scrivere a nessuno)

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
     lambda cwd, radici: r"^Yes, I trust this folder" if sotto(cwd, radici) else None),
    ("permesso", re.compile(r"Do you want to (proceed|make this edit|create|allow|run)"), lambda cwd, radici: r"^No\b"),
]
OPZIONE = re.compile(r"^[\s│|]*(❯|>|↑|↓)?\s*(\d{1,2})\.\s+(.*?)[\s│|]*$")
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


# Per indice, non «repeat with t in tabs»: lì «contents of t» è la scheda stessa (dereferenza di AppleScript), non il testo.
SCHERMO = ["on run argv", 'tell application "Terminal"', "repeat with w in windows", "repeat with i from 1 to (count tabs of w)",
           "if tty of tab i of w is (item 1 of argv) then", "return contents of tab i of w", "end if", "end repeat",
           "end repeat", "end tell", 'return ""', "end run"]
SCRIVI = ["on run argv", 'tell application "Terminal"', "repeat with w in windows", "repeat with i from 1 to (count tabs of w)",
          "if tty of tab i of w is (item 1 of argv) then", "do script (item 2 of argv) in tab i of w", 'return "ok"', "end if",
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


def menu(coda):
    """Menu aperto in fondo allo schermo → (opzioni [(posizione, etichetta)], posizione evidenziata) o ([], None).
    Il menu è il blocco di righe non vuote attorno all'ultima riga «❯ …» che non è la casella d'ingresso. Se nel blocco
    ci sono righe numerate («2. …») contano solo quelle (le altre sono a capo o descrizioni); altrimenti ogni riga è
    un'opzione (es. il dialogo della cartella: «❯ No, exit» / «Yes, I trust this folder», senza numeri)."""
    idx = max((i for i, l in enumerate(coda) if l.lstrip(" │").startswith("❯")), default=None)
    if idx is None:
        return [], None
    a = idx
    while a > 0 and coda[a - 1].strip() and not BORDO.match(coda[a - 1]):
        a -= 1
    b = idx
    while b + 1 < len(coda) and coda[b + 1].strip() and not BORDO.match(coda[b + 1]) and not PIEDE_MENU.search(coda[b + 1]):
        b += 1
    blocco = list(range(a, b + 1))
    numerate = [(i, OPZIONE.match(coda[i])) for i in blocco if OPZIONE.match(coda[i])]
    if numerate:
        opzioni = [(int(m.group(2)), m.group(3).strip()) for _, m in numerate]
        evid = next((int(m.group(2)) for i, m in numerate if i == idx), None)
    else:
        righe = [coda[i].strip(" │").lstrip("❯").strip() for i in blocco]
        opzioni = list(enumerate(righe, 1))
        evid = blocco.index(idx) + 1
    return opzioni, evid


def classifica(righe, cwd="", radici=()):
    """Dallo schermo visibile → None (nessun dialogo) oppure dict(chiave, opzioni, evidenziata, scelta, firma).
    chiave «sconosciuto» = menu aperto che nessuna regola conosce; scelta None = non premere niente."""
    if not righe or casella_aperta(righe):
        return None
    coda = righe[-40:]
    testo = "\n".join(coda)
    opzioni, evid = menu(coda)

    def esito(chiave, scelta):
        return {"chiave": chiave, "opzioni": opzioni, "evidenziata": evid, "scelta": scelta,
                "firma": chiave + "|" + "|".join(et for _, et in opzioni)}
    for chiave, segno, regola in DIALOGHI:
        if segno.search(testo):
            voluta = regola(cwd, radici)
            if not voluta:
                return esito(chiave, None)
            scelta = next((n for n, et in opzioni if re.search(voluta, et)), None)
            return esito(chiave if scelta is not None and evid is not None else chiave + "-senza-opzione", scelta if evid else None)
    if len(opzioni) >= 2 and evid is not None and PIEDE_MENU.search(testo):
        return esito("sconosciuto", None)
    return None


def tasti(d):
    """Frecce dalla riga evidenziata all'opzione scelta; l'invio lo aggiunge `do script` (provato dal vivo 13/11)."""
    passi = d["scelta"] - d["evidenziata"]
    return ("\x1b[B" * passi if passi > 0 else "\x1b[A" * -passi) or ""


def sessioni():
    out = subprocess.run([CLAUDE, "agents", "--json"], capture_output=True, text=True, timeout=30).stdout
    return json.loads(out or "[]")


def non_registrate(lista):
    """Processi claude con un tty che `claude agents` non elenca ancora: una sessione ferma sul dialogo della cartella
    non è registrata finché non si risponde (visto dal vivo 13/11). Nome «?ttysNNN», cartella da lsof."""
    noti = {s.get("pid") for s in lista}
    out = subprocess.run(["ps", "-A", "-o", "pid=,tty=,comm="], capture_output=True, text=True, timeout=10).stdout
    extra = []
    for riga in out.splitlines():
        p = riga.split(None, 2)
        if len(p) == 3 and os.path.basename(p[2]) == "claude" and p[1] != "??" and int(p[0]) not in noti:
            cwd = subprocess.run(["lsof", "-a", "-p", p[0], "-d", "cwd", "-Fn"], capture_output=True, text=True,
                                 timeout=10).stdout
            cwd = next((l[1:] for l in cwd.splitlines() if l.startswith("n")), "")
            extra.append({"kind": "interactive", "pid": int(p[0]), "name": "?" + p[1], "cwd": cwd})
    return extra


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
    if a["avvio"]:
        cmd += ["--avvio", a["avvio"]]
    if prova:
        cmd.append("--prova")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout + r.stderr).strip()


def giro(a):
    stato = leggi_stato()
    nuovo, bloccati, adesso = {}, 0, time.time()
    try:
        lista = sessioni()
        lista += non_registrate(lista)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print(f"claude agents non risponde: {e}", file=sys.stderr)
        return 1
    for s in lista:
        nome, pid = s.get("name") or "", s.get("pid")
        if s.get("kind") != "interactive" or not pid or (a["solo"] and nome.upper() not in a["solo"] and not nome.startswith("?")):
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
            ok = scrivi(tty, tasti(d))
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
        if (d["scelta"] is None and d["chiave"] != "sconosciuto" and not d["chiave"].endswith("-senza-opzione")) \
                or nome.upper() in a["no_doppia"] or nome.startswith("?"):
            if not prima.get("avvisato"):
                avvisa(a["avvisa"], f"Sblocco: {nome} fermo su «{d['chiave']}» da {int(fermo / 60)} min; "
                                    f"nessuna risposta automatica prevista, serve il coordinatore.", a["prova"])
                prima["avvisato"] = True
            continue
        codice, uscita = doppia(nome, a, a["prova"])
        if codice == 0 and not a["prova"]:
            bloccati -= 1
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
    a = {"prova": False, "soglia": 100, "radici": [], "avvisa": [], "apri": [], "no_doppia": set(), "solo": set(), "avvio": None,
         "leggi": None}
    i = 0
    while i < len(argv):
        x = argv[i]
        if x == "--prova":
            a["prova"] = True
        elif x in ("--soglia", "--radice", "--avvisa", "--apri", "--no-doppia", "--solo", "--leggi", "--avvio-copia") and i + 1 < len(argv):
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
            elif x == "--avvio-copia":
                a["avvio"] = v
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
