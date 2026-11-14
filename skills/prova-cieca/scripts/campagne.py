#!/usr/bin/env python3
"""Sessioni di campagne: schede, profili, manuale, controlli, preparazione dei giri, quadro e memoria.

Non lancia modelli e non spende: prepara i file che campagna.py usa e legge ciò che produce.
Formato dei dati: references/dati.md. Libreria globale (profili, manuale globale, ricette): --lib DIR o $CAMPAGNE_LIB.

Sessione
  campagne.py nuova SESS --domanda "…" [--consegna URL] [--versione v1]
  campagne.py stato SESS                      riassunto: schede, stati, cosa blocca
  campagne.py verifica SESS                   controllo di completezza (exit 1 se qualcosa blocca il gioco)
  campagne.py imposta SESS chiave valore      campo della sessione (domanda, consegna.link, seme, …)
  campagne.py protagonista SESS CAMPAGNA SCHEDA [--variante V]   aggiunge una campagna (un protagonista)
  campagne.py evento SESS ID "testo" [--peso 1] [--dal-turno 1]  mazzo di eventi del mondo
Schede
  campagne.py scheda nuova SESS TIPO ID [--profilo P [--versione N]]   TIPO: protagonista|esterno|scena|secondario
  campagne.py scheda imposta SESS ID CAMPO "valore" [--fonte F] [--blocca|--sblocca] [--personalizzato]
  campagne.py scheda approva SESS ID          approva (rifiuta se mancano obbligatori o ci sono righe DEDOTTO)
  campagne.py scheda conferma SESS ID CAMPO   riga DEDOTTO/GENERATO confermata dall'autore → fonte AUTORE
  campagne.py scheda versioni SESS ID [VA VB] versioni affiancate (cosa è cambiato)
Controlli (tre livelli: globale → sessione → campagna)
  campagne.py controllo SESS CHIAVE VALORE [--campagna C] [--blocca]
  campagne.py controlli SESS [--campagna C]   valori risolti, con il livello che vince
Generare (non spende: scrive una richiesta che chi coordina esegue)
  campagne.py genera SESS ID [--campo C | --sezione tutti]       → SESS/richieste/genera-<ID>-<ora>.json + prompt
  campagne.py applica SESS ID RISPOSTA.json   riempie solo campi vuoti e non bloccati, come GENERATO (bozza)
Giro
  campagne.py prepara SESS GIRO              file per ogni campagna + comandi.sh (campagna.py), mazzo estratto col seme
  campagne.py quadro SESS GIRO               C1: tabella delle campagne + prompt per l'analisi trasversale
  campagne.py confronta GIRO C1 C2           A2: due campagne affiancate turno per turno
  campagne.py stabilita GIRO                 A4: ripetizioni della stessa campagna, quanto cambia l'esito
  campagne.py memoria SESS GIRO              C2: aggiorna la memoria del progetto (buchi, motivi, profili consumati)
Libreria
  campagne.py profilo salva SESS SCHEDA [--nome P]       scheda protagonista → profilo (versione nuova se esiste)
  campagne.py profilo deriva P NUOVO [campo=valore …]    profilo simile, «derivato da P vN»
  campagne.py profilo lista
  campagne.py ricetta salva SESS NOME | ricetta usa NOME SESS_NUOVA
  campagne.py esporta SESS FILE.zip | importa FILE.zip DIR
"""
import copy, difflib, glob, json, os, random, re, shutil, sys, time, zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
FONTI = ("AUTORE", "FATTO", "COORDINATORE", "DEDOTTO", "GENERATO")
DA_CONFERMARE = ("DEDOTTO", "GENERATO")

# Struttura guidata delle schede (references/schede.md). (campo, obbligatorio, nota)
STRUTTURE = {
    "protagonista": [
        ("nome_eta_luogo", True, "luoghi reali solo se coerenti: il protagonista li cercherà"),
        ("attivita", True, "cosa fa, quanto è grande, da quanto, con chi"),
        ("prima", True, "era X: scelte, soldi, esperienze passate (anche cattive) con proposte simili"),
        ("adesso", True, "è Y: cosa lo preoccupa oggi, cosa vorrebbe, cosa ha già provato"),
        ("tratti", True, "carattere, diffidenza, dimestichezza digitale, tempo, budget, chi decide con lui"),
        ("abitudini_ricerca", False, "come si informa"),
        ("cosa_non_sa", False, "lacune realistiche"),
        ("variazioni", False, "casualità 2: tratti variati decisi PRIMA del giro, scritti qui"),
        ("diario", False, "RISERVATO saghe (A1): cosa ricorda il personaggio di episodi passati; non costruito"),
    ],
    "esterno": [
        ("come_si_presenta", True, "solo questo nome può arrivare al protagonista"),
        ("chi_e", True, "lavoro, situazione, tempo, come scrive e parla"),
        ("cosa_sa_fare", True, "solo ciò che è vero oggi; «in arrivo» detto come tale"),
        ("cosa_non_puo", True, "vincoli veri: fiscali, legali, di tempo, di competenza"),
        ("prezzi_condizioni", True, "forbice, minimo, rate, sconti, su misura; o «il master propone dentro la forbice»"),
        ("flessibilita", True, "quanto si adatta; emerge solo se il protagonista la chiede"),
        ("canali_tempi", True, "mail, telefono, incontro; tempi di risposta"),
        ("cosa_non_si_sa", False, "ciò che il master non deve inventare (diventa un buco)"),
        ("parole_vietate", True, "ciò che non deve mai arrivare al protagonista, una per riga"),
    ],
    "scena": [
        ("domanda", True, "solo per coordinatore e master"),
        ("come_arriva", True, "chi porta la consegna e con quali parole"),
        ("cosa_riceve", True, "link o testo; per varianti: righe «variante: testo»"),
        ("frasi_da_copiare", False, "una per riga: il master le riporta identiche (link, istruzione sul browser)"),
        ("mondo", True, "stagione, momento, terze persone ammesse, imprevisti ammessi"),
    ],
    "secondario": [
        ("ruolo", True, "socio, familiare, amico che ha passato il link, concorrente, ospite…"),
        ("chi_e", True, "due righe: chi è, cosa vuole"),
        ("rapporto", True, "che rapporto ha col protagonista e quanto pesa nelle sue decisioni"),
        ("come_parla", False, "tono, poche parole"),
        ("cosa_sa_dell_esterno", False, "RISERVATO: lo decide l'autore; vuoto = sa solo ciò che dice la scena"),
    ],
}
RISERVATI = {"diario", "cosa_sa_dell_esterno"}  # campi previsti, non usati finché non sono decisi

# Controlli globali di default (references/manuale.md). agisce: programma | master | schede
CONTROLLI = {
    "turni": (6, "programma"), "chiamate": (12, "programma"), "chiamate_browser_min": (25, "programma"),
    "browser": (False, "programma"), "parallelo": (2, "programma"), "ripetizioni": (1, "programma"),
    "modello_tester": ("sonnet", "programma"), "modello_master": ("sonnet", "programma"),
    "modello_controllo": ("haiku", "programma"), "controllo_turno": (True, "programma"),
    "controllo_turno_azione": ("ferma", "programma"), "tetto_campagna_usd": (None, "programma"),
    "tetto_sessione_usd": (None, "programma"), "livello": (3, "programma"),
    "casualita": (1, "master"), "attivita_mondo": ("normale", "master"), "ritardo": ("", "master"),
    "severita": ("media", "schede"), "canale": ("", "schede"), "momento": ("", "schede"),
    "chi_decide": ("da solo", "schede"), "dimestichezza": ("", "schede"), "profondita_ricerca": (None, "programma"),
}
VALORI = {"casualita": (0, 1, 2), "attivita_mondo": ("fermo", "normale", "vivo"), "severita": ("bassa", "media", "alta"),
          "controllo_turno_azione": ("ferma", "segna"), "livello": (2, 3)}
# Frasi vietate nelle schede: esiti suggeriti e istruzioni di durezza (references/schede.md)
VIETATE_SCHEDE = [r"\bsii (severo|duro|critico)\b", r"\b(severo|severa) nel giudizio\b", r"\bè interessat[oa]\b",
                  r"\bscettic[oa] ma\b", r"\bcomprer[àa]\b", r"\bdeve (comprare|rifiutare)\b"]


# ---------- file ----------
def leggi(p, default=None):
    if not os.path.exists(p):
        return copy.deepcopy(default)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def scrivi(p, d):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def ora():
    return time.strftime("%Y-%m-%d %H:%M")


def lib_dir(o):
    d = o.get("lib") or os.environ.get("CAMPAGNE_LIB")
    if not d:
        sys.exit("serve la libreria: --lib DIR o $CAMPAGNE_LIB")
    return os.path.abspath(d)


def sess_file(s):
    return os.path.join(s, "sessione.json")


def carica_sess(s):
    d = leggi(sess_file(s))
    if d is None:
        sys.exit(f"sessione non trovata: {s}")
    return d


# ---------- schede (versionate) ----------
def scheda_dir(s, sid):
    return os.path.join(s, "schede", sid)


def versioni(s, sid):
    return sorted(int(re.search(r"v(\d+)\.json$", f).group(1)) for f in glob.glob(os.path.join(scheda_dir(s, sid), "v*.json")))


def carica_scheda(s, sid, v=None):
    vs = versioni(s, sid)
    if not vs:
        sys.exit(f"scheda non trovata: {sid}")
    v = v or vs[-1]
    return leggi(os.path.join(scheda_dir(s, sid), f"v{v}.json"))


def salva_scheda(s, sc):
    """Una scheda già giocata non si modifica: la modifica crea la versione successiva."""
    if sc.get("giocata_in"):
        sc = copy.deepcopy(sc)
        sc["versione"] = versioni(s, sc["id"])[-1] + 1
        sc["giocata_in"] = []
        sc["stato"] = "bozza"
        sc["creata"] = ora()
    sc["modificata"] = ora()
    scrivi(os.path.join(scheda_dir(s, sc["id"]), f"v{sc['versione']}.json"), sc)
    return sc


def campo_vuoto(c):
    return c is None or not str(c.get("valore") or "").strip()


def nuova_scheda(tipo, sid):
    if tipo not in STRUTTURE:
        sys.exit(f"tipo sconosciuto: {tipo} (protagonista|esterno|scena|secondario)")
    return {"id": sid, "tipo": tipo, "versione": 1, "stato": "bozza", "creata": ora(), "giocata_in": [],
            "origine": None, "campi": {n: {"valore": "", "fonte": None, "data": None, "bloccato": False}
                                       for n, _, _ in STRUTTURE[tipo]},
            "personalizzati": []}


def problemi_scheda(sc):
    """Ciò che impedisce di approvare (lista di stringhe)."""
    p = []
    for n, obbl, _ in STRUTTURE[sc["tipo"]]:
        if obbl and campo_vuoto(sc["campi"].get(n)):
            p.append(f"{sc['id']}: campo obbligatorio vuoto «{n}»")
    for n, c in sc["campi"].items():
        if campo_vuoto(c):
            continue
        if n in RISERVATI and n != "cosa_sa_dell_esterno":
            p.append(f"{sc['id']}: «{n}» è riservato a una funzione non ancora decisa: va lasciato vuoto")
        if n == "cosa_sa_dell_esterno":
            p.append(f"{sc['id']}: «cosa_sa_dell_esterno» lo decide l'autore (non ancora deciso): va lasciato vuoto")
        if c.get("fonte") in DA_CONFERMARE:
            p.append(f"{sc['id']}: «{n}» ha fonte {c['fonte']}: da confermare con l'autore")
        if sc["tipo"] == "protagonista":
            for r in VIETATE_SCHEDE:
                if re.search(r, str(c["valore"]), re.I):
                    p.append(f"{sc['id']}: «{n}» suggerisce l'esito o la durezza ({r}): togli, metti un fatto")
    return p


# ---------- controlli a tre livelli ----------
def manuale_globale(o):
    d = o.get("lib") or os.environ.get("CAMPAGNE_LIB")
    m = leggi(os.path.join(d, "manuale.json"), {}) if d else {}
    return m or {}


def risolvi_controlli(o, S, campagna=None):
    """{chiave: (valore, livello, bloccato)}. Un valore bloccato a un livello non si sovrascrive sotto."""
    out = {k: (v, "default", False) for k, (v, _) in CONTROLLI.items()}
    livelli = [("globale", manuale_globale(o).get("controlli", {})), ("sessione", S.get("controlli", {}))]
    if campagna:
        c = next((x for x in S["campagne"] if x["campagna"] == campagna), None)
        if c is None:
            sys.exit(f"campagna non trovata: {campagna}")
        livelli.append(("campagna", c.get("controlli", {})))
    for nome, liv in livelli:
        for k, x in liv.items():
            if k in out and out[k][2]:
                continue  # bloccato più in alto
            out[k] = (x["valore"], nome, bool(x.get("bloccato")))
    return out


def valore(ctrl, k):
    return ctrl[k][0]


def converti(k, v):
    base = CONTROLLI.get(k, (None,))[0]
    if v in ("null", "none", ""):
        return None if base is None or not isinstance(base, str) else ""
    if isinstance(base, bool):
        return v.lower() in ("1", "si", "sì", "true", "yes")
    if isinstance(base, int) or k in ("profondita_ricerca", "casualita"):
        return int(v)
    if k.endswith("_usd"):
        return float(v)
    return v


# ---------- verifica ----------
def verifica(o, S, s):
    """(blocchi, avvisi)"""
    b, a = [], []
    if not S.get("domanda"):
        b.append("sessione: manca la domanda")
    if not S.get("campagne"):
        b.append("sessione: nessuna campagna (protagonista)")
    if len(S.get("campagne", [])) > 5:
        b.append("sessione: più di 5 campagne (oltre non si impara di più)")
    usate = [S.get("esterno"), S.get("scena")] + S.get("secondari", []) + [c["scheda"] for c in S.get("campagne", [])]
    if not S.get("esterno"):
        b.append("sessione: manca la scheda del personaggio esterno")
    if not S.get("scena"):
        b.append("sessione: manca la scheda della scena")
    for sid in [x for x in usate if x]:
        if not versioni(s, sid):
            b.append(f"{sid}: scheda inesistente")
            continue
        sc = carica_scheda(s, sid)
        if sc["stato"] != "approvata":
            b.append(f"{sid}: in bozza (v{sc['versione']})")
        b += problemi_scheda(sc)
    for c in S.get("campagne", []):
        ctrl = risolvi_controlli(o, S, c["campagna"])
        for k, ammessi in VALORI.items():
            if valore(ctrl, k) not in ammessi:
                b.append(f"{c['campagna']}: controllo {k}={valore(ctrl, k)!r} fuori da {ammessi}")
        if not versioni(s, c["scheda"]):
            continue
        p = carica_scheda(s, c["scheda"])
        if valore(ctrl, "casualita") == 2 and campo_vuoto(p["campi"].get("variazioni")):
            b.append(f"{c['campagna']}: casualità 2 chiede le variazioni scritte nella scheda {c['scheda']} prima del giro")
        if valore(ctrl, "chi_decide") not in ("", "da solo") and not S.get("secondari"):
            b.append(f"{c['campagna']}: chi_decide={valore(ctrl, 'chi_decide')!r} chiede una scheda secondaria (chi decide con lui)")
        if valore(ctrl, "severita") == "alta":
            testo = " ".join(str(x.get("valore", "")) for x in p["campi"].values()).lower()
            if not re.search(r"propost|preventiv|budget|soldi|tempo|concorren|brutt|fregat|delus", testo):
                a.append(f"{c['campagna']}: severità alta ma la scheda non dice niente di proposte ricevute, budget, "
                         "tempo o esperienze cattive: la severità agisce solo da lì")
        for k in ("canale", "momento", "dimestichezza"):
            v = valore(ctrl, k)
            if v and v.lower() not in json.dumps(p, ensure_ascii=False).lower() + json.dumps(
                    carica_scheda(s, S["scena"]) if S.get("scena") and versioni(s, S["scena"]) else {}, ensure_ascii=False).lower():
                a.append(f"{c['campagna']}: controllo {k}={v!r} non compare nelle schede: scrivilo nella scheda o togli il controllo")
        if valore(ctrl, "browser") and valore(ctrl, "chiamate") < valore(ctrl, "chiamate_browser_min"):
            a.append(f"{c['campagna']}: browser con {valore(ctrl, 'chiamate')} chiamate per turno: ne servono almeno "
                     f"{valore(ctrl, 'chiamate_browser_min')} (prepara le alza)")
        if c.get("variante") and S.get("scena") and versioni(s, S["scena"]):
            if not variante_testo(carica_scheda(s, S["scena"]), c["variante"]):
                b.append(f"{c['campagna']}: variante «{c['variante']}» assente in cosa_riceve della scena")
    att = S.get("controlli", {}).get("attivita_mondo", {}).get("valore")
    if att == "vivo" and not S.get("mazzo"):
        a.append("sessione: attività del mondo «vivo» ma il mazzo di eventi è vuoto")
    return b, a


def variante_testo(scena, variante):
    txt = scena["campi"]["cosa_riceve"]["valore"]
    if not variante:
        return txt
    for riga in txt.splitlines():
        m = re.match(r"\s*([^:]+):\s*(.+)", riga)
        if m and m.group(1).strip().lower() == variante.lower():
            return m.group(2).strip()
    return None


# ---------- prepara ----------
def righe(v):
    return [x.strip() for x in str(v or "").splitlines() if x.strip()]


ETICHETTE = {"chi_e": "Chi è", "nome_eta_luogo": "Nome, età, luogo", "attivita": "Attività", "cosa_non_puo": "Cosa non può fare o promettere",
             "prezzi_condizioni": "Prezzi e condizioni", "flessibilita": "Flessibilità", "canali_tempi": "Canali e tempi",
             "abitudini_ricerca": "Abitudini di ricerca"}


def etichetta(n):
    return ETICHETTE.get(n) or n.replace("_", " ").capitalize()


def blocco(sc, titolo):
    out = [f"== {titolo} ({sc['id']} v{sc['versione']}) =="]
    for n, _, nota in STRUTTURE[sc["tipo"]]:
        c = sc["campi"].get(n)
        if n in RISERVATI or campo_vuoto(c):
            continue
        out.append(f"{etichetta(n)}: {c['valore']}")
    for n in sc.get("personalizzati", []):
        if not campo_vuoto(sc["campi"].get(n)):
            out.append(f"{n.replace('_', ' ').capitalize()}: {sc['campi'][n]['valore']}")
    return "\n".join(out)


def estrai_eventi(S, ctrl, turni, seme):
    """B2: eventi estratti prima del giro (ripetibili col seme), segnati turno per turno."""
    att, cas = valore(ctrl, "attivita_mondo"), valore(ctrl, "casualita")
    mazzo = [e for e in S.get("mazzo", []) if e.get("peso", 1) > 0]
    if att == "fermo" or cas == 0 or not mazzo:
        return []
    rnd = random.Random(seme)
    quanti = 1 if att == "normale" else max(1, turni // 2)
    scelti, pool = [], list(mazzo)
    for _ in range(min(quanti, len(pool))):
        e = rnd.choices(pool, weights=[x.get("peso", 1) for x in pool])[0]
        pool.remove(e)
        primo = max(1, int(e.get("dal_turno", 1)))
        if primo > turni:
            continue
        scelti.append({"turno": rnd.randint(primo, turni), "id": e["id"], "testo": e["testo"]})
    return sorted(scelti, key=lambda x: x["turno"])


def prepara(o, S, s, giro):
    b, a = verifica(o, S, s)
    if b:
        print("NON SI GIOCA, blocca:\n- " + "\n- ".join(b)); return 1
    giro = os.path.abspath(giro)
    os.makedirs(giro, exist_ok=True)
    tmpl = open(os.path.join(BASE, "..", "references", "master-template.md"), encoding="utf-8").read()
    est, scena = carica_scheda(s, S["esterno"]), carica_scheda(s, S["scena"])
    sec = [carica_scheda(s, x) for x in S.get("secondari", [])]
    globale = manuale_globale(o)
    vietate = righe(est["campi"]["parole_vietate"]["valore"]) + globale.get("parole_vietate", [])
    comandi, meta_c = ["#!/bin/bash", f"# giro preparato {ora()} da campagne.py — sessione {S['id']}", "set -u",
                       f'C="{os.path.join(BASE, "campagna.py")}"'], []
    seme0 = int(S.get("seme") or 1)
    for i, c in enumerate(S["campagne"]):
        ctrl = risolvi_controlli(o, S, c["campagna"])
        prot = carica_scheda(s, c["scheda"])
        turni = 2 if valore(ctrl, "livello") == 2 else int(valore(ctrl, "turni"))
        chiamate = int(valore(ctrl, "profondita_ricerca") or valore(ctrl, "chiamate"))
        if valore(ctrl, "browser"):
            chiamate = max(chiamate, int(valore(ctrl, "chiamate_browser_min")))
        rip = max(1, int(valore(ctrl, "ripetizioni")))
        for r in range(1, rip + 1):
            nome = c["campagna"] + (f"-r{r}" if rip > 1 else "")
            d = os.path.join(giro, "_prep", nome)
            os.makedirs(d, exist_ok=True)
            ricevuto = variante_testo(scena, c.get("variante"))
            copia = righe(scena["campi"].get("frasi_da_copiare", {}).get("valore")) + ([ricevuto] if ricevuto and re.match(r"https?://", ricevuto) else [])
            regole_s = "\n".join(f"- {x}" for x in globale.get("regole", []) + S.get("regole", []))
            ctrl_master = [f"Casualità {valore(ctrl, 'casualita')}: " + {0: "nessun imprevisto del mondo.",
                           1: "contrattempi piccoli e realistici ammessi (un ritardo, una telefonata); mai fatti nuovi su persone, prezzi o condizioni.",
                           2: "imprevisti piccoli ammessi; le variazioni dei tratti sono già scritte nella scheda."}[valore(ctrl, "casualita")],
                           f"Attività del mondo: {valore(ctrl, 'attivita_mondo')}" + (
                               " (solo risposte, nessun evento)." if valore(ctrl, "attivita_mondo") == "fermo" else
                               "; gli eventi del mondo che cambiano la situazione te li indica il programma nel turno giusto: non inventarne altri.")]
            if valore(ctrl, "ritardo"):
                ctrl_master.append(f"Tempo fra l'azione del protagonista e la risposta del personaggio esterno: {valore(ctrl, 'ritardo')} "
                                   "(mettilo in scena: cosa succede intanto, senza nuovi fatti fuori dal mazzo).")
            contesto = "\n\n".join(x for x in [
                tmpl.split("```")[1].strip() if "```" in tmpl else tmpl,
                "== SCHEDE APPROVATE (fonte unica dei fatti: non le cambi) ==",
                blocco(est, "PERSONAGGIO ESTERNO, chi interpreti"),
                blocco(scena, "SCENA"),
                blocco(prot, "PROTAGONISTA"),
                "\n\n".join(blocco(x, "PERSONAGGIO SECONDARIO (lo interpreti tu, parla poco)") for x in sec)
                + ("\nSe il protagonista chiede a un secondario cosa sa del personaggio esterno: sa solo ciò che dice la scena."
                   if sec else ""),
                "== REGOLE DELLA SESSIONE ==\n" + (regole_s or "- nessuna oltre le globali")
                + ("\nResta fuori dalla storia (rispondi in modo neutro): " + "; ".join(S["fuori_storia"]) if S.get("fuori_storia") else "")
                + ("\nSi può dire: " + "; ".join(S["si_puo_dire"]) if S.get("si_puo_dire") else ""),
                "== CONTROLLI ==\n" + "\n".join(ctrl_master),
            ] if x)
            open(os.path.join(d, "master.md"), "w", encoding="utf-8").write(contesto)
            apertura = "\n\n".join(x for x in [
                "PRIMA: " + prot["campi"]["prima"]["valore"], "ADESSO: " + prot["campi"]["adesso"]["valore"],
                "COME ARRIVA: " + scena["campi"]["come_arriva"]["valore"],
                "COSA RICEVE: " + (ricevuto or ""),
                ("FRASI DA COPIARE PAROLA PER PAROLA:\n" + "\n".join(copia)) if copia else ""] if x)
            open(os.path.join(d, "apertura.txt"), "w", encoding="utf-8").write(apertura)
            open(os.path.join(d, "copia.txt"), "w", encoding="utf-8").write("\n".join(copia) + ("\n" if copia else ""))
            open(os.path.join(d, "vietate.txt"), "w", encoding="utf-8").write("\n".join(vietate) + "\n")
            seme = seme0 * 1000 + i  # stesso seme per le ripetizioni: A4 misura il modello, non il mazzo
            eventi = estrai_eventi(S, ctrl, turni, seme)
            scrivi(os.path.join(d, "eventi.json"), eventi)
            tester_desc = prot["campi"]["nome_eta_luogo"]["valore"] + " — " + prot["campi"]["attivita"]["valore"]
            cmd = [f'python3 "$C" --giro "{giro}" --nome {nome}', f'--master "{d}/master.md"',
                   f"--tester {json.dumps(tester_desc, ensure_ascii=False)}", f'--vietate "{d}/vietate.txt"',
                   f'--apertura "{d}/apertura.txt"', f'--copia "{d}/copia.txt"', f'--eventi "{d}/eventi.json"',
                   f"--livello {valore(ctrl, 'livello')} --turni {turni} --chiamate {chiamate}",
                   f"--modello-tester {valore(ctrl, 'modello_tester')} --modello-master {valore(ctrl, 'modello_master')}",
                   f"--controllo {valore(ctrl, 'modello_controllo')}"]
            if valore(ctrl, "controllo_turno"):
                cmd.append(f"--controllo-turno {valore(ctrl, 'modello_controllo')} --controllo-turno-azione {valore(ctrl, 'controllo_turno_azione')}")
            if valore(ctrl, "ritardo"):
                cmd.append(f"--ritardo {json.dumps(valore(ctrl, 'ritardo'), ensure_ascii=False)}")
            if valore(ctrl, "browser"):
                siti = ",".join(sorted({re.sub(r"^https?://([^/]+).*", r"\1", x) for x in copia if re.match(r"https?://", x)}))
                cmd.append("--chrome" + (f" --siti {siti}" if siti else ""))
            parallelo = int(valore(ctrl, "parallelo"))
            fondo = not valore(ctrl, "browser") and parallelo > 1
            comandi.append(" \\\n  ".join(cmd) + (" &" if fondo else ""))
            if fondo and (len(meta_c) + 1) % parallelo == 0:
                comandi.append("wait")
            meta_c.append({"nome": nome, "campagna": c["campagna"], "ripetizione": r if rip > 1 else None,
                           "scheda": f"{prot['id']} v{prot['versione']}", "variante": c.get("variante"),
                           "eventi": eventi, "controlli": {k: {"valore": v, "livello": l} for k, (v, l, _) in ctrl.items()}})
    comandi += ["wait", f'python3 "$C" indice "{giro}"', ""]
    p = os.path.join(giro, "comandi.sh")
    open(p, "w", encoding="utf-8").write("\n".join(comandi))
    os.chmod(p, 0o755)
    meta = {"sessione": S["id"], "domanda": S["domanda"], "consegna": S.get("consegna"), "preparato": ora(),
            "schede": {x: f"v{carica_scheda(s, x)['versione']}" for x in [S["esterno"], S["scena"]] + S.get("secondari", [])},
            "campagne_previste": meta_c, "confronto": S.get("confronto"), "avvisi": a}
    scrivi(os.path.join(giro, "giro-meta.json"), meta)
    # le schede usate restano legate a questo giro: una modifica successiva crea una versione nuova
    for sid in {S["esterno"], S["scena"], *S.get("secondari", []), *[c["scheda"] for c in S["campagne"]]}:
        sc = carica_scheda(s, sid)
        if os.path.basename(giro) not in sc["giocata_in"]:
            sc["giocata_in"].append(os.path.basename(giro))
            scrivi(os.path.join(scheda_dir(s, sid), f"v{sc['versione']}.json"), sc)
    S.setdefault("giri", []).append({"giro": os.path.basename(giro), "cartella": giro, "preparato": ora()})
    S["stato"] = "preparata"
    scrivi(sess_file(s), S)
    print(f"preparato: {p} ({len(meta_c)} campagne)" + ("\navvisi:\n- " + "\n- ".join(a) if a else ""))
    return 0


# ---------- dopo il giro ----------
def campagne_giro(giro):
    out = []
    for f in sorted(glob.glob(os.path.join(giro, "*", "campagna.json"))):
        out.append(leggi(f))
    return out


def quadro(o, S, s, giro):
    cs = campagne_giro(giro)
    if not cs:
        print("nessuna campagna nel giro"); return 1
    righe_t = ["| campagna | esito | valida | turni | decisione | costo $ |", "|---|---|---|---|---|---|"]
    for c in cs:
        dec = next((t.get("decisione") for t in reversed(c.get("turni", [])) if t.get("decisione")), "") or ""
        righe_t.append(f"| {c['nome']} | {c['esito']} | {c['valida']} | {len(c.get('turni', []))} | "
                       f"{dec[:60].replace('|', '/')} | {c.get('costo_usd')} |")
    tabella = "\n".join(righe_t)
    parti = []
    for c in cs:
        d = os.path.join(giro, c["nome"])
        an = os.path.join(d, "analisi.md")
        fonte = an if os.path.exists(an) else os.path.join(d, "resoconto.md")
        parti.append(f"### {c['nome']} ({os.path.basename(fonte)})\n" + (open(fonte, encoding="utf-8").read() if os.path.exists(fonte) else "(manca)"))
    prompt = (f"Domanda della sessione: {S['domanda']}\n\nSotto ci sono le analisi delle campagne di una sessione. Ogni "
              "campagna è la storia di una persona diversa: non mediare, confronta. Scrivi in italiano, con queste sezioni:\n"
              "1) OBIEZIONI RICORRENTI (quante campagne, con le parole dei protagonisti)\n2) DOVE SI FERMANO (punto preciso della consegna)\n"
              "3) ESITO PER TIPO DI PERSONA\n4) RISPOSTE DEL PERSONAGGIO ESTERNO CHE HANNO PESATO\n5) BUCHI COMUNI (domande per l'autore)\n"
              "6) CAMPAGNE NON VALIDE e perché (non contano negli esiti)\n7) COSA FARE ADESSO\n\n" + tabella + "\n\n" + "\n\n".join(parti))
    open(os.path.join(giro, "quadro-prompt.md"), "w", encoding="utf-8").write(prompt)
    open(os.path.join(giro, "quadro-tabella.md"), "w", encoding="utf-8").write(tabella + "\n")
    print(tabella + f"\n\nprompt per l'analisi trasversale: {os.path.join(giro, 'quadro-prompt.md')} "
          "(lo esegue chi coordina; la risposta va in quadro.md)")
    return 0


def confronta(giro, a, b):
    ca, cb = leggi(os.path.join(giro, a, "campagna.json")), leggi(os.path.join(giro, b, "campagna.json"))
    if not ca or not cb:
        sys.exit("campagna mancante")
    out = [f"# Confronto {a} ↔ {b}", f"esito: {ca['esito']} ↔ {cb['esito']} · valida: {ca['valida']} ↔ {cb['valida']}"]
    for n in range(1, max(len(ca["turni"]), len(cb["turni"])) + 1):
        ta = next((t for t in ca["turni"] if t["n"] == n), {})
        tb = next((t for t in cb["turni"] if t["n"] == n), {})
        out.append(f"\n## Turno {n}\n**{a}** fa: {ta.get('tester_fa', '—')}\n  pensa: {ta.get('tester_conclusione', '—')}"
                   f"\n**{b}** fa: {tb.get('tester_fa', '—')}\n  pensa: {tb.get('tester_conclusione', '—')}")
    testo = "\n".join(out)
    open(os.path.join(giro, f"confronto-{a}-{b}.md"), "w", encoding="utf-8").write(testo + "\n")
    print(testo)
    return 0


def stabilita(giro):
    gruppi = {}
    for c in campagne_giro(giro):
        base = re.sub(r"-r\d+$", "", c["nome"])
        gruppi.setdefault(base, []).append(c)
    out = {}
    for base, cs in gruppi.items():
        if len(cs) < 2:
            continue
        valide = [c for c in cs if c["valida"]]
        esiti = [c["esito"] for c in valide]
        dom = max(set(esiti), key=esiti.count) if esiti else None
        out[base] = {"ripetizioni": len(cs), "valide": len(valide), "esiti": esiti,
                     "stabilita": round(esiti.count(dom) / len(esiti), 2) if esiti else None, "esito_prevalente": dom}
    scrivi(os.path.join(giro, "stabilita.json"), out)
    for k, v in out.items():
        print(f"{k}: {v['esiti']} → stabilità {v['stabilita']}" + ("  (esito ambiguo: la consegna si legge in più modi)" if (v["stabilita"] or 1) < 0.67 else ""))
    if not out:
        print("nessuna campagna ripetuta nel giro")
    return 0


def memoria(o, S, s, giro):
    """C2: registro del progetto, accanto alle sessioni (SESS/../memoria.json)."""
    mp = os.path.join(os.path.dirname(os.path.abspath(s)), "memoria.json")
    M = leggi(mp, {"domande_in_attesa": [], "motivi": [], "esiti_profili": {}, "obiezioni": [], "giri": []})
    g = os.path.basename(os.path.abspath(giro))
    if g in M["giri"]:
        print(f"giro {g} già in memoria"); return 0
    meta = leggi(os.path.join(giro, "giro-meta.json"), {})
    prev = {x["nome"]: x for x in meta.get("campagne_previste", [])}
    for c in campagne_giro(giro):
        if c.get("buchi"):
            M["domande_in_attesa"].append({"giro": g, "campagna": c["nome"], "testo": c["buchi"], "stato": "aperta"})
        for m in c.get("motivi", []):
            M["motivi"].append({"giro": g, "campagna": c["nome"], "motivo": m})
        prof = prev.get(c["nome"], {}).get("scheda")
        if prof and c["valida"]:
            M["esiti_profili"].setdefault(prof.split(" v")[0], []).append({"giro": g, "versione": prof, "esito": c["esito"]})
    q = os.path.join(giro, "quadro.md")
    if os.path.exists(q):
        m = re.search(r"1\)\s*OBIEZIONI RICORRENTI(.*?)(?=\n\s*2\)|\Z)", open(q, encoding="utf-8").read(), re.S | re.I)
        if m and m.group(1).strip():
            M["obiezioni"].append({"giro": g, "testo": m.group(1).strip()})
    M["giri"].append(g)
    consumati = [p for p, es in M["esiti_profili"].items() if len(es) >= 3 and len({e["esito"] for e in es[-3:]}) == 1]
    M["profili_consumati"] = consumati
    M["aggiornata"] = ora()
    scrivi(mp, M)
    aperte = sum(1 for d in M["domande_in_attesa"] if d["stato"] == "aperta")
    print(f"memoria: {mp} · domande in attesa {aperte} · profili consumati {consumati or 'nessuno'}")
    return 0


# ---------- genera (richiesta, non spesa) ----------
def genera(o, S, s, sid, campo=None):
    sc = carica_scheda(s, sid)
    struttura = {n: nota for n, _, nota in STRUTTURE[sc["tipo"]]}
    vuoti = [n for n in (struttura.keys() if not campo else [campo]) if n not in RISERVATI
             and campo_vuoto(sc["campi"].get(n)) and not (sc["campi"].get(n) or {}).get("bloccato")]
    if campo and campo not in struttura and campo not in sc["personalizzati"]:
        sys.exit(f"campo sconosciuto: {campo}")
    if not vuoti:
        print("niente da generare: campi pieni o bloccati (si genera solo ciò che manca)"); return 0
    pieni = {n: c["valore"] for n, c in sc["campi"].items() if not campo_vuoto(c)}
    prompt = (f"Scheda «{sc['tipo']}» per una simulazione. Domanda della sessione: {S.get('domanda', '')}\n"
              f"Campi già decisi (non cambiarli, restaci coerente):\n{json.dumps(pieni, ensure_ascii=False, indent=1)}\n\n"
              f"Proponi SOLO questi campi, concreti e realistici:\n" + "\n".join(f"- {n}: {struttura.get(n, 'campo personalizzato')}" for n in vuoti)
              + "\nVietato: esiti suggeriti (è interessato, comprerà), istruzioni di durezza. Ammesso un prior realistico."
              "\nRispondi solo con un oggetto JSON {campo: testo}.")
    rq = {"tipo": "genera", "sessione": S["id"], "scheda": sid, "versione": sc["versione"], "campi": vuoti,
          "creata": ora(), "stato": "in coda", "prompt": prompt}
    p = os.path.join(s, "richieste", f"genera-{sid}-{time.strftime('%Y%m%d-%H%M%S')}.json")
    scrivi(p, rq)
    print(f"richiesta in coda: {p} ({len(vuoti)} campi). La esegue chi coordina; poi: campagne.py applica {s} {sid} <risposta.json>")
    return 0


def applica(o, S, s, sid, risposta):
    sc = carica_scheda(s, sid)
    r = leggi(risposta)
    fatti = []
    for n, v in (r or {}).items():
        c = sc["campi"].get(n)
        if c is None or n in RISERVATI or c.get("bloccato") or not campo_vuoto(c):
            continue
        sc["campi"][n] = {"valore": str(v), "fonte": "GENERATO", "data": ora(), "bloccato": False}
        fatti.append(n)
    sc["stato"] = "bozza"
    sc = salva_scheda(s, sc)
    print(f"{sid} v{sc['versione']}: generati {fatti or 'nessuno'} (bozza, da confermare)")
    return 0


# ---------- libreria ----------
def profilo_salva(o, s, sid, nome=None):
    L = lib_dir(o)
    sc = carica_scheda(s, sid)
    if sc["tipo"] != "protagonista":
        sys.exit("solo le schede protagonista diventano profili")
    nome = nome or sid
    d = os.path.join(L, "profili", nome)
    vs = sorted(int(re.search(r"v(\d+)", f).group(1)) for f in glob.glob(os.path.join(d, "v*.json")))
    p = copy.deepcopy(sc)
    p.update({"id": nome, "versione": (vs[-1] + 1) if vs else 1, "giocata_in": [], "salvato": ora(),
              "da_sessione": os.path.basename(os.path.abspath(s)), "da_scheda": f"{sid} v{sc['versione']}"})
    p["campi"].pop("diario", None)
    scrivi(os.path.join(d, f"v{p['versione']}.json"), p)
    print(f"profilo {nome} v{p['versione']}")
    return 0


def profilo_carica(o, nome, v=None):
    d = os.path.join(lib_dir(o), "profili", nome)
    vs = sorted(int(re.search(r"v(\d+)", f).group(1)) for f in glob.glob(os.path.join(d, "v*.json")))
    if not vs:
        sys.exit(f"profilo non trovato: {nome}")
    return leggi(os.path.join(d, f"v{v or vs[-1]}.json"))


def profilo_deriva(o, nome, nuovo, modifiche):
    p = profilo_carica(o, nome)
    q = copy.deepcopy(p)
    q.update({"id": nuovo, "versione": 1, "salvato": ora(), "origine": {"derivato_da": nome, "versione": p["versione"]}})
    for m in modifiche:
        k, _, v = m.partition("=")
        if k not in q["campi"]:
            sys.exit(f"campo sconosciuto: {k}")
        q["campi"][k] = {"valore": v, "fonte": "COORDINATORE", "data": ora(), "bloccato": False}
    d = os.path.join(lib_dir(o), "profili", nuovo)
    if os.path.exists(d):
        sys.exit(f"profilo già esistente: {nuovo}")
    scrivi(os.path.join(d, "v1.json"), q)
    print(f"profilo {nuovo} v1, derivato da {nome} v{p['versione']}")
    return 0


def profilo_lista(o):
    L = lib_dir(o)
    for d in sorted(glob.glob(os.path.join(L, "profili", "*"))):
        vs = sorted(glob.glob(os.path.join(d, "v*.json")))
        p = leggi(vs[-1])
        print(f"{os.path.basename(d)} v{p['versione']} · {p['campi']['nome_eta_luogo']['valore'][:50]}"
              + (f" · derivato da {p['origine']['derivato_da']}" if (p.get("origine") or {}).get("derivato_da") else ""))
    return 0


def ricetta_salva(o, s, nome):
    S = carica_sess(s)
    d = os.path.join(lib_dir(o), "ricette", nome)
    if os.path.exists(d):
        sys.exit(f"ricetta già esistente: {nome}")
    r = {k: S.get(k) for k in ("domanda", "regole", "fuori_storia", "si_puo_dire", "controlli", "mazzo", "esterno", "scena", "secondari")}
    r["campagne"] = [{k: v for k, v in c.items()} for c in S["campagne"]]
    r.update({"nome": nome, "salvata": ora(), "da_sessione": S["id"]})
    os.makedirs(d)
    scrivi(os.path.join(d, "ricetta.json"), r)
    for sid in {S.get("esterno"), S.get("scena"), *S.get("secondari", []), *[c["scheda"] for c in S["campagne"]]} - {None}:
        sc = carica_scheda(s, sid)
        sc.update({"versione": 1, "giocata_in": [], "stato": "bozza", "origine": {"ricetta": nome, "da": f"{sid} v{sc['versione']}"}})
        scrivi(os.path.join(d, "schede", sid, "v1.json"), sc)
    print(f"ricetta {nome}: {d}")
    return 0


def ricetta_usa(o, nome, s):
    d = os.path.join(lib_dir(o), "ricette", nome)
    r = leggi(os.path.join(d, "ricetta.json"))
    if r is None:
        sys.exit(f"ricetta non trovata: {nome}")
    if os.path.exists(sess_file(s)):
        sys.exit(f"sessione già esistente: {s}")
    S = nuova_sess(os.path.basename(os.path.abspath(s)), r.get("domanda", ""))
    for k in ("regole", "fuori_storia", "si_puo_dire", "controlli", "mazzo", "esterno", "scena", "secondari", "campagne"):
        if r.get(k) is not None:
            S[k] = r[k]
    S["origine"] = {"ricetta": nome}
    scrivi(sess_file(s), S)
    if os.path.isdir(os.path.join(d, "schede")):
        shutil.copytree(os.path.join(d, "schede"), os.path.join(s, "schede"), dirs_exist_ok=True)
    print(f"sessione {s} dalla ricetta {nome}: schede in bozza, da riapprovare")
    return 0


def esporta(s, f):
    s = os.path.abspath(s)
    with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(s):
            if "_prep" in root.split(os.sep):
                continue
            for x in files:
                if x.endswith(".json") or x.endswith(".md"):
                    p = os.path.join(root, x)
                    z.write(p, os.path.join(os.path.basename(s), os.path.relpath(p, s)))
    print(f"esportata: {f}")
    return 0


def importa(f, dest):
    with zipfile.ZipFile(f) as z:
        for n in z.namelist():
            if n.startswith("/") or ".." in n.split("/"):
                sys.exit(f"percorso non ammesso nell'archivio: {n}")
        radice = z.namelist()[0].split("/")[0]
        if os.path.exists(os.path.join(dest, radice)):
            sys.exit(f"esiste già: {os.path.join(dest, radice)}")
        z.extractall(dest)
    print(f"importata: {os.path.join(dest, radice)}")
    return 0


def nuova_sess(sid, domanda):
    return {"id": sid, "creata": ora(), "stato": "bozza", "domanda": domanda, "consegna": {"link": "", "versione": ""},
            "esterno": None, "scena": None, "secondari": [], "campagne": [], "regole": [], "fuori_storia": [],
            "si_puo_dire": [], "controlli": {}, "mazzo": [], "seme": 1, "giri": [], "confronto": None,
            # previsti, non costruiti: si attivano dopo la decisione dell'autore
            "riservato": {"saga": None, "bivi": None, "taratura": None, "copilota": None}}


# ---------- CLI ----------
def opzioni(a):
    pos, o = [], {}
    i = 0
    flag = {"blocca", "sblocca", "personalizzato"}
    while i < len(a):
        if a[i].startswith("--"):
            k = a[i][2:]
            if k in flag:
                o[k] = True; i += 1
            else:
                o[k] = a[i + 1]; i += 2
        else:
            pos.append(a[i]); i += 1
    return pos, o


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return 2
    pos, o = opzioni(a)
    cmd = pos[0]
    if cmd == "nuova":
        s = pos[1]
        if os.path.exists(sess_file(s)):
            sys.exit(f"esiste già: {s}")
        S = nuova_sess(os.path.basename(os.path.abspath(s)), o.get("domanda", ""))
        S["consegna"] = {"link": o.get("consegna", ""), "versione": o.get("versione", "")}
        scrivi(sess_file(s), S); print(f"sessione {s}"); return 0
    if cmd in ("stato", "verifica", "imposta", "protagonista", "evento", "controllo", "controlli", "genera",
               "applica", "prepara", "quadro", "memoria"):
        s = pos[1]; S = carica_sess(s)
    if cmd == "imposta":
        k, v = pos[2], pos[3]
        if k in ("riservato", "id", "giri"):
            sys.exit(f"«{k}» non si imposta a mano")
        if k.startswith("consegna."):
            S["consegna"][k.split(".", 1)[1]] = v
        elif k in ("regole", "fuori_storia", "si_puo_dire", "secondari"):
            S[k] = [x for x in v.split("|") if x.strip()]
        elif k == "seme":
            S[k] = int(v)
        elif k == "confronto":
            S[k] = {"tipo": "versioni", "consegne": [{"versione": x.split("=")[0], "link": x.split("=", 1)[1]} for x in v.split("|")]}
        else:
            S[k] = v
        scrivi(sess_file(s), S); print(f"{k} impostato"); return 0
    if cmd == "protagonista":
        camp, sid = pos[2], pos[3]
        if any(c["campagna"] == camp for c in S["campagne"]):
            sys.exit(f"campagna già presente: {camp}")
        S["campagne"].append({"campagna": camp, "scheda": sid, "variante": o.get("variante"), "controlli": {}})
        scrivi(sess_file(s), S); print(f"campagna {camp} → {sid}"); return 0
    if cmd == "evento":
        S["mazzo"] = [e for e in S["mazzo"] if e["id"] != pos[2]] + [
            {"id": pos[2], "testo": pos[3], "peso": float(o.get("peso", 1)), "dal_turno": int(o.get("dal-turno", 1))}]
        scrivi(sess_file(s), S); print(f"evento {pos[2]} nel mazzo ({len(S['mazzo'])})"); return 0
    if cmd == "controllo":
        k, v = pos[2], pos[3]
        if k not in CONTROLLI:
            sys.exit(f"controllo sconosciuto: {k} (noti: {', '.join(CONTROLLI)})")
        x = {"valore": converti(k, v), "bloccato": bool(o.get("blocca"))}
        if o.get("campagna"):
            c = next((c for c in S["campagne"] if c["campagna"] == o["campagna"]), None)
            if c is None:
                sys.exit("campagna non trovata")
            c.setdefault("controlli", {})[k] = x
        else:
            S["controlli"][k] = x
        scrivi(sess_file(s), S)
        r = risolvi_controlli(o, S, o.get("campagna"))[k]
        print(f"{k} = {r[0]!r} (vince: {r[1]})" + (" — bloccato più in alto, il tuo valore non vale" if r[1] != ("campagna" if o.get("campagna") else "sessione") else ""))
        return 0
    if cmd == "controlli":
        for k, (v, liv, bl) in risolvi_controlli(o, S, o.get("campagna")).items():
            print(f"{k:24} {v!r:14} {liv}{' (bloccato)' if bl else ''} · agisce: {CONTROLLI[k][1]}")
        return 0
    if cmd in ("stato", "verifica"):
        b, av = verifica(o, S, s)
        if cmd == "stato":
            print(f"sessione {S['id']} · {S['stato']} · campagne {len(S['campagne'])} · giri {len(S.get('giri', []))}")
            for sid in sorted(os.listdir(os.path.join(s, "schede"))) if os.path.isdir(os.path.join(s, "schede")) else []:
                sc = carica_scheda(s, sid)
                print(f"  {sid:20} {sc['tipo']:12} v{sc['versione']} {sc['stato']}" + (f" · giocata in {sc['giocata_in']}" if sc["giocata_in"] else ""))
        print(("BLOCCA:\n- " + "\n- ".join(b)) if b else "pronta da giocare")
        if av:
            print("avvisi:\n- " + "\n- ".join(av))
        return 1 if b else 0
    if cmd == "genera":
        return genera(o, S, s, pos[2], o.get("campo"))
    if cmd == "applica":
        return applica(o, S, s, pos[2], pos[3])
    if cmd == "prepara":
        return prepara(o, S, s, pos[2])
    if cmd == "quadro":
        return quadro(o, S, s, pos[2])
    if cmd == "memoria":
        return memoria(o, S, s, pos[2])
    if cmd == "confronta":
        return confronta(pos[1], pos[2], pos[3])
    if cmd == "stabilita":
        return stabilita(pos[1])
    if cmd == "scheda":
        sub, s = pos[1], pos[2]
        if sub == "nuova":
            tipo, sid = pos[3], pos[4]
            if versioni(s, sid):
                sys.exit(f"scheda già esistente: {sid}")
            if o.get("profilo"):
                p = profilo_carica(o, o["profilo"], int(o["versione"]) if o.get("versione") else None)
                sc = nuova_scheda("protagonista", sid)
                sc["campi"].update({k: v for k, v in p["campi"].items() if k != "diario"})
                sc["personalizzati"] = p.get("personalizzati", [])
                sc["origine"] = {"profilo": p["id"], "versione": p["versione"]}
            else:
                sc = nuova_scheda(tipo, sid)
            salva_scheda(s, sc)
            S = carica_sess(s)
            if sc["tipo"] in ("esterno", "scena"):
                S[sc["tipo"]] = sid
            elif sc["tipo"] == "secondario" and sid not in S["secondari"]:
                S["secondari"].append(sid)
            scrivi(sess_file(s), S)
            print(f"scheda {sid} ({sc['tipo']}) v1 bozza" + (f", dal profilo {o['profilo']}" if o.get("profilo") else ""))
            return 0
        sid = pos[3]
        sc = carica_scheda(s, sid)
        if sub == "imposta":
            campo, v = pos[4], pos[5]
            if campo not in sc["campi"]:
                if not o.get("personalizzato"):
                    sys.exit(f"campo «{campo}» non previsto: aggiungi --personalizzato per crearlo")
                sc["personalizzati"].append(campo)
            c = sc["campi"].get(campo) or {"valore": "", "fonte": None, "data": None, "bloccato": False}
            fonte = o.get("fonte", "COORDINATORE").upper()
            if fonte not in FONTI:
                sys.exit(f"fonte: {FONTI}")
            c.update({"valore": v, "fonte": fonte, "data": ora()})
            if o.get("blocca"):
                c["bloccato"] = True
            if o.get("sblocca"):
                c["bloccato"] = False
            sc["campi"][campo] = c
            sc["stato"] = "bozza"
            sc = salva_scheda(s, sc)
            print(f"{sid} v{sc['versione']}: {campo} ({fonte}{', bloccato' if c['bloccato'] else ''})")
            return 0
        if sub == "conferma":
            campo = pos[4]
            sc["campi"][campo]["fonte"] = "AUTORE"
            sc["campi"][campo]["data"] = ora()
            sc = salva_scheda(s, sc)
            print(f"{sid}: {campo} confermato"); return 0
        if sub == "approva":
            p = problemi_scheda(sc)
            if p:
                print("non approvabile:\n- " + "\n- ".join(p)); return 1
            sc["stato"] = "approvata"; sc["approvata"] = ora()
            scrivi(os.path.join(scheda_dir(s, sid), f"v{sc['versione']}.json"), sc)
            print(f"{sid} v{sc['versione']} approvata"); return 0
        if sub == "versioni":
            vs = versioni(s, sid)
            if len(pos) < 6:
                print(f"{sid}: versioni {vs}"); return 0
            A, B = carica_scheda(s, sid, int(pos[4].lstrip("v"))), carica_scheda(s, sid, int(pos[5].lstrip("v")))
            for n in sorted(set(A["campi"]) | set(B["campi"])):
                va, vb = (A["campi"].get(n) or {}).get("valore", ""), (B["campi"].get(n) or {}).get("valore", "")
                if va != vb:
                    print(f"## {n}")
                    for l in difflib.unified_diff(str(va).splitlines(), str(vb).splitlines(), lineterm="", n=0):
                        if not l.startswith(("---", "+++", "@@")):
                            print("  " + l)
            return 0
    if cmd == "profilo":
        sub = pos[1]
        if sub == "salva":
            return profilo_salva(o, pos[2], pos[3], o.get("nome"))
        if sub == "deriva":
            return profilo_deriva(o, pos[2], pos[3], pos[4:])
        if sub == "lista":
            return profilo_lista(o)
    if cmd == "ricetta":
        return ricetta_salva(o, pos[2], pos[3]) if pos[1] == "salva" else ricetta_usa(o, pos[2], pos[3])
    if cmd == "esporta":
        return esporta(pos[1], pos[2])
    if cmd == "importa":
        return importa(pos[1], pos[2])
    print(f"comando sconosciuto: {' '.join(pos)}\n"); print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
