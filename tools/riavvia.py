#!/usr/bin/env python3
"""Riavvio sicuro di una sessione Claude in una scheda di Terminal (dopo /passaggio).

Sostituisce $TMPDIR/riavvia.sh e /tmp/t.scpt, che scrivevano «/exit», «2» o «/clear» nella scheda anche mentre la
sessione lavorava: il testo entrava in coda e un /clear cancellava il contesto senza nota (utente 11/11 15:31:
«stavo per mandare un clear durante i lavori in corso, ti avrebbe riavviato? se sì devi impedirlo»).

Uso:
  riavvia.py NOME TTY CARTELLA                 agente: /exit, poi  cd CARTELLA && claude -n NOME … "/riparti NOME"
  riavvia.py SUPERAGENTE TTY --sup             SUP: /clear, poi "/riparti superagente" (stessa sessione)
  opzioni:  --attendi MIN   aspetta fino a MIN minuti che le guardie siano verdi (al posto dei vecchi «until … sleep»)
            --prova         controlla e dice cosa farebbe, senza scrivere niente nella scheda

Guardie (tutte, ricontrollate subito prima di ogni invio):
  a. la nota ~/.claude/passaggi/NOME.md esiste ed è di meno di 10 minuti fa;
  b. la sessione NOME è ferma (claude agents --json: status idle) e il suo processo sta proprio su TTY;
  c. al massimo un riavvio per scheda ogni 5 minuti (file di blocco ~/.claude/consumo/riavvii/<tty>.json);
  d. nessun altro riavvio in attesa per la stessa scheda (ps: altri riavvia.py o il vecchio riavvia.sh).
Una guardia rossa = niente invio, motivo stampato e scritto in ~/.claude/consumo/riavvii.log (uscita 2).
"""
import json, os, subprocess, sys, time

CASA = os.path.expanduser("~")
PASSAGGI = os.path.join(CASA, ".claude", "passaggi")
BLOCCHI = os.path.join(CASA, ".claude", "consumo", "riavvii")
LOG = os.path.join(CASA, ".claude", "consumo", "riavvii.log")
NOTA_MAX_S = 10 * 60
BLOCCO_S = 5 * 60

APPLESCRIPT = [  # testo e tty passati come argomenti: niente testo dentro il codice AppleScript
    "on run argv",
    'tell application "Terminal"',
    "repeat with w in windows",
    "repeat with t in tabs of w",
    "if tty of t is (item 1 of argv) then",
    "do script (item 2 of argv) in t",
    'return "ok"',
    "end if",
    "end repeat",
    "end repeat",
    "end tell",
    'return "scheda non trovata"',
    "end run",
]


def ora():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def registra(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{ora()} {msg}\n")


def tty_corto(t):
    return t.replace("/dev/", "").strip()


def g_nota(nome):
    p = os.path.join(PASSAGGI, f"{nome}.md")
    if not os.path.exists(p):
        return f"nota {p} assente (prima /passaggio)"
    eta = time.time() - os.path.getmtime(p)
    return None if eta <= NOTA_MAX_S else f"nota {nome}.md vecchia di {int(eta // 60)} min (serve < 10)"


def sessione(nome):
    try:
        out = subprocess.run(["claude", "agents", "--json"], capture_output=True, text=True, timeout=30).stdout
        return [x for x in json.loads(out or "[]") if (x.get("name") or "").upper() == nome.upper() and x.get("pid")]
    except Exception as e:  # noqa: BLE001
        return e


def tty_di(pid):
    try:
        return subprocess.run(["ps", "-o", "tty=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def g_ferma(nome, tty):
    s = sessione(nome)
    if isinstance(s, Exception):
        return f"claude agents non risponde ({s})"
    su_tty = [x for x in s if tty_di(x["pid"]) == tty_corto(tty)]
    if not su_tty:
        dove = ", ".join(tty_di(x["pid"]) or "?" for x in s) or "nessuna"
        return f"nessuna sessione {nome} su {tty_corto(tty)} (trovate su: {dove})"
    busy = [x for x in su_tty if x.get("status") != "idle"]
    return f"{nome} sta lavorando (status {busy[0].get('status')}): niente invio" if busy else None


def g_blocco(tty):
    p = os.path.join(BLOCCHI, tty_corto(tty) + ".json")
    try:
        with open(p, encoding="utf-8") as f:
            prima = json.load(f)
        eta = time.time() - prima.get("t", 0)
        if eta < BLOCCO_S:
            return f"già un riavvio su {tty_corto(tty)} {int(eta)} s fa ({prima.get('nome')}): aspetta 5 min"
    except (OSError, ValueError):
        pass
    return None


def blocca(tty, nome):
    os.makedirs(BLOCCHI, exist_ok=True)
    with open(os.path.join(BLOCCHI, tty_corto(tty) + ".json"), "w", encoding="utf-8") as f:
        json.dump({"t": time.time(), "ora": ora(), "nome": nome}, f)


def antenati():
    pids, p = set(), os.getpid()
    while p > 1 and p not in pids:
        pids.add(p)
        try:
            p = int(subprocess.run(["ps", "-o", "ppid=", "-p", str(p)], capture_output=True, text=True, timeout=5).stdout.strip() or 0)
        except (ValueError, subprocess.SubprocessError):
            break
    return pids


def g_altri(tty):
    try:
        ps = subprocess.run(["ps", "-A", "-ww", "-o", "pid=,command="], capture_output=True, text=True, timeout=5).stdout
    except subprocess.SubprocessError:
        return "ps non risponde"
    miei, t = antenati(), tty_corto(tty)
    for riga in ps.splitlines():
        pid, _, cmd = riga.strip().partition(" ")
        if not pid.isdigit() or int(pid) in miei:
            continue
        if ("riavvia.py" in cmd or "riavvia.sh" in cmd) and (f"/dev/{t}" in cmd or f" {t}" in cmd):
            return f"altro riavvio in attesa per {t}: pid {pid}"
    return None


def guardie(nome, tty, *, nota=True):
    for g in ([lambda: g_nota(nome)] if nota else []) + [lambda: g_ferma(nome, tty), lambda: g_blocco(tty), lambda: g_altri(tty)]:
        motivo = g()
        if motivo:
            return motivo
    return None


def scrivi(tty, testo, prova):
    if prova:
        print(f"  (prova) scriverei in {tty_corto(tty)}: {testo}")
        return True
    r = subprocess.run(["osascript", *[x for riga in APPLESCRIPT for x in ("-e", riga)], "/dev/" + tty_corto(tty), testo],
                       capture_output=True, text=True, timeout=15)
    ok = r.stdout.strip() == "ok"
    registra(f"{tty_corto(tty)} ← {testo!r}: {r.stdout.strip() or r.stderr.strip()}")
    return ok


def claude_su(tty):
    try:
        out = subprocess.run(["ps", "-t", tty_corto(tty), "-o", "command="], capture_output=True, text=True, timeout=5).stdout
    except subprocess.SubprocessError:
        return True
    return any(l.strip().startswith("claude") for l in out.splitlines())


def esci(msg, codice):
    print(msg, file=sys.stderr if codice else sys.stdout)
    sys.exit(codice)


def main(a):
    if len(a) < 2 or a[0] in ("-h", "--help"):
        esci(__doc__, 0 if a else 1)
    prova, sup = "--prova" in a, "--sup" in a
    attendi = 0
    if "--attendi" in a:
        i = a.index("--attendi")
        attendi = float(a[i + 1])
        del a[i:i + 2]
    a = [x for x in a if x not in ("--prova", "--sup")]
    nome, tty = a[0].upper(), a[1]
    cartella = a[2] if len(a) > 2 else None
    if not sup and not cartella:
        esci("manca CARTELLA (per il SUP: --sup)", 1)
    if sup and nome != "SUPERAGENTE":
        esci("--sup solo con SUPERAGENTE", 1)

    fine = time.time() + attendi * 60
    while True:
        motivo = guardie(nome, tty)
        if not motivo:
            break
        if time.time() >= fine:
            registra(f"RIFIUTATO {nome} {tty_corto(tty)}: {motivo}")
            esci(f"NIENTE RIAVVIO di {nome}: {motivo}", 2)
        time.sleep(10)

    if not prova:
        blocca(tty, nome)
    if sup:
        if not scrivi(tty, "/clear", prova):
            esci("scheda non trovata: niente riavvio", 2)
        time.sleep(0 if prova else 6)
        # dopo /clear la sessione è vuota e ferma: ricontrollo solo che sia ferma e ancora lì
        motivo = None if prova else g_ferma(nome, tty)
        if motivo:
            registra(f"DOPO /clear {nome}: {motivo}")
            esci(f"/clear mandato, ma «/riparti» no: {motivo}", 2)
        scrivi(tty, "/riparti superagente", prova)
        registra(f"RIAVVIATO {nome} {tty_corto(tty)}{' (prova)' if prova else ''}")
        esci(f"{nome} riavviato su {tty_corto(tty)}{' (prova)' if prova else ''}", 0)

    if not scrivi(tty, "/exit", prova):
        esci("scheda non trovata: niente riavvio", 2)
    for _ in range(0 if prova else 15):
        time.sleep(1)
        if not claude_su(tty):
            break
    if not prova and claude_su(tty):
        # niente «2» alla cieca (il vecchio script lo scriveva: se la sessione era viva diventava un prompt)
        registra(f"ANCORA VIVA {nome} {tty_corto(tty)} dopo /exit")
        esci(f"{nome} ancora viva dopo /exit: guarda la scheda {tty_corto(tty)}", 2)
    q = cartella.replace("'", "'\\''")
    scrivi(tty, f"cd '{q}' && claude -n {nome} --disallowedTools=AskUserQuestion \"/riparti {nome}\"", prova)
    registra(f"RIAVVIATO {nome} {tty_corto(tty)}{' (prova)' if prova else ''}")
    esci(f"{nome} riavviato su {tty_corto(tty)}{' (prova)' if prova else ''}", 0)


if __name__ == "__main__":
    main(sys.argv[1:])
