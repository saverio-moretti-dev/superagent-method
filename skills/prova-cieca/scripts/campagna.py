#!/usr/bin/env python3
"""Alias per un giro (14/11): campagna.py si chiama ora storia.py (argomento > campagna > storia).
Inoltra tutto a storia.py; da togliere al giro dopo, insieme a campagna.json e alla chiave "campagne" di giro.json."""
import os, sys
os.execv(sys.executable, [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "storia.py")] + sys.argv[1:])
