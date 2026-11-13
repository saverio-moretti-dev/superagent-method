#!/usr/bin/env python3
"""Installa (o toglie) contesto-guardia.py come hook utente di Claude Code.

  installa-guardia.py              -> aggiunge l'hook a UserPromptSubmit, PostToolUse, PreToolUse, Stop in ~/.claude/settings.json
  installa-guardia.py --togli      -> lo toglie
  installa-guardia.py --prova      -> dice cosa farebbe, senza scrivere
  opzioni: --settings FILE (default ~/.claude/settings.json)

Idempotente: se l'hook c'e' gia' non lo duplica. Prima di scrivere fa una copia FILE.bak-AAAAMMGG-HHMM.
Cambiare settings.json e' un cambio di impostazioni: si lancia solo con l'approvazione di chi usa la macchina.
Spegnimento d'emergenza senza toccare settings.json: touch ~/.claude/consumo/contesto-guardia.off
"""
import json, os, shutil, sys, time

GUARDIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contesto-guardia.py")
COMANDO = f'python3 "{GUARDIA}"'
EVENTI = ("UserPromptSubmit", "PostToolUse", "PreToolUse", "Stop")


def main(a):
    s_path = a[a.index("--settings") + 1] if "--settings" in a else os.path.expanduser("~/.claude/settings.json")
    togli, prova = "--togli" in a, "--prova" in a
    try:
        with open(s_path, encoding="utf-8") as f:
            s = json.load(f)
    except FileNotFoundError:
        s = {}
    hooks = s.setdefault("hooks", {})
    cambi = []
    for ev in EVENTI:
        gruppi = hooks.setdefault(ev, [])
        c_e = any(h.get("command") == COMANDO for g in gruppi for h in g.get("hooks", []))
        if togli and c_e:
            for g in gruppi:
                g["hooks"] = [h for h in g.get("hooks", []) if h.get("command") != COMANDO]
            hooks[ev] = [g for g in gruppi if g.get("hooks")]
            cambi.append(f"tolto da {ev}")
        elif not togli and not c_e:
            gruppi.append({"hooks": [{"type": "command", "command": COMANDO, "timeout": 30}]})
            cambi.append(f"aggiunto a {ev}")
        if not hooks.get(ev):
            hooks.pop(ev, None)
    if not cambi:
        print("niente da fare: " + ("non installato" if togli else "gia' installato"))
        return 0
    print("\n".join(cambi))
    if prova:
        print("(prova: niente scritto)")
        return 0
    if os.path.exists(s_path):
        bak = f"{s_path}.bak-{time.strftime('%Y%m%d-%H%M')}"
        shutil.copy2(s_path, bak)
        print(f"copia: {bak}")
    with open(s_path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
        f.write("\n")
    json.load(open(s_path + ".tmp", encoding="utf-8"))  # controllo: JSON valido prima di sostituire
    os.replace(s_path + ".tmp", s_path)
    print(f"scritto {s_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
