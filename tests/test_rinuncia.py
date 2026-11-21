#!/usr/bin/env python3
"""Tests of tools/rinuncia.py (lock with an age, time limit) and of its use in sblocca.py and doppia.py.

No real Terminal tab and no real `claude agents`: giro()/sessioni()/sostituisci() are replaced in-process.
Usage: python3 tests/test_rinuncia.py
"""
import importlib
import os
import subprocess
import sys
import tempfile
import time
import unittest

QUI = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(QUI), "tools")
sys.path.insert(0, TOOLS)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.lock = os.path.join(self.tmp, "x.lock")
        os.environ["RINUNCIA_LOG"] = os.path.join(self.tmp, "rinuncia.log")
        import rinuncia
        self.r = importlib.reload(rinuncia)
        self.figli = []

    def tearDown(self):
        for p in self.figli:
            p.kill()
            p.wait()

    def figlio(self, nome="fake-run.py", secondi=30):
        """A live process whose command line contains «nome» (like a running copy of the program)."""
        p = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({secondi})", nome])
        self.figli.append(p)
        return p

    def scrivi_lock(self, pid, eta=0, percorso=None):
        percorso = percorso or self.lock
        with open(percorso, "w") as f:
            f.write(f"{pid} {int(time.time())}\n")
        if eta:
            t = time.time() - eta
            os.utime(percorso, (t, t))

    def log(self):
        p = os.environ["RINUNCIA_LOG"]
        return open(p).read() if os.path.exists(p) else ""


class Lock(Base):
    def test_free_taken_and_released(self):
        self.assertEqual(self.r.prendi(self.lock, 60, "fake-run.py"), "preso")
        self.assertEqual(self.r.prendi(self.lock, 60, "fake-run.py"), "preso")  # same pid
        self.r.lascia(self.lock)
        self.assertFalse(os.path.exists(self.lock))

    def test_live_copy(self):
        self.scrivi_lock(self.figlio().pid)
        self.assertEqual(self.r.prendi(self.lock, 60, "fake-run.py"), "viva")
        self.assertEqual(self.log(), "")  # silent: no log line on every turn

    def test_hung_copy_never_killed(self):
        p = self.figlio()
        self.scrivi_lock(p.pid, eta=120)
        self.assertEqual(self.r.prendi(self.lock, 60, "fake-run.py"), "appesa")
        self.assertIsNone(p.poll(), "a hung copy must not be killed")
        self.assertIn("APPESA", self.log())

    def test_dead_pid(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        self.scrivi_lock(p.pid)
        self.assertEqual(self.r.prendi(self.lock, 60, "fake-run.py"), "preso")
        self.assertIn("VECCHIO", self.log())
        self.assertEqual(open(self.lock).read().split()[0], str(os.getpid()))

    def test_pid_reused_by_another_program(self):
        self.scrivi_lock(self.figlio(nome="other.py").pid)
        self.assertEqual(self.r.prendi(self.lock, 60, "fake-run.py"), "preso")

    def test_release_only_own(self):
        self.scrivi_lock(self.figlio().pid)
        self.r.lascia(self.lock)
        self.assertTrue(os.path.exists(self.lock))

    def test_old_format_pid_only(self):
        with open(self.lock, "w") as f:
            f.write(str(self.figlio().pid))
        self.assertEqual(self.r.prendi(self.lock, 60, "fake-run.py"), "viva")

    def test_refresh(self):
        self.scrivi_lock(self.figlio().pid, eta=120)
        self.r.rinfresca(self.lock)
        self.assertEqual(self.r.prendi(self.lock, 60, "fake-run.py"), "viva")


class Tempo(Base):
    def test_expires_and_stops_direct_child(self):
        t0 = time.time()
        with self.assertRaises(self.r.TempoScaduto):
            with self.r.tempo_massimo(1):
                subprocess.run(["sleep", "20"])
        self.assertLess(time.time() - t0, 5)
        time.sleep(0.2)
        ps = subprocess.run(["ps", "-A", "-o", "ppid=,command="], capture_output=True, text=True).stdout.splitlines()
        figli = [r for r in ps if r.split(None, 1)[0] == str(os.getpid()) and "sleep 20" in r]
        self.assertEqual(figli, [])

    def test_not_swallowed_by_except_exception(self):
        with self.assertRaises(self.r.TempoScaduto):
            with self.r.tempo_massimo(1):
                try:
                    time.sleep(3)
                except Exception:
                    self.fail("swallowed")

    def test_within_limit(self):
        with self.r.tempo_massimo(5):
            x = 1
        self.assertEqual(x, 1)


class Sblocca(Base):
    def setUp(self):
        super().setUp()
        import sblocca
        self.s = importlib.reload(sblocca)
        self.s.DIR, self.s.LOG = self.tmp, os.path.join(self.tmp, "sblocca.log")
        self.s.LOCK = os.path.join(self.tmp, "sblocca.lock")
        self.giri = []

    def finto_giro(self, secondi=0, rc=0):
        def giro(a):
            self.giri.append(os.path.exists(self.s.LOCK))
            time.sleep(secondi)
            return rc
        self.s.giro = giro

    def test_run_takes_and_releases_lock(self):
        self.finto_giro(rc=2)
        self.assertEqual(self.s.main([]), 2)
        self.assertEqual(self.giri, [True])
        self.assertFalse(os.path.exists(self.s.LOCK))

    def test_live_copy_gives_up_silently(self):
        self.finto_giro()
        self.scrivi_lock(self.figlio(nome="sblocca.py").pid, percorso=self.s.LOCK)
        self.assertEqual(self.s.main([]), 0)
        self.assertEqual(self.giri, [])
        self.assertFalse(os.path.exists(self.s.LOG))
        self.assertTrue(os.path.exists(self.s.LOCK), "the other copy's lock must stay")

    def test_hung_copy_exit_3(self):
        self.finto_giro()
        p = self.figlio(nome="sblocca.py")
        self.scrivi_lock(p.pid, eta=self.s.LOCK_ETA_S + 60, percorso=self.s.LOCK)
        self.assertEqual(self.s.main([]), 3)
        self.assertEqual(self.giri, [])
        self.assertIsNone(p.poll())

    def test_dry_run_takes_no_lock(self):
        self.finto_giro(rc=0)
        self.scrivi_lock(self.figlio(nome="sblocca.py").pid, percorso=self.s.LOCK)
        self.assertEqual(self.s.main(["--prova"]), 0)
        self.assertEqual(self.giri, [True])  # ran anyway, read-only

    def test_time_limit(self):
        self.finto_giro(secondi=5)
        self.s.TEMPO_MAX_S = 1
        t0 = time.time()
        self.assertEqual(self.s.main([]), 1)
        self.assertLess(time.time() - t0, 4)
        self.assertIn("SCADUTO", open(self.s.LOG).read())
        self.assertFalse(os.path.exists(self.s.LOCK))


class Doppia(Base):
    def setUp(self):
        super().setUp()
        import doppia
        self.d = importlib.reload(doppia)
        self.d.DIR, self.d.LOG = self.tmp, os.path.join(self.tmp, "doppia.log")
        self.liste = [[{"name": "AGENT", "pid": os.getpid(), "cwd": self.tmp}]]
        self.d.sessioni = lambda: self.liste[0] if len(self.liste) == 1 else self.liste.pop(0)
        self.d.tty_di = lambda pid: "/dev/ttys999"
        self.sost = []

        def sostituisci(*a, secondi=0):
            self.sost.append(os.path.exists(os.path.join(self.tmp, "doppia-AGENT-2.lock")))
            time.sleep(self.attesa)
            return 0
        self.attesa = 0
        self.d.sostituisci = sostituisci

    def test_lock_held_during_replacement(self):
        self.assertEqual(self.d.main(["AGENT"]), 0)
        self.assertEqual(self.sost, [True])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "doppia-AGENT-2.lock")))

    def test_second_doppia_same_name_exit_6(self):
        self.scrivi_lock(self.figlio(nome="doppia.py").pid, percorso=os.path.join(self.tmp, "doppia-AGENT-2.lock"))
        self.assertEqual(self.d.main(["AGENT"]), 6)
        self.assertEqual(self.sost, [])

    def test_copy_opened_meanwhile_exit_5(self):
        self.liste = [[{"name": "AGENT", "pid": 1}], [{"name": "AGENT", "pid": 1}, {"name": "AGENT-2", "pid": 2}]]
        self.assertEqual(self.d.main(["AGENT"]), 5)
        self.assertEqual(self.sost, [])

    def test_time_limit(self):
        self.d.TEMPO_MAX_S = 1
        self.attesa = 5
        t0 = time.time()
        self.assertEqual(self.d.main(["AGENT"]), 1)
        self.assertLess(time.time() - t0, 4)
        self.assertIn("SCADUTO", open(self.d.LOG).read())
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "doppia-AGENT-2.lock")))


if __name__ == "__main__":
    unittest.main()
