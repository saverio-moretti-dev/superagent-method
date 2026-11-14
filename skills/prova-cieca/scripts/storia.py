#!/usr/bin/env python3
"""Una storia di prova cieca (livelli 2-3): un master e un tester, processi separati, una partita a due.
Argomento > campagna (N storie, un master) > storia (un tester): questo programma gioca UNA storia.
Prima del 14/11 si chiamava campagna.py (resta come alias per un giro).

Uso:
  storia.py --giro DIR --nome t1 --master MASTER.md --tester "chi è il tester (per il master)"
              [--vietate parole.txt] [--livello 3] [--turni 6] [--chiamate 12]
              [--modello-tester sonnet] [--modello-master sonnet] [--chrome --siti host1,host2]
              [--controllo haiku]
              [--apertura APERTURA.txt] [--copia frasi.txt] [--eventi eventi.json] [--ritardo "due giorni"]
              [--controllo-turno haiku] [--controllo-turno-azione ferma|segna]
              [--bivio ORIGINE/storia.json --dal-turno N --risposta RISPOSTA.txt]
              [--copilota [--copilota-attesa 120] [--copilota-scadenza ferma|parte]]
  (i file --apertura/--copia/--eventi li prepara campagne.py prepara, dalle schede approvate)
  storia.py indice DIR        rifà DIR/giro.json dalle storie presenti

Ogni turno:
  master (sessione sua, ripresa) → MESSAGGIO AL TESTER + NOTE PRIVATE
  il messaggio passa da check_fuga.py: fuga → il master lo riscrive una volta, poi la storia è NON VALIDA
  tester (run_blind.sh, sessione sua, ripresa) → COSA FACCIO + A CHE CONCLUSIONE SONO ARRIVATO, o DECISIONE
  al master arriva solo COSA FACCIO (l'autore non legge le conclusioni dichiarate dal cliente).
Un errore dell'API in un transcript (master o tester) rende la storia NON VALIDA: niente rilanci automatici.
Tetto morbido: tester fermato (sorvegliante o --max-turns) prima di rispondere → si riprende la sua sessione una
volta con CHIUSURA (tetto 1) e risponde con ciò che ha visto; il turno porta «chiuso_dal_tetto». Senza risposta: NON VALIDA.
Primo turno con --apertura: il master mette in scena la storia di partenza approvata senza cambiarne i fatti; ogni riga
di --copia deve comparire identica nel messaggio, altrimenti il master lo riscrive una volta (poi NON VALIDA).
--eventi: eventi del mondo estratti prima del giro, dati al master nel turno indicato. --ritardo: tempo fra azione e risposta.
--controllo-turno: dopo ogni risposta del master un modello leggero la confronta col contesto; DA RIVEDERE → con
«ferma» (default) la storia si ferma NON VALIDA, con «segna» resta un motivo.
Fine: il master riceve la partita intera e scrive il RESOCONTO; con --controllo un terzo agente leggero confronta
le risposte del master col suo contesto. Uscita in DIR/<nome>/: storia.json, resoconto.md, partita.md, transcript.
Le sessioni salvate dalla CLI per master e tester si cancellano a fine storia.
--bivio (extra «bivi», A3; lo prepara campagne.py bivio): rigioca una storia già giocata dal turno N con un'altra risposta
del personaggio esterno, scritta dall'autore. I turni 1..N-1 si ereditano (copiati, «ereditato») e tester e master
partono in sessioni nuove con quei turni come ricordo; la risposta nuova passa da check_fuga, non dal controllo del turno
(cambiare le condizioni è lo scopo del bivio). Solo dalla stessa storia: niente da altre storie o altri tester.
--copilota (extra «copilota», D1; lo aggiunge campagne.py prepara): ogni risposta del master al tester (non la storia di
partenza) prima di partire va in DIR/<nome>/copilota/turno-N.json con stato «in attesa»; la storia aspetta che l'autore
la segni «approvata» o «corretta» con il suo testo (campagne.py copilota). La correzione passa da check_fuga: se fuga, il
file torna «in attesa» con il motivo. Attesa massima --copilota-attesa minuti (default 120): poi con «ferma» (default) la
storia si chiude NON VALIDA, con «parte» va la proposta del master, segnata «scaduta». Il turno porta «copilota».
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
Ogni chiamata conta come azione: una ricerca, una pagina aperta, e nel browser anche aprire una scheda, scorrere, fare una schermata.
"""

REGOLA_CHROME = ("Nel browser: chiudi la scheda PRIMA di scrivere la risposta. La risposta (COSA FACCIO / A CHE CONCLUSIONE SONO "
                 "ARRIVATO / DECISIONE) è l'ultima cosa che scrivi nel turno, dopo l'ultima azione.\n")  # prova CASA 14/11

CHIUSURA = ("Le azioni di questo turno sono finite: niente altre ricerche né pagine. Rispondi adesso con quello che hai già "
            "visto, nel formato COSA FACCIO / A CHE CONCLUSIONE SONO ARRIVATO (o DECISIONE se hai deciso).")


def args(a):
    o = {"livello": 3, "turni": 6, "chiamate": 12, "modello-tester": "sonnet", "modello-master": "sonnet",
         "vietate": None, "chrome": False, "siti": "", "controllo": None,
         "apertura": None, "copia": None, "eventi": None, "ritardo": "", "controllo-turno": None,
         "controllo-turno-azione": "ferma", "bivio": None, "dal-turno": None, "risposta": None,
         "copilota": False, "copilota-attesa": 120, "copilota-scadenza": "ferma"}
    i = 0
    while i < len(a):
        k = a[i].lstrip("-")
        if k in ("chrome", "copilota"):
            o[k] = True; i += 1; continue
        o[k] = a[i + 1]; i += 2
    for k in ("livello", "turni", "chiamate"):
        o[k] = int(o[k])
    o["copilota-attesa"] = float(o["copilota-attesa"])
    if o["copilota-scadenza"] not in ("ferma", "parte"):
        sys.exit("--copilota-scadenza: ferma | parte")
    if o["bivio"]:
        if not o["dal-turno"] or not o["risposta"]:
            sys.exit("--bivio chiede --dal-turno N e --risposta FILE")
        o["dal-turno"] = int(o["dal-turno"])
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


def storia(o):
    giro = os.path.abspath(o["giro"]); dove = os.path.join(giro, o["nome"])
    if os.path.exists(os.path.join(dove, "storia.json")):
        sys.exit(f"storia già presente: {dove}")
    os.makedirs(dove, exist_ok=True)
    contesto = open(o["master"], encoding="utf-8").read()
    vietate = check_fuga.carica(o["vietate"])
    lavoro = tempfile.mkdtemp(prefix="storia.")  # cartelle vuote dei processi, fuori da ogni repo, tolte alla fine
    cm, ct = os.path.join(lavoro, "m"), os.path.join(lavoro, "t")
    sm, st = str(uuid.uuid4()), str(uuid.uuid4())
    soglia = max(1, o["chiamate"] - 3)
    regole = REGOLE_TESTER.format(turni=o["turni"], azioni=o["chiamate"], soglia=soglia) + (REGOLA_CHROME if o["chrome"] else "")
    C = {"nome": o["nome"], "livello": o["livello"], "tester": o["tester"], "inizio": time.strftime("%Y-%m-%d %H:%M"),
         "modelli": {"master": o["modello-master"], "tester": o["modello-tester"]}, "turni": [],
         "esito": "INCOMPLETA", "valida": True, "motivi": [], "costo_usd": 0.0, "stato": "in corso"}

    def salva():
        json.dump(C, open(os.path.join(dove, "storia.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        vecchio = os.path.join(dove, "campagna.json")  # nome di prima (14/11): la Regia lo legge ancora; via con l'alias
        if not os.path.lexists(vecchio):
            os.symlink("storia.json", vecchio)

    def master(prompt, n, nuovo=False, copia=()):
        """Turno del master con controllo di fuga (e, al primo turno, delle frasi da copiare); una sola riscrittura."""
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
                mancanti = [f for f in copia if f not in msg]
                if not fuga and not mancanti:
                    return msg, note, tentativo
                problema = ("il messaggio contiene parole che il tester non deve leggere: " + ", ".join(fuga)) if fuga else (
                    "mancano, identiche, queste frasi da copiare parola per parola: " + " | ".join(mancanti))
            prompt = (f"Il tuo turno non può arrivare al tester: {problema}. Riscrivilo, stesso contenuto nella scena, "
                      "con le due parti MESSAGGIO AL TESTER e NOTE PRIVATE.")
        C["valida"] = False; C["motivi"].append(f"master turno {n}: {problema}")
        return None, note, 2

    copia = [l.strip() for l in open(o["copia"], encoding="utf-8") if l.strip()] if o["copia"] else []
    eventi = json.load(open(o["eventi"], encoding="utf-8")) if o["eventi"] else []
    C["eventi_previsti"] = eventi
    if o["apertura"]:
        C["apertura"] = open(o["apertura"], encoding="utf-8").read()
    controlli_turno = []
    B = None
    if o["bivio"]:
        O = json.load(open(o["bivio"], encoding="utf-8"))
        N = o["dal-turno"]
        fatti = [t for t in O.get("turni", []) if t.get("tester_fa") and t["n"] < N]
        if N < 2 or len(fatti) != N - 1:
            sys.exit(f"bivio: dal turno {N} servono i turni 1..{N - 1} giocati con un'azione del tester (ce ne sono {len(fatti)})")
        risposta = open(o["risposta"], encoding="utf-8").read().strip()
        fuga = check_fuga.trova(risposta, check_fuga.SEMPRE + vietate) + check_fuga.segnaposto(risposta)
        if fuga:
            sys.exit("bivio: la risposta contiene parole che il tester non deve leggere: " + ", ".join(fuga))
        B = {"da": os.path.abspath(o["bivio"]), "origine": O.get("nome"), "dal_turno": N, "risposta": risposta,
             "esito_origine": O.get("esito")}
        C["bivio"] = B
        C["storia"], C["note_storia"] = O.get("storia"), O.get("note_storia", "")
        C["turni"] = [dict(t, ereditato=True) for t in fatti]

    def ricordo(turni, per_master):
        r = []
        for tu in turni:
            if tu["n"] > 1:
                r.append(f"Turno {tu['n']} — {'hai risposto' if per_master else 'hai ricevuto'}: {tu['master']}")
            r.append(f"Turno {tu['n']} — {'il tester ha fatto' if per_master else 'hai fatto'}: {tu['tester_fa']}"
                     + ("" if per_master else f"\n  avevi concluso: {tu['tester_conclusione']}"))
        return "\n".join(r)

    def controllo_turno(n, msg):
        """C4: risposta del master confrontata subito col contesto. Ritorna True se la storia può continuare."""
        if not o["controllo-turno"]:
            return True
        cc = os.path.join(lavoro, f"ct{n}")
        r, c, rc_c = lancia(cc, str(uuid.uuid4()), True, (
            "Controlla UN messaggio del master di una simulazione contro il suo CONTESTO. Rispondi solo con:\n"
            "FUORI SCHEDA: <promesse, prezzi, condizioni, fatti o persone che il contesto non dà, o «nessuno»>\n"
            "TONO: PIÙ MORBIDO | FEDELE | PIÙ DURO del contesto, una riga\nVERDETTO: FEDELE | DA RIVEDERE\n\n"
            "== CONTESTO ==\n" + contesto + "\n\n== MESSAGGIO DEL MASTER ==\n" + msg),
            os.path.join(dove, f"controllo-m{n}"), o["controllo-turno"], 1)
        C["costo_usd"] += c
        pulisci_sessioni([cc])
        da_rivedere = bool(re.search(r"VERDETTO\W*DA RIVEDERE", r, re.I))
        controlli_turno.append({"turno_master": n, "verdetto": "DA RIVEDERE" if da_rivedere else ("ERRORE" if rc_c == 4 else "FEDELE"),
                                "testo": r.strip()[:600]})
        C["controlli_turno"] = controlli_turno
        if da_rivedere:
            C["motivi"].append(f"controllo del master, turno {n}: DA RIVEDERE")
            if o["controllo-turno-azione"] == "ferma":
                C["valida"] = False
                return False
        return True

    def extra_mondo(n):
        """Eventi previsti per il turno n del tester (B2) e tempo che passa (B3), da dare al master."""
        ev = [e for e in eventi if e.get("turno") == n]
        t = ""
        if ev:
            t += ("\nEvento del mondo da mettere in scena in questa risposta (deciso prima, non cambiarlo, non aggiungerne): "
                  + " | ".join(e["testo"] for e in ev) + ".")
        if o["ritardo"]:
            t += f"\nFra l'azione del tester e la risposta dell'autore passano: {o['ritardo']}. Mettilo in scena."
        return t, [e["id"] for e in ev]

    def scrivi_atomico(p, d):
        tmp = p + ".tmp"
        json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, p)

    def copilota(n_dest, fa, msg, note):
        """D1: la risposta del master aspetta l'autore. Ritorna (testo da mandare o None, info per il turno)."""
        cdir = os.path.join(dove, "copilota"); os.makedirs(cdir, exist_ok=True)
        f = os.path.join(cdir, f"turno-{n_dest}.json")
        scrivi_atomico(f, {"storia": o["nome"], "turno": n_dest, "tester_ha_fatto": fa, "proposta": msg,
                           "note_master": note, "stato": "in attesa", "scritta": time.strftime("%Y-%m-%d %H:%M")})
        C["stato"] = "aspetta l'autore"; C["copilota_attesa"] = f; salva()
        print(f"{o['nome']}: risposta del turno {n_dest} in attesa dell'autore → campagne.py copilota", flush=True)
        passo = float(os.environ.get("STORIA_COPILOTA_PASSO", "5"))
        scade = time.time() + o["copilota-attesa"] * 60
        while True:
            try:
                d = json.load(open(f, encoding="utf-8"))
            except (OSError, ValueError):
                d = {}
            stato = d.get("stato")
            if stato == "approvata":
                testo, info = msg, {"stato": "approvata"}
                break
            if stato == "corretta":
                testo = (d.get("testo") or "").strip()
                fuga = check_fuga.trova(testo, check_fuga.SEMPRE + vietate) + check_fuga.segnaposto(testo) if testo else ["testo vuoto"]
                if not fuga:
                    info = {"stato": "corretta", "proposta": msg}
                    break
                d.update(stato="in attesa", rifiutata="la correzione contiene parole che il tester non deve leggere: " + ", ".join(fuga))
                scrivi_atomico(f, d)
            if time.time() > scade:
                if o["copilota-scadenza"] == "parte":
                    testo, info = msg, {"stato": "scaduta"}
                else:
                    testo, info = None, {"stato": "scaduta", "proposta": msg}
                    C["valida"] = False; C["motivi"].append(f"copilota: l'autore non ha risposto al turno {n_dest} in {o['copilota-attesa']:g} min")
                d["stato"] = "scaduta"; scrivi_atomico(f, d)
                break
            time.sleep(passo)
        d.update(esito=info["stato"], chiusa=time.strftime("%Y-%m-%d %H:%M"))
        scrivi_atomico(f, d)
        C["stato"] = "in corso"; C.pop("copilota_attesa", None); salva()
        return testo, info

    salva()
    if B:
        primo = None
    elif o["apertura"]:
        primo = (contesto + f"\n\n== TESTER DI QUESTA STORIA ==\n{o['tester']}\n\nLivello {o['livello']}, al massimo "
                 f"{o['turni']} turni del tester.\n\n== STORIA DI PARTENZA APPROVATA ==\n{C['apertura']}\n\n"
                 "Ora il PRIMO TURNO, nel formato MESSAGGIO AL TESTER / NOTE PRIVATE: metti in scena questa storia per il tester, "
                 "in seconda persona. Non cambiare, non aggiungere e non togliere fatti: puoi solo raccontare l'arrivo della "
                 "consegna. Le FRASI DA COPIARE vanno nel messaggio identiche, parola per parola. La storia riguarda solo lui: "
                 "chi propone la consegna occupa al massimo una riga (il canale).\n"
                 "Sempre, in tutta la storia: le terze persone parlano poco e solo per far andare avanti la scena; se il "
                 "tester vuole contattare l'autore, il contatto arriva subito. Non inventare dati che le schede non danno "
                 "(numeri di telefono, indirizzi, prezzi, condizioni): scrivili in forma generica o segnali come BUCO. "
                 "Mai segnaposto tra parentesi quadre.")
    else:
        primo = (contesto + f"\n\n== TESTER DI QUESTA STORIA ==\n{o['tester']}\n\nLivello {o['livello']}, al massimo "
             f"{o['turni']} turni del tester.\nOra il PRIMO TURNO, nel formato MESSAGGIO AL TESTER / NOTE "
             "PRIVATE: la storia di partenza presa dalla scheda del protagonista e dalla scena nel tuo contesto, senza "
             "cambiarne i fatti (regole di storia-tester). La storia riguarda solo lui.\n"
             "Sempre, in tutta la storia: le terze persone (amici, fornitori) parlano poco e solo per far andare avanti "
             "la scena; se il tester vuole contattare l'autore, il contatto arriva subito. Non inventare dati che il "
             "contesto non dà (numeri di telefono, indirizzi, prezzi, condizioni): scrivili in forma generica (\"il "
             "numero che ti ha girato\") o segnali come BUCO. Mai segnaposto tra parentesi quadre.")
    m_nuovo, m_recap = False, ""
    cop = None  # esito del copilota per la risposta che arriva al prossimo turno
    if B:
        # bivio: la risposta dell'autore apre il turno N; il master parte in una sessione nuova alla prima risposta
        msg, note, tent = B["risposta"], "(risposta scelta dall'autore: bivio)", 1
        n, primo_t = B["dal_turno"], True
        m_nuovo = True
        m_recap = (contesto + f"\n\n== TESTER DI QUESTA STORIA ==\n{o['tester']}\n\nLivello {o['livello']}, al massimo "
                   f"{o['turni']} turni del tester.\n\n== STORIA FIN QUI (già giocata: non cambiarla) ==\nStoria di partenza: "
                   f"{C['storia']}\n{ricordo(C['turni'], True)}\nTurno {n} — hai risposto: {B['risposta']}\n\nQuest'ultima risposta "
                   "l'ha decisa l'autore: vale come un fatto delle schede, da qui resta coerente con essa.\n\n")
    else:
        msg, note, tent = master(primo, 0, nuovo=True, copia=copia)
        if msg is not None and not controllo_turno(0, msg):
            msg = None
        C["storia"] = msg; C["note_storia"] = note
        n, primo_t = 1, True
    while msg is not None and n <= o["turni"]:
        ultimo = n == o["turni"]
        if primo_t and B:
            ptest = (C["storia"] + "\n" + regole + "\n\nLa storia è già cominciata. Ecco cosa è successo finora (sono i tuoi "
                     "ricordi):\n" + ricordo(C["turni"], False) + "\n\nRisposta che ricevi adesso:\n\n" + msg
                     + ("\n\nÈ il tuo ultimo turno: scrivi la DECISIONE (COMPRO, LASCIO o ASPETTO)." if ultimo else ""))
        elif primo_t:
            ptest = msg + "\n" + regole
        else:
            ptest = "Risposta che ricevi:\n\n" + msg + ("\n\nÈ il tuo ultimo turno: scrivi la DECISIONE (COMPRO, LASCIO o ASPETTO)." if ultimo else "")
        out_t = os.path.join(dove, f"t{n}")
        t, c, rc = lancia(ct, st, primo_t, ptest, out_t, o["modello-tester"], o["chiamate"], o["chrome"])
        primo_t = False
        C["costo_usd"] += c
        chiuso = False
        fermato = rc == 3 or t.startswith("[FERMATO dalla CLI: error_max_turns")  # sorvegliante o --max-turns
        if fermato and not sezione(t, "COSA FACCIO", ()) and not sezione(t, "DECISIONE", ()):
            # tetto morbido: fermato dal sorvegliante prima di rispondere → si riprende la sua sessione e gli si chiede
            # la risposta con quello che ha già visto (tetto 1: niente nuove ricerche)
            t2, c2, rc2 = lancia(ct, st, False, CHIUSURA, out_t + "-chiusura", o["modello-tester"], 1, o["chrome"])
            C["costo_usd"] += c2
            if rc2 == 4:
                rc, t = 4, t2
            elif sezione(t2, "COSA FACCIO", ()) or sezione(t2, "DECISIONE", ()):
                t, rc, chiuso = t2, 0, True
        if rc == 4:
            C["valida"] = False; C["motivi"].append(f"tester turno {n}: errore API ({t.strip()[:120]})")
            C["turni"].append({"n": n, "master": msg, "master_note": note, "errore_api": t.strip()[:300]}); salva()
            break
        ok, rapporto = cieco(out_t, o["siti"])
        open(os.path.join(out_t, "cieco.txt"), "w").write(rapporto)
        if chiuso:  # anche la ripresa di chiusura passa dal controllo cieco
            ok2, rapporto2 = cieco(out_t + "-chiusura", o["siti"])
            open(os.path.join(out_t + "-chiusura", "cieco.txt"), "w").write(rapporto2)
            ok = ok and ok2
        mr = re.search(r"ricerche web: (\d+)\s+fetch: (\d+)", rapporto)
        ricerche = int(mr.group(1)) + int(mr.group(2)) if mr else 0
        fa = sezione(t, "COSA FACCIO", ("A CHE CONCLUSIONE SONO ARRIVATO", "DECISIONE")) or ""
        concl = sezione(t, "A CHE CONCLUSIONE SONO ARRIVATO", ("COSA FACCIO", "DECISIONE")) or ""
        dec = sezione(t, "DECISIONE", ())
        turno = {"n": n, "master": msg, "master_note": note, "riscritto": tent == 2, "tester_fa": fa,
                 "tester_conclusione": concl, "chiuso_dal_tetto": chiuso, "decisione": dec, "cieco": ok, "interrotto": rc == 3, "ricerche": ricerche}
        if cop:
            turno["copilota"] = cop
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
            if not fa:
                # storia ferma senza risposta del tester: il turno non ha dati, la storia non vale (14/11, prova CASA:
                # «nessun COSA FACCIO» lasciava valida True e la storia sembrava buona)
                C["valida"] = False
                C["motivi"].append(f"tester turno {n}: " + ("interrotto dal tetto di chiamate prima di rispondere (alzare --chiamate)"
                                                            if rc == 3 else "nessun COSA FACCIO né DECISIONE: storia ferma senza risposta"))
            break
        extra, ev_ids = extra_mondo(n)
        avviso = ("L'autore ha corretto la tua ultima risposta: al tester è arrivata questa, non la tua. Da qui resta coerente "
                  f"con essa, vale come un fatto delle schede:\n\n{C['turni'][-1]['master']}\n\n"
                  if (C["turni"][-1].get("copilota") or {}).get("stato") == "corretta" else "")
        msg, note, tent = master(m_recap + avviso + f"Turno {n} del tester. Il tester fa:\n\n{fa}\n\nRispondi come l'autore o il mondo, "
                                 "formato MESSAGGIO AL TESTER / NOTE PRIVATE." + extra, n, nuovo=m_nuovo)
        m_nuovo, m_recap = False, ""
        if ev_ids:
            C["turni"][-1]["eventi_dopo"] = ev_ids
        if msg is not None and not controllo_turno(n, msg):
            C["turni"][-1]["master_dopo_scartato"] = msg
            msg = None
        cop = None
        if msg is not None and o["copilota"]:
            msg, cop = copilota(n + 1, fa, msg, note)
            if msg is None:
                C["turni"][-1]["copilota_dopo"] = cop
        n += 1

    C["ricerche"] = sum(t.get("ricerche", 0) for t in C["turni"])
    if C["turni"] and not C["ricerche"] and not o["chrome"]:
        C["motivi"].append("tester: zero ricerche in tutta la storia (checklist punto 2)")
    # resoconto: ora il master legge anche le conclusioni dichiarate dal tester (la partita è chiusa)
    partita = [f"# Storia {o['nome']} — livello {o['livello']}\n\nTester (per il master): {o['tester']}\n",
               f"## Storia di partenza\n{C.get('storia') or '(nessuna)'}\n"]
    if B:
        partita.insert(1, f"BIVIO: rigiocata da «{B['origine']}» (esito {B['esito_origine']}) dal turno {B['dal_turno']} con la "
                          "risposta dell'autore cambiata. I turni prima sono ereditati.\n")
    for tu in C["turni"]:
        if "errore_api" in tu:
            continue
        if tu["n"] > 1:
            cp = (tu.get("copilota") or {}).get("stato")
            nota = {"corretta": " (scritta dall'autore)", "approvata": " (approvata dall'autore)", "scaduta": " (non vista dall'autore)"}.get(cp, "")
            partita.append(f"## Master, risposta al turno {tu['n'] - 1}{nota}\n{tu['master']}\n")
        partita.append(f"## Tester, turno {tu['n']}{' (ereditato)' if tu.get('ereditato') else ''}\nCOSA FACCIO: {tu['tester_fa']}\nA CHE CONCLUSIONE SONO ARRIVATO: {tu['tester_conclusione']}\n"
                       + (f"DECISIONE: {tu['decisione']}\n" if tu["decisione"] else ""))
    testo_partita = "\n".join(partita)
    open(os.path.join(dove, "partita.md"), "w", encoding="utf-8").write(testo_partita)
    if C.get("storia"):
        r, c, rc_r = lancia(cm, sm, m_nuovo, m_recap + f"La storia è chiusa (esito {C['esito']}). Ecco la partita intera, compresi "
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
    pulisci_sessioni([cm, ct, os.path.join(lavoro, "c")] + [os.path.join(lavoro, f"ct{i}") for i in range(o["turni"] + 1)])
    shutil.rmtree(lavoro, ignore_errors=True)
    indice(giro)
    print(f"{o['nome']}: esito {C['esito']} · valida {C['valida']} · turni {len(C['turni'])} · ${C['costo_usd']}"
          + (" · " + "; ".join(C["motivi"]) if C["motivi"] else ""))
    return 0 if C["valida"] else 1


def indice(giro):
    """giro.json per la Regia: metadati (giro-meta.json, se c'è), conclusioni.md, una riga per storia."""
    giro = os.path.abspath(giro)
    meta = {}
    mp = os.path.join(giro, "giro-meta.json")
    if os.path.exists(mp):
        meta = json.load(open(mp, encoding="utf-8"))
    camp = []
    for d in sorted(os.listdir(giro)):
        f = os.path.join(giro, d, "storia.json")
        if not os.path.isfile(f):
            f = os.path.join(giro, d, "campagna.json")  # giri fatti prima della rinomina (14/11)
        if os.path.isfile(f):
            c = json.load(open(f, encoding="utf-8"))
            camp.append({k: c.get(k) for k in ("nome", "livello", "tester", "esito", "valida", "motivi", "costo_usd",
                                               "stato", "inizio", "fine")} | {"turni": len(c.get("turni", [])),
                                                                              "cartella": d})
    concl = os.path.join(giro, "conclusioni.md")
    g = {"id": os.path.basename(giro), **meta, "storie": camp, "campagne": camp,  # "campagne": nome di prima, per la Regia; via con l'alias
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
    sys.exit(storia(o))
