#!/usr/bin/env python3
"""Prove di tools/contesto-guardia.py (blocco G1 B5): blocco e riavvio a fine turno, per coordinatore e agenti.

Tutto finto: trascrizioni con usage a scelta, cartelle stato/passaggi in temp (CG_CONFIG), riavvia.py e sup.py finti
che registrano gli argomenti. Il tty si passa con CG_TTY (nelle prove non c'e' un terminale vero).
Uso: python3 tests/test_guardia.py   (ogni hook gira in un processo nuovo, come in Claude Code)
"""
import json, os, subprocess, sys, tempfile, time, unittest

QUI = os.path.dirname(os.path.abspath(__file__))
GUARDIA = os.environ.get("CG_GUARDIA") or os.path.join(os.path.dirname(QUI), "tools", "contesto-guardia.py")  # CG_GUARDIA: provare una copia

FINTO_RIAVVIA = """import os, sys, time
open(os.environ["FINTO_LOG"], "a").write("riavvia " + " ".join(sys.argv[1:]) + "\\n")
n = sum(l.startswith("riavvia") for l in open(os.environ["FINTO_LOG"]))
lista = os.environ.get("FINTO_RC", "0").split(",")  # «2,2,0» = un codice per tentativo, poi l'ultimo
rc = int(lista[min(n, len(lista)) - 1])
if "--prima" in sys.argv and os.environ.get("FINTO_VERDE", "1") == "1":  # come riavvia.py: --prima solo a guardie verdi
    import json, subprocess
    subprocess.run(json.loads(sys.argv[sys.argv.index("--prima") + 1]))
time.sleep(float(os.environ.get("FINTO_SLEEP", "0")))
print("gira gia' un'altra sessione" if rc == 3 else "riavviato")
sys.exit(rc)
"""
FINTO_VIVI = """import os
print(os.environ.get("FINTO_VIVI", "[]"))
"""
FINTO_SUP = """import os, sys
open(os.environ["FINTO_LOG"], "a").write("sup " + " ".join(sys.argv[1:2]) + "\\n")
if sys.argv[1] == "trascrivi":  # come il vero: nota assente = errore, mai creata
    import time; time.sleep(float(os.environ.get("FINTO_TRASCRIVI_SLEEP", "0")))
    if not os.path.exists(sys.argv[2]):
        sys.exit(1)
    with open(sys.argv[2], "r+") as f:
        f.seek(0, 2); f.write("\\n- messaggio trascritto\\n")
"""


class Guardia(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix="guardia-")
        self.log = os.path.join(self.t, "finti.log")
        open(self.log, "w").close()
        for nome, testo in (("riavvia.py", FINTO_RIAVVIA), ("sup.py", FINTO_SUP), ("vivi.py", FINTO_VIVI)):
            with open(os.path.join(self.t, nome), "w") as f:
                f.write(testo)
        self.passaggi = os.path.join(self.t, "passaggi")
        self.stato = os.path.join(self.t, "stato")
        os.makedirs(self.passaggi)
        self.conf = os.path.join(self.t, "conf.json")
        with open(self.conf, "w") as f:
            json.dump({"coordinatori": ["COORD-T"], "stato_dir": self.stato, "passaggi_dir": self.passaggi,
                       "riavvia": os.path.join(self.t, "riavvia.py"), "sup_py": os.path.join(self.t, "sup.py"),
                       "vivi": os.path.join(self.t, "vivi.py"), "riavvii_log": os.path.join(self.t, "riavvii.log"),
                       "off_file": os.path.join(self.t, "off")}, f)
        self.env = dict(os.environ, CG_CONFIG=self.conf, CG_TTY="/dev/ttysPROVA", CG_PID="12345", FINTO_LOG=self.log)
        self.env.pop("CONTESTO_GUARDIA", None)

    def trascrizione(self, nome, k, sid):
        p = os.path.join(self.t, f"{sid}.jsonl")
        with open(p, "w") as f:
            f.write(json.dumps({"type": "custom-title", "customTitle": nome}, separators=(",", ":")) + "\n")
            f.write(json.dumps({"message": {"usage": {"input_tokens": k * 1000}}}) + "\n")
        return p

    def hook(self, ev, nome, k, sid="s1", **extra):
        d = dict(hook_event_name=ev, session_id=sid, transcript_path=self.trascrizione(nome, k, sid), **extra)
        r = subprocess.run([sys.executable, GUARDIA], input=json.dumps(d), capture_output=True, text=True, env=self.env, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else {}

    def nota(self, nome, riga2=None):
        p = os.path.join(self.passaggi, f"{nome}.md")
        with open(p, "w") as f:
            f.write(f"# PASSAGGIO\nnome: {riga2 or nome} · cartella: /x\n")
        return p

    def lanci(self, attesa=3.0):
        fine = time.time() + attesa  # il riavvio parte staccato: si aspetta che scriva
        while time.time() < fine:
            righe = [l for l in open(self.log).read().splitlines() if l.startswith("riavvia")]
            if righe:
                time.sleep(0.5)
                return [l for l in open(self.log).read().splitlines() if l.startswith("riavvia")]
            time.sleep(0.1)
        return []

    def negato(self, out):
        return out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    # --- agenti (B5: prima solo avviso) ---
    def test_agente_210k_blocca_lavoro(self):
        self.assertTrue(self.negato(self.hook("PreToolUse", "AGENTE-T", 210, tool_name="Bash", tool_input={"command": "make"})))
        self.assertFalse(self.negato(self.hook("PreToolUse", "AGENTE-T", 210, tool_name="Read", tool_input={"file_path": "/x"})))
        self.assertFalse(self.negato(self.hook("PreToolUse", "AGENTE-T", 190, tool_name="Bash", tool_input={"command": "make"})))

    def test_agente_stop_senza_nota_rimanda(self):
        out = self.hook("Stop", "AGENTE-T", 210)
        self.assertEqual(out.get("decision"), "block")
        self.assertEqual(self.hook("Stop", "AGENTE-T", 210, stop_hook_active=True), {})

    def test_agente_nota_fresca_un_riavvio_senza_sup(self):
        self.nota("AGENTE-T")
        self.hook("Stop", "AGENTE-T", 210)
        l = self.lanci()
        self.assertEqual(len(l), 1, l)
        self.assertNotIn("--sup", l[0])
        self.assertNotIn("sup pausa", open(self.log).read())
        self.assertIn("GUARDIA AGENTE-T", open(os.path.join(self.t, "riavvii.log")).read())

    def test_agente_nota_basso_k_riavvia(self):
        self.nota("AGENTE-T")
        self.hook("Stop", "AGENTE-T", 40)
        self.assertEqual(len(self.lanci()), 1)

    def test_agente_nota_di_un_altro_niente(self):
        self.nota("AGENTE-T", riga2="ALTRO")
        self.hook("Stop", "AGENTE-T", 40)
        self.assertEqual(self.lanci(1.5), [])

    def test_agente_nota_con_riga_sopra_intestazione_riavvia(self):
        # 23/11: una riga sopra il titolo spinge «nome:» alla riga 4 -> nota scartata, niente riavvio, niente log
        with open(os.path.join(self.passaggi, "AGENTE-T.md"), "w") as f:
            f.write("Prima di tutto: agenda `agende/AGENTE-T.md`\n\n# PASSAGGIO\nnome: AGENTE-T · cartella: /x\n")
        self.hook("Stop", "AGENTE-T", 40)
        self.assertEqual(len(self.lanci()), 1)

    def test_agente_nota_fresca_scartata_lascia_il_motivo(self):
        with open(os.path.join(self.passaggi, "AGENTE-T.md"), "w") as f:
            f.write("# PASSAGGIO\nintestazione mancante\n")
        self.hook("Stop", "AGENTE-T", 40)
        self.assertEqual(self.lanci(1.5), [])
        testo = open(os.path.join(self.t, "riavvii.log")).read()
        self.assertIn("GUARDIA AGENTE-T", testo)
        self.assertIn("nome:", testo)
        self.hook("Stop", "AGENTE-T", 40)  # stessa nota: il motivo si scrive una volta, non a ogni fine turno
        self.assertEqual(open(os.path.join(self.t, "riavvii.log")).read().count("GUARDIA AGENTE-T"), 1)

    def test_agente_nota_scartata_a_210k_una_sola_risposta(self):
        with open(os.path.join(self.passaggi, "AGENTE-T.md"), "w") as f:
            f.write("# PASSAGGIO\nintestazione mancante\n")
        out = self.hook("Stop", "AGENTE-T", 210)  # hook() fa json.loads: due risposte di fila farebbero errore
        self.assertIn("Riavvio non lanciato", out.get("systemMessage", ""))

    def test_agente_nota_di_un_altro_lascia_il_motivo(self):
        self.nota("AGENTE-T", riga2="ALTRO")
        self.hook("Stop", "AGENTE-T", 40)
        self.assertIn("ALTRO", open(os.path.join(self.t, "riavvii.log")).read())

    def test_agente_lavoro_vivo_niente(self):
        self.env["FINTO_VIVI"] = json.dumps([{"pid": 1, "kind": "Monitor", "id": "b1"}])
        self.nota("AGENTE-T")
        out = self.hook("Stop", "AGENTE-T", 210)
        self.assertIn("lavoro in sottofondo vivo", out.get("systemMessage", ""))
        self.assertEqual(self.lanci(1.5), [])
        self.env["FINTO_VIVI"] = "[]"  # fermato il lavoro: al fine turno dopo parte
        self.hook("Stop", "AGENTE-T", 210)
        self.assertEqual(len(self.lanci()), 1)

    # --- doppio riavvio (SUP 13/11 22:37:42 / 22:38:23) ---
    def test_secondo_stop_stessa_sessione_nota_toccata(self):
        n = self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        self.assertEqual(len(self.lanci()), 1)
        t = time.time() + 5
        os.utime(n, (t, t))  # la nota cambia durante il turno FERMA
        self.hook("Stop", "COORD-T", 160)
        time.sleep(1.5)
        self.assertEqual(len(self.lanci()), 1, "secondo lancio per la stessa sessione")

    def test_rc3_e_esito_buono(self):
        self.env["FINTO_RC"] = "3"
        self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        self.lanci()
        time.sleep(1.0)
        self.assertNotIn("sup riprendi", open(self.log).read())
        self.assertTrue(os.path.exists(os.path.join(self.stato, "riavvio-COORD-T.json")), "firma tolta dopo rc=3")

    def test_rc1_toglie_pausa_e_firma(self):
        self.env["FINTO_RC"] = "1"
        self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        self.lanci()
        time.sleep(1.0)
        self.assertIn("sup riprendi", open(self.log).read())

    def test_sessione_nuova_non_rilancia(self):
        self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160, sid="vecchia")
        self.assertEqual(len(self.lanci()), 1)
        self.hook("Stop", "COORD-T", 5, sid="nuova")  # stessa nota (non ancora letta da /riparti)
        time.sleep(1.5)
        self.assertEqual(len(self.lanci()), 1)

    # --- 24/11: ritenta da sola, pausa solo a guardie verdi ---
    def opzioni(self, **k):
        with open(self.conf) as f:
            conf = json.load(f)
        conf.update(k)
        with open(self.conf, "w") as f:
            json.dump(conf, f)

    def aspetta(self, vero, secondi=8):
        fine = time.time() + secondi
        while time.time() < fine and not vero():
            time.sleep(0.1)
        time.sleep(0.7)

    def finti(self):
        return open(self.log).read().splitlines()

    def n_lanci(self):
        return sum(l.startswith("riavvia") for l in self.finti())

    def riavvii(self):
        try:
            return open(os.path.join(self.t, "riavvii.log")).read()
        except OSError:
            return ""

    def test_ritenta_senza_un_altro_stop(self):
        for nome in ("COORD-T", "AGENTE-T"):
            with self.subTest(nome):
                open(self.log, "w").close()
                self.opzioni(ritenta_s=0.2)
                self.env["FINTO_RC"] = "2,2,0"
                self.nota(nome)
                self.hook("Stop", nome, 160, sid="sid-" + nome, cwd="/x")
                self.aspetta(lambda: self.n_lanci() >= 3)
                self.assertEqual(self.n_lanci(), 3)
                self.assertTrue(all(f"--sid sid-{nome}" in l for l in self.finti() if l.startswith("riavvia")))
                self.assertIn("tentativo 2", self.riavvii())
                self.assertNotIn("RIAVVIO FALLITO " + nome, self.riavvii())
                self.assertTrue(os.path.exists(os.path.join(self.stato, f"riavvio-{nome}.json")))

    def test_ritenta_non_oltre_il_tempo_e_avvisa(self):
        self.opzioni(ritenta_s=0.2, riavvio_max_s=2)
        self.env["FINTO_RC"] = "2"
        self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        self.aspetta(lambda: "RIAVVIO FALLITO" in self.riavvii())
        self.assertRegex(self.riavvii(), r"(?m)^\S+ \S+ RIAVVIO FALLITO COORD-T \S+ \(riavvio \d{4}-\d\d-\d\d \d\d:\d\d:\d\d\): .+$")
        n = self.n_lanci()
        self.assertGreater(n, 1)
        time.sleep(1)
        self.assertEqual(self.n_lanci(), n)
        self.assertFalse(os.path.exists(os.path.join(self.stato, "riavvio-COORD-T.json")), "firma rimasta: il prossimo fine turno non riprova")

    def test_ritenta_si_ferma_a_nota_vecchia(self):
        self.opzioni(ritenta_s=0.2, nota_fresca_s=2)
        self.env["FINTO_RC"] = "2"
        self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        self.aspetta(lambda: "RIAVVIO FALLITO" in self.riavvii())
        self.assertIn("nota", self.riavvii().split("RIAVVIO FALLITO")[1])

    def test_ritenta_nota_riscritta_continua(self):
        """Nota riscritta durante l'attesa: si continua con quella nuova (il suo Stop e' gia' passato)."""
        self.opzioni(ritenta_s=0.2, nota_fresca_s=3)
        self.env["FINTO_RC"] = "2," * 40 + "0"
        n = self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        for _ in range(10):
            time.sleep(0.5)
            os.utime(n)
        self.assertNotIn("RIAVVIO FALLITO", self.riavvii())
        self.assertGreater(self.n_lanci(), 4)
        os.remove(n)  # letta da /riparti: si smette, senza allarme
        self.aspetta(lambda: False, 1.5)
        k = self.n_lanci()
        time.sleep(1)
        self.assertEqual(self.n_lanci(), k)
        self.assertNotIn("RIAVVIO FALLITO", self.riavvii())
        self.assertFalse(os.path.exists(os.path.join(self.stato, "riavvio-COORD-T.json")), "processo caduto: firma rimasta")

    def test_nota_letta_prima_di_trascrivi_niente_pausa(self):
        """Nota letta fra la guardia verde e --prima: niente trascrivi ne' pausa, la nota non rinasce."""
        self.hook("Stop", "COORD-T", 10)  # crea la cartella di stato
        subprocess.run([sys.executable, GUARDIA, "--prima-riavvio", "COORD-T"], env=self.env, timeout=30)
        self.assertEqual([l for l in self.finti() if l.startswith("sup")], [])
        self.assertEqual(os.listdir(self.passaggi), [])

    def test_nota_letta_durante_trascrivi_niente_pausa(self):
        self.hook("Stop", "COORD-T", 10)
        self.env["FINTO_TRASCRIVI_SLEEP"] = "1"
        n = self.nota("COORD-T")
        p = subprocess.Popen([sys.executable, GUARDIA, "--prima-riavvio", "COORD-T"], env=self.env)
        fine = time.time() + 5
        while time.time() < fine and "sup trascrivi" not in self.finti():
            time.sleep(0.05)
        os.remove(n)
        p.wait(30)
        self.assertEqual([l for l in self.finti() if l.startswith("sup")], ["sup trascrivi"])
        self.assertEqual(os.listdir(self.passaggi), [])

    def test_altri_codici_non_ritenta(self):
        self.opzioni(ritenta_s=0.2)
        for rc in ("4", "5", "6", "8"):
            with self.subTest(rc):
                open(self.log, "w").close()
                self.env["FINTO_RC"] = rc
                self.nota("COORD-T")
                self.hook("Stop", "COORD-T", 160, sid="s" + rc)
                self.aspetta(lambda: "sup riprendi" in self.finti())
                self.assertEqual(self.n_lanci(), 1)

    def test_guardie_rosse_niente_pausa(self):
        self.opzioni(ritenta_s=0.2, riavvio_max_s=2)
        self.env.update(FINTO_RC="2", FINTO_VERDE="0")
        self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        self.aspetta(lambda: "RIAVVIO FALLITO" in self.riavvii())
        self.assertEqual([l for l in self.finti() if l.startswith("sup")], [], "pausa, riprendi o trascrivi a guardie rosse")

    def test_guardie_verdi_trascrivi_poi_pausa(self):
        self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        self.aspetta(lambda: "sup pausa" in self.finti(), 4)
        self.assertEqual([l for l in self.finti() if l.startswith("sup")], ["sup trascrivi", "sup pausa"])
        n = os.path.getmtime(os.path.join(self.passaggi, "COORD-T.md"))
        with open(os.path.join(self.stato, "riavvio-COORD-T.json")) as f:
            self.assertEqual(json.load(f)["nota"], f"{n:.0f}")  # trascrivi riscrive la nota, la data resta

    def test_pausa_tolta_fra_un_tentativo_e_l_altro(self):
        self.opzioni(ritenta_s=0.2)
        self.env["FINTO_RC"] = "2,0"
        self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        self.aspetta(lambda: self.n_lanci() >= 2)
        self.assertEqual([l.split()[1] for l in self.finti() if l.startswith("sup")],
                         ["trascrivi", "pausa", "riprendi", "trascrivi", "pausa"])

    # --- G20: lock con età e tempo massimo del riavvio ---
    def firma(self, nome, eta):
        os.makedirs(self.stato, exist_ok=True)
        with open(os.path.join(self.stato, f"riavvio-{nome}.json"), "w") as f:  # pid vivo (questo processo), altra nota
            json.dump({"nota": "1", "sid": "altra", "pid": os.getpid(), "t": time.time() - eta}, f)

    def test_firma_recente_pid_vivo_non_rilancia(self):
        self.nota("COORD-T")
        self.firma("COORD-T", 60)
        self.hook("Stop", "COORD-T", 160)
        time.sleep(1.5)
        self.assertEqual(self.lanci(0.5), [])

    def test_firma_vecchia_pid_vivo_rilancia(self):  # pid riusato o riavvio appeso: non blocca per sempre
        self.nota("COORD-T")
        self.firma("COORD-T", 1800 + 200)
        self.hook("Stop", "COORD-T", 160)
        self.assertEqual(len(self.lanci()), 1)

    def test_riavvio_appeso_scade(self):
        with open(self.conf) as f:
            conf = json.load(f)
        conf["riavvio_max_s"] = 1
        with open(self.conf, "w") as f:
            json.dump(conf, f)
        self.env["FINTO_SLEEP"] = "10"
        self.nota("COORD-T")
        self.hook("Stop", "COORD-T", 160)
        self.lanci()
        fine = time.time() + 6
        while time.time() < fine and "sup riprendi" not in open(self.log).read():
            time.sleep(0.2)
        self.assertIn("sup riprendi", open(self.log).read())
        self.assertFalse(os.path.exists(os.path.join(self.stato, "riavvio-COORD-T.json")), "firma rimasta dopo lo scaduto")
        self.assertIn("SCADUTO", open(os.path.join(self.stato, "guardia.log")).read())


if __name__ == "__main__":
    unittest.main()
