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
FIDUCIA = [" Accessing workspace:", " /tmp/prova", "", " Quick safety check: Is this a project you created or one you trust?",
           " ❯ 1. Yes, I trust this folder", "   2. No, continue without these permissions", "", " Enter to confirm · Esc to cancel"]
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
        self.assertEqual(sblocca.classifica(FIDUCIA, "/tmp/prova", ["/tmp"])["scelta"], 1)
        self.assertEqual(sblocca.classifica(FIDUCIA, "/etc", ["/tmp"])["scelta"], 2)
        self.assertEqual(sblocca.classifica(FIDUCIA, "/tmpx", ["/tmp"])["scelta"], 2)   # prefisso non è radice

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

    def test_vuoto(self):
        self.assertIsNone(sblocca.classifica([]))
        self.assertIsNone(sblocca.classifica(["$ sleep 600"]))


class NomeCopia(unittest.TestCase):
    def test_nomi(self):
        self.assertEqual(doppia.nome_copia("METODO"), "METODO-2")
        self.assertEqual(doppia.nome_copia("METODO-2"), "METODO-3")


if __name__ == "__main__":
    unittest.main()
