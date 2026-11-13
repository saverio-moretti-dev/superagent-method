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
time.sleep(float(os.environ.get("FINTO_SLEEP", "0")))
rc = int(os.environ.get("FINTO_RC", "0"))
print("gira gia' un'altra sessione" if rc == 3 else "riavviato")
sys.exit(rc)
"""
FINTO_VIVI = """import os
print(os.environ.get("FINTO_VIVI", "[]"))
"""
FINTO_SUP = """import os, sys
open(os.environ["FINTO_LOG"], "a").write("sup " + " ".join(sys.argv[1:2]) + "\\n")
if sys.argv[1] == "trascrivi":
    open(sys.argv[2], "a").write("\\n- messaggio trascritto\\n")
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


if __name__ == "__main__":
    unittest.main()
