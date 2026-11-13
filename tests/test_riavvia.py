#!/usr/bin/env python3
"""Test di tools/riavvia.py — nessun invio vero: HOME temporanea, `claude agents`, ps e osascript finti, orologio finto.

Lancio:  python3 -m unittest discover -s tests -v     (dalla radice di superagent-method)

Casi (ordine SUP 11/11 17:58): idle · busy vero (turno aperto, tool in corso, permesso) · busy con turno finito e
comando in sottofondo (caso misurato 11/11 17:46) · local_command dopo /clear · trascrizione vuota/assente dopo /clear ·
cron che sveglia a metà attesa · messaggio Regia in arrivo · quiete < 20 s · nota scaduta al lancio · nota scritta
durante l'attesa · nota già .letta (SUPERATO) · doppia attesa sulla stessa scheda · blocco 5 min · sequenza completa
--sup · log ATTESA senza doppioni · integrazione sulle trascrizioni vere (se presenti sul Mac).
"""
import glob, importlib.util, json, os, shutil, subprocess, sys, tempfile, time, types, unittest
from unittest import mock

QUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("RIAVVIA_SCRIPT") or os.path.join(QUI, "..", "tools", "riavvia.py")  # RIAVVIA_SCRIPT: prova una copia
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
        self.scrivi_vero = self.r.scrivi  # per Muto: osascript finto che non risponde

        def scrivi(tty, testo, prova, svuota=0):  # sessione finta: /clear e /riparti partono davvero
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            self.simula(testo)
            return True
        self.r.scrivi = scrivi
        self.r.pulisci = lambda tty, prova: True  # la casella sullo schermo non c'è nei test: vedi Casella

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    # aiuti
    def simula(self, testo):
        """Effetto vero di un comando ben scritto: /clear = sessionId e trascrizione nuovi; /riparti = voce comando."""
        if testo == "/clear":
            self.sid = "aaaaaaaa-bbbb-cccc-dddd-%012d" % len(self.inviati)
            self.trascrivi(CLEAR, fa_s=0)
        elif testo.startswith("/riparti"):
            p = self.trascrivi_aggiungi([{"type": "user", "message": {"content": "<command-name>/riparti</command-name>"}},
                                         {"type": "system", "subtype": "turn_duration"}])

    def trascrivi_aggiungi(self, voci):
        p = os.path.join(self.home, ".claude", "projects", "p", f"{self.sid}.jsonl")
        quando = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(self.ora.t))  # come le trascrizioni vere
        with open(p, "a", encoding="utf-8") as f:
            f.write("".join(json.dumps(dict(v, timestamp=quando)) + "\n" for v in voci))
        os.utime(p, (self.ora.t - 60, self.ora.t - 60))
        return p

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

    con_ferma = False  # i casi fino al 13/11 provano il resto: il passo h (B4) ha la sua classe Ferma

    def lancia(self, *argv):
        argv = list(argv) + ([] if self.con_ferma else ["--senza-ferma"])
        with self.assertRaises(SystemExit) as e, mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            self.r.main(argv)
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

        def scrivi(tty, testo, prova, svuota=0):
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            if testo == "/clear":
                self.sid = nuovo
                self.trascrivi(CLEAR, fa_s=0, sid=nuovo)
            else:
                self.simula(testo)
            return True
        self.r.scrivi = scrivi
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup", "--attendi", "15"), 0)
        self.assertEqual([t for _, t, _ in self.inviati], ["/clear", "/riparti superagente"])
        self.assertIn("RIAVVIATO SUPERAGENTE ttys002", self.log())

    def test_20_dopo_clear_turno_vero_niente_riparti(self):
        self.nota(fa_s=60)
        self.trascrivi(FINE, fa_s=60)

        def scrivi(tty, testo, prova, svuota=0):
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


class Casella(Base):
    """Fallimento dell'11/11 19:40: avanzo nella casella → «rit/clear» messaggio normale. Logica pura (sessione finta)."""

    def setUp(self):
        super().setUp()
        self.stato = "idle"
        self.nota(fa_s=60)
        self.trascrivi(FINE, fa_s=60)

    def guasto(self, quanti):
        """I primi `quanti` /clear arrivano come «rit/clear» (messaggio normale, stesso sid); poi funzionano."""
        conta = []

        def scrivi(tty, testo, prova, svuota=0):
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            if testo == "/clear" and len(conta) < quanti:
                conta.append(1)
                self.trascrivi_aggiungi([{"type": "user", "message": {"content": "rit/clear"}},
                                         {"type": "assistant", "message": {"content": [{"type": "text", "text": "?"}]}},
                                         {"type": "system", "subtype": "turn_duration"}])
            else:
                self.simula(testo)
            return True
        self.r.scrivi = scrivi

    def test_26_rit_clear_due_volte_niente_riparti(self):
        self.guasto(2)
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 4)
        self.assertEqual([t for _, t, _ in self.inviati], ["/clear", "/clear"])
        self.assertIn("arrivato come messaggio normale", self.log())
        self.assertIn("FALLITO SUPERAGENTE", self.log())
        self.assertNotIn("RIAVVIATO", self.log())

    def test_27_rit_clear_una_volta_poi_ok(self):
        self.guasto(1)
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 0)
        self.assertEqual([t for _, t, _ in self.inviati], ["/clear", "/clear", "/riparti superagente"])
        self.assertIn("CLEAR OK", self.log())
        self.assertIn("RIAVVIATO SUPERAGENTE ttys002: verificato", self.log())

    def test_28_clear_senza_effetto_niente_riparti(self):
        def scrivi(tty, testo, prova, svuota=0):  # nessun segno, sid uguale: non partito
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            return True
        self.r.scrivi = scrivi
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 4)
        self.assertEqual([t for _, t, _ in self.inviati], ["/clear", "/clear"])

    def test_29_clear_in_coda_dietro_un_cron(self):
        """Il cron entra nello stesso istante: /clear resta in coda finché la sessione lavora, poi parte."""
        self.stato = "busy"
        self.trascrivi(FINE, fa_s=60)
        vero = self.r.scrivi

        def scrivi(tty, testo, prova, svuota=0):
            if testo == "/clear":
                self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
                self.trascrivi(CRON, fa_s=0)
                parte = self.ora.t + 90

                def gancio(o):
                    if o.t >= parte and self.stato == "busy":
                        self.stato = "idle"
                        self.simula("/clear")
                self.ora.gancio = gancio
                return True
            return vero(tty, testo, prova, svuota)
        self.r.scrivi = scrivi
        guardie = self.r.guardie
        self.r.guardie = lambda *a, **k: None  # verde al lancio (il cron arriva dopo)
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 0)
        self.r.guardie = guardie
        self.assertEqual([t for _, t, _ in self.inviati], ["/clear", "/riparti superagente"])

    def test_30_casella_non_svuotabile_niente_invio(self):
        self.r.pulisci = lambda tty, prova: False
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 4)
        self.assertEqual(self.inviati, [])
        self.assertIn("NON mandato", self.log())

    def test_31_riparti_come_messaggio_poi_ok(self):
        conta = []

        def scrivi(tty, testo, prova, svuota=0):
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            if testo.startswith("/riparti") and not conta:
                conta.append(1)
                self.trascrivi_aggiungi([{"type": "user", "message": {"content": "x/riparti superagente"}},
                                         {"type": "system", "subtype": "turn_duration"}])
            else:
                self.simula(testo)
            return True
        self.r.scrivi = scrivi
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 0)
        self.assertEqual([t for _, t, _ in self.inviati], ["/clear", "/riparti superagente", "/riparti superagente"])
        self.assertIn("RIPARTI NON RIUSCITO", self.log())

    def test_32_segno_sullo_schermo(self):
        S = self.r.SEGNO
        self.assertTrue(self.r.casella_col_segno([f" {S}", "  ", ""]))
        self.assertFalse(self.r.casella_col_segno([f" rit{S}", ""]))
        self.assertFalse(self.r.casella_col_segno([" rit", f" {S}"]))
        self.assertFalse(self.r.casella_col_segno([f" {S}", " avanzo"]))
        self.assertFalse(self.r.casella_col_segno(None))

    def test_33_leggi_casella_ultima(self):
        schermo = "❯ vecchio messaggio\nrisposta\n──── X ─\n❯ " + self.r.SEGNO + "\n  \n─────\n  stato\n"
        with mock.patch.object(self.r.subprocess, "run", return_value=types.SimpleNamespace(stdout=schermo)):
            self.assertEqual(self.r.leggi_casella(TTY), [" " + self.r.SEGNO, "  "])
        with mock.patch.object(self.r.subprocess, "run", return_value=types.SimpleNamespace(stdout="niente")):
            self.assertIsNone(self.r.leggi_casella(TTY))

    def test_34_blocchi_corti(self):
        """Oltre ~60 caratteri un do script diventa incolla (misurato 11/11 19:47): i blocchi restano corti."""
        self.assertLessEqual(len(self.r.SVUOTA * 8 + self.r.SEGNO + "\\"), 40)
        self.assertLessEqual(len(self.r.SVUOTA * 8 + "/riparti superagente"), 40)

    def test_35_variabili_prova(self):
        with mock.patch.dict(os.environ, {"RIAVVIA_BLOCCO_S": "0", "RIAVVIA_NOTA_MAX_S": "30"}):
            r = carica(self.home)
        self.assertEqual((r.BLOCCO_S, r.NOTA_MAX_S), (0, 30))
        self.assertEqual((self.r.BLOCCO_S, self.r.NOTA_MAX_S), (300, 600))
        self.assertEqual(self.lancia("PROVA-X", TTY, "--sup"), 1)


class Agente(Base):
    """Ramo agente: /exit, poi «cd … && claude -n NOME … "/riparti NOME"», con verifica della sessione nuova."""

    def setUp(self):
        super().setUp()
        self.stato = "idle"
        self.nota(fa_s=60, nome="PROVA-A")
        self.trascrivi(FINE, fa_s=60)
        self.r.claude_su = lambda tty: self.vivo
        self.vivo = True

    def scrivi_agente(self, parte):
        def scrivi(tty, testo, prova, svuota=0):
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            if testo == "/exit":
                self.vivo = False
            elif testo.startswith("cd ") and parte:
                self.sid = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"
                self.trascrivi([], fa_s=0)
                self.trascrivi_aggiungi([{"type": "user", "message": {"content": "<command-name>/riparti</command-name>"}}])
            return True
        self.r.scrivi = scrivi

    def test_36_agente_verificato(self):
        self.scrivi_agente(True)
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 0)
        self.assertEqual([t for _, t, _ in self.inviati][0], "/exit")
        self.assertIn("RIAVVIATO PROVA-A ttys002: verificato", self.log())

    def test_37_agente_non_ripartito(self):
        self.scrivi_agente(False)
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 5)
        self.assertIn("FALLITO PROVA-A", self.log())

    def test_38_agente_casella_sporca_niente_exit(self):
        self.scrivi_agente(True)
        self.r.pulisci = lambda tty, prova: False
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 2)
        self.assertEqual(self.inviati, [])

    # G1-B5-model (SUP 14/11): rilancio col modello della sessione vecchia, letto dalla trascrizione
    def cd_inviato(self):
        return [t for _, t, _ in self.inviati if t.startswith("cd ")][0]

    def test_39a_modello_della_sessione(self):
        haiku = {"type": "assistant", "message": {"model": "claude-haiku-5-5", "content": [{"type": "text", "text": "x"}]}}
        sint = {"type": "assistant", "message": {"model": "<synthetic>", "content": [{"type": "text", "text": "y"}]}}
        self.trascrivi([haiku, sint] + FINE, fa_s=60)
        self.scrivi_agente(True)
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 0)
        self.assertIn("--model claude-haiku-5-5 ", self.cd_inviato())
        self.assertNotIn("MODELLO PROVA-A", self.log())

    def test_39b_modello_non_letto_predefinito_e_log(self):
        self.scrivi_agente(True)
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 0)
        self.assertNotIn("--model", self.cd_inviato())
        self.assertIn("MODELLO PROVA-A ttys002: non letto", self.log())

    def test_39c_extra_con_model_vince(self):
        haiku = {"type": "assistant", "message": {"model": "claude-haiku-5-5", "content": []}}
        self.trascrivi([haiku] + FINE, fa_s=60)
        self.scrivi_agente(True)
        with mock.patch.dict(os.environ, {"RIAVVIA_EXTRA": "--model sonnet"}):
            self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 0)
        self.assertIn("--model sonnet ", self.cd_inviato())
        self.assertNotIn("haiku", self.cd_inviato())

    def test_39d_modello_strano_rifiutato(self):
        cattivo = {"type": "assistant", "message": {"model": "claude-x; rm -rf ~", "content": []}}
        self.trascrivi([cattivo] + FINE, fa_s=60)
        self.scrivi_agente(True)
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 0)
        self.assertNotIn("--model", self.cd_inviato())



class Muto(Base):
    """Blocco del 13/11 20:07: osascript appeso 15 s → riavvia.py moriva senza togliere il blocco del tty."""

    def setUp(self):
        super().setUp()
        self.stato = "idle"
        self.nota(fa_s=60)
        self.trascrivi(FINE, fa_s=60)
        self.r.scrivi = self.scrivi_vero
        self.chiamate = []
        self.rispondi = []  # per ogni chiamata osascript: "ok" oppure None (= timeout)

    def run_finto(self, cmd, **kw):
        self.chiamate.append(cmd)
        esito = self.rispondi.pop(0) if self.rispondi else None
        if esito is None:
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        return types.SimpleNamespace(stdout=esito + "\n", stderr="", returncode=0)

    def blocco(self):
        return os.path.exists(os.path.join(self.r.BLOCCHI, "ttys002.json"))

    def lancia_muto(self, *argv):
        with mock.patch.object(self.r.subprocess, "run", self.run_finto):
            return self.lancia(*argv)

    def test_40_timeout_al_primo_invio_blocco_tolto(self):
        self.assertEqual(self.lancia_muto("SUPERAGENTE", TTY, "--sup"), 7)
        self.assertFalse(self.blocco())
        self.assertIn("Terminal non risponde da 15 s", self.log())
        self.assertIn("FALLITO SUPERAGENTE ttys002", self.log())
        self.assertIn("SBLOCCATO ttys002", self.log())
        self.assertIsNone(self.r.g_blocco(TTY))  # un nuovo riavvio può partire subito

    def test_41_timeout_dopo_un_invio_blocco_resta(self):
        self.rispondi = ["ok"]  # /clear arriva, poi Terminal non risponde più
        self.r.attendi_clear = lambda *a: (None, "finto")
        self.r.attendi_ferma = lambda *a: None
        self.assertEqual(self.lancia_muto("SUPERAGENTE", TTY, "--sup"), 7)
        self.assertTrue(self.blocco())
        self.assertNotIn("SBLOCCATO", self.log())

    def test_42_agente_timeout_su_exit(self):
        self.r.g_sottofondo = lambda *a: None
        self.nota(fa_s=60, nome="PROVA-X")
        self.assertEqual(self.lancia_muto("PROVA-X", TTY, self.home), 7)
        self.assertFalse(self.blocco())

    def test_43_leggi_schermo_timeout_lista_vuota_e_log(self):
        with mock.patch.object(self.r.subprocess, "run", self.run_finto):
            self.assertEqual(self.r.leggi_schermo(TTY), [])
        self.assertIn("lettura dello schermo", self.log())

    def test_44_altra_eccezione_senza_invii_blocco_tolto(self):
        self.r.comando = mock.Mock(side_effect=RuntimeError("guasto"))
        with self.assertRaises(RuntimeError), mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            self.r.main(["SUPERAGENTE", TTY, "--sup"])
        self.assertFalse(self.blocco())

    def test_45_prova_niente_blocco_niente_osascript(self):
        self.assertEqual(self.lancia_muto("SUPERAGENTE", TTY, "--sup", "--prova"), 0)
        self.assertEqual(self.chiamate, [])



class Ferma(Base):
    """G1 B4 (13/11): passo h (TaskStop + CronDelete, NOME.pronto) e passo i (doppioni dopo /riparti)."""
    con_ferma = True

    def setUp(self):
        super().setUp()
        self.stato = "idle"
        self.vivo = True
        self.figli = []            # figli in sottofondo che restano dopo FERMA
        self.risponde = True       # la sessione scrive NOME.pronto
        self.altre = []            # sessioni con lo stesso nome su altri tty
        self.r.claude_su = lambda tty: self.vivo
        self.r.leggi_casella = lambda tty: None
        self.r.figli_lavoro = lambda pid: self.figli
        self.r.tty_di = lambda pid: {4242: "ttys002"}.get(pid) or next((a["tty"] for a in self.altre if a["pid"] == pid and a["vivo"]), "")
        self.r.sessione = lambda nome: ([{"name": nome, "pid": 4242, "status": self.stato, "sessionId": self.sid}] +
                                        [dict(a, name=a.get("name", nome)) for a in self.altre if a["vivo"]])
        self.chiusi = []
        finto = types.ModuleType("doppia")

        def chiudi(tty):
            self.chiusi.append(tty)
            for a in self.altre:
                if a["tty"] == tty and a.get("sola", True):
                    a["vivo"] = False
                    return True, "chiusura chiesta"
            return False, f"{tty} sta in una finestra con altre schede: non chiusa"
        finto.chiudi = chiudi
        sys.modules["doppia"] = finto
        self.addCleanup(sys.modules.pop, "doppia", None)

    def prepara(self, nome):
        self.nome = nome
        self.nota(fa_s=60, nome=nome)
        self.trascrivi(FINE, fa_s=60)

        def scrivi(tty, testo, prova, svuota=0):
            self.inviati.append((self.r.tty_corto(tty), testo, self.ora.t))
            if testo == self.r.TESTO_FERMA and self.risponde:
                with open(os.path.join(self.home, ".claude", "passaggi", f"{nome}.pronto"), "w") as f:
                    f.write("task b1 coda\ncron c1 giro\nfine\n")
            elif testo == "/exit":
                self.vivo = False
            elif testo.startswith("cd "):
                self.sid = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"
                self.trascrivi([], fa_s=0)
                self.trascrivi_aggiungi([{"type": "user", "message": {"content": "<command-name>/riparti</command-name>"}}])
            else:
                self.simula(testo)
            return True
        self.r.scrivi = scrivi

    def inviati_testi(self):
        return [t for _, t, _ in self.inviati]

    def test_50_agente_ferma_poi_exit(self):
        self.prepara("PROVA-A")
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 0)
        self.assertEqual(self.inviati_testi()[:2], [self.r.TESTO_FERMA, "/exit"])
        self.assertIn("FERMA OK PROVA-A ttys002: task b1 coda | cron c1 giro | fine", self.log())
        with open(self.r.FERMA_MD, encoding="utf-8") as f:
            self.assertIn("CronDelete", f.read())

    def test_51_niente_pronto_niente_exit(self):
        self.prepara("PROVA-A")
        self.risponde = False
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 8)
        self.assertNotIn("/exit", self.inviati_testi())
        self.assertIn("nessun PROVA-A.pronto", self.log())

    def test_52_pronto_vecchio_non_vale(self):
        self.prepara("PROVA-A")
        self.risponde = False
        p = os.path.join(self.home, ".claude", "passaggi", "PROVA-A.pronto")
        with open(p, "w") as f:
            f.write("fine\n")
        os.utime(p, (self.ora.t - 600, self.ora.t - 600))
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 8)

    def test_53_agente_figli_rimasti_niente_exit(self):
        self.prepara("PROVA-A")
        self.figli = ["zsh 999"]
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 8)
        self.assertNotIn("/exit", self.inviati_testi())

    def test_54_sup_figli_rimasti_va_avanti(self):
        self.prepara("SUPERAGENTE")
        self.figli = ["zsh 999"]
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 0)
        self.assertEqual(self.inviati_testi()[:2], [self.r.TESTO_FERMA, "/clear"])
        self.assertIn("VIVI DOPO FERMA SUPERAGENTE", self.log())

    def test_55_figli_prima_non_bloccano_le_guardie(self):
        self.prepara("PROVA-A")
        self.assertIsNone(self.r.guardie("PROVA-A", TTY, uscita=False))

    def test_56_doppione_fermo_chiuso(self):
        self.prepara("PROVA-A")
        self.altre = [{"pid": 777, "tty": "ttys009", "status": "idle", "vivo": True, "name": "PROVA-A (2)"}]
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 0)
        self.assertEqual(self.chiusi, ["ttys009"])
        self.assertIn("DOPPIONE PROVA-A (2) pid 777 su ttys009", self.log())

    def test_57_doppione_occupato_non_chiuso(self):
        self.prepara("PROVA-A")
        self.altre = [{"pid": 777, "tty": "ttys009", "status": "busy", "vivo": True}]
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 9)
        self.assertEqual(self.chiusi, [])

    def test_58_doppione_in_finestra_con_altre_schede(self):
        self.prepara("PROVA-A")
        self.altre = [{"pid": 777, "tty": "ttys009", "status": "idle", "vivo": True, "sola": False}]
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 9)

    def test_62_away_summary_dopo_fine_turno(self):  # prova B4 22:38: rifiutata una sessione ferma
        ok, _ = self.r.stato_voci(FINE + [{"type": "system", "subtype": "away_summary"}])
        self.assertTrue(ok)
        ok, _ = self.r.stato_voci([{"type": "user", "message": {"content": "x"}}, {"type": "system", "subtype": "away_summary"}])
        self.assertFalse(ok)

    def test_63_sup_non_cancella_i_cron(self):
        self.prepara("SUPERAGENTE")
        self.assertEqual(self.lancia("SUPERAGENTE", TTY, "--sup"), 0)
        with open(self.r.FERMA_MD, encoding="utf-8") as f:
            t = f.read()
        self.assertNotIn("CronDelete", t)
        self.assertIn("I cron NON si toccano", t)

    def test_59_stesso_nome(self):
        f = self.r.stesso_nome
        self.assertTrue(f("PROVA-A", "prova-a"))
        self.assertTrue(f("PROVA-A (2)", "PROVA-A"))
        self.assertFalse(f("PROVA-A-2", "PROVA-A"))
        self.assertFalse(f("PROVA-A (x)", "PROVA-A"))
        self.assertFalse(f("PROVA-AB", "PROVA-A"))

    def test_60_senza_ferma(self):
        self.prepara("PROVA-A")
        self.con_ferma = False
        self.assertEqual(self.lancia("PROVA-A", TTY, "/tmp/x"), 0)
        self.assertNotIn(self.r.TESTO_FERMA, self.inviati_testi())

    def test_61_testo_ferma_corto(self):
        self.assertLessEqual(len(self.r.TESTO_FERMA), 44)

if __name__ == "__main__":
    unittest.main()
