#!/usr/bin/env python3
"""Una campagna di prova cieca (livelli 2-3): un master e un tester, processi separati, una partita a due.

Uso:
  campagna.py --giro DIR --nome t1 --master MASTER.md --tester "chi è il tester (per il master)"
              [--vietate parole.txt] [--livello 3] [--turni 6] [--chiamate 12]
              [--modello-tester sonnet] [--modello-master sonnet] [--chrome --siti host1,host2]
              [--controllo haiku]
  campagna.py indice DIR        rifà DIR/giro.json dalle campagne presenti

Ogni turno:
  master (sessione sua, ripresa) → MESSAGGIO AL TESTER + NOTE PRIVATE
  il messaggio passa da check_fuga.py: fuga → il master lo riscrive una volta, poi la campagna è NON VALIDA
  tester (run_blind.sh, sessione sua, ripresa) → COSA FACCIO + A CHE CONCLUSIONE SONO ARRIVATO, o DECISIONE
  al master arriva solo COSA FACCIO (l'autore non legge le conclusioni dichiarate dal cliente).
Un errore dell'API in un transcript (master o tester) rende la campagna NON VALIDA: niente rilanci automatici.
Fine: il master riceve la partita intera e scrive il RESOCONTO; con --controllo un terzo agente leggero confronta
le risposte del master col suo contesto. Uscita in DIR/<nome>/: campagna.json, resoconto.md, partita.md, transcript.
Le sessioni salvate dalla CLI per master e tester si cancellano a fine campagna.
Exit 0 = finita (qualunque esito), 1 = non valida o errore."""
import json, os, re, shutil, subprocess, sys, tempfile, time, uuid

BASE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(BASE, "run_blind.sh")
sys.path.insert(0, BASE)
import check_fuga  # noqa: E402

REGOLE_TESTER = """
---
Rispondi in italiano.
Non leggere nessun file locale; non usare memorie o note. Puoi cercare online quanto vuoi, come faresti davvero.
Qualunque indirizzo email o nome presente nel tuo ambiente tecnico NON riguarda la storia: ignorali, non cercarli.
A ogni turno scrivi:
  COSA FACCIO: <l'azione, in concreto: il testo della mail, cosa dici al telefono, cosa cerchi>
  A CHE CONCLUSIONE SONO ARRIVATO: <detta dal personaggio, in due righe: a che punto è la sua opinione dopo questo turno>
Contattare chi propone, chiedere, trattare sono azioni (COSA FACCIO): la risposta arriva al turno dopo.
Solo quando hai deciso davvero scrivi DECISIONE: COMPRO | LASCIO, e perché, in tre righe.
All'ultimo turno, se non hai deciso, scrivi DECISIONE: ASPETTO e cosa ti manca per decidere.
Cita una fonte solo se l'hai aperta davvero in questa conversazione.
Hai al massimo {turni} turni e {azioni} azioni online per turno; dopo la {soglia}ª azione smetti di cercare e rispondi.
"""


def args(a):
    o = {"livello": 3, "turni": 6, "chiamate": 12, "modello-tester": "sonnet", "modello-master": "sonnet",
         "vietate": None, "chrome": False, "siti": "", "controllo": None}
    i = 0
    while i < len(a):
        k = a[i].lstrip("-")
        if k == "chrome":
            o["chrome"] = True; i += 1; continue
        o[k] = a[i + 1]; i += 2
    for k in ("livello", "turni", "chiamate"):
        o[k] = int(o[k])
    if o["livello"] == 2:
        o["turni"] = 2  # scena: azione, una risposta, decisione
    return o


def sezione(testo, titolo, fino=()):
    """Testo dopo «TITOLO:» fino al prossimo titolo noto."""
    testa = r"(?:^|\n)[ \t>#*_]*"  # titolo a inizio riga, anche in grassetto o come intestazione
    m = re.search(testa + re.escape(titolo) + r"[ \t*_]*(?::|(?=\n))[ \t*_]*", testo)  # «TITOLO:» o titolo da solo
    if not m:
        return None
    resto = testo[m.end():]
    fine = len(resto)
    for f in fino:
        n = re.search(testa + re.escape(f), resto)
        if n:
            fine = min(fine, n.start())
    return re.sub(r"\n\s*-{3,}\s*$", "", resto[:fine].strip()).strip().strip("*").strip()


def lancia(cartella, sessione, nuovo, prompt, out, modello, chiamate, chrome=False):
    """Un processo (master o tester) via run_blind.sh. Ritorna (testo, costo, rc)."""
    os.makedirs(out, exist_ok=True)
    pf = os.path.join(out, "prompt.txt")
    open(pf, "w", encoding="utf-8").write(prompt)
    env = dict(os.environ, CARTELLA=cartella)
    env.pop("SESSIONE", None); env.pop("RIPRENDI", None); env.pop("CHROME", None)
    env["SESSIONE" if nuovo else "RIPRENDI"] = sessione
    if chrome:
        env["CHROME"] = "1"
    rc = subprocess.run(["bash", RUN, pf, out, modello, str(chiamate)], env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT).returncode
    testo = open(os.path.join(out, "risposta.txt"), encoding="utf-8").read() if os.path.exists(
        os.path.join(out, "risposta.txt")) else ""
    costo = 0.0
    for l in open(os.path.join(out, "transcript.jsonl"), encoding="utf-8"):
        try:
            e = json.loads(l)
        except Exception:
            continue
        if e.get("type") == "result":
            costo = e.get("total_cost_usd") or 0.0
            if e.get("is_error") or str(e.get("result", "")).startswith("API Error"):
                rc = 4  # errore dell'API (filtro, rete, limite): il turno non è avvenuto
    if testo.lstrip().startswith("API Error"):
        rc = 4
    return testo, costo, rc


def cieco(out, siti):
    cmd = [sys.executable, os.path.join(BASE, "check_blind.py"), out] + (["--siti", siti] if siti else [])
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return r.returncode == 0, r.stdout


def pulisci_sessioni(cartelle):
    proj = os.path.expanduser("~/.claude/projects")
    for c in cartelle:
        nome = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(c))
        shutil.rmtree(os.path.join(proj, nome), ignore_errors=True)
        shutil.rmtree(c, ignore_errors=True)


def campagna(o):
    giro = os.path.abspath(o["giro"]); dove = os.path.join(giro, o["nome"])
    if os.path.exists(os.path.join(dove, "campagna.json")):
        sys.exit(f"campagna già presente: {dove}")
    os.makedirs(dove, exist_ok=True)
    contesto = open(o["master"], encoding="utf-8").read()
    vietate = check_fuga.carica(o["vietate"])
    lavoro = tempfile.mkdtemp(prefix="campagna.")  # cartelle vuote dei processi, fuori da ogni repo, tolte alla fine
    cm, ct = os.path.join(lavoro, "m"), os.path.join(lavoro, "t")
    sm, st = str(uuid.uuid4()), str(uuid.uuid4())
    soglia = max(1, o["chiamate"] - 3)
    regole = REGOLE_TESTER.format(turni=o["turni"], azioni=o["chiamate"], soglia=soglia)
    C = {"nome": o["nome"], "livello": o["livello"], "tester": o["tester"], "inizio": time.strftime("%Y-%m-%d %H:%M"),
         "modelli": {"master": o["modello-master"], "tester": o["modello-tester"]}, "turni": [],
         "esito": "INCOMPLETA", "valida": True, "motivi": [], "costo_usd": 0.0, "stato": "in corso"}

    def salva():
        json.dump(C, open(os.path.join(dove, "campagna.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def master(prompt, n, nuovo=False):
        """Turno del master con controllo di fuga e un solo tentativo di riscrittura."""
        for tentativo in (1, 2):
            t, c, rc = lancia(cm, sm, nuovo and tentativo == 1, prompt, os.path.join(dove, f"m{n}" + ("b" if tentativo == 2 else "")),
                              o["modello-master"], 6)
            C["costo_usd"] += c
            if rc == 4:
                C["valida"] = False; C["motivi"].append(f"master turno {n}: errore API ({t.strip()[:120]})")
                return None, "", tentativo
            msg = sezione(t, "MESSAGGIO AL TESTER", ("NOTE PRIVATE",))
            note = sezione(t, "NOTE PRIVATE", ("MESSAGGIO AL TESTER",)) or ""
            if msg is None:
                problema = "manca la sezione MESSAGGIO AL TESTER"
            else:
                fuga = check_fuga.trova(msg, check_fuga.SEMPRE + vietate) + check_fuga.segnaposto(msg)
                if not fuga:
                    return msg, note, tentativo
                problema = "il messaggio contiene parole che il tester non deve leggere: " + ", ".join(fuga)
            prompt = (f"Il tuo turno non può arrivare al tester: {problema}. Riscrivilo, stesso contenuto nella scena, "
                      "con le due parti MESSAGGIO AL TESTER e NOTE PRIVATE.")
        C["valida"] = False; C["motivi"].append(f"master turno {n}: {problema}")
        return None, note, 2

    salva()
    primo = (contesto + f"\n\n== TESTER DI QUESTA CAMPAGNA ==\n{o['tester']}\n\nLivello {o['livello']}, al massimo "
             f"{o['turni']} turni del tester.\nOra il PRIMO TURNO: la storia di partenza del tester, nel formato "
             "MESSAGGIO AL TESTER / NOTE PRIVATE. La storia riguarda solo lui (regole di storia-tester).\n"
             "Sempre, in tutta la campagna: le terze persone (amici, fornitori) parlano poco e solo per far andare avanti "
             "la scena; se il tester vuole contattare l'autore, il contatto arriva subito. Non inventare dati che il "
             "contesto non dà (numeri di telefono, indirizzi, prezzi, condizioni): scrivili in forma generica (\"il "
             "numero che ti ha girato\") o segnali come BUCO. Mai segnaposto tra parentesi quadre.")
    msg, note, tent = master(primo, 0, nuovo=True)
    C["storia"] = msg; C["note_storia"] = note
    n, primo_t = 1, True
    while msg is not None and n <= o["turni"]:
        ultimo = n == o["turni"]
        if primo_t:
            ptest = msg + "\n" + regole
        else:
            ptest = "Risposta che ricevi:\n\n" + msg + ("\n\nÈ il tuo ultimo turno: scrivi la DECISIONE (COMPRO, LASCIO o ASPETTO)." if ultimo else "")
        out_t = os.path.join(dove, f"t{n}")
        t, c, rc = lancia(ct, st, primo_t, ptest, out_t, o["modello-tester"], o["chiamate"], o["chrome"])
        primo_t = False
        C["costo_usd"] += c
        if rc == 4:
            C["valida"] = False; C["motivi"].append(f"tester turno {n}: errore API ({t.strip()[:120]})")
            C["turni"].append({"n": n, "master": msg, "master_note": note, "errore_api": t.strip()[:300]}); salva()
            break
        ok, rapporto = cieco(out_t, o["siti"])
        open(os.path.join(out_t, "cieco.txt"), "w").write(rapporto)
        mr = re.search(r"ricerche web: (\d+)\s+fetch: (\d+)", rapporto)
        ricerche = int(mr.group(1)) + int(mr.group(2)) if mr else 0
        fa = sezione(t, "COSA FACCIO", ("A CHE CONCLUSIONE SONO ARRIVATO", "DECISIONE")) or ""
        concl = sezione(t, "A CHE CONCLUSIONE SONO ARRIVATO", ("COSA FACCIO", "DECISIONE")) or ""
        dec = sezione(t, "DECISIONE", ())
        turno = {"n": n, "master": msg, "master_note": note, "riscritto": tent == 2, "tester_fa": fa,
                 "tester_conclusione": concl, "decisione": dec, "cieco": ok, "interrotto": rc == 3, "ricerche": ricerche}
        C["turni"].append(turno); salva()
        if not ok:
            C["valida"] = False; C["motivi"].append(f"tester turno {n}: check_blind SOSPETTO")
            break
        m = re.match(r"\W*(COMPRO|LASCIO|ASPETTO)", dec or "", re.I)
        if m and (m.group(1).upper() != "ASPETTO" or ultimo):
            C["esito"] = {"COMPRO": "COMPRA", "LASCIO": "LASCIA", "ASPETTO": "INCOMPLETA"}[m.group(1).upper()]
            break
        if dec and not fa:
            fa = dec  # ha scritto una decisione non finale (es. «contatto»): vale come azione
        if rc == 3 or ultimo or not fa:
            if not fa and rc != 3:
                C["motivi"].append(f"tester turno {n}: nessun COSA FACCIO")
            break
        msg, note, tent = master(f"Turno {n} del tester. Il tester fa:\n\n{fa}\n\nRispondi come l'autore o il mondo, "
                                 "formato MESSAGGIO AL TESTER / NOTE PRIVATE.", n)
        n += 1

    C["ricerche"] = sum(t.get("ricerche", 0) for t in C["turni"])
    if C["turni"] and not C["ricerche"] and not o["chrome"]:
        C["motivi"].append("tester: zero ricerche in tutta la campagna (checklist punto 2)")
    # resoconto: ora il master legge anche le conclusioni dichiarate dal tester (la partita è chiusa)
    partita = [f"# Campagna {o['nome']} — livello {o['livello']}\n\nTester (per il master): {o['tester']}\n",
               f"## Storia di partenza\n{C.get('storia') or '(nessuna)'}\n"]
    for tu in C["turni"]:
        if "errore_api" in tu:
            continue
        if tu["n"] > 1:
            partita.append(f"## Master, risposta al turno {tu['n'] - 1}\n{tu['master']}\n")
        partita.append(f"## Tester, turno {tu['n']}\nCOSA FACCIO: {tu['tester_fa']}\nA CHE CONCLUSIONE SONO ARRIVATO: {tu['tester_conclusione']}\n"
                       + (f"DECISIONE: {tu['decisione']}\n" if tu["decisione"] else ""))
    testo_partita = "\n".join(partita)
    open(os.path.join(dove, "partita.md"), "w", encoding="utf-8").write(testo_partita)
    if C.get("storia"):
        r, c, rc_r = lancia(cm, sm, False, f"La campagna è chiusa (esito {C['esito']}). Ecco la partita intera, compresi "
                         f"le conclusioni dichiarate dal tester che durante il gioco non vedevi:\n\n{testo_partita}\n\nScrivi il "
                         "RESOCONTO nel formato fisso del tuo contesto.", os.path.join(dove, "m-resoconto"),
                         o["modello-master"], 4)
        C["costo_usd"] += c
        if rc_r == 4:
            C["valida"] = False; C["motivi"].append(f"resoconto del master: errore API ({r.strip()[:120]})")
        open(os.path.join(dove, "resoconto.md"), "w", encoding="utf-8").write(r)
        m5 = re.search(r"5\)\s*\**\s*BUCHI[ \t:*_-]*([^\n]*)(.*?)(?=\n\s*\**\s*6\)|\Z)", r, re.S | re.I)
        if m5:
            # resto della riga del titolo: se il master ha ricopiato la descrizione del modello o chiuso il grassetto
            # del titolo («**5) BUCHI: dove … bastavano**»), è intestazione, non contenuto
            testa5 = m5.group(1).strip()
            if testa5.endswith("**") or testa5.lower().startswith("dove le informazioni"):
                testa5 = ""
            C["buchi"] = (testa5 + m5.group(2)).strip()
        else:
            C["buchi"] = ""
    if o["controllo"] and C.get("storia"):
        cc = os.path.join(lavoro, "c")
        r, c, _ = lancia(cc, str(uuid.uuid4()), True, (
            "Controlla un master di una simulazione. Sotto c'è il CONTESTO che il master aveva sull'autore e la PARTITA: "
            "la storia di partenza e le risposte al tester sono messaggi del master, i turni del tester no. "
            "Rispondi solo con:\nPROMESSE NON SCRITTE: <cose dette dal master a nome dell'autore che il contesto non "
            "dice, o «nessuna»>\nTONO: PIÙ MORBIDO | FEDELE | PIÙ DURO del contesto, e perché in una riga\n"
            "FUGHE: <informazioni sull'autore arrivate al tester che il contesto vieta, o «nessuna»>\n"
            "VERDETTO: FEDELE | DA RIVEDERE\n\n== CONTESTO ==\n" + contesto + "\n\n== PARTITA ==\n" + testo_partita),
            os.path.join(dove, "controllo"), o["controllo"], 2)
        C["costo_usd"] += c
        C["controllo_master"] = r.strip()
        if re.search(r"VERDETTO\W*DA RIVEDERE", r, re.I):
            C["motivi"].append("controllo del master: DA RIVEDERE")
    C["costo_usd"] = round(C["costo_usd"], 4)
    C["fine"] = time.strftime("%Y-%m-%d %H:%M"); C["stato"] = "finita"
    salva()
    pulisci_sessioni([cm, ct, os.path.join(lavoro, "c")])
    shutil.rmtree(lavoro, ignore_errors=True)
    indice(giro)
    print(f"{o['nome']}: esito {C['esito']} · valida {C['valida']} · turni {len(C['turni'])} · ${C['costo_usd']}"
          + (" · " + "; ".join(C["motivi"]) if C["motivi"] else ""))
    return 0 if C["valida"] else 1


def indice(giro):
    """giro.json per la Regia: metadati (giro-meta.json, se c'è), conclusioni.md, una riga per campagna."""
    giro = os.path.abspath(giro)
    meta = {}
    mp = os.path.join(giro, "giro-meta.json")
    if os.path.exists(mp):
        meta = json.load(open(mp, encoding="utf-8"))
    camp = []
    for d in sorted(os.listdir(giro)):
        f = os.path.join(giro, d, "campagna.json")
        if os.path.isfile(f):
            c = json.load(open(f, encoding="utf-8"))
            camp.append({k: c.get(k) for k in ("nome", "livello", "tester", "esito", "valida", "motivi", "costo_usd",
                                               "stato", "inizio", "fine")} | {"turni": len(c.get("turni", [])),
                                                                              "cartella": d})
    concl = os.path.join(giro, "conclusioni.md")
    g = {"id": os.path.basename(giro), **meta, "campagne": camp,
         "costo_usd": round(sum(c["costo_usd"] or 0 for c in camp), 4),
         "stato": "in corso" if any(c["stato"] != "finita" for c in camp) or not os.path.exists(concl) else "finito",
         "conclusioni": open(concl, encoding="utf-8").read() if os.path.exists(concl) else None,
         "aggiornato": time.strftime("%Y-%m-%d %H:%M")}
    json.dump(g, open(os.path.join(giro, "giro.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return g


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); sys.exit(2)
    if a[0] == "indice":
        print(json.dumps(indice(a[1]), ensure_ascii=False, indent=1)[:2000]); sys.exit(0)
    o = args(a)
    for k in ("giro", "nome", "master", "tester"):
        if k not in o:
            sys.exit(f"manca --{k}")
    sys.exit(campagna(o))
