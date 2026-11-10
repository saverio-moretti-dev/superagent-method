#!/usr/bin/env python3
"""Handoff notes keyed by SESSION NAME, not by folder (superagent-method).

Notes live in ~/.claude/passaggi/ (override: env PASSAGGI_DIR).
  <NAME>.md        note waiting to be read        (NAME = session name, upper case)
  <NAME>.letta.md  last note read                 (only one; older ones go to archivio/)
  <NAME>.prec.md   previous note, overwritten     (only one; older ones go to archivio/)
  dir-<folder>.md  fallback when the session has no name (cloud, unnamed session)

Commands (standard library only, zero tokens):
  nome [NAME]          print the key for this session; line 2 says where it came from
  elenco               notes not read yet: key, name in header, date, age
  scrivi               rotate before writing: <KEY>.md -> <KEY>.prec.md (old .prec -> archivio/);
                       prints the two header lines with the SYSTEM date/time, to copy as they are
  timbra [KEY]         right after writing: puts the system date/time in the header ("scritta:" and the
                       date of line 1). Agents wrote times from memory ("23:30" at 20:17): the clock decides
  leggi KEY            mark as read: <KEY>.md -> <KEY>.letta.md (old .letta -> archivio/)
  archivia [--fai]     move extra .letta*/.prec* files to archivio/AAAA-MM/ (dry run without --fai)
  migra MAP [--fai]    rename notes listed in MAP (lines "old-file-name -> NEWKEY"), dry run without --fai
Nothing is ever deleted: files are only renamed or moved.
"""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

ALIASES = {"SUPERAGENT": "SUPERAGENTE"}
DIR = Path(os.environ.get("PASSAGGI_DIR", Path.home() / ".claude" / "passaggi"))
NOW = dt.datetime.now()


def norm(name):
    n = re.sub(r"[^A-Z0-9_-]+", "-", name.strip().upper()).strip("-")
    return ALIASES.get(n, n)


def folder_key(cwd=None):
    p = str(cwd or os.getcwd())
    return "dir-" + re.sub(r"[/ ]", "-", p).lstrip("-")


def session_name():
    """(name, source-message). Reads Claude Code's own session record; never raises."""
    pid = os.environ.get("CLAUDE_PID")
    if not pid:
        return None, "CLAUDE_PID assente (non in Claude Code o cloud)"
    f = Path.home() / ".claude" / "sessions" / f"{pid}.json"
    try:
        d = json.loads(f.read_text())
    except FileNotFoundError:
        return None, f"{f} non esiste"
    except Exception as e:  # format changed
        return None, f"{f} illeggibile ({type(e).__name__})"
    n = d.get("name") if isinstance(d, dict) else None
    if not isinstance(n, str) or not n.strip():
        return None, "sessione senza nome"
    return norm(n), f"sessione {d.get('sessionId', '?')[:8]}"


def session_id():
    pid = os.environ.get("CLAUDE_PID")
    try:
        return json.loads((Path.home() / ".claude" / "sessions" / f"{pid}.json").read_text()).get("sessionId", "")[:8]
    except Exception:
        return ""


STAMP = "%Y-%m-%d %H:%M"
WRITTEN = re.compile(r"(scritta:\s*)(\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2})")


def stamp_note(path, when):
    """Put `when` in 'scritta:' (added to the nome: line if missing) and in line 1's date. Returns (old, new)."""
    lines = path.read_text(encoding="utf-8").split("\n")
    new = when.strftime(STAMP)
    old = ""
    hit = False
    for i, line in enumerate(lines[:6]):
        m = WRITTEN.search(line)
        if m:
            old = m.group(2)
            lines[i] = WRITTEN.sub(lambda mm: mm.group(1) + new, line, count=1)
            hit = True
            break
    if not hit:
        for i, line in enumerate(lines[:6]):
            if re.search(r"\bnome:", line):
                lines[i] = re.sub(r"\s*·\s*scritta:[^·]*", "", line).rstrip() + f" · scritta: {new}"
                hit = True
                break
    if not hit:
        lines.insert(1, f"scritta: {new}")
    if lines and lines[0].startswith("# PASSAGGIO"):
        lines[0] = re.sub(r"(# PASSAGGIO\s*—\s*)\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}", lambda mm: mm.group(1) + new,
                          lines[0], count=1)
    path.write_text("\n".join(lines), encoding="utf-8")
    return old, new


def written_drift(path):
    """Minutes between the header's 'scritta:' and the file's mtime (None if no header time)."""
    m = WRITTEN.search(header_field_raw(path))
    if not m:
        return None
    try:
        w = dt.datetime.strptime(m.group(2).replace("T", " "), STAMP)
    except ValueError:
        return None
    return abs((dt.datetime.fromtimestamp(path.stat().st_mtime) - w).total_seconds()) / 60


def header_field_raw(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return "".join(next(fh, "") for _ in range(6))
    except OSError:
        return ""


def key(arg=None):
    if arg:
        return norm(arg), "argomento"
    n, why = session_name()
    if n:
        return n, why
    return folder_key(), f"cartella (nome non disponibile: {why})"


def archive(path):
    stamp = dt.datetime.fromtimestamp(path.stat().st_mtime)
    dest = DIR / "archivio" / stamp.strftime("%Y-%m")
    dest.mkdir(parents=True, exist_ok=True)
    stem = path.name[:-3] if path.name.endswith(".md") else path.name
    target = dest / f"{stem}.{stamp:%Y%m%d-%H%M}.md"
    i = 2
    while target.exists():
        target = dest / f"{stem}.{stamp:%Y%m%d-%H%M}-{i}.md"
        i += 1
    path.rename(target)
    return target


def header_name(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = [next(fh, "") for _ in range(6)]
    except OSError:
        return "?"
    for line in head:
        m = re.search(r"nome:\s*([A-Za-z0-9_-]+)", line)
        if m:
            return norm(m.group(1))
    for line in head:
        m = re.search(r"\b(?:agente|sessione|Sessione|Agente)\s+([A-Z][A-Z0-9_-]{2,})", line)
        if m:
            return m.group(1) + " (dal testo)"
    return "—"


def header_field(path, field):
    """Value of 'field:' in the note's first 6 lines (header line: 'nome: X · cartella: … · stato: …')."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = "".join(next(fh, "") for _ in range(6))
    except OSError:
        return ""
    m = re.search(field + r":\s*([^·\n]+)", head)
    return m.group(1).strip() if m else ""


def unread():
    return sorted(p for p in DIR.glob("*.md") if not re.search(r"\.(letta|prec)[^/]*\.md$", p.name))


def cmd_nome(args):
    k, why = key(args[0] if args else None)
    print(k)
    print(f"fonte: {why}")
    if k.startswith("dir-"):
        print("ATTENZIONE: nota di cartella; con un nome di sessione usa /riparti NOME")
    # folder notes for this folder (new dir- form or the old "-Users-..." form): never read, only reported
    fk = folder_key()
    for p in (DIR / f"{fk}.md", DIR / ("-" + fk[4:] + ".md")):
        if p.exists() and p.name != f"{k}.md":
            print(f"ALTRA NOTA di cartella non letta: {p.name} (nome: {header_name(p)}, "
                  f"{dt.datetime.fromtimestamp(p.stat().st_mtime):%d/%m %H:%M}) — non leggerla, segnalala al coordinatore")


def cmd_elenco(_):
    rows = unread()
    if not rows:
        print("nessuna nota da leggere")
    for p in rows:
        m = dt.datetime.fromtimestamp(p.stat().st_mtime)
        age = (NOW - m).total_seconds() / 3600
        st = header_field(p, "stato")
        d = written_drift(p)
        if d is not None and d > 15:
            st = (st + "; " if st else "") + f"ora intestazione lontana {d:.0f} min dal file"
        print(f"{p.name[:-3]:<60} nome: {header_name(p):<22} {m:%d/%m %H:%M}  {age:5.0f} h"
              + (f"  [{st}]" if st else ""))
    extra = len(list(DIR.glob("*.md"))) - len(rows)
    print(f"-- {len(rows)} da leggere · {extra} lette/precedenti · archivio: "
          f"{sum(1 for _ in (DIR / 'archivio').rglob('*.md')) if (DIR / 'archivio').exists() else 0}")


def cmd_scrivi(args):
    k, _ = key(args[0] if args else None)
    DIR.mkdir(parents=True, exist_ok=True)
    cur, prec = DIR / f"{k}.md", DIR / f"{k}.prec.md"
    if cur.exists():
        if prec.exists():
            print(f"archiviata {archive(prec)}")
        cur.rename(prec)
        print(f"{cur.name} -> {prec.name}")
    print(f"scrivi la nota in: {cur}")
    now = NOW.strftime(STAMP)
    sid = session_id() or "<id>"
    print("intestazione (ora di sistema, copiala così):")
    print(f"# PASSAGGIO — {now} — <repo/cartella>")
    print(f"nome: {k} · cartella: {os.getcwd()} · sessione: {sid} · scritta: {now}")
    print(f"appena scritta: python3 {Path(__file__).resolve()} timbra {k}")


def cmd_timbra(args):
    k, _ = key(args[0] if args else None)
    cur = DIR / f"{k}.md"
    if not cur.exists():
        sys.exit(f"{cur.name} non esiste")
    old, new = stamp_note(cur, dt.datetime.now())
    print(f"{cur.name}: scritta {old or '(mancava)'} -> {new}")


def cmd_leggi(args):
    if not args:
        sys.exit("uso: leggi KEY")
    k = args[0] if args[0].startswith("dir-") else norm(args[0])
    cur, letta = DIR / f"{k}.md", DIR / f"{k}.letta.md"
    if not cur.exists():
        sys.exit(f"{cur.name} non esiste")
    if letta.exists():
        print(f"archiviata {archive(letta)}")
    d = written_drift(cur)
    if d is not None and d > 15:
        print(f"ATTENZIONE: ora 'scritta:' nell'intestazione lontana {d:.0f} min dal file "
              f"({dt.datetime.fromtimestamp(cur.stat().st_mtime):%Y-%m-%d %H:%M}): vale l'ora del file")
    cur.rename(letta)
    print(f"{cur.name} -> {letta.name}")


def cmd_archivia(args):
    fai = "--fai" in args
    groups = {}
    for p in DIR.glob("*.md"):
        m = re.match(r"(.+?)\.(letta|prec)([^/]*)\.md$", p.name)
        if m:
            groups.setdefault((m.group(1), m.group(2)), []).append(p)
    moves = []
    for (base, kind), files in groups.items():
        canon = DIR / f"{base}.{kind}.md"
        keep = canon if canon in files else max(files, key=lambda f: f.stat().st_mtime)
        moves += [f for f in files if f != keep]
    before = len(list(DIR.rglob("*.md")))
    for f in sorted(moves):
        print(("sposto " if fai else "sposterei ") + f.name + ("  -> " + str(archive(f).relative_to(DIR)) if fai else ""))
    after = len(list(DIR.rglob("*.md")))
    print(f"-- {len(moves)} file {'spostati' if fai else 'da spostare'} · file totali prima {before} dopo {after}")
    if fai and before != after:
        sys.exit("ERRORE: il conteggio è cambiato")


def cmd_migra(args):
    if not args:
        sys.exit("uso: migra MAPPA [--fai]")
    fai = "--fai" in args
    for line in Path(args[0]).read_text().splitlines():
        if "->" not in line or line.lstrip().startswith("#"):
            continue
        old, new = (s.strip() for s in line.split("->", 1))
        src = DIR / old
        new = new if new.startswith("dir-") else norm(new)
        dst = DIR / f"{new}.md"
        if not src.exists():
            print(f"manca {old}")
            continue
        if dst.exists():
            print(f"FERMO: {dst.name} esiste già, {old} non si tocca")
            continue
        print(f"{'rinomino' if fai else 'rinominerei'} {old} -> {dst.name}  (intestazione: {header_name(src)})")
        if fai:
            src.rename(dst)


def main():
    cmds = {"nome": cmd_nome, "elenco": cmd_elenco, "scrivi": cmd_scrivi, "timbra": cmd_timbra, "leggi": cmd_leggi,
            "archivia": cmd_archivia, "migra": cmd_migra}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(2)
    cmds[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
