#!/usr/bin/env python3
"""Guardia del contesto: hook di Claude Code per sessioni con nome (coordinatore e agenti).

Eventi (in settings.json, stesso comando per tutti): UserPromptSubmit, PostToolUse, PreToolUse, Stop.

Coordinatore (nomi in `coordinatori`), soglie 150/175/200K:
  >=150K  avviso una volta (poi ogni 30 min): finisci i lavori in corso, niente pausa; appena fermo /passaggio.
  >=175K  sollecito a ogni messaggio e ogni 5 min fra gli strumenti; a fine turno rimanda indietro una volta ogni 10 min.
  >=200K  blocco: PreToolUse nega tutto tranne gli strumenti del passaggio; a fine turno rimanda indietro una volta.
  Riavvio: a FINE TURNO (= sessione ferma), se la nota ~/.claude/passaggi/NOME.md e' fresca (< 10 min) l'hook
  trascrive nella nota i messaggi arrivati e non letti, mette in pausa la coda (sup.py pausa) e lancia staccato
  riavvia.py NOME TTY --sup --attendi 3. Se il riavvio fallisce toglie la pausa (sup.py riprendi). Il coordinatore
  non lancia mai riavvia.py a turno aperto.
Agenti (soglie 150/200K): avviso >=150K, sollecito >=200K. Nessun blocco.

Spegnimento d'emergenza: esiste il file `off_file` (default ~/.claude/consumo/contesto-guardia.off) oppure
CONTESTO_GUARDIA=0 -> l'hook esce subito senza fare nulla, senza toccare settings.json.
Configurazione: JSON in CG_CONFIG (default ~/.claude/consumo/contesto-guardia.json), tutte le chiavi facoltative.
Prova a mano: contesto-guardia.py --misura TRASCRIZIONE  -> nome e K, con i millisecondi.
"""
import json, os, re, subprocess, sys, time

HOME = os.path.expanduser("~")
QUI = os.path.dirname(os.path.abspath(__file__))
DEF = {
    "coordinatori": ["SUPERAGENTE"],
    "soglie_coordinatore": [150, 175, 200],
    "soglie_agente": [150, 200],
    "off_file": f"{HOME}/.claude/consumo/contesto-guardia.off",
    "stato_dir": f"{HOME}/.claude/consumo/contesto-guardia",
    "passaggi_dir": f"{HOME}/.claude/passaggi",
    "riavvia": os.path.join(QUI, "riavvia.py"),
    "sup_py": "",            # script della coda messaggi (comandi pausa/riprendi/trascrivi); vuoto = niente pausa
    "plancia_dati": "",      # PLANCIA_DATI per sup_py (solo nelle prove)
    "env_riavvio": {},       # variabili in piu' per riavvia.py (es. RIAVVIA_PROVA=1 nelle prove)
    "attendi_min": 3,
    "nota_fresca_s": 600,
}
SKILL_OK = {"passaggio", "riparti"}
STRUMENTI_OK = {"Read", "Grep", "Glob", "LS", "TaskStop", "TaskList", "TaskGet", "TaskOutput", "CronList", "CronDelete",
                "SendMessage", "ListAgents", "ToolSearch"}
BASH_OK = {"git", "date", "ls", "cat", "head", "tail", "grep", "wc", "echo", "printf", "mkdir", "test", "[", "cd", "find",
           "sed", "awk", "sort", "uniq", "cut", "tr", "true", "mv", "cp", "touch", "pwd", "basename", "dirname", "stat"}
SCRIPT_OK = re.compile(r"(passaggi|sup|riavvia|contesti|stime|albero|controlla|cerca|contesto-guardia)\.py\b")


def cfg():
    c = dict(DEF)
    try:
        with open(os.environ.get("CG_CONFIG", f"{HOME}/.claude/consumo/contesto-guardia.json"), encoding="utf-8") as f:
            c.update(json.load(f))
    except (OSError, ValueError):
        pass
    if os.environ.get("CG_COORDINATORI"):
        c["coordinatori"] = os.environ["CG_COORDINATORI"].split(",")
    if os.environ.get("CG_SOGLIE"):  # solo prove: «20,25,30» per il coordinatore
        c["soglie_coordinatore"] = [int(x) for x in os.environ["CG_SOGLIE"].split(",")]
    return c


def leggi_coda(path, n=400_000):
    with open(path, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - n))
        return f.read().decode("utf-8", "ignore").splitlines()


def misura(path, nome_noto=""):
    """(nome, K): ultima usage con contesto > 0 (come contesti.py) e nome (customTitle/agentName) dalla trascrizione."""
    k, nome = None, nome_noto
    try:
        righe = leggi_coda(path)
    except OSError:
        return nome, 0
    for l in reversed(righe):
        if k is None and '"usage"' in l:
            try:
                u = json.loads(l).get("message", {}).get("usage") or {}
            except (ValueError, AttributeError):
                u = {}
            t = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            if t > 0:
                k = t // 1000
        if not nome:
            m = re.search(r'"(?:agentName|customTitle)":"([^"]+)"', l)
            if m:
                nome = m.group(1)
        if k is not None and nome:
            break
    if not nome:
        try:
            with open(path, "rb") as f:
                m = re.search(rb'"(?:agentName|customTitle)":"([^"]+)"', f.read(65536))
            nome = m.group(1).decode() if m else ""
        except OSError:
            pass
    return nome, k or 0


def stato_path(c, sid):
    os.makedirs(c["stato_dir"], exist_ok=True)
    return os.path.join(c["stato_dir"], f"{sid}.json")


def leggi_stato(c, sid):
    try:
        with open(stato_path(c, sid), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def scrivi_stato(c, sid, s):
    p = stato_path(c, sid)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(s, f)
    os.replace(p + ".tmp", p)


def log(c, msg):
    try:
        with open(os.path.join(c["stato_dir"], "guardia.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def esce(ev, testo):
    if ev in ("UserPromptSubmit", "PostToolUse"):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": ev, "additionalContext": testo}}))
    sys.exit(0)


def ogni(s, chiave, secondi):
    """True se `chiave` non e' scattata negli ultimi `secondi` (e la segna)."""
    if time.time() - s.get(chiave, 0) < secondi:
        return False
    s[chiave] = time.time()
    return True


def bash_ammesso(cmd):
    for pezzo in re.split(r"&&|\|\||[;|\n]", cmd):
        p = pezzo.strip().lstrip("(").strip()
        while re.match(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+", p):  # VAR=valore comando
            p = re.sub(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+", "", p, count=1)
        if not p or p.startswith("#"):
            continue
        w = p.split()[0].strip("'\"")
        if os.path.basename(w) in BASH_OK:
            continue
        if os.path.basename(w).startswith("python") and SCRIPT_OK.search(p):
            continue
        if SCRIPT_OK.search(w):
            continue
        return False
    return True


def strumento_ammesso(nome, inp):
    if nome in STRUMENTI_OK:
        return True
    if nome == "Skill":
        return (inp.get("skill") or "").split(":")[-1] in SKILL_OK
    if nome in ("Write", "Edit", "MultiEdit"):
        p = inp.get("file_path") or ""
        return p.endswith(".md") or p.startswith(f"{HOME}/.claude/")
    if nome == "Bash":
        return bash_ammesso(inp.get("command") or "")
    return False


def tty_claude():
    """tty della sessione claude che ha lanciato l'hook (primo antenato con un tty)."""
    p = os.getpid()
    for _ in range(12):
        try:
            out = subprocess.run(["ps", "-o", "ppid=,tty=", "-p", str(p)], capture_output=True, text=True, timeout=3).stdout.split()
        except subprocess.SubprocessError:
            return ""
        if len(out) < 2:
            return ""
        if out[1] not in ("??", "-"):
            return "/dev/" + out[1]
        p = int(out[0])
        if p <= 1:
            return ""
    return ""


def sup(c, *argomenti):
    if not c["sup_py"]:
        return 0, ""
    env = dict(os.environ)
    if c["plancia_dati"]:
        env["PLANCIA_DATI"] = c["plancia_dati"]
    r = subprocess.run([sys.executable, c["sup_py"], *argomenti], capture_output=True, text=True, timeout=30, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def lancia_riavvio(c, nome, sid, nota):
    tty = tty_claude()
    if not tty:
        log(c, f"{nome}: tty non trovato, niente riavvio")
        return "tty della sessione non trovato: riavvio non lanciato (usa riavvia.py a mano a fine turno)"
    rc, out = sup(c, "trascrivi", nota)
    log(c, f"{nome}: trascrivi rc={rc} {out[:200]}")
    rc, out = sup(c, "pausa", "riavvio automatico")
    log(c, f"{nome}: pausa rc={rc}")
    env = dict(os.environ, **{k: str(v) for k, v in c["env_riavvio"].items()})
    if c["plancia_dati"]:
        env["PLANCIA_DATI"] = c["plancia_dati"]
    with open(os.path.join(c["stato_dir"], "riavvio.log"), "a") as lf:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--esegui-riavvio", nome, tty],
                         stdin=subprocess.DEVNULL, stdout=lf, stderr=lf, start_new_session=True, env=env)
    log(c, f"{nome}: riavvio lanciato su {tty}")
    return ""


def esegui_riavvio(nome, tty):
    """Processo staccato: riavvia.py; se fallisce, toglie la pausa perche' la coda non resti ferma."""
    c = cfg()
    t0 = time.time()
    r = subprocess.run([sys.executable, c["riavvia"], nome, tty, "--sup", "--attendi", str(c["attendi_min"])],
                       capture_output=True, text=True)
    log(c, f"{nome}: riavvia.py rc={r.returncode} in {time.time() - t0:.0f} s: {(r.stdout + r.stderr).strip()[-300:]}")
    if r.returncode != 0:
        rc, out = sup(c, "riprendi")
        log(c, f"{nome}: riavvio fallito -> pausa tolta (rc={rc})")


def main():
    if os.environ.get("CONTESTO_GUARDIA") == "0":
        return
    c = cfg()
    if os.path.exists(c["off_file"]):
        return
    if len(sys.argv) > 1:
        if sys.argv[1] == "--esegui-riavvio":
            return esegui_riavvio(sys.argv[2], sys.argv[3])
        if sys.argv[1] == "--misura":
            t0 = time.perf_counter()
            n, k = misura(sys.argv[2])
            print(f"{n or '?'} {k}K ({(time.perf_counter() - t0) * 1000:.1f} ms)")
            return
    try:
        d = json.load(sys.stdin)
    except ValueError:
        return
    ev, sid, tr = d.get("hook_event_name", ""), d.get("session_id", ""), d.get("transcript_path", "")
    if not sid or not tr:
        return
    s = leggi_stato(c, sid)
    nome, k = misura(tr, s.get("nome", ""))
    if not nome:
        return
    s["nome"], s["k"] = nome, k
    coord = nome.upper() in {x.upper() for x in c["coordinatori"]}
    try:
        if coord:
            coordinatore(c, d, ev, s, nome, k, sid)
        else:
            agente(ev, s, k, c["soglie_agente"])
    finally:
        scrivi_stato(c, sid, s)


def agente(ev, s, k, soglie):
    a, b = soglie
    if ev not in ("UserPromptSubmit", "PostToolUse"):
        return
    if k >= b and (ev == "UserPromptSubmit" or ogni(s, "t_soll", 600)):
        esce(ev, f"CONTESTO {k}K (>= {b}K): /passaggio al primo punto sicuro (fine del passo, niente build o test a meta'), "
                 "poi una riga al coordinatore «nota pronta, riavviami».")
    if a <= k < b and ogni(s, "t_avv", 1800):
        esce(ev, f"CONTESTO {k}K (>= {a}K): finito il lavoro in corso, /passaggio prima di cominciarne un altro.")


def coordinatore(c, d, ev, s, nome, k, sid):
    a, b, z = c["soglie_coordinatore"]
    nota = os.path.join(c["passaggi_dir"], f"{nome}.md")
    if ev == "PreToolUse":
        if k >= z and not strumento_ammesso(d.get("tool_name", ""), d.get("tool_input") or {}):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                  "permissionDecisionReason": f"BLOCCO CONTESTO {k}K (>= {z}K): niente lavoro nuovo. Ammessi solo: "
                  "/passaggio (Skill), lettura, scrittura di .md e file in ~/.claude, git, passaggi.py/sup.py, "
                  "TaskStop/CronDelete, SendMessage. Scrivi la nota e chiudi il turno: il riavvio parte da solo."}}))
            log(c, f"{nome}: negato {d.get('tool_name')} a {k}K")
        return
    if ev == "Stop":
        fresca = os.path.exists(nota) and time.time() - os.path.getmtime(nota) < c["nota_fresca_s"]
        if fresca:
            firma = f"{os.path.getmtime(nota):.0f}"
            g = os.path.join(c["stato_dir"], f"riavvio-{nome}.json")  # per nome: la sessione nuova ha un altro id
            try:
                with open(g, encoding="utf-8") as f:
                    if json.load(f).get("nota") == firma:
                        return  # gia' lanciato per questa nota
            except (OSError, ValueError):
                pass
            errore = lancia_riavvio(c, nome, sid, nota)
            with open(g, "w", encoding="utf-8") as f:  # firma DOPO trascrivi (che riscrive la nota)
                json.dump({"nota": f"{os.path.getmtime(nota):.0f}", "ora": time.strftime("%Y-%m-%d %H:%M:%S"), "sid": sid}, f)
            if errore:
                print(json.dumps({"systemMessage": errore}))
            return
        if d.get("stop_hook_active"):
            return
        if k >= z or (k >= b and ogni(s, "t_stop", 600)):
            print(json.dumps({"decision": "block", "reason":
                  f"CONTESTO {k}K: {'BLOCCO' if k >= z else 'sollecito'}. Se hai lavori vivi (sotto-agenti, build) lasciali "
                  "finire; altrimenti adesso: avvisa gli agenti che lavorano, ferma i tuoi Monitor e cron, /passaggio, "
                  "poi chiudi il turno. Il riavvio lo lancia l'hook a fine turno: NON lanciare riavvia.py."}))
        return
    if ev not in ("UserPromptSubmit", "PostToolUse"):
        return
    if k >= z:
        esce(ev, f"BLOCCO CONTESTO {k}K (>= {z}K): solo /passaggio. Gli strumenti di lavoro sono negati. "
                 "Nota scritta + fine turno = riavvio automatico.")
    if k >= b and (ev == "UserPromptSubmit" or ogni(s, "t_soll", 300)):
        esce(ev, f"SOLLECITO CONTESTO {k}K (>= {b}K): riavviati il prima possibile. Nessun lavoro nuovo; chiudi quello vivo, "
                 "poi /passaggio e fine turno (il riavvio lo lancia l'hook, non tu). I messaggi che arrivano: nella nota, non si lavorano.")
    if a <= k < b and ((ev == "UserPromptSubmit" and ogni(s, "t_avv", 1800)) or not s.get("avvisato")):
        s["avvisato"] = True
        s["t_avv"] = time.time()
        esce(ev, f"AVVISO CONTESTO {k}K (>= {a}K): prepara il riavvio. Finisci i lavori in corso, non andare in pausa; "
                 "appena fermo: /passaggio e fine turno (il riavvio parte da solo). I messaggi nuovi si scrivono nella nota senza lavorarli.")


if __name__ == "__main__":
    main()
