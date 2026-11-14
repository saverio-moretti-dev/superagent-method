#!/usr/bin/env python3
"""Test di skills/prova-cieca/scripts/storia.py: una storia che si ferma senza risposta del tester non è valida.
Nessun processo vero: lancia() e cieco() sono finti, il turno del tester passa da risposta.py su un transcript finto.
python3 tests/test_storia_valida.py"""
import importlib.util, json, os, shutil, sys, tempfile, unittest

QUI = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(QUI, "..", "skills", "prova-cieca", "scripts")


def carica(nome):
    spec = importlib.util.spec_from_file_location(nome, os.path.join(SCRIPTS, nome + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


storia = carica("storia")
risposta = carica("risposta")

MASTER = "MESSAGGIO AL TESTER:\nUn amico ti gira il link di una pagina per la tua casa vacanze.\n\nNOTE PRIVATE:\nnessuna"
RISPOSTA = ("COSA FACCIO: Ho aperto la pagina sul telefono e l'ho letta. Scrivo all'autore per chiedere il prezzo totale.\n\n"
            "A CHE CONCLUSIONE SONO ARRIVATO: pagina chiara, prezzo in evidenza.\n\nDECISIONE: ASPETTO, mi manca il prezzo totale.")
CHIUSA = "Ho chiuso la scheda del browser."


def testo(t):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}}


def strumento(n):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": n, "input": {}}]}}


class StoriaValida(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.master = os.path.join(self.d, "MASTER.md")
        open(self.master, "w").write("contesto finto")
        self.vero_lancia, self.vero_cieco = storia.lancia, storia.cieco
        storia.cieco = lambda out, siti: (True, "ricerche web: 1  fetch: 0")

    def tearDown(self):
        storia.lancia, storia.cieco = self.vero_lancia, self.vero_cieco
        shutil.rmtree(self.d, ignore_errors=True)

    def gioca(self, eventi_tester):
        """Storia di 2 turni: il master risponde sempre, il tester (out t1, t2…) scrive gli eventi dati."""
        def lancia(cartella, sessione, nuovo, prompt, out, modello, chiamate, chrome=False):
            os.makedirs(out, exist_ok=True)
            if os.path.basename(out).startswith("t"):
                with open(os.path.join(out, "transcript.jsonl"), "w") as f:
                    for e in eventi_tester:
                        f.write(json.dumps(e) + "\n")
                return risposta.estrai(out), 0.0, 0
            return MASTER, 0.0, 0
        storia.lancia = lancia
        o = storia.args(["--giro", os.path.join(self.d, "giro"), "--nome", "casa", "--master", self.master,
                         "--tester", "titolare finto", "--turni", "2", "--chrome"])
        storia.storia(o)
        return json.load(open(os.path.join(self.d, "giro", "casa", "storia.json")))

    def test_ferma_senza_risposta_non_valida(self):
        """Prova CASA 14/11 com'era prima di a882bf2: risposta.txt = solo «Ho chiuso la scheda» → non valida."""
        C = self.gioca([testo(CHIUSA), {"type": "result", "subtype": "success", "result": CHIUSA}])
        self.assertFalse(C["valida"])
        self.assertTrue(any("nessun COSA FACCIO" in m for m in C["motivi"]), C["motivi"])
        self.assertEqual(len(C["turni"]), 1)

    def test_risposta_poi_scheda_chiusa_continua(self):
        """Risposta col formato, poi chiusura della scheda e testo senza formato: il turno vale e la storia va avanti."""
        C = self.gioca([testo(RISPOSTA), strumento("mcp__claude-in-chrome__tabs_close_mcp"), testo(CHIUSA),
                        {"type": "result", "subtype": "success", "result": CHIUSA}])
        self.assertTrue(C["valida"], C["motivi"])
        self.assertIn("prezzo totale", C["turni"][0]["tester_fa"])
        self.assertEqual(len(C["turni"]), 2)
        self.assertEqual(C["esito"], "INCOMPLETA")  # ASPETTO all'ultimo turno


if __name__ == "__main__":
    unittest.main(verbosity=2)
