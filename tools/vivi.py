#!/usr/bin/env python3
"""Background work still alive in a Claude Code session (Monitor, background Bash), seen from outside.

Why: Monitor tasks and background commands survive /clear (12/11: two listeners on the same queue = every user message
arrived twice; R40, R78). After /clear the new context does not know them and creates them again. Crons survive /clear
too, but they live only in memory: CronList in the session itself is the only way to see them.

How: the session's claude process has one /bin/zsh child per background task, with the tool's command inside
`eval '…'`. The task id comes from the session's transcripts (tool_use Monitor/Bash → «Monitor started (task X» /
«running in background with ID: X»), matched on the command text. Read-only: it never stops anything.

Usage:
  vivi.py --nome NAME [--json]     tasks alive in session NAME (claude agents --json → pid)
  vivi.py --pid PID [--json]       same, from the claude process pid
  vivi.py --hook                   SessionStart hook (matcher «clear»): reads the hook JSON on stdin and, if something
                                   is alive, injects «alive from before: … do not create them again» as context
Exit: 0 ok (also with nothing alive), 1 session not found.
"""
import glob, json, os, re, subprocess, sys, time

CASA = os.path.expanduser("~")
CLAUDE = os.path.join(CASA, ".local", "bin", "claude")
NORMALI = {"caffeinate"}   # fixed children of every session, not background work


def ps(pid, campi):
    try:
        return subprocess.run(["ps", "-o", campi + "=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
    except subprocess.SubprocessError:
        return ""


def e_claude(cmd):
    """True for the claude CLI process itself (not the bundled ugrep/rg it runs with the same binary)."""
    if not cmd:
        return False
    primo = cmd.split()[0]
    base = os.path.basename(primo)
    if base in ("ugrep", "rg"):
        return False
    return base == "claude" or "/claude/versions/" in primo or re.fullmatch(r"\d+\.\d+\.\d+", base) is not None


def claude_antenato(pid=None):
    """Pid of the claude process that runs this hook (walking up the parents), or None."""
    pid = pid or os.getppid()
    for _ in range(12):
        if not pid or pid == 1:
            return None
        if e_claude(ps(pid, "command")):
            return pid
        pid = int(ps(pid, "ppid") or 0)
    return None


def pid_di(nome):
    try:
        out = subprocess.run([CLAUDE, "agents", "--json"], capture_output=True, text=True, timeout=30).stdout
        return [x["pid"] for x in json.loads(out or "[]") if (x.get("name") or "").upper() == nome.upper() and x.get("pid")]
    except (subprocess.SubprocessError, ValueError, OSError):
        return []


def comando_eval(riga):
    """The tool command inside «eval '…'» of the zsh wrapper, with the shell quoting undone; None if not a wrapper."""
    i = riga.find("eval '")
    if i < 0:
        return None
    resto = riga[i + 6:]
    j = resto.rfind("' < /dev/null")
    if j < 0:
        j = resto.rfind("'")
    return resto[:j].replace("'\"'\"'", "'") if j >= 0 else None


def figli(pid):
    """[(child pid, tool command)] of the background tasks of the claude process pid."""
    try:
        out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True, timeout=5).stdout.split()
    except subprocess.SubprocessError:
        return []
    vivi = []
    for p in out:
        cmd = ps(p, "command")
        if not cmd or os.path.basename(cmd.split()[0]) in NORMALI:
            continue
        c = comando_eval(cmd)
        if c is not None:
            vivi.append((int(p), c))
        elif not e_claude(cmd) and "mcp" not in cmd.lower() and "lsp" not in cmd.lower():
            vivi.append((int(p), cmd[:200]))
    return vivi


def avvio_processo(pid):
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=5,
                             env={**os.environ, "LC_ALL": "C"}).stdout.strip()
        return time.mktime(time.strptime(out, "%a %b %d %H:%M:%S %Y"))
    except (subprocess.SubprocessError, ValueError):
        return None


def nome_di(pid):
    try:
        out = subprocess.run([CLAUDE, "agents", "--json"], capture_output=True, text=True, timeout=30).stdout
        return next((x.get("name") for x in json.loads(out or "[]") if x.get("pid") == pid), None)
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def trascrizioni(pid):
    """Transcripts of this session written since its claude process started (a /clear opens a new one in the same
    process), oldest first: same session name in the header, so another session's identical Monitor is not mixed in."""
    t0 = avvio_processo(pid) or (time.time() - 86400)
    nome = nome_di(pid)
    segno = f'"agentName":"{nome}"' if nome else None
    out = []
    for f in glob.glob(os.path.join(CASA, ".claude", "projects", "*", "*.jsonl")):
        try:
            if os.path.getmtime(f) < t0:
                continue
            if segno:
                with open(f, encoding="utf-8", errors="replace") as h:
                    if segno not in "".join(h.readline() for _ in range(6)):
                        continue
        except OSError:
            continue
        out.append(f)
    return sorted(out, key=os.path.getmtime)


ID_MON = re.compile(r"Monitor started \(task (\w+)")
ID_BASH = re.compile(r"running in background with ID: (\w+)")


def id_dei_task(files):
    """{command: (kind, id, description)} from the Monitor / background-Bash tool calls in the transcripts."""
    uso, mappa = {}, {}
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as h:
                righe = h.readlines()
        except OSError:
            continue
        for r in righe:
            if '"tool_use"' not in r and '"tool_result"' not in r:
                continue
            try:
                c = (json.loads(r).get("message") or {}).get("content")
            except ValueError:
                continue
            for b in c if isinstance(c, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and b.get("name") in ("Monitor", "Bash"):
                    inp = b.get("input") or {}
                    if b["name"] == "Monitor" or inp.get("run_in_background"):
                        uso[b.get("id")] = (b["name"], inp.get("command", ""), inp.get("description", ""))
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in uso:
                    t = b.get("content")
                    t = t if isinstance(t, str) else json.dumps(t)
                    m = ID_MON.search(t) or ID_BASH.search(t)
                    if m:
                        tipo, cmd, desc = uso[b["tool_use_id"]]
                        mappa[cmd.strip()] = (tipo, m.group(1), desc)
    return mappa


def vivi(pid):
    """[{pid, kind, id, description, command}] for each background task alive in the claude process pid."""
    lista = figli(pid)
    if not lista:
        return []
    mappa = id_dei_task(trascrizioni(pid))
    out = []
    for p, cmd in lista:
        tipo, tid, desc = mappa.get(cmd.strip(), ("?", None, ""))
        out.append({"pid": p, "kind": tipo, "id": tid, "description": desc, "command": cmd})
    return out


def testo(lista):
    righe = []
    for x in lista:
        chi = f"{x['kind']} {x['id']}" if x["id"] else "background task (id unknown)"
        desc = f" «{x['description']}»" if x["description"] else ""
        righe.append(f"- {chi}{desc}: {x['command'][:160]}")
    return "\n".join(righe)


def hook():
    try:
        dati = json.load(sys.stdin)
    except ValueError:
        dati = {}
    if dati.get("source", "clear") != "clear":
        return 0
    pid = claude_antenato()
    lista = vivi(pid) if pid else []
    if not lista:
        return 0
    msg = ("ALIVE FROM BEFORE /clear in this session (they survive /clear — do NOT create them again; to change one, "
           "TaskStop its id first):\n" + testo(lista) +
           "\nCrons also survive /clear: run CronList before any CronCreate.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": msg}}))
    return 0


def main(a):
    if "--hook" in a:
        return hook()
    if "--nome" in a:
        pids = pid_di(a[a.index("--nome") + 1])
    elif "--pid" in a:
        pids = [int(a[a.index("--pid") + 1])]
    else:
        print(__doc__)
        return 1
    if not pids:
        print("session not found", file=sys.stderr)
        return 1
    lista = [x for p in pids for x in vivi(p)]
    print(json.dumps(lista, ensure_ascii=False, indent=1) if "--json" in a else (testo(lista) or "nothing alive"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
