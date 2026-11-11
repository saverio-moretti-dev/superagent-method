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
  a. la nota ~/.claude/passaggi/NOME.md esiste ed è stata scritta al più 10 minuti prima del LANCIO dello script
     (con --attendi l'età si misura sulla partenza, non su adesso: 11/11 17:43 la nota «scadeva» durante l'attesa);
  b. la sessione NOME è ferma e il suo processo sta proprio su TTY. Ferma = status idle in claude agents --json,
     OPPURE status busy ma la trascrizione dice turno finito (ultima voce = fine turno, file fermo da 20 s):
     claude agents dà «busy» per tutto il tempo in cui un comando in sottofondo è vivo (misurato 11/11 17:46-17:50:
     SUP fermo, http.server 4322 lanciato prima di un /clear → busy per 4 min; ogni riavvio del SUP rifiutato);
  c. al massimo un riavvio per scheda ogni 5 minuti (file di blocco ~/.claude/consumo/riavvii/<tty>.json);
  d. nessun altro riavvio in attesa per la stessa scheda (ps: altri riavvia.py o il vecchio riavvia.sh).
Una guardia rossa = niente invio, motivo stampato e scritto in ~/.claude/consumo/riavvii.log (uscita 2).
Con --attendi ogni CAMBIO di guardia rossa si scrive nel log con l'ora (ATTESA …), così si vede perché non è partito.
"""
import glob, json, os, subprocess, sys, time

CASA = os.path.expanduser("~")
PASSAGGI = os.path.join(CASA, ".claude", "passaggi")
BLOCCHI = os.path.join(CASA, ".claude", "consumo", "riavvii")
LOG = os.path.join(CASA, ".claude", "consumo", "riavvii.log")
NOTA_MAX_S = 10 * 60
BLOCCO_S = 5 * 60
QUIETE_S = 20          # trascrizione ferma da almeno tanto per credere al «turno finito»
FINE_TURNO = ("turn_duration", "stop_hook_summary")
SOLO_DATI = {"last-prompt", "tools-used", "bridge-session", "file-history-snapshot", "summary", "custom-title",
             "ai-title", "agent-name", "mode", "session-owner", "cost-state", "atis-latch"}  # voci che non sono lavoro; ogni altro tipo (anche sconosciuto) conta come lavoro

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


def g_nota(nome, t0=None):
    p = os.path.join(PASSAGGI, f"{nome}.md")
    if not os.path.exists(p):
        return f"nota {p} assente (prima /passaggio)"
    eta = (time.time() if t0 is None else t0) - os.path.getmtime(p)
    return None if eta <= NOTA_MAX_S else f"nota {nome}.md scritta {int(eta // 60)} min prima del lancio (serve < 10)"


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


def _locale(d):
    """Voce «utente» che è solo il segno di un comando locale (/clear, /model…): non apre un turno."""
    c = (d.get("message") or {}).get("content") if isinstance(d.get("message"), dict) else None
    if isinstance(c, list):
        c = " ".join(b.get("text", "") for b in c if isinstance(b, dict))
    return isinstance(c, str) and any(k in c for k in ("<local-command-caveat>", "<command-name>", "<local-command-stdout>"))


def stato_voci(voci, dopo_clear=False):
    """UNICA regola (11/11): (True, perché) se dalle voci della trascrizione nessun turno è in corso.
    Dal fondo, saltando i soli metadati: fine turno (turn_duration/stop_hook_summary) o comando locale finito
    (system local_command, con le sue voci «utente» di comando) = ferma; qualunque altra voce, anche sconosciuta
    (user, assistant, queue-operation, attachment, api-request…, scheduled_task_fire del cron) = al lavoro.
    Nessuna voce: ferma solo subito dopo un /clear (sessione nuova vuota), altrimenti non dimostrabile."""
    for d in reversed(voci):
        t = d.get("type")
        if t in SOLO_DATI:
            continue
        if t == "system" and d.get("subtype") in FINE_TURNO:
            return True, "turno finito"
        if t == "system" and d.get("subtype") == "local_command":
            return True, "comando locale finito (es. /clear), nessun turno aperto"
        if t == "user" and _locale(d):
            continue
        return False, f"ultima voce della trascrizione: {t} {d.get('subtype') or ''}".strip()
    return (True, "trascrizione vuota dopo /clear") if dopo_clear else (False, "nessuna voce leggibile")


def trascrizione(sid):
    f = glob.glob(os.path.join(CASA, ".claude", "projects", "*", f"{sid}.jsonl")) if sid else []
    return f[0] if f else None


def turno_finito(sid, dopo_clear=False):
    """stato_voci sulla coda della trascrizione, solo se il file è fermo da QUIETE_S."""
    f = trascrizione(sid)
    if not f:
        return (True, "trascrizione non ancora creata dopo /clear") if dopo_clear else (False, "trascrizione non trovata")
    ferma = time.time() - os.path.getmtime(f)
    if ferma < QUIETE_S:
        return False, f"trascrizione scritta {int(ferma)} s fa"
    with open(f, "rb") as h:
        h.seek(max(0, os.path.getsize(f) - 262144))
        righe = h.read().decode("utf-8", "replace").splitlines()
    voci = []
    for r in righe:
        try:
            voci.append(json.loads(r))
        except ValueError:
            continue
    ok, perche = stato_voci(voci, dopo_clear)
    return ok, f"{perche}, ferma da {int(ferma)} s" if ok else perche


def g_ferma(nome, tty, dopo_clear=False):
    s = sessione(nome)
    if isinstance(s, Exception):
        return f"claude agents non risponde ({s})"
    su_tty = [x for x in s if tty_di(x["pid"]) == tty_corto(tty)]
    if not su_tty:
        dove = ", ".join(tty_di(x["pid"]) or "?" for x in s) or "nessuna"
        return f"nessuna sessione {nome} su {tty_corto(tty)} (trovate su: {dove})"
    for x in su_tty:
        if x.get("status") == "idle":
            continue
        # busy: claude agents lo dice anche da ferma se un comando in sottofondo è vivo → decide la trascrizione
        ok, perche = turno_finito(x.get("sessionId"), dopo_clear)
        if not ok:
            return f"{nome} sta lavorando (status {x.get('status')}; {perche}): niente invio"
    return None


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


def sid_su(nome, tty):
    """Id della sessione NOME su quel tty (None se non c'è o claude agents non risponde)."""
    s = sessione(nome)
    if isinstance(s, Exception):
        return None
    return next((x.get("sessionId") for x in s if tty_di(x["pid"]) == tty_corto(tty)), None)


def superato(nome, tty, sid0, t0):
    """L'attesa non serve più: la nota è già stata letta da un /riparti dopo la partenza (NOME.letta.md più nuova)
    o su quel tty gira un'altra sessione NOME. Senza, un'attesa vecchia resta viva fino alla scadenza."""
    letta = os.path.join(PASSAGGI, f"{nome}.letta.md")
    if not os.path.exists(os.path.join(PASSAGGI, f"{nome}.md")) and os.path.exists(letta) and os.path.getmtime(letta) > t0:
        return f"nota {nome}.md già letta dopo la partenza (riavvio fatto da altri)"
    sid = sid_su(nome, tty)
    if sid0 and sid and sid != sid0:
        return f"su {tty_corto(tty)} gira già un'altra sessione {nome}"
    return None


def guardie(nome, tty, *, nota=True, t0=None):
    for g in ([lambda: g_nota(nome, t0)] if nota else []) + [lambda: g_ferma(nome, tty), lambda: g_blocco(tty), lambda: g_altri(tty)]:
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

    t0 = time.time()
    fine = t0 + attendi * 60
    sid0 = sid_su(nome, tty) if attendi else None
    prima = None
    while True:
        motivo = guardie(nome, tty, t0=t0)
        tipo = "".join(c for c in (motivo or "") if not c.isdigit())  # «scritta 8 s fa» e «19 s fa» = stessa guardia
        if attendi and tipo != prima:  # ogni cambio di guardia nel log, con l'ora
            registra(f"ATTESA {nome} {tty_corto(tty)}: {motivo or 'guardie verdi'}")
            prima = tipo
        if not motivo:
            break
        oltre = attendi and superato(nome, tty, sid0, t0)
        if oltre:
            registra(f"SUPERATO {nome} {tty_corto(tty)}: {oltre}")
            esci(f"NIENTE RIAVVIO di {nome}: {oltre}", 3)
        if time.time() >= fine:
            registra(f"RIFIUTATO {nome} {tty_corto(tty)}: {motivo}")
            esci(f"NIENTE RIAVVIO di {nome}: {motivo}", 2)
        time.sleep(10)

    if not prova:
        blocca(tty, nome)
    if sup:
        if not scrivi(tty, "/clear", prova):
            esci("scheda non trovata: niente riavvio", 2)
        # dopo /clear la sessione è vuota e ferma: ricontrollo solo che sia ferma e ancora lì (fino a 30 s:
        # la trascrizione del /clear deve restare ferma QUIETE_S prima di crederle)
        motivo = None
        for _ in range(0 if prova else 6):
            time.sleep(6)
            motivo = g_ferma(nome, tty, dopo_clear=True)
            if not motivo:
                break
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
