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
  d. nessun altro riavvio in attesa per la stessa scheda (ps: altri riavvia.py o il vecchio riavvia.sh);
  g. (12/11) nessun sotto-agente vivo o dubbio (<sid>/subagents/*: non «finished» e scritto da < 30 min) e, prima di
     /exit, nessun comando in sottofondo (figli del processo claude, esclusi caffeinate/MCP/LSP): con uno vivo /exit
     apre «Background work is running», e un tasto scritto dopo può chiudere la sessione. Se la finestra compare
     comunque: uscita 6, niente scritto.
Dopo /clear (--sup) basta una quiete di QUIETE_CLEAR_S se la trascrizione nuova ha solo /clear + hook (era ~21 s).
Una guardia rossa = niente invio, motivo stampato e scritto in ~/.claude/consumo/riavvii.log (uscita 2).
Con --attendi ogni CAMBIO di guardia rossa si scrive nel log con l'ora (ATTESA …), così si vede perché non è partito.

Casella d'ingresso e verifica (fallimento dell'11/11 19:40, causa dimostrata su sessione di prova):
  `do script` scrive testo + invio IN CODA a quello che c'è già nella casella: con «rit» già scritto, «/clear»
  è diventato il messaggio normale «rit/clear», il contesto è rimasto, e «/riparti» è partito sul contesto vecchio.
  Quindi, prima di ogni comando:
  e. la casella si svuota con Ctrl-K + Ctrl-U ripetuti (misurato: svuotano anche più righe col cursore in mezzo
     ed escono dal modo shell «!») e si scrive un segno; si legge lo schermo della scheda e il segno deve essere
     da solo nella casella. Blocchi corti: oltre ~60 caratteri in un solo `do script` Claude Code lo prende come
     incolla (i tasti di controllo diventano testo e l'invio non manda);
  f. ogni comando si VERIFICA: /clear = sessionId nuovo sul processo di quel tty (claude agents) + nuova
     trascrizione con la voce <command-name>/clear</command-name>; /riparti = voce <command-name>/riparti</command-name>
     nella trascrizione nuova. Un /clear scritto mentre la sessione lavora (cron, messaggi) resta in coda e parte
     a fine turno: si aspetta finché è occupata. /clear non riuscito: un solo nuovo tentativo, poi uscita 4 e
     niente /riparti (MAI /riparti sul contesto vecchio). /riparti non arrivato: un nuovo tentativo, poi uscita 5.
  Il log scrive l'esito misurato (CLEAR OK sid vecchio → nuovo, RIPARTI OK, oppure FALLITO e perché).

Variabili d'ambiente (solo per le prove; senza, valori normali):
  RIAVVIA_BLOCCO_S=N      blocco per scheda in secondi (normale 300) — 10 riavvii di fila nelle prove
  RIAVVIA_NOTA_MAX_S=N    età massima della nota in secondi (normale 600)
  RIAVVIA_PROVA=1         consente --sup su una sessione di prova il cui nome comincia per PROVA-
                          (manda «/riparti <nome in minuscolo>», come «/riparti superagente» per il SUP)
"""
import glob, json, os, subprocess, sys, time

CASA = os.path.expanduser("~")
PASSAGGI = os.path.join(CASA, ".claude", "passaggi")
BLOCCHI = os.path.join(CASA, ".claude", "consumo", "riavvii")
LOG = os.path.join(CASA, ".claude", "consumo", "riavvii.log")
NOTA_MAX_S = int(os.environ.get("RIAVVIA_NOTA_MAX_S") or 10 * 60)
BLOCCO_S = int(os.environ.get("RIAVVIA_BLOCCO_S") or 5 * 60)
SVUOTA = "\x0b\x15"          # Ctrl-K + Ctrl-U: cancella a destra e a sinistra del cursore (a inizio/fine riga unisce)
SEGNO = "QZXRIAVVIO"         # segno scritto dopo lo svuotamento: deve restare da solo nella casella
ATTESA_OCCUPATA_S = 600      # quanto aspettare che un comando in coda parta, se la sessione lavora
QUIETE_S = 20          # trascrizione ferma da almeno tanto per credere al «turno finito»
QUIETE_CLEAR_S = 2     # dopo /clear, se la trascrizione nuova ha solo /clear + hook + metadati (nessun turno): basta
                       # questo. Misura 12/11 20:20: QUIETE_S pieno faceva perdere ~21 s fra «CLEAR OK» e «/riparti»
                       # (il SUP risulta busy per il riavvia.py stesso in sottofondo; trascrizione ferma da 20:20:47)
SOTTOAGENTE_VIVO_S = 120    # trascrizione di un sotto-agente scritta da meno di tanto e non conclusa = vivo
SOTTOAGENTE_DUBBIO_S = 1800 # non conclusa e scritta da meno di 30 min = dubbio → niente riavvio (D4 del 12/11)
PROCESSI_NORMALI = ("caffeinate", "node", "clangd", "npm", "npx", "uv", "uvx", "python", "python3")  # figli fissi (MCP, LSP)
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
    return None if eta <= NOTA_MAX_S else f"nota {nome}.md scritta {int(eta // 60)} min prima del lancio (serve < {NOTA_MAX_S // 60})"


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
    with open(f, "rb") as h:
        h.seek(max(0, os.path.getsize(f) - 262144))
        righe = h.read().decode("utf-8", "replace").splitlines()
    voci = []
    for r in righe:
        try:
            voci.append(json.loads(r))
        except ValueError:
            continue
    quiete = QUIETE_CLEAR_S if dopo_clear and solo_clear(voci) else QUIETE_S
    if ferma < quiete:
        return False, f"trascrizione scritta {int(ferma)} s fa (serve {quiete} s)"
    ok, perche = stato_voci(voci, dopo_clear)
    return ok, f"{perche}, ferma da {int(ferma)} s" if ok else perche


def solo_clear(voci):
    """True se la trascrizione (nuova, dopo /clear) non ha nessun turno: solo metadati, allegati degli hook
    (SessionStart:clear), voci «utente» di comando locale e la voce system local_command. Basta una voce assistant,
    un messaggio vero o un tipo sconosciuto e torna False (si aspetta la quiete piena)."""
    visto_clear = False
    for d in voci:
        t = d.get("type")
        if t in SOLO_DATI or t == "attachment" or t == "artifact-comment-monitor":
            continue
        if t == "system" and d.get("subtype") == "local_command":
            visto_clear = True
            continue
        if t == "user" and _locale(d):
            continue
        return False
    return visto_clear


def sottoagenti(sid):
    """(vivi, dubbi): sotto-agenti della sessione sid dalle loro trascrizioni <sid>/subagents/*.jsonl.
    Concluso = .meta.json con finished true, oppure ultima voce assistant con stop_reason end_turn. Non concluso e scritto da < SOTTOAGENTE_VIVO_S = vivo;
    non concluso e scritto da < SOTTOAGENTE_DUBBIO_S = dubbio. claude agents non li lega al padre (D4, 12/11)."""
    f = trascrizione(sid)
    if not f:
        return [], []
    vivi, dubbi = [], []
    for s in glob.glob(os.path.join(f[:-len(".jsonl")], "subagents", "*.jsonl")):
        eta = time.time() - os.path.getmtime(s)
        if eta >= SOTTOAGENTE_DUBBIO_S:
            continue
        try:  # <agente>.meta.json ha "finished": true a lavoro concluso (visto 12/11 23:17): segnale più sicuro
            with open(s[:-len(".jsonl")] + ".meta.json", encoding="utf-8") as h:
                if json.load(h).get("finished") is True:
                    continue
        except (OSError, ValueError):
            pass
        ultima = None
        try:
            with open(s, "rb") as h:
                h.seek(max(0, os.path.getsize(s) - 65536))
                for r in h.read().decode("utf-8", "replace").splitlines():
                    try:
                        d = json.loads(r)
                    except ValueError:
                        continue
                    if d.get("type") in ("user", "assistant"):
                        ultima = d
        except OSError:
            continue
        m = (ultima or {}).get("message") or {}
        if ultima and ultima.get("type") == "assistant" and isinstance(m, dict) and m.get("stop_reason") == "end_turn":
            continue
        nome = os.path.basename(s)[:-len(".jsonl")]
        (vivi if eta < SOTTOAGENTE_VIVO_S else dubbi).append(f"{nome} ({int(eta)} s)")
    return vivi, dubbi


def figli_lavoro(pid):
    """Processi figli della sessione che sono lavoro in sottofondo (comandi della shell, Monitor…), esclusi i fissi
    (caffeinate, server MCP, LSP). Con uno di questi vivo /exit apre «Background work is running» (bug 12/11)."""
    try:
        out = subprocess.run(["pgrep", "-lP", str(pid)], capture_output=True, text=True, timeout=5).stdout
    except subprocess.SubprocessError:
        return ["pgrep non risponde"]
    figli = []
    for riga in out.splitlines():
        p, _, nome = riga.strip().partition(" ")
        if nome and os.path.basename(nome) not in PROCESSI_NORMALI:
            figli.append(f"{nome} {p}")
    return figli


def g_sottofondo(nome, tty, uscita):
    """Rossa se la sessione ha sotto-agenti vivi o dubbi (sempre) o, prima di /exit, comandi in sottofondo vivi."""
    s = sessione(nome)
    if isinstance(s, Exception):
        return f"claude agents non risponde ({s})"
    for x in s:
        if tty_di(x["pid"]) != tty_corto(tty):
            continue
        vivi, dubbi = sottoagenti(x.get("sessionId"))
        if vivi:
            return f"{nome} ha sotto-agenti vivi: {', '.join(vivi)}"
        if dubbi:
            return f"{nome} ha sotto-agenti forse vivi (non conclusi): {', '.join(dubbi)} — nel dubbio niente riavvio"
        if uscita:
            f = figli_lavoro(x["pid"])
            if f:
                return f"{nome} ha lavoro in sottofondo ({', '.join(f)}): /exit aprirebbe «Background work is running» — prima TaskStop"
    return None


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
            return f"già un riavvio su {tty_corto(tty)} {int(eta)} s fa ({prima.get('nome')}): aspetta {BLOCCO_S} s"
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


def e_riavvio(cmd):
    """Vero solo se il processo È riavvia.py/riavvia.sh (interprete + script, o lo script stesso), non una shell
    genitrice che lo nomina nella riga di comando (zsh -c «… riavvia.py … ttys001»: bloccò 6 min il SUP il 13/11 19:40)."""
    p = cmd.split()
    if not p:
        return False
    if p[0].endswith(("riavvia.py", "riavvia.sh")):
        return True
    base = os.path.basename(p[0]).lower()
    if not (base.startswith("python") or base in ("bash", "sh")):
        return False
    script = next((x for x in p[1:] if not x.startswith("-")), "")
    return script.endswith(("riavvia.py", "riavvia.sh"))


assert e_riavvio("/opt/homebrew/bin/python3 /x/tools/riavvia.py --sup --attendi 3 /dev/ttys001")
assert e_riavvio("/Library/Frameworks/Python.framework/Versions/3.15/Resources/Python.app/Contents/MacOS/Python -u /x/riavvia.py ttys001")
assert e_riavvio("/bin/bash /tmp/riavvia.sh ttys001")
assert not e_riavvio("/bin/zsh -c source /x/snap.sh && python3 /x/riavvia.py --sup ttys001")
assert not e_riavvio("grep riavvia.py ttys001")


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
        if e_riavvio(cmd) and (f"/dev/{t}" in cmd or f" {t}" in cmd):
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


def guardie(nome, tty, *, nota=True, t0=None, uscita=False):
    for g in ([lambda: g_nota(nome, t0)] if nota else []) + [lambda: g_ferma(nome, tty), lambda: g_sottofondo(nome, tty, uscita),
                                                             lambda: g_blocco(tty), lambda: g_altri(tty)]:
        motivo = g()
        if motivo:
            return motivo
    return None


def scrivi(tty, testo, prova, svuota=0):
    """do script nella scheda: SVUOTA×svuota, poi testo, poi invio (l'invio lo aggiunge Terminal)."""
    if prova:
        print(f"  (prova) scriverei in {tty_corto(tty)}: {testo}")
        return True
    r = subprocess.run(["osascript", *[x for riga in APPLESCRIPT for x in ("-e", riga)], "/dev/" + tty_corto(tty),
                        SVUOTA * svuota + testo], capture_output=True, text=True, timeout=15)
    ok = r.stdout.strip() == "ok"
    registra(f"{tty_corto(tty)} ← {testo!r}: {r.stdout.strip() or r.stderr.strip()}")
    return ok


LEGGI_SCHEDA = [
    "on run argv",
    'tell application "Terminal"',
    "repeat with w in windows",
    "repeat with t in tabs of w",
    "if tty of t is (item 1 of argv) then",
    "set c to history of t",
    "return c",
    "end if",
    "end repeat",
    "end repeat",
    "end tell",
    'return ""',
    "end run",
]


def leggi_schermo(tty):
    """Righe della storia della scheda (lista vuota se non si legge)."""
    try:
        r = subprocess.run(["osascript", *[x for riga in LEGGI_SCHEDA for x in ("-e", riga)], "/dev/" + tty_corto(tty)],
                           capture_output=True, text=True, timeout=15)
    except subprocess.SubprocessError:
        return []
    return r.stdout.splitlines()


def leggi_casella(tty):
    """Righe della casella d'ingresso come appaiono ora sullo schermo della scheda (None se non si legge):
    dall'ultima riga che comincia con «❯» fino al bordo «───» sotto."""
    righe = leggi_schermo(tty)
    inizio = max((i for i, l in enumerate(righe) if l.startswith("❯")), default=None)
    if inizio is None:
        return None
    casella = [righe[inizio][1:]]
    for l in righe[inizio + 1:]:
        if l.startswith("──"):
            return casella
        casella.append(l)
    return None


def casella_col_segno(casella):
    """True se nella casella c'è solo il segno (più righe vuote): tutto quello che c'era prima è stato cancellato."""
    return bool(casella) and casella[0].strip() == SEGNO and not any(l.strip() for l in casella[1:])


def pulisci(tty, prova):
    """Svuota la casella e lo dimostra: blocco corto Ctrl-K/Ctrl-U ×8 + segno + «\\» (l'invio di do script diventa
    a capo, non manda), poi lettura dello schermo. Fino a 4 blocchi (8 righe di avanzo l'uno). Non manda niente."""
    if prova:
        print(f"  (prova) svuoterei la casella di {tty_corto(tty)}")
        return True
    for _ in range(4):
        if not scrivi(tty, SEGNO + "\\", prova, svuota=8):
            return False
        time.sleep(0.8)
        if casella_col_segno(leggi_casella(tty)):
            return True
    return False


def comando(tty, testo, prova):
    """Casella svuotata e verificata, poi il comando DA SOLO (il segno e l'a capo si cancellano nello stesso blocco)."""
    if not pulisci(tty, prova):
        registra(f"{tty_corto(tty)}: casella non svuotata (segno non visto sullo schermo): {testo!r} NON mandato")
        return False
    return scrivi(tty, testo, prova, svuota=8)  # 8 coppie: cancella anche ciò che qualcuno scrive fra lettura e invio


def voci_di(sid):
    f = trascrizione(sid)
    if not f:
        return []
    out = []
    with open(f, encoding="utf-8", errors="replace") as h:
        for r in h:
            try:
                out.append(json.loads(r))
            except ValueError:
                continue
    return out


def _quando(d):
    try:
        from datetime import datetime
        return datetime.fromisoformat(d.get("timestamp", "").replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def esito_comando(sid, nome_cmd, t_invio, testo=None):
    """Nella trascrizione sid, dopo t_invio: 'ok' se c'è <command-name>/nome_cmd</command-name>, 'messaggio:<testo>' se
    il testo del comando è arrivato come messaggio normale (il guasto delle 19:40), None se niente ancora."""
    for d in voci_di(sid):
        if d.get("type") != "user":
            continue
        q = _quando(d)
        if q is not None and q < t_invio - 2:
            continue
        c = (d.get("message") or {}).get("content") if isinstance(d.get("message"), dict) else None
        if isinstance(c, list):
            c = " ".join(b.get("text", "") for b in c if isinstance(b, dict))
        if not isinstance(c, str):
            continue
        if f"<command-name>/{nome_cmd}</command-name>" in c:
            return "ok"
        if c.rstrip().endswith(testo or f"/{nome_cmd}") and not c.lstrip().startswith("<"):  # «avanzo/clear»
            return "messaggio:" + c[:80]
    return None


def occupata(nome, tty):
    s = sessione(nome)
    if isinstance(s, Exception):
        return True
    return any(x.get("status") not in ("idle", None) for x in s if tty_di(x["pid"]) == tty_corto(tty))


def attendi_clear(nome, tty, sid0, t_invio):
    """(sid nuovo, None) se il /clear è partito davvero; (None, motivo) se no. Aspetta finché la sessione è occupata
    (il /clear resta in coda e parte a fine turno), poi 20 s di sessione ferma senza segni = non partito."""
    fine, ferma_da = time.time() + ATTESA_OCCUPATA_S, None
    while time.time() < fine:
        time.sleep(2)
        sid = sid_su(nome, tty)
        if sid and sid != sid0 and esito_comando(sid, "clear", t_invio) == "ok":
            return sid, None
        guasto = esito_comando(sid0, "clear", t_invio, "/clear")
        if guasto and guasto.startswith("messaggio:"):
            return None, f"/clear arrivato come messaggio normale ({guasto[10:]!r}): contesto NON svuotato"
        if occupata(nome, tty):
            ferma_da = None
            continue
        ferma_da = ferma_da or time.time()
        if time.time() - ferma_da >= 20:
            return None, f"sessione ferma, sessionId ancora {(sid or '?')[:8]}: /clear non partito"
    return None, f"dopo {ATTESA_OCCUPATA_S} s nessun /clear partito"


def attendi_comando(nome, tty, sid, nome_cmd, t_invio, testo=None):
    """None se /nome_cmd è partito come comando nella sessione sid, altrimenti il motivo (stessa attesa di sopra)."""
    fine, ferma_da = time.time() + ATTESA_OCCUPATA_S, None
    while time.time() < fine:
        time.sleep(2)
        e = esito_comando(sid, nome_cmd, t_invio, testo)
        if e == "ok":
            return None
        if e:
            return f"/{nome_cmd} arrivato come messaggio normale ({e[10:]!r})"
        if occupata(nome, tty):
            ferma_da = None
            continue
        ferma_da = ferma_da or time.time()
        if time.time() - ferma_da >= 20:
            return f"/{nome_cmd} non visto nella trascrizione {sid[:8]}"
    return f"dopo {ATTESA_OCCUPATA_S} s /{nome_cmd} non visto"


def attendi_ferma(nome, tty, dopo_clear, secondi):
    """Aspetta che la sessione sia ferma. Ogni CAMBIO di motivo va nel log con l'ora (debito 12/11 20:21: senza, i
    21 s persi dopo /clear non avevano spiegazione). Dopo /clear si ricontrolla ogni secondo, prima ogni 5."""
    motivo, prima, t_in = None, None, time.time()
    fine = t_in + secondi
    while time.time() < fine:
        motivo = g_ferma(nome, tty, dopo_clear=dopo_clear)
        if not motivo:
            if prima:
                registra(f"FERMA {nome} {tty_corto(tty)} dopo {time.time() - t_in:.1f} s")
            return None
        tipo = "".join(c for c in motivo if not c.isdigit())
        if tipo != prima:
            registra(f"ATTESA {'DOPO /clear ' if dopo_clear else ''}{nome} {tty_corto(tty)}: {motivo}")
            prima = tipo
        time.sleep(1 if dopo_clear else 5)
    return motivo or "tempo scaduto"


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
    if sup and nome != "SUPERAGENTE" and not (os.environ.get("RIAVVIA_PROVA") == "1" and nome.startswith("PROVA-")):
        esci("--sup solo con SUPERAGENTE (o con RIAVVIA_PROVA=1 su una sessione PROVA-…)", 1)

    t0 = time.time()
    fine = t0 + attendi * 60
    sid0 = sid_su(nome, tty) if attendi else None
    prima = None
    while True:
        motivo = guardie(nome, tty, t0=t0, uscita=not sup)
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
        riparti = f"/riparti {nome.lower()}"
        if prova:
            comando(tty, "/clear", prova)
            comando(tty, riparti, prova)
            esci(f"{nome}: prova, niente scritto", 0)
        sid0, sid1, perche = sid_su(nome, tty), None, None
        for n in (1, 2):
            if n == 2:  # nuovo tentativo solo a sessione ferma e ancora sul contesto vecchio
                m = attendi_ferma(nome, tty, False, 300)
                if m:
                    perche = f"{perche}; secondo tentativo non fatto: {m}"
                    break
            t_invio = time.time()
            if not comando(tty, "/clear", prova):
                perche = "casella non svuotata o scheda non trovata"
                continue
            sid1, perche = attendi_clear(nome, tty, sid0, t_invio)
            if sid1:
                break
            registra(f"CLEAR NON RIUSCITO {nome} {tty_corto(tty)} (tentativo {n}): {perche}")
        if not sid1:
            registra(f"FALLITO {nome} {tty_corto(tty)}: /clear non partito ({perche}); /riparti NON mandato")
            esci(f"RIAVVIO FALLITO di {nome}: /clear non partito ({perche}). /riparti non mandato: contesto vecchio.", 4)
        registra(f"CLEAR OK {nome} {tty_corto(tty)}: sessione {(sid0 or '?')[:8]} → {sid1[:8]}")
        for n in (1, 2):
            motivo = attendi_ferma(nome, tty, True, 300)
            if motivo:
                registra(f"DOPO /clear {nome}: {motivo}")
                esci(f"/clear fatto, ma «/riparti» no: {motivo}", 2)
            if sid_su(nome, tty) != sid1:
                registra(f"DOPO /clear {nome}: sessione cambiata ancora, /riparti non mandato")
                esci("/clear fatto, ma la sessione è cambiata di nuovo: /riparti non mandato", 2)
            t_invio = time.time()
            perche = "casella non svuotata" if not comando(tty, riparti, prova) else attendi_comando(nome, tty, sid1, "riparti", t_invio, riparti)
            if not perche:
                break
            registra(f"RIPARTI NON RIUSCITO {nome} {tty_corto(tty)} (tentativo {n}): {perche}")
        if perche:
            registra(f"FALLITO {nome} {tty_corto(tty)}: contesto svuotato ({sid1[:8]}) ma {riparti} non partito: {perche}")
            esci(f"RIAVVIO A METÀ di {nome}: contesto svuotato, ma {riparti} non partito ({perche})", 5)
        registra(f"RIAVVIATO {nome} {tty_corto(tty)}: verificato (/clear {(sid0 or '?')[:8]} → {sid1[:8]}, {riparti} partito)")
        esci(f"{nome} riavviato su {tty_corto(tty)} (verificato)", 0)

    sid0 = sid_su(nome, tty)
    if not comando(tty, "/exit", prova):
        esci("casella non svuotata o scheda non trovata: niente riavvio", 2)
    for _ in range(0 if prova else 15):
        time.sleep(1)
        if not claude_su(tty):
            break
    if not prova and claude_su(tty):
        # niente «2» alla cieca (il vecchio script lo scriveva: se la sessione era viva diventava un prompt)
        schermo = "\n".join(leggi_schermo(tty)[-30:])
        if "Background work is running" in schermo or "stop tasks" in schermo:
            # bug 12/11: la finestra resta aperta; un tasto qualunque (es. «3» scritto dopo) può chiudere la sessione
            registra(f"ANCORA VIVA {nome} {tty_corto(tty)} dopo /exit: finestra «Background work is running» aperta. "
                     "NON rispondere a caso: Esc nella scheda per tornare alla sessione, poi TaskStop e nuovo riavvio")
            esci(f"{nome}: /exit ha aperto «Background work is running» su {tty_corto(tty)}. Non scrivere niente: "
                 "Esc nella scheda, ferma i task in sottofondo, poi rilancia", 6)
        registra(f"ANCORA VIVA {nome} {tty_corto(tty)} dopo /exit")
        esci(f"{nome} ancora viva dopo /exit: guarda la scheda {tty_corto(tty)}", 2)
    q = cartella.replace("'", "'\\''")
    t_invio = time.time()
    scrivi(tty, f"cd '{q}' && claude -n {nome} --disallowedTools=AskUserQuestion \"/riparti {nome}\"", prova)
    if prova:
        esci(f"{nome} riavviato su {tty_corto(tty)} (prova)", 0)
    sid1 = None
    for _ in range(30):  # la sessione nuova deve comparire su quel tty con la voce /riparti
        time.sleep(2)
        sid1 = sid_su(nome, tty)
        if sid1 and sid1 != sid0 and esito_comando(sid1, "riparti", t_invio) == "ok":
            registra(f"RIAVVIATO {nome} {tty_corto(tty)}: verificato (sessione {(sid0 or '?')[:8]} → {sid1[:8]}, /riparti partito)")
            esci(f"{nome} riavviato su {tty_corto(tty)} (verificato)", 0)
    registra(f"FALLITO {nome} {tty_corto(tty)}: dopo 60 s nessuna sessione nuova con /riparti (sid {(sid1 or '?')[:8]})")
    esci(f"RIAVVIO NON VERIFICATO di {nome}: guarda la scheda {tty_corto(tty)}", 5)


if __name__ == "__main__":
    main(sys.argv[1:])
