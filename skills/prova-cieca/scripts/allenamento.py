#!/usr/bin/env python3
"""Allenamento a ruoli invertiti (extra «allenamento», D2): un uso nuovo, non un collaudo.
Il modello fa il PROTAGONISTA (dalla sua scheda e dalla scena) e l'autore risponde come farebbe con un contatto vero.
Lo prepara campagne.py allenamento CAMP STORIA; le risposte le scrive l'autore (campagne.py allenamento CAMP NOME --rispondi).

Uso:
  allenamento.py --dir DIR --protagonista PROTAGONISTA.md --apertura APERTURA.txt
                 [--turni 6] [--chiamate 6] [--modello sonnet] [--modello-resoconto sonnet] [--attesa 120]

Ogni turno:
  protagonista (run_blind.sh, sessione sua, ripresa; può cercare online come farebbe davvero)
    → COSA FACCIO + A CHE CONCLUSIONE SONO ARRIVATO, o DECISIONE
  COSA FACCIO va in DIR/turno-N.json con stato «in attesa»; l'autore scrive «risposta» (stato «risposta»)
  la risposta arriva al protagonista al turno dopo. Le conclusioni del protagonista l'autore le vede solo alla fine.
Attesa massima --attesa minuti (default 120) per ogni risposta: poi l'allenamento si chiude INCOMPLETO («scaduto»).
Fine: un modello legge la partita intera (con le conclusioni) e scrive il RESOCONTO per l'autore, con le frasi
dell'autore che hanno funzionato o no: materiale per la sua scheda, che però si cambia solo dopo averne parlato.
Uscita in DIR: allenamento.json, partita.md, resoconto.md, transcript. Niente entra nei giri, nella memoria o in analisi.
Exit 0 = finito (qualunque esito), 1 = errore."""
import json, os, re, shutil, sys, tempfile, time, uuid

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from storia import lancia, sezione, cieco, pulisci_sessioni  # noqa: E402

REGOLE = """
---
Sei la persona descritta qui sopra, nella tua vita di tutti i giorni. Rispondi in italiano, in prima persona.
Non leggere nessun file locale; non usare memorie o note. Puoi cercare online quanto vuoi, come faresti davvero.
Qualunque indirizzo email o nome presente nel tuo ambiente tecnico NON riguarda la storia: ignorali, non cercarli.
Chi ti ha contattato è una persona vera e ti risponde lei: scrivile come scriveresti tu (mail, messaggio, telefonata).
A ogni turno scrivi:
  COSA FACCIO: <l'azione, in concreto: il testo della mail o del messaggio, cosa dici al telefono, cosa cerchi>
  A CHE CONCLUSIONE SONO ARRIVATO: <in due righe: a che punto è la tua opinione dopo questo turno>
Solo quando hai deciso davvero scrivi DECISIONE: COMPRO | LASCIO, e perché, in tre righe.
All'ultimo turno, se non hai deciso, scrivi DECISIONE: ASPETTO e cosa ti manca per decidere.
Hai al massimo {turni} turni e {azioni} azioni online per turno.
"""


def args(a):
    o = {"turni": 6, "chiamate": 6, "modello": "sonnet", "modello-resoconto": "sonnet", "attesa": 120}
    i = 0
    while i < len(a):
        o[a[i].lstrip("-")] = a[i + 1]; i += 2
    for k in ("dir", "protagonista", "apertura"):
        if k not in o:
            sys.exit(f"manca --{k}")
    o["turni"], o["chiamate"], o["attesa"] = int(o["turni"]), int(o["chiamate"]), float(o["attesa"])
    return o


def scrivi_atomico(p, d):
    tmp = p + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def allenamento(o):
    dove = os.path.abspath(o["dir"])
    if os.path.exists(os.path.join(dove, "allenamento.json")):
        sys.exit(f"allenamento già giocato: {dove}")
    os.makedirs(dove, exist_ok=True)
    prot = open(o["protagonista"], encoding="utf-8").read()
    apertura = open(o["apertura"], encoding="utf-8").read()
    lavoro = tempfile.mkdtemp(prefix="allenamento.")
    cp, sp = os.path.join(lavoro, "p"), str(uuid.uuid4())
    A = {"nome": os.path.basename(dove), "inizio": time.strftime("%Y-%m-%d %H:%M"), "modello": o["modello"],
         "turni": [], "esito": "INCOMPLETA", "stato": "in corso", "motivi": [], "costo_usd": 0.0}

    def salva():
        scrivi_atomico(os.path.join(dove, "allenamento.json"), A)

    def aspetta_autore(n, fa):
        f = os.path.join(dove, f"turno-{n}.json")
        scrivi_atomico(f, {"allenamento": A["nome"], "turno": n, "messaggio": fa, "stato": "in attesa",
                           "scritta": time.strftime("%Y-%m-%d %H:%M")})
        A["stato"] = "aspetta l'autore"; salva()
        print(f"{A['nome']}: messaggio del turno {n} in attesa della tua risposta → campagne.py allenamento", flush=True)
        passo = float(os.environ.get("STORIA_COPILOTA_PASSO", "5"))
        scade = time.time() + o["attesa"] * 60
        while True:
            try:
                d = json.load(open(f, encoding="utf-8"))
            except (OSError, ValueError):
                d = {}
            if d.get("stato") == "risposta" and (d.get("risposta") or "").strip():
                risposta = d["risposta"].strip()
                break
            if time.time() > scade:
                risposta = None
                d["stato"] = "scaduta"
                A["motivi"].append(f"nessuna risposta dell'autore al turno {n} in {o['attesa']:g} min")
                break
            time.sleep(passo)
        d["chiusa"] = time.strftime("%Y-%m-%d %H:%M"); scrivi_atomico(f, d)
        A["stato"] = "in corso"; salva()
        return risposta

    salva()
    regole = REGOLE.format(turni=o["turni"], azioni=o["chiamate"])
    prompt = prot + "\n\n== COSA TI SUCCEDE ==\n" + apertura + "\n" + regole
    n, ultimo = 1, False
    while n <= o["turni"]:
        ultimo = n == o["turni"]
        if ultimo and n > 1:
            prompt += "\n\nÈ il tuo ultimo turno: scrivi la DECISIONE (COMPRO, LASCIO o ASPETTO)."
        out = os.path.join(dove, f"p{n}")
        t, c, rc = lancia(cp, sp, n == 1, prompt, out, o["modello"], o["chiamate"])
        A["costo_usd"] += c
        if rc == 4:
            A["motivi"].append(f"turno {n}: errore API ({t.strip()[:120]})"); break
        ok, rapporto = cieco(out, "")
        open(os.path.join(out, "cieco.txt"), "w").write(rapporto)
        fa = sezione(t, "COSA FACCIO", ("A CHE CONCLUSIONE SONO ARRIVATO", "DECISIONE")) or ""
        concl = sezione(t, "A CHE CONCLUSIONE SONO ARRIVATO", ("COSA FACCIO", "DECISIONE")) or ""
        dec = sezione(t, "DECISIONE", ())
        turno = {"n": n, "protagonista_fa": fa, "conclusione": concl, "decisione": dec, "cieco": ok}
        A["turni"].append(turno); salva()
        if not ok:
            A["motivi"].append(f"turno {n}: check_blind SOSPETTO")
        m = re.match(r"\W*(COMPRO|LASCIO|ASPETTO)", dec or "", re.I)
        if m and (m.group(1).upper() != "ASPETTO" or ultimo):
            A["esito"] = {"COMPRO": "COMPRA", "LASCIO": "LASCIA", "ASPETTO": "INCOMPLETA"}[m.group(1).upper()]
            break
        fa = fa or dec or ""
        if ultimo or not fa:
            if not fa:
                A["motivi"].append(f"turno {n}: nessun COSA FACCIO")
            break
        risposta = aspetta_autore(n, fa)
        if risposta is None:
            break
        turno["autore"] = risposta; salva()
        prompt = "Risposta che ricevi:\n\n" + risposta
        n += 1

    partita = [f"# Allenamento {A['nome']}\n", f"## Cosa succede al protagonista\n{apertura}\n"]
    for tu in A["turni"]:
        partita.append(f"## Protagonista, turno {tu['n']}\nCOSA FACCIO: {tu['protagonista_fa']}\n"
                       f"A CHE CONCLUSIONE SONO ARRIVATO: {tu['conclusione']}\n"
                       + (f"DECISIONE: {tu['decisione']}\n" if tu["decisione"] else ""))
        if tu.get("autore"):
            partita.append(f"## Autore, risposta al turno {tu['n']}\n{tu['autore']}\n")
    testo = "\n".join(partita)
    open(os.path.join(dove, "partita.md"), "w", encoding="utf-8").write(testo)
    if A["turni"]:
        cr = os.path.join(lavoro, "r")
        r, c, _ = lancia(cr, str(uuid.uuid4()), True, (
            "Sotto c'è un allenamento: una persona (il protagonista, descritto nella sua scheda) è stata contattata da "
            "chi propone qualcosa (l'autore), che ha risposto di persona. Ora l'autore legge anche le conclusioni che il "
            f"protagonista non diceva. Esito: {A['esito']}. Scrivi per l'autore, in italiano semplice, solo:\n"
            "1) COME È ANDATA: tre righe.\n2) RISPOSTE CHE HANNO FUNZIONATO: frasi dell'autore che hanno spostato "
            "l'opinione, citate, e perché.\n3) RISPOSTE CHE HANNO FATTO PERDERE TERRENO: citate, e cosa voleva sentire.\n"
            "4) DOMANDE A CUI NON ERA PRONTO.\n5) DA TENERE PER LA SCHEDA: modo di rispondere, prezzi, condizioni o tono "
            "che l'autore ha usato davvero e che il personaggio esterno delle prove dovrebbe avere (proposte: si decidono "
            "dopo, non si applicano).\n\n== SCHEDA DEL PROTAGONISTA ==\n" + prot + "\n\n== PARTITA ==\n" + testo),
            os.path.join(dove, "resoconto-gen"), o["modello-resoconto"], 1)
        A["costo_usd"] += c
        open(os.path.join(dove, "resoconto.md"), "w", encoding="utf-8").write(r)
        pulisci_sessioni([cr])
    A["costo_usd"] = round(A["costo_usd"], 4)
    A["fine"] = time.strftime("%Y-%m-%d %H:%M"); A["stato"] = "finito"
    salva()
    pulisci_sessioni([cp])
    shutil.rmtree(lavoro, ignore_errors=True)
    print(f"{A['nome']}: esito {A['esito']} · turni {len(A['turni'])} · ${A['costo_usd']}"
          + (" · " + "; ".join(A["motivi"]) if A["motivi"] else ""))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(2)
    sys.exit(allenamento(args(sys.argv[1:])))
