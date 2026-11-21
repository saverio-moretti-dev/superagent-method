#!/usr/bin/env python3
"""Every automatic job must be able to give up: a lock with an age, plus a time limit. Standard library only.

A program that starts on its own (hook, launchd, Monitor, cron) first takes the lock: if a copy of it is already running
it gives up; then it works inside a time limit and stops by itself when the limit expires.

  from rinuncia import prendi, rinfresca, lascia, tempo_massimo, TempoScaduto, scrivi_log

  esito = prendi(LOCK, eta_max=900, nome="script.py")
      "preso"   the lock is yours (also when the lock of a dead copy was there: the log says so)
      "viva"    a copy is alive and its lock is fresh -> exit (silently, if you run on every turn)
      "appesa"  the copy is alive but its lock has not been refreshed for more than eta_max -> exit and report (log);
                never kill: the time limit stops only the run itself and its direct children, never claude processes
  rinfresca(LOCK)   heartbeat for long-running programs (one cycle = one refresh)
  lascia(LOCK)      removes the lock only if it is still yours
  with tempo_massimo(300): ...   when it expires it raises TempoScaduto in the main thread; a subprocess.run in
                                 progress receives the exception and kills its direct child (subprocess behaviour)

Lock = file created with O_EXCL, holding «pid time». Dead pid, or a pid reused by a process that is not «nome» -> old lock.
Log: ~/.claude/rinuncia.log (RINUNCIA_LOG). Lock errors never block the caller: when in doubt, "preso".
Same API as the copy kept by the coordinator repo: keep the two in step.
"""
import contextlib
import os
import signal
import subprocess
import time

LOG = os.path.expanduser(os.environ.get("RINUNCIA_LOG", "~/.claude/rinuncia.log"))


class TempoScaduto(BaseException):
    """BaseException: a generic «except Exception» in the caller does not swallow it."""


def scrivi_log(testo):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {testo}\n")
    except OSError:
        pass


def _vivo(pid, nome):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass  # exists, owned by another user
    except OSError:
        return False
    if not nome:
        return True
    try:
        cmd = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return True  # in doubt: alive (better to give up than to run twice)
    return nome in cmd


def _leggi(percorso):
    try:
        with open(percorso, encoding="utf-8") as f:
            pid = int((f.read().split() or ["0"])[0])
        return pid, time.time() - os.path.getmtime(percorso)
    except (OSError, ValueError):
        return 0, None


def prendi(percorso, eta_max, nome=None):
    """See the module docstring. eta_max in seconds."""
    try:
        os.makedirs(os.path.dirname(percorso) or ".", exist_ok=True)
    except OSError:
        return "preso"
    for _ in range(2):
        try:
            fd = os.open(percorso, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w") as f:
                f.write(f"{os.getpid()} {int(time.time())}\n")
            return "preso"
        except FileExistsError:
            pass
        except OSError:
            return "preso"
        pid, eta = _leggi(percorso)
        if eta is None and not os.path.exists(percorso):
            continue  # removed meanwhile: retry
        if pid == os.getpid():
            return "preso"
        if pid and _vivo(pid, nome):
            if eta is not None and eta > eta_max:
                scrivi_log(f"APPESA {os.path.basename(percorso)}: pid {pid} alive, lock not refreshed for {int(eta)} s (max {eta_max})")
                return "appesa"
            return "viva"
        scrivi_log(f"VECCHIO {os.path.basename(percorso)}: pid {pid} dead, lock removed")
        try:
            os.remove(percorso)
        except OSError:
            pass
    return "viva"  # lost twice to another copy that has just taken the lock


def rinfresca(percorso):
    try:
        os.utime(percorso)
    except OSError:
        pass


def lascia(percorso):
    pid, _ = _leggi(percorso)
    if pid == os.getpid():
        try:
            os.remove(percorso)
        except OSError:
            pass


@contextlib.contextmanager
def tempo_massimo(secondi):
    """Main thread only (signal.alarm). secondi <= 0 = no limit."""
    if secondi <= 0:
        yield
        return

    def scaduto(*_):
        raise TempoScaduto(f"time limit of {secondi} s exceeded")

    prima = signal.signal(signal.SIGALRM, scaduto)
    signal.alarm(int(secondi))
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prima)
