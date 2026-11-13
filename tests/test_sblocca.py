#!/usr/bin/env python3
"""Prove di classifica() di sblocca.py e nome_copia() di doppia.py su schermi costruiti (nessuna scheda vera)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import doppia  # noqa: E402
import sblocca  # noqa: E402

BORDO = "─" * 60
CASELLA = ["● Fatto.", "", BORDO, "❯ ", BORDO, "  ? for shortcuts"]
USCITA = ["", BORDO, " Background work is running", " The following will stop when you exit:", "  · Monitor tail -F x", "",
          " ❯ 1. Exit and stop tasks", "   2. Move to background and exit", "   3. Stay", "", " Enter to confirm · Esc to cancel"]
PERMESSO = [BORDO, " Bash command", "   rm -rf build", "", " Do you want to proceed?", " ❯ 1. Yes",
            "   2. Yes, and don't ask again for rm commands", "   3. No, and tell Claude what to do differently (esc)"]
# Copiato dallo schermo vero (13/11, v2.1.325): opzioni senza numero, evidenziata «No, exit».
FIDUCIA = [" Accessing workspace:", "", " /tmp/prova", "", " Quick safety check: Is this a project you created or one you trust?",
           "", " Claude Code'll be able to read, edit, and execute files here.", "", " Security guide", "",
           " ❯ No, exit", "   Yes, I trust this folder", "", " Enter to confirm · Esc to cancel"]
CASELLA_VERA = ["⚠ Your login expires in 2 days", "", "─" * 64 + " PROVA ─", '❯ Try "how do I log an error?"', "─" * 80,
                "  consumo: in attesa del primo messaggio"]
IMPOSTAZIONI = [" Managed settings require approval", " ❯ 1. Yes, I trust these settings", "   2. No, exit Claude Code"]
MENU = [" Which plot do you prefer?", " ❯ 1. Plot A", "   2. Plot B", "   3. Type something.", "", " Enter to select · ↑/↓ to navigate · Esc to cancel"]
DISCORSO = ["● Ecco i passi:", "  1. leggere", "  2. scrivere", "  Do you want to proceed with this plan?", ""] + CASELLA


class Classifica(unittest.TestCase):
    def test_casella_aperta_niente(self):
        self.assertIsNone(sblocca.classifica(CASELLA))
        self.assertIsNone(sblocca.classifica(DISCORSO))   # domanda e lista nel discorso, casella aperta: niente

    def test_uscita_stay(self):
        d = sblocca.classifica(CASELLA[:2] + USCITA)
        self.assertEqual((d["chiave"], d["scelta"]), ("uscita", 3))

    def test_uscita_senza_background(self):
        d = sblocca.classifica(USCITA[:6] + [" ❯ 1. Exit and stop tasks", "   2. Stay"])
        self.assertEqual(d["scelta"], 2)

    def test_permesso_no(self):
        d = sblocca.classifica(PERMESSO)
        self.assertEqual((d["chiave"], d["scelta"]), ("permesso", 3))

    def test_fiducia_radice(self):
        d = sblocca.classifica(FIDUCIA, "/tmp/prova", ["/tmp"])
        self.assertEqual((d["scelta"], d["evidenziata"], sblocca.tasti(d)), (2, 1, "\x1b[B"))
        self.assertIsNone(sblocca.classifica(FIDUCIA, "/etc", ["/tmp"])["scelta"])      # fuori: solo avviso
        self.assertIsNone(sblocca.classifica(FIDUCIA, "/tmpx", ["/tmp"])["scelta"])     # prefisso non è radice

    def test_casella_vera(self):
        self.assertIsNone(sblocca.classifica(CASELLA_VERA))

    def test_tasti_su(self):
        d = sblocca.classifica(USCITA)
        self.assertEqual(sblocca.tasti(d), "\x1b[B\x1b[B")
        d["evidenziata"] = 3
        d["scelta"] = 1
        self.assertEqual(sblocca.tasti(d), "\x1b[A\x1b[A")

    def test_impostazioni_non_tocca(self):
        d = sblocca.classifica(IMPOSTAZIONI)
        self.assertEqual((d["chiave"], d["scelta"]), ("impostazioni", None))

    def test_menu_sconosciuto(self):
        d = sblocca.classifica(MENU)
        self.assertEqual((d["chiave"], d["scelta"]), ("sconosciuto", None))
        self.assertEqual(len(d["opzioni"]), 3)

    def test_firma_stabile(self):
        self.assertEqual(sblocca.classifica(PERMESSO)["firma"], sblocca.classifica(["altro"] + PERMESSO)["firma"])

    def test_opzione_mancante(self):
        d = sblocca.classifica([" Background work is running", " ❯ 1. Exit and stop tasks", "   2. Something new"])
        self.assertEqual((d["chiave"], d["scelta"]), ("uscita-senza-opzione", None))

    def test_menu_con_freccia(self):   # /model vero: «↑ 3.» in cima alla lista visibile
        d = sblocca.classifica([" Select model", "   ↑ 3.  Fable", "     4.  Sonnet", "   ❯ 5.  Haiku ✔", "      … +1 model",
                                " Enter to set as default · Esc to cancel"])
        self.assertEqual(([n for n, _ in d["opzioni"]], d["chiave"]), ([3, 4, 5], "sconosciuto"))

    def test_vuoto(self):
        self.assertIsNone(sblocca.classifica([]))
        self.assertIsNone(sblocca.classifica(["$ sleep 600"]))


class NomeCopia(unittest.TestCase):
    def test_nomi(self):
        self.assertEqual(doppia.nome_copia("METODO"), "METODO-2")
        self.assertEqual(doppia.nome_copia("METODO-2"), "METODO-3")


if __name__ == "__main__":
    unittest.main()
