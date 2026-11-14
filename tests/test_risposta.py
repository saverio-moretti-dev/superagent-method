#!/usr/bin/env python3
"""Test di skills/prova-cieca/scripts/risposta.py: quale testo del turno finisce in risposta.txt. python3 tests/test_risposta.py"""
import importlib.util, json, os, shutil, subprocess, tempfile, unittest

QUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(QUI, "..", "skills", "prova-cieca", "scripts", "risposta.py")
spec = importlib.util.spec_from_file_location("risposta", SCRIPT)
risposta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(risposta)

RISPOSTA = ("COSA FACCIO: Ho aperto la pagina sul telefono e l'ho letta. Rispondo all'amico: «girami la mail»\n\n"
            "A CHE CONCLUSIONE SONO ARRIVATO: pagina chiara, prezzo in evidenza.\n\nDECISIONE: ASPETTO, mi manca il prezzo totale.")


def testo(t):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}}


def strumento(n):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": n, "input": {}}]}}


def result(t, subtype="success"):
    return {"type": "result", "subtype": subtype, "result": t}


class Risposta(unittest.TestCase):
    def setUp(self):
        self.o = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.o, ignore_errors=True)

    def gira(self, eventi, interrotto=None):
        with open(os.path.join(self.o, "transcript.jsonl"), "w") as f:
            for e in eventi:
                f.write(json.dumps(e) + "\n")
        if interrotto:
            open(os.path.join(self.o, "INTERROTTO"), "w").write(interrotto)
        risposta.estrai(self.o)
        return open(os.path.join(self.o, "risposta.txt")).read()

    def test_casa_scheda_chiusa_dopo(self):  # prova CASA 14/11: risposta, poi chiude la scheda e scrive solo quello
        r = self.gira([strumento("navigate"), strumento("computer"), testo(RISPOSTA), strumento("tabs_close_mcp"),
                       testo("Ho chiuso la scheda del browser."), result("Ho chiuso la scheda del browser.")])
        self.assertEqual(r, RISPOSTA)

    def test_normale(self):
        self.assertEqual(self.gira([strumento("navigate"), testo(RISPOSTA), result(RISPOSTA)]), RISPOSTA)

    def test_result_senza_formato_e_nessun_testo_col_formato(self):  # niente da recuperare: resta il result
        self.assertEqual(self.gira([testo("Guardo."), result("Non so cosa dire.")]), "Non so cosa dire.")

    def test_formato_in_grassetto(self):
        t = "**COSA FACCIO:** scrivo una mail\n**A CHE CONCLUSIONE SONO ARRIVATO:** boh"
        self.assertEqual(self.gira([testo(t), testo("Fatto."), result("Fatto.")]), t)

    def test_ultimo_col_formato_vince(self):
        vecchio = "COSA FACCIO: prima idea"
        self.assertEqual(self.gira([testo(vecchio), testo(RISPOSTA), testo("Chiudo."), result("Chiudo.")]), RISPOSTA)

    def test_interrotto_prende_il_testo_col_formato(self):
        r = self.gira([testo(RISPOSTA), strumento("tabs_close_mcp"), testo("Chiudo la scheda.")], interrotto="tetto 22")
        self.assertEqual(r, "[INTERROTTO: tetto 22]\n\n" + RISPOSTA)

    def test_fermato_dalla_cli(self):
        r = self.gira([testo(RISPOSTA), testo("ok"), result("ok", "error_max_turns")])
        self.assertEqual(r, "[FERMATO dalla CLI: error_max_turns]\n\n" + RISPOSTA)

    def test_testi_dopo_il_result_ignorati(self):  # un messaggio di un'altra sessione dopo il turno non conta
        r = self.gira([testo(RISPOSTA), result(RISPOSTA), testo("COSA FACCIO: messaggio estraneo")])
        self.assertEqual(r, RISPOSTA)

    def test_nessun_result(self):
        r = self.gira([testo(RISPOSTA), testo("Chiudo.")])
        self.assertEqual(r, "[NESSUN RISULTATO: claude uscito senza evento result]\n\n" + RISPOSTA)

    def test_da_riga_di_comando(self):  # come lo chiama run_blind.sh: python3 -I risposta.py <out>
        with open(os.path.join(self.o, "transcript.jsonl"), "w") as f:
            for e in (testo(RISPOSTA), testo("Ho chiuso."), result("Ho chiuso.")):
                f.write(json.dumps(e) + "\n")
        subprocess.run(["python3", "-I", SCRIPT, self.o], check=True)
        self.assertEqual(open(os.path.join(self.o, "risposta.txt")).read(), RISPOSTA)


if __name__ == "__main__":
    unittest.main()
