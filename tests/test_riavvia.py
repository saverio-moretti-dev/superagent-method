#!/usr/bin/env python3
"""Test di tools/riavvia.py — nessun invio vero: HOME temporanea, `claude agents`, ps e osascript finti, orologio finto.

Lancio:  python3 -m unittest discover -s tests -v     (dalla radice di superagent-method)

Casi (ordine SUP 11/11 17:58): idle · busy vero (turno aperto, tool in corso, permesso) · busy con turno finito e
comando in sottofondo (caso misurato 11/11 17:46) · local_command dopo /clear · trascrizione vuota/assente dopo /clear ·
cron che sveglia a metà attesa · messaggio Regia in arrivo · quiete < 20 s · nota scaduta al lancio · nota scritta
durante l'attesa · nota già .letta (SUPERATO) · doppia attesa sulla stessa scheda · blocco 5 min · sequenza completa
--sup · log ATTESA senza doppioni · integrazione sulle trascrizioni vere (se presenti sul Mac).
"""
import glob, importlib.util, json, os, shutil, sys, tempfile, time, types, unittest
from unittest import mock

QUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(QUI, "..", "tools", "riavvia.py")
CASA_VERA = os.path.expanduser("~")
TTY = "/dev/ttys002"
SID = "11111111-2222-3333-4444-555555555555"


def carica(home):
    with mock.patch.dict(os.environ, {"HOME": home}):
        spec = importlib.util.spec_from_file_location("riavvia_test", SCRIPT)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    return m


# voci tipiche delle trascrizioni (forme copiate da trascrizioni vere dell'11/11)
FINE = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "fatto"}]}},
        {"type": "system", "subtype": "stop_hook_summary"}, {"type": "system", "subtype": "turn_duration"},
        {"type": "bridge-session"}, {"type": "cost-state"}]
CLEAR = [{"type": "custom-title"}, {"type": "agent-name"}, {"type": "mode"}, {"type": "session-owner"},
         {"type": "bridge-session"}, {"type": "file-history-snapshot"}, {"type": "attachment"},
         {"type": "user", "message": {"content": "<local-command-caveat>The command below was run directly…</local-command-caveat>"}},
         {"type": "user", "message": {"content": "<command-name>/clear</command-name> <command-message>clear</command-message>"}},
         {"type": "system", "subtype": "local_command"}, {"type": "file-history-snapshot"}]
TOOL_APERTO = [{"type": "user", "message": {"content": "fai x"}},
               {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}]
TOOL_RISULTATO = TOOL_APERTO + [{"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}]
CRON = FINE + [{"type": "queue-operation"}, {"type": "system", "subtype": "scheduled_task_fire"},
               {"type": "user", "message": {"content": "Giro Regia (SUP)…"}}, {"type": "attachment"}, {"type": "api-request"}]
REGIA_IN_ARRIVO = FINE + [{"type": "queue-operation"}]


class Orologio:
    """time finto: sleep avanza il tempo e chiama un gancio (per cambiare lo stato a metà attesa)."""

    def __init__(self, t):
        self.t, self.gancio, self.dormito = t, None, 0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s
        self.dormito += s
        if self.gancio:
            self.gancio(self)

    def strftime(self, f, *a):
        return time.strftime(f, time.localtime(self.t))


class Base(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="riavvia-test-")
        self.r = carica(self.home)
        self.ora = Orologio(time.time())
        self.r.time = self.ora
        os.makedirs(os.path.join(self.home, ".claude", "passaggi"))
        os.makedirs(os.path.join(self.home, ".claude", "projects", "p"))
        self.stato = "busy"
        self.sid = SID
        self.inviati = []
        self.r.sessione = lambda nome: [{"name": nome, "pid": 4242, "status": self.stato, "sessionId": self.sid}]
        self.r.tty_di = lambda pid: "ttys002"
        self.r.g_altri = lambda tty: None

        def scrivi(tty, testo, prova):
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            return True
        self.r.scrivi = scrivi

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    # aiuti
    def trascrivi(self, voci, fa_s=60, sid=None):
        p = os.path.join(self.home, ".claude", "projects", "p", f"{sid or self.sid}.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(v) + "\n" for v in voci))
        os.utime(p, (self.ora.t - fa_s, self.ora.t - fa_s))
        return p

    def nota(self, fa_s=60, nome="SUPERAGENTE", letta=False):
        p = os.path.join(self.home, ".claude", "passaggi", f"{nome}{'.letta' if letta else ''}.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"# PASSAGGIO\nnome: {nome}\n")
        os.utime(p, (self.ora.t - fa_s, self.ora.t - fa_s))
        return p

    def log(self):
        try:
            with open(self.r.LOG, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def lancia(self, *argv):
        with self.assertRaises(SystemExit) as e, mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            self.r.main(list(argv))
        return e.exception.code


class Regola(Base):
    """stato_voci / g_ferma: la regola unica."""

    def test_01_idle(self):
        self.stato = "idle"
        self.assertIsNone(self.r.g_ferma("SUPERAGENTE", TTY))

    def test_02_busy_vero_tool_aperto(self):
        self.trascrivi(TOOL_APERTO, fa_s=120)  # anche fermo da 2 min (permesso in attesa) resta al lavoro
        self.assertIn("sta lavorando", self.r.g_ferma("SUPERAGENTE", TTY))

    def test_03_busy_vero_tool_risultato(self):
        self.trascrivi(TOOL_RISULTATO, fa_s=60)
        self.assertIn("sta lavorando", self.r.g_ferma("SUPERAGENTE", TTY))

    def test_04_busy_ma_turno_finito_sottofondo(self):
        self.trascrivi(FINE, fa_s=60)  # caso 11/11 17:46: busy per un comando in sottofondo
        self.assertIsNone(self.r.g_ferma("SUPERAGENTE", TTY))

    def test_05_local_command_dopo_clear(self):
        self.trascrivi(CLEAR, fa_s=30)
        self.assertIsNone(self.r.g_ferma("SUPERAGENTE", TTY, dopo_clear=True))
        self.assertIsNone(self.r.g_ferma("SUPERAGENTE", TTY))  # stessa regola anche fuori dal punto del /clear

    def test_06_vuota_o_assente_dopo_clear(self):
        self.assertIsNone(self.r.g_ferma("SUPERAGENTE", TTY, dopo_clear=True))  # file non ancora creato
        self.assertIn("sta lavorando", self.r.g_ferma("SUPERAGENTE", TTY))    # fuori dal /clear: non dimostrabile
        self.trascrivi([{"type": "bridge-session"}, {"type": "mode"}], fa_s=30)
        self.assertIsNone(self.r.g_ferma("SUPERAGENTE", TTY, dopo_clear=True))
        self.assertIn("sta lavorando", self.r.g_ferma("SUPERAGENTE", TTY))

    def test_07_cron_a_meta(self):
        self.trascrivi(CRON, fa_s=30)
        self.assertIn("sta lavorando", self.r.g_ferma("SUPERAGENTE", TTY))

    def test_08_messaggio_regia_in_arrivo(self):
        self.trascrivi(REGIA_IN_ARRIVO, fa_s=30)
        self.assertIn("sta lavorando", self.r.g_ferma("SUPERAGENTE", TTY))

    def test_09_quiete_sotto_20s(self):
        self.trascrivi(FINE, fa_s=5)
        self.assertIn("scritta 5 s fa", self.r.g_ferma("SUPERAGENTE", TTY))

    def test_10_tipo_sconosciuto_conta_come_lavoro(self):
        self.trascrivi(FINE + [{"type": "nuovo-tipo-mai-visto"}], fa_s=60)
        self.assertIn("sta lavorando", self.r.g_ferma("SUPERAGENTE", TTY))

    def test_11_altra_scheda(self):
        self.r.tty_di = lambda pid: "ttys009"
        self.stato = "idle"
        self.assertIn("nessuna sessione SUPERAGENTE su ttys002", self.r.g_ferma("SUPERAGENTE", TTY))


class Attesa(Base):
    """main(): nota, SUPERATO, doppia attesa, blocco, sequenza --sup, log."""

    def test_12_nota_scaduta_al_lancio(self):
        self.stato = "idle"
        self.nota(fa_s=11 * 60)
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 2)
        self.assertEqual(self.inviati, [])
        self.assertIn("min prima del lancio", self.log())

    def test_13_nota_non_scade_durante_attesa(self):
        self.nota(fa_s=8 * 60)  # scritta 8 min prima del lancio; il SUP lavora ancora 5 min
        self.trascrivi(TOOL_APERTO, fa_s=60)
        lancio = self.ora.t

        def gancio(o):
            if o.t - lancio >= 300 and self.stato != "idle":
                self.stato = "idle"
        self.ora.gancio = gancio
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup", "--attendi", "15"), 0)
        self.assertEqual([t for _, t, _ in self.inviati], ["/clear", "/riparti superagente"])
        self.assertGreaterEqual(self.inviati[0][2] - lancio, 300)

    def test_14_nota_scritta_durante_attesa(self):
        self.stato = "idle"
        lancio = self.ora.t
        self.trascrivi(FINE)

        def gancio(o):
            if o.t - lancio >= 120 and not os.path.exists(os.path.join(self.home, ".claude", "passaggi", "SUPERAGENTE.md")):
                self.nota(fa_s=0)
        self.ora.gancio = gancio
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup", "--attendi", "5"), 0)
        self.assertEqual(len(self.inviati), 2)

    def test_15_nota_gia_letta_superato(self):
        self.nota(fa_s=60)
        self.trascrivi(TOOL_APERTO)
        lancio = self.ora.t

        def gancio(o):  # a metà attesa un /riparti fatto da altri legge la nota
            n = os.path.join(self.home, ".claude", "passaggi", "SUPERAGENTE.md")
            if o.t - lancio >= 60 and os.path.exists(n):
                os.remove(n)
                self.nota(fa_s=0, letta=True)
        self.ora.gancio = gancio
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup", "--attendi", "15"), 3)
        self.assertEqual(self.inviati, [])
        self.assertIn("SUPERATO", self.log())

    def test_16_altra_sessione_sul_tty_superato(self):
        self.nota(fa_s=60)
        self.trascrivi(TOOL_APERTO)

        def gancio(o):
            self.sid = "99999999-0000-0000-0000-000000000000"
        self.ora.gancio = gancio
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup", "--attendi", "15"), 3)
        self.assertEqual(self.inviati, [])

    def test_17_doppia_attesa(self):
        vero = carica(self.home)  # g_altri vera, con ps finto
        ps = "  1 /sbin/launchd\n 777 python3 /x/riavvia.py SUPERAGENTE /dev/ttys002 --sup --attendi 15\n"
        fake = types.SimpleNamespace(run=lambda cmd, **k: types.SimpleNamespace(stdout=ps if "-A" in cmd else "1"),
                                     SubprocessError=Exception)
        vero.subprocess = fake
        vero.antenati = lambda: {os.getpid()}
        self.assertIn("pid 777", vero.g_altri(TTY))
        self.assertIsNone(vero.g_altri("/dev/ttys005"))
        self.r.g_altri = vero.g_altri
        self.stato = "idle"
        self.nota(fa_s=60)
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 2)
        self.assertEqual(self.inviati, [])

    def test_18_blocco_5_minuti(self):
        self.stato = "idle"
        self.nota(fa_s=60)
        self.trascrivi(FINE)
        self.r.blocca(TTY, "ALTRO")
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 2)
        self.assertEqual(self.inviati, [])
        self.ora.t += 301
        self.nota(fa_s=60)
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 0)

    def test_19_sequenza_sup_completa_con_sottofondo(self):
        """Il caso di oggi da cima a fondo: busy per il sottofondo, turno finito → /clear → la trascrizione nuova
        (local_command) resta busy per il sottofondo → /riparti, una volta sola, in quest'ordine."""
        self.nota(fa_s=60)
        self.trascrivi(FINE, fa_s=60)
        nuovo = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        def scrivi(tty, testo, prova):
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            if testo == "/clear":
                self.sid = nuovo
                self.trascrivi(CLEAR, fa_s=0, sid=nuovo)
            return True
        self.r.scrivi = scrivi
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup", "--attendi", "15"), 0)
        self.assertEqual([t for _, t, _ in self.inviati], ["/clear", "/riparti superagente"])
        self.assertIn("RIAVVIATO SUPERAGENTE ttys002", self.log())

    def test_20_dopo_clear_turno_vero_niente_riparti(self):
        self.nota(fa_s=60)
        self.trascrivi(FINE, fa_s=60)

        def scrivi(tty, testo, prova):
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            if testo == "/clear":  # qualcuno scrive subito nella sessione pulita: turno vero
                self.sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                self.trascrivi(CLEAR + TOOL_APERTO, fa_s=0, sid=self.sid)
            return True
        self.r.scrivi = scrivi
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup", "--attendi", "15"), 2)
        self.assertEqual([t for _, t, _ in self.inviati], ["/clear"])
        self.assertIn("DOPO /clear", self.log())

    def test_21_cron_a_meta_attesa_niente_invio_nel_buco(self):
        self.nota(fa_s=60)
        self.trascrivi(FINE, fa_s=60)
        lancio, fasi = self.ora.t, []
        guardie_vere = self.r.guardie

        def guardie(*a, **k):  # prima verifica: verde subito → invio. Qui il cron parte proprio prima del controllo
            if not fasi:
                fasi.append("cron")
                self.trascrivi(CRON, fa_s=0)
            elif self.ora.t - lancio >= 60 and fasi == ["cron"]:
                fasi.append("fine")
                self.trascrivi(CRON + FINE[1:], fa_s=30)
            return guardie_vere(*a, **k)
        self.r.guardie = guardie
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup", "--attendi", "15"), 0)
        self.assertEqual(fasi, ["cron", "fine"])
        self.assertGreaterEqual(self.inviati[0][2] - lancio, 60)  # niente invio mentre il cron lavorava

    def test_22_log_attesa_senza_doppioni(self):
        self.nota(fa_s=60)
        self.trascrivi(TOOL_APERTO, fa_s=0)
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup", "--attendi", "1"), 2)
        righe = [l for l in self.log().splitlines() if " ATTESA " in l]
        # «scritta 0 s fa», «10 s fa»… e poi «ultima voce…»: al massimo 2 tipi, non una riga ogni 10 s
        self.assertLessEqual(len(righe), 2, righe)
        self.assertIn("RIFIUTATO", self.log())


class Integrazione(unittest.TestCase):
    """Le trascrizioni vere dell'11/11 sul Mac (saltato altrove)."""

    def voci(self, sid, fino=None):
        f = glob.glob(os.path.join(CASA_VERA, ".claude", "projects", "*", f"{sid}.jsonl"))
        if not f:
            self.skipTest(f"trascrizione {sid[:8]} non presente")
        out = []
        with open(f[0], encoding="utf-8", errors="replace") as h:
            for r in h:
                try:
                    d = json.loads(r)
                except ValueError:
                    continue
                if fino and d.get("timestamp") and d["timestamp"] > fino:
                    break
                out.append(d)
        return out

    def test_23_sup_fermo_alle_17_46(self):
        r = carica(CASA_VERA)
        voci = self.voci("e9e064be-fdfa-4ce9-8778-bbbccf112b04", fino="2026-11-11T16:47:00Z")
        self.assertEqual(r.stato_voci(voci)[0], True)

    def test_24_sup_cron_alle_17_48_al_lavoro(self):
        r = carica(CASA_VERA)
        voci = self.voci("e9e064be-fdfa-4ce9-8778-bbbccf112b04", fino="2026-11-11T16:48:16Z")
        self.assertEqual(r.stato_voci(voci)[0], False)

    def test_25_sup_dopo_clear_alle_17_53(self):
        r = carica(CASA_VERA)
        f = glob.glob(os.path.join(CASA_VERA, ".claude", "projects", "*", "f9ff74b0*.jsonl"))
        if not f:
            self.skipTest("trascrizione dopo /clear non presente")
        voci = self.voci(os.path.basename(f[0])[:-6], fino="2026-11-11T16:53:30Z")
        self.assertEqual(r.stato_voci(voci, dopo_clear=True)[0], True)


if __name__ == "__main__":
    unittest.main()
