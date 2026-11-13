#!/usr/bin/env python3
"""Sostituisce una sessione Claude Code bloccata con una copia NOME-2 che riparte dalla nota di NOME.

Procedura (nessun passo dell'utente, mai kill):
  1. trova NOME in `claude agents --json`: pid, cartella, tty;
  2. apre NOME-2 nella stessa cartella con:  claude -n NOME-2 --disallowedTools=AskUserQuestion "/riparti NOME"
     (con --apri CMD: CMD NOME-2 CARTELLA COMANDO, es. lo script di casa che apre schede; senza: finestra nuova di
     Terminal con `do script` senza «in», che non può scrivere dentro una sessione esistente);
  3. aspetta che NOME-2 compaia (fino a 120 s); se non compare, la prima NON si chiude;
  4. chiude la prima solo se sul suo tty c'è ancora il suo pid: finestra con quella sola scheda → close + «Terminate»
     sul foglio di conferma; finestra con altre schede → non si chiude (servirebbe il primo piano) e lo dice;
  5. dopo 20 s verifica che il pid vecchio non ci sia più: ne deve restare una sola.

Uso:  doppia.py NOME [--prova] [--apri CMD]... [--avvio TESTO]
      --avvio TESTO  primo messaggio della copia al posto di «/riparti NOME» (prove: una copia di prova che fa /riparti
                     scrive al coordinatore, visto il 13/11)
Uscita: 0 fatto (una sola sessione, la copia), 2 copia aperta ma la prima resta aperta, 3 NOME non trovato,
        4 copia non partita (la prima resta), 5 esiste già una copia viva, 1 errore/Terminal muto.
"""
import json
import os
import re
import subprocess
import sys
import time

CASA = os.path.expanduser("~")
TETTO_S = 10
CLAUDE = os.environ.get("CLAUDE_BIN") or next(
    (p for p in (os.path.join(CASA, ".local", "bin", "claude"), "/opt/homebrew/bin/claude", "/usr/local/bin/claude")
     if os.path.exists(p)), "claude")
ATTESA_COPIA_S = int(os.environ.get("DOPPIA_ATTESA_S") or 120)
LOG = os.path.join(os.environ.get("SBLOCCA_DIR") or os.path.join(CASA, ".claude", "sblocca"), "doppia.log")


def registra(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def osa(righe, *argomenti):
    try:
        r = subprocess.run(["osascript", *[x for l in righe for x in ("-e", l)], *argomenti],
                           capture_output=True, text=True, timeout=TETTO_S)
    except subprocess.TimeoutExpired:
        return None
    return r.stdout.strip()


def sessioni():
    out = subprocess.run([CLAUDE, "agents", "--json"], capture_output=True, text=True, timeout=30).stdout
    return [x for x in json.loads(out or "[]") if x.get("pid")]


def trova(nome, lista):
    return next((x for x in lista if (x.get("name") or "").upper() == nome.upper()), None)


def tty_di(pid):
    try:
        return subprocess.run(["ps", "-o", "tty=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
    except subprocess.SubprocessError:
        return ""


def vivo(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def nome_copia(nome):
    m = re.match(r"^(.*)-(\d+)$", nome)
    return f"{m.group(1)}-{int(m.group(2)) + 1}" if m else f"{nome}-2"


def apri(nome2, cartella, comando, cmd_apri):
    if cmd_apri:
        r = subprocess.run([*cmd_apri, nome2, cartella, comando], capture_output=True, text=True, timeout=60)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    out = osa(["on run argv", 'tell application "Terminal" to return tty of (do script (item 1 of argv))', "end run"],
              f"cd '{cartella}' && {comando}")
    return bool(out), out or "Terminal non risponde"


CERCA = ["on run argv", 'tell application "Terminal"', 'set esito to "assente"', "repeat with w in windows",
         "repeat with t in tabs of w", "if tty of t is (item 1 of argv) then", "if (count of tabs of w) is 1 then",
         'set esito to "una " & (name of w)', "else", 'set esito to "multi"', "end if", "end if", "end repeat",
         "end repeat", "return esito", "end tell", "end run"]
CHIUDI = ["on run argv", 'tell application "Terminal"', "repeat with w in windows",
          "if (count of tabs of w) is 1 and tty of tab 1 of w is (item 1 of argv) then close w saving no",
          "end repeat", "end tell", "end run"]
TERMINA = ["on run argv", 'tell application "System Events" to tell process "Terminal"',
           "set f to (first window whose name is (item 1 of argv))", "try", 'click button "Terminate" of sheet 1 of f',
           "on error", 'click button "Termina" of sheet 1 of f', "end try", "end tell", "end run"]


def chiudi(tty):
    """Chiude la sola scheda di tty se è sola nella sua finestra. → (ok, messaggio)."""
    t = "/dev/" + tty.replace("/dev/", "")
    r = osa(CERCA, t)
    if r is None:
        return False, "Terminal non risponde"
    if r == "assente":
        return True, "scheda già chiusa"
    if r == "multi":
        return False, f"{tty} sta in una finestra con altre schede: non chiusa"
    osa(CHIUDI, t)
    time.sleep(1)
    osa(TERMINA, r[4:])
    return True, "chiusura chiesta"


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 1
    nome, prova, cmd_apri, avvio = argv[0], "--prova" in argv, [], None
    i = 1
    while i < len(argv):
        if argv[i] == "--apri" and i + 1 < len(argv):
            cmd_apri.append(argv[i + 1])
            i += 1
        elif argv[i] == "--avvio" and i + 1 < len(argv):
            avvio = argv[i + 1]
            i += 1
        i += 1
    try:
        lista = sessioni()
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print(f"claude agents non risponde: {e}")
        return 1
    s = trova(nome, lista)
    if not s:
        print(f"{nome}: nessuna sessione viva con questo nome")
        return 3
    nome2 = nome_copia(nome)
    if trova(nome2, lista):
        print(f"{nome2} esiste già: nessuna nuova copia")
        return 5
    pid, cartella, tty = s["pid"], s.get("cwd") or CASA, tty_di(s["pid"])
    comando = f"{CLAUDE} -n {nome2} --disallowedTools=AskUserQuestion \"{avvio or '/riparti ' + nome}\""
    if prova:
        print(f"(prova) aprirei {nome2} in {cartella}: {comando}")
        print(f"(prova) poi chiuderei {nome} (pid {pid}, {tty}) se sola nella sua finestra")
        return 0
    ok, msg = apri(nome2, cartella, comando, cmd_apri)
    registra(f"{nome} → {nome2}: apertura {'ok' if ok else 'fallita'} {msg!r}")
    fine = time.time() + ATTESA_COPIA_S
    while time.time() < fine and not trova(nome2, sessioni()):
        time.sleep(5)
    if not trova(nome2, sessioni()):
        print(f"{nome2} non è partita entro {ATTESA_COPIA_S} s: {nome} resta aperta")
        registra(f"{nome2} non partita")
        return 4
    if not vivo(pid) or tty_di(pid) != tty:
        print(f"{nome2} aperta; {nome} si era già chiusa")
        return 0
    ok, msg = chiudi(tty)
    registra(f"chiudi {nome} {tty}: {msg}")
    time.sleep(20)
    if vivo(pid):
        print(f"{nome2} aperta, ma {nome} è ancora aperta ({msg})")
        return 2
    print(f"{nome2} aperta e {nome} chiusa: ne resta una")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
