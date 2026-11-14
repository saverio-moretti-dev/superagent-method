#!/usr/bin/env python3
"""Argomenti, campagne e storie: schede, profili, manuale, controlli, preparazione dei giri, quadro, memoria, analisi.

Gerarchia (14/11): ARGOMENTO (una cartella/repo per argomento di test, es. «forni di quartiere»: memoria e analisi di
tutte le campagne) > CAMPAGNA (N storie con le loro schede e controlli; si rifà cambiando schede o storia) > STORIA
(un protagonista, un tester, giocata da storia.py). Fino al 14/11 «campagna» si chiamava sessione e «storia» campagna.

Non lancia modelli e non spende: prepara i file che storia.py usa e legge ciò che produce.
Formato dei dati: references/dati.md. Libreria globale (profili, manuale globale, ricette): --lib DIR o $CAMPAGNE_LIB.

Argomento
  campagne.py argomento nuovo DIR [--titolo "…"]   cartella dell'argomento: argomento.json, memoria.json, campagne/ (git locale)
  campagne.py argomento stato DIR                   campagne, giri, storie, domande in attesa
  campagne.py analisi DIR                           tutte le campagne dell'argomento: tabella + prompt per l'analisi
Extra selezionabili (mai attivi da soli: si accendono per argomento o per campagna; references/dati.md § Extra)
  campagne.py extra DIR                             elenco degli extra e stato (DIR = argomento o campagna)
  campagne.py extra DIR NOME on|off                 taratura (argomento) · saga, bivi, copilota, allenamento (campagna)
  campagne.py esito-vero DIR --esito COMPRA|LASCIA|INCOMPLETA --chi "tipo di persona" [--come SCHEDA|PROFILO]
                         [--canale …] [--quando AAAA-MM] [--motivo "…"] [--versione v2] [--campagna C] [--anche-remoto]
                                                    C3: esito di una persona VERA, anonimo, solo nella repo locale dell'argomento
  campagne.py esiti-veri DIR                        esiti veri registrati e confronto con quelli delle storie
Campagna (CAMP = DIR/campagne/<nome>; fuori da un argomento la memoria sta accanto alla campagna)
  campagne.py nuova CAMP --domanda "…" [--consegna URL] [--versione v1]
  campagne.py stato CAMP                      riassunto: schede, stati, cosa blocca
  campagne.py verifica CAMP                   controllo di completezza (exit 1 se qualcosa blocca il gioco)
  campagne.py imposta CAMP chiave valore      campo della campagna (domanda, consegna.link, seme, …)
  campagne.py protagonista CAMP STORIA SCHEDA [--variante V] [--segue [CAMPAGNA/]GIRO/STORIA]
                                              aggiunge una storia (un protagonista); --segue: episodio successivo (extra saga)
  campagne.py bivio CAMP GIRO STORIA --dal-turno N --risposta "testo"|@file [--nome S]
                                              A3: rigioca STORIA dal turno N con un'altra risposta (extra bivi)
  campagne.py copilota GIRO [STORIA [--approva | --correggi "testo"|@file]]
                                              D1: risposte del master in attesa dell'autore (extra copilota)
  campagne.py allenamento CAMP [STORIA [--turni 6 --chiamate 6 --nome N] | NOME --rispondi "testo"|@file]
                                              D2: ruoli invertiti, il modello fa il protagonista di STORIA e l'autore
                                              risponde (extra allenamento); senza altro: allenamenti e risposte attese
  campagne.py diario CAMP SCHEDA --da [CAMPAGNA/]GIRO/STORIA   A1: richiesta del diario nel personaggio dall'episodio
  campagne.py evento CAMP ID "testo" [--peso 1] [--dal-turno 1]  mazzo di eventi del mondo
Schede
  campagne.py scheda nuova CAMP TIPO ID [--profilo P [--versione N]]   TIPO: protagonista|esterno|scena|secondario
  campagne.py scheda imposta CAMP ID CAMPO "valore" [--fonte F] [--blocca|--sblocca] [--personalizzato]
  campagne.py scheda approva CAMP ID          approva (rifiuta se mancano obbligatori o ci sono righe DEDOTTO)
  campagne.py scheda conferma CAMP ID CAMPO   riga DEDOTTO/GENERATO confermata dall'autore → fonte AUTORE
  campagne.py scheda versioni CAMP ID [VA VB] versioni affiancate (cosa è cambiato)
Controlli (tre livelli: globale → campagna → storia)
  campagne.py controllo CAMP CHIAVE VALORE [--storia S] [--blocca]
  campagne.py controlli CAMP [--storia S]     valori risolti, con il livello che vince
Generare (non spende: scrive una richiesta che chi coordina esegue)
  campagne.py genera CAMP ID [--campo C | --sezione tutti]       → CAMP/richieste/genera-<ID>-<ora>.json + prompt
  campagne.py applica CAMP ID RISPOSTA.json   riempie solo campi vuoti e non bloccati, come GENERATO (bozza)
Giro
  campagne.py prepara CAMP GIRO              file per ogni storia + comandi.sh (storia.py), mazzo estratto col seme
  campagne.py quadro CAMP GIRO               C1: tabella delle storie + prompt per l'analisi trasversale
  campagne.py confronta GIRO S1 S2           A2: due storie affiancate turno per turno
  campagne.py stabilita GIRO                 A4: ripetizioni della stessa storia, quanto cambia l'esito
  campagne.py memoria CAMP GIRO              C2: aggiorna la memoria dell'argomento (buchi, motivi, profili consumati)
Libreria
  campagne.py profilo salva CAMP SCHEDA [--nome P]       scheda protagonista → profilo (versione nuova se esiste)
  campagne.py profilo deriva P NUOVO [campo=valore …]    profilo simile, «derivato da P vN»
  campagne.py profilo lista
  campagne.py ricetta salva CAMP NOME | ricetta usa NOME CAMP_NUOVA
  campagne.py esporta CAMP FILE.zip | importa FILE.zip DIR
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
        ("diario", False, "solo con l'extra «saga» (A1): cosa ricorda lui degli episodi passati, in prima persona, mai dati della prova"),
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
        ("cosa_sa_l_amico", False, "cosa sanno i secondari (l'amico che ha passato il link, il socio…) del personaggio "
         "esterno e della proposta; dipende dalla storia della campagna; vuoto = solo ciò che dice la scena"),
        ("frasi_da_copiare", False, "una per riga: il master le riporta identiche (link, istruzione sul browser)"),
        ("mondo", True, "stagione, momento, terze persone ammesse, imprevisti ammessi"),
    ],
    "secondario": [
        ("ruolo", True, "socio, familiare, amico che ha passato il link, concorrente, ospite…"),
        ("chi_e", True, "due righe: chi è, cosa vuole"),
        ("rapporto", True, "che rapporto ha col protagonista e quanto pesa nelle sue decisioni"),
        ("come_parla", False, "tono, poche parole"),
    ],
}
RISERVATI = {"diario"}  # campi usati solo se la campagna sceglie l'extra «saga» (A1)

# Extra selezionabili (utente 14/11 01:38: «roba extra che si può selezionare e aggiungere ai test», mai sempre attivi).
# livello: dove si accende. costruito: False = previsto, non ancora accendibile.
EXTRA = {
    "taratura": ("argomento", True, "C3: esiti di persone vere (anonimi) accanto a quelli delle storie"),
    "saga": ("campagna", True, "A1: lo stesso protagonista torna in una storia nuova con il suo diario"),
    "bivi": ("campagna", True, "A3: si rigioca una storia da un turno con un'altra risposta del personaggio esterno"),
    "copilota": ("campagna", True, "D1: l'autore approva o corregge le risposte del personaggio esterno"),
    "allenamento": ("campagna", True, "D2: ruoli invertiti, il master fa il protagonista e l'autore risponde"),
}
ESITI = ("COMPRA", "LASCIA", "INCOMPLETA")
# Il diario di una saga resta nel mondo del protagonista: niente parole della prova
DIARIO_VIETATO = [(r"\b(test|prova cieca|simulazion\w*|tester|master|giro|turno|campagna|valutazion\w*)\b", "parole della prova"),
                  (r"\b(COMPRA|LASCIA|INCOMPLETA)\b", "esito della prova"), (r"\b(AI|IA|intelligenza artificiale|modello)\b", "chi la gioca")]
# Anonimato degli esiti veri: niente contatti, indirizzi web, profili social, numeri lunghi
NON_ANONIMO = [(r"[\w.+-]+@[\w-]+\.[\w.]+", "indirizzo email"), (r"https?://|www\.", "indirizzo web"),
               (r"(?<!\w)@\w{2,}", "profilo social"), (r"\+?\d[\d .-]{6,}\d", "numero di telefono o codice"),
               (r"(?<![.!?]\s)(?<!^)\b[A-ZÀ-Ý][a-zà-ÿ]+\s+[A-ZÀ-Ý][a-zà-ÿ]+\b", "possibile nome e cognome")]

# Controlli globali di default (references/manuale.md). agisce: programma | master | schede
CONTROLLI = {
    "turni": (6, "programma"), "chiamate": (12, "programma"), "chiamate_browser_min": (25, "programma"),
    "browser": (False, "programma"), "parallelo": (2, "programma"), "ripetizioni": (1, "programma"),
    "modello_tester": ("sonnet", "programma"), "modello_master": ("sonnet", "programma"),
    "modello_controllo": ("haiku", "programma"), "controllo_turno": (True, "programma"),
    "controllo_turno_azione": ("ferma", "programma"), "tetto_storia_usd": (None, "programma"),
    "tetto_campagna_usd": (None, "programma"), "livello": (3, "programma"),
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


def camp_file(s):
    return os.path.join(s, "campagna.json")


def carica_camp(s):
    d = leggi(camp_file(s))
    if d is None:
        sys.exit(f"campagna non trovata: {s}")
    if "extra" not in d:  # campagne create prima degli extra (14/11): «riservato» → «extra», tutto spento
        d.pop("riservato", None)
        d["extra"] = {k: False for k, v in EXTRA.items() if v[0] == "campagna"}
    return d


def extra_attivo(S, nome):
    return bool((S or {}).get("extra", {}).get(nome))


# ---------- argomento ----------
def argomento_di(s):
    """La cartella dell'argomento che contiene la campagna (quella con argomento.json), o None."""
    d = os.path.abspath(s)
    while True:
        if os.path.isfile(os.path.join(d, "argomento.json")):
            return d
        su = os.path.dirname(d)
        if su == d:
            return None
        d = su


def memoria_file(s):
    a = argomento_di(s)
    return os.path.join(a, "memoria.json") if a else os.path.join(os.path.dirname(os.path.abspath(s)), "memoria.json")


MEMORIA_VUOTA = {"domande_in_attesa": [], "motivi": [], "esiti_profili": {}, "obiezioni": [], "giri": []}


def argomento_nuovo(d, titolo):
    d = os.path.abspath(d)
    if os.path.exists(os.path.join(d, "argomento.json")):
        sys.exit(f"argomento già esistente: {d}")
    os.makedirs(os.path.join(d, "campagne"), exist_ok=True)
    scrivi(os.path.join(d, "argomento.json"), {"id": os.path.basename(d), "titolo": titolo or os.path.basename(d), "creato": ora(),
                                               "extra": {k: False for k, v in EXTRA.items() if v[0] == "argomento"}})
    if not os.path.exists(os.path.join(d, "memoria.json")):
        scrivi(os.path.join(d, "memoria.json"), MEMORIA_VUOTA)
    leggimi = os.path.join(d, "LEGGIMI.md")
    if not os.path.exists(leggimi):
        open(leggimi, "w", encoding="utf-8").write(
            f"# {titolo or os.path.basename(d)}\n\nArgomento di prove cieche: ogni cartella in `campagne/` è una campagna "
            "(storie, schede, giri). `memoria.json` raccoglie buchi, motivi ed esiti di tutte; `campagne.py analisi` le "
            "mette a confronto. Formato: references/dati.md della skill prova-cieca.\n")
    git = ""
    if not os.path.isdir(os.path.join(d, ".git")) and shutil.which("git"):
        import subprocess
        r = subprocess.run(["git", "init", "-q", d], capture_output=True, text=True)
        git = " · git locale" if r.returncode == 0 else f" · git init fallito: {r.stderr.strip()}"
    print(f"argomento {d}{git} (nessun remoto: pubblicarlo è una scelta dell'autore)")
    return 0


def campagne_di(arg):
    out = []
    for f in sorted(glob.glob(os.path.join(arg, "campagne", "*", "campagna.json"))):
        out.append((os.path.dirname(f), leggi(f)))
    return out


def argomento_stato(arg):
    arg = os.path.abspath(arg)
    A = leggi(os.path.join(arg, "argomento.json"))
    if A is None:
        sys.exit(f"argomento non trovato: {arg}")
    M = leggi(os.path.join(arg, "memoria.json"), MEMORIA_VUOTA)
    cs = campagne_di(arg)
    print(f"argomento {A['titolo']} · campagne {len(cs)} · giri in memoria {len(M.get('giri', []))}")
    for d, S in cs:
        storie = sum(len(storie_giro(g.get("cartella") or os.path.join(d, "giri", g["giro"]))) for g in S.get("giri", []))
        print(f"  {S['id']:20} {S['stato']:10} storie previste {len(S.get('storie', []))} · giri {len(S.get('giri', []))} · storie giocate {storie}")
    aperte = [x for x in M.get("domande_in_attesa", []) if x.get("stato") == "aperta"]
    print(f"domande in attesa per l'autore: {len(aperte)} · profili consumati: {M.get('profili_consumati') or 'nessuno'}")
    return 0


def analisi(arg):
    """Tutte le campagne dell'argomento, contestualizzate: cosa è cambiato fra una campagna e l'altra e cosa è successo."""
    arg = os.path.abspath(arg)
    A = leggi(os.path.join(arg, "argomento.json"))
    if A is None:
        sys.exit(f"argomento non trovato: {arg}")
    M = leggi(os.path.join(arg, "memoria.json"), MEMORIA_VUOTA)
    righe_t = ["| campagna | giro | storia | scheda | consegna | esito | valida | decisione |", "|---|---|---|---|---|---|---|---|"]
    contesti, n = [], 0
    for d, S in campagne_di(arg):
        contesti.append(f"## Campagna {S['id']}\nDomanda: {S.get('domanda', '')}\nConsegna: {(S.get('consegna') or {}).get('versione', '')} "
                        f"{(S.get('consegna') or {}).get('link', '')}")
        for g in S.get("giri", []):
            gd = g.get("cartella") or os.path.join(d, "giri", g["giro"])
            meta = leggi(os.path.join(gd, "giro-meta.json"), {})
            prev = {x["nome"]: x for x in meta.get("storie_previste", [])}
            contesti.append(f"### giro {g['giro']} · schede {meta.get('schede', {})}")
            for c in storie_giro(gd):
                n += 1
                dec = next((t.get("decisione") for t in reversed(c.get("turni", [])) if t.get("decisione")), "") or ""
                righe_t.append(f"| {S['id']} | {g['giro']} | {c['nome']} | {prev.get(c['nome'], {}).get('scheda', '')} | "
                               f"{(S.get('consegna') or {}).get('versione', '')} | {c['esito']} | {c['valida']} | {dec[:50].replace('|', '/')} |")
            q = os.path.join(gd, "quadro.md")
            if os.path.exists(q):
                contesti.append(open(q, encoding="utf-8").read())
    if not n:
        print("nessuna storia giocata nell'argomento"); return 1
    tabella = "\n".join(righe_t)
    tar = taratura(arg)
    prompt = (f"Argomento di test: {A['titolo']}. Sotto ci sono tutte le campagne fatte su questo argomento: per ognuna la "
              "domanda, la versione della consegna, le schede usate, l'esito di ogni storia e il quadro del giro. Le campagne "
              "differiscono per schede, storia o consegna: leggi ogni risultato nel suo contesto, non mediare fra campagne "
              "diverse. Scrivi in italiano, con queste sezioni:\n1) COSA È CAMBIATO FRA LE CAMPAGNE e cosa ha cambiato negli esiti\n"
              "2) OBIEZIONI CHE TORNANO IN PIÙ CAMPAGNE\n3) ESITI PER TIPO DI PERSONA, su tutte le campagne\n"
              "4) BUCHI ANCORA APERTI (domande per l'autore)\n5) PROFILI CONSUMATI (rigiocarli non insegna niente)\n"
              "6) STORIE NON VALIDE e perché (non contano)\n7) PROSSIMA CAMPAGNA: cosa cambiare\n"
              + ("8) TARATURA: dove gli esiti delle storie somigliano a quelli delle persone vere e dove no; quali "
                 "profili, controlli o severità cambiare. Gli esiti veri valgono più delle storie.\n" if tar else "")
              + "\n" + tabella + "\n\n" + "\n\n".join(contesti)
              + ("\n\n## Esiti di persone vere (anonimi) e confronto\n" + "\n".join(tar) if tar else "")
              + "\n\n## Memoria dell'argomento\n" + json.dumps({k: M.get(k) for k in ("domande_in_attesa", "esiti_profili",
                                                                                     "profili_consumati", "motivi")}, ensure_ascii=False, indent=1))
    open(os.path.join(arg, "analisi-prompt.md"), "w", encoding="utf-8").write(prompt)
    open(os.path.join(arg, "analisi-tabella.md"), "w", encoding="utf-8").write(tabella + "\n")
    print(tabella + f"\n\nprompt per l'analisi dell'argomento: {os.path.join(arg, 'analisi-prompt.md')} "
          "(lo esegue chi coordina; la risposta va in analisi.md)")
    return 0


# ---------- extra ----------
def extra_cmd(d, nome=None, stato=None):
    d = os.path.abspath(d)
    if os.path.isfile(os.path.join(d, "argomento.json")):
        liv, f = "argomento", os.path.join(d, "argomento.json")
        X = leggi(f)
        X.setdefault("extra", {k: False for k, v in EXTRA.items() if v[0] == "argomento"})
    elif os.path.isfile(camp_file(d)):
        liv, f = "campagna", camp_file(d)
        X = carica_camp(d)
    else:
        sys.exit(f"né argomento né campagna: {d}")
    if nome is None:
        for k, (l, costruito, testo) in EXTRA.items():
            if l == liv:
                print(f"{k:12} {'ACCESO' if X['extra'].get(k) else 'spento':7} {testo}" + ("" if costruito else "  (non ancora costruito)"))
        altri = [k for k, v in EXTRA.items() if v[0] != liv]
        print(f"(a livello {'campagna' if liv == 'argomento' else 'argomento'}: {', '.join(altri)})")
        return 0
    if nome not in EXTRA:
        sys.exit(f"extra sconosciuto: {nome} (noti: {', '.join(EXTRA)})")
    if EXTRA[nome][0] != liv:
        sys.exit(f"«{nome}» si accende per {EXTRA[nome][0]}, non per {liv}")
    if stato not in ("on", "off"):
        sys.exit("stato: on | off")
    if stato == "on" and not EXTRA[nome][1]:
        sys.exit(f"«{nome}» è previsto ma non ancora costruito")
    X["extra"][nome] = stato == "on"
    scrivi(f, X)
    print(f"{nome} {'acceso' if stato == 'on' else 'spento'} per {liv} {X['id']}")
    return 0


def esiti_file(arg):
    return os.path.join(arg, "esiti-veri.json")


def controlla_luogo_esiti(arg, anche_remoto):
    """Gli esiti veri stanno solo nella repo locale dell'argomento: mai dentro la skill, mai in una repo con remoto senza scelta."""
    skill = os.path.dirname(BASE)
    if os.path.commonpath([os.path.realpath(arg), os.path.realpath(skill)]) == os.path.realpath(skill):
        sys.exit("l'argomento è dentro la skill: gli esiti veri non si salvano qui (la skill può essere pubblica)")
    import subprocess
    r = subprocess.run(["git", "-C", arg, "remote", "-v"], capture_output=True, text=True) if shutil.which("git") else None
    if r and r.returncode == 0 and r.stdout.strip() and not anche_remoto:
        sys.exit("la repo dell'argomento ha un remoto: gli esiti veri restano locali. Se l'autore ha scelto altrimenti: --anche-remoto")


def anonimo(testi):
    p = []
    for campo, v in testi.items():
        for rx, cosa in NON_ANONIMO:
            m = re.search(rx, v or "")
            if m:
                p.append(f"{campo}: {cosa} («{m.group(0)}»)")
    return p


def esito_vero(arg, o):
    arg = os.path.abspath(arg)
    A = leggi(os.path.join(arg, "argomento.json"))
    if A is None:
        sys.exit(f"argomento non trovato: {arg} (gli esiti veri stanno solo in un argomento)")
    if not (A.get("extra") or {}).get("taratura"):
        sys.exit(f"extra «taratura» spento: campagne.py extra {arg} taratura on")
    controlla_luogo_esiti(arg, o.get("anche-remoto"))
    esito = (o.get("esito") or "").upper()
    if esito not in ESITI:
        sys.exit(f"--esito: {' | '.join(ESITI)}")
    if not o.get("chi"):
        sys.exit("--chi: il tipo di persona (es. «titolare di forno, 60 anni, poco digitale»), mai il nome")
    quando = o.get("quando") or time.strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", quando):
        sys.exit("--quando: AAAA-MM (solo il mese: il giorno aiuta a riconoscere la persona)")
    testi = {k: o.get(k, "") for k in ("chi", "canale", "motivo", "come")}
    p = anonimo(testi)
    if p and not o.get("controllato"):
        sys.exit("non anonimo, non salvato:\n- " + "\n- ".join(p) + "\n(se è un falso allarme, riscrivi o aggiungi --controllato)")
    E = leggi(esiti_file(arg), {"esiti": []})
    n = max([e["n"] for e in E["esiti"]] or [0]) + 1
    E["esiti"].append({"n": n, "quando": quando, "chi": o["chi"], "come": o.get("come", ""), "canale": o.get("canale", ""),
                       "esito": esito, "motivo": o.get("motivo", ""), "versione": o.get("versione", ""),
                       "campagna": o.get("campagna", ""), "registrato": time.strftime("%Y-%m")})  # solo il mese: anonimato
    scrivi(esiti_file(arg), E)
    print(f"esito vero n. {n} salvato in {esiti_file(arg)} (solo locale)" + (" — usa --come per confrontarlo con le storie" if not o.get("come") else ""))
    return 0


def esiti_simulati(arg):
    """Esiti delle storie valide per scheda e per profilo d'origine, da memoria.json e dalle schede delle campagne."""
    M = leggi(os.path.join(arg, "memoria.json"), MEMORIA_VUOTA)
    sim = {}
    for sid, es in M.get("esiti_profili", {}).items():
        sim.setdefault(sid, []).extend(e["esito"] for e in es)
    for d, _S in campagne_di(arg):
        for sid in os.listdir(os.path.join(d, "schede")) if os.path.isdir(os.path.join(d, "schede")) else []:
            vs = versioni(d, sid)
            prof = (carica_scheda(d, sid).get("origine") or {}).get("profilo") if vs else None
            if prof and prof != sid:
                sim.setdefault(prof, []).extend(sim.get(sid, []) if sid in M.get("esiti_profili", {}) else [])
    return sim


def taratura(arg):
    """Righe di confronto vero ↔ storie per l'analisi; [] se l'extra è spento o non ci sono esiti."""
    A = leggi(os.path.join(arg, "argomento.json"), {})
    E = leggi(esiti_file(arg), {"esiti": []})
    if not (A.get("extra") or {}).get("taratura") or not E["esiti"]:
        return []
    sim = esiti_simulati(arg)
    out = ["| come | esiti veri | esiti delle storie | accordo |", "|---|---|---|---|"]
    gruppi = {}
    for e in E["esiti"]:
        gruppi.setdefault(e["come"] or "(non collegato)", []).append(e["esito"])
    for come, veri in gruppi.items():
        s = sim.get(come, [])
        acc = ""
        if s and come != "(non collegato)":
            dom = max(set(s), key=s.count)
            acc = f"{sum(1 for v in veri if v == dom)}/{len(veri)} come l'esito prevalente delle storie ({dom})"
        out.append(f"| {come} | {', '.join(veri)} | {', '.join(s) or '—'} | {acc or '—'} |")
    return out


def esiti_veri_cmd(arg):
    arg = os.path.abspath(arg)
    E = leggi(esiti_file(arg), {"esiti": []})
    if not E["esiti"]:
        print("nessun esito vero registrato"); return 0
    for e in E["esiti"]:
        print(f"{e['n']:3} {e['quando']} {e['esito']:10} {e['chi']}" + (f" · come {e['come']}" if e["come"] else "")
              + (f" · {e['motivo']}" if e["motivo"] else ""))
    t = taratura(arg)
    print("\n" + ("\n".join(t) if t else "(extra «taratura» spento: nessun confronto)"))
    return 0


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


def problemi_scheda(sc, saga=False):
    """Ciò che impedisce di approvare (lista di stringhe). saga: la campagna ha acceso l'extra «saga» (diario ammesso)."""
    p = []
    for n, obbl, _ in STRUTTURE[sc["tipo"]]:
        if obbl and campo_vuoto(sc["campi"].get(n)):
            p.append(f"{sc['id']}: campo obbligatorio vuoto «{n}»")
    for n, c in sc["campi"].items():
        if campo_vuoto(c):
            continue
        if n in RISERVATI and not saga:
            p.append(f"{sc['id']}: «{n}» si usa solo con l'extra «saga» acceso nella campagna: va lasciato vuoto")
        if n == "diario" and saga:
            for rx, cosa in DIARIO_VIETATO:
                if re.search(rx, str(c["valore"]), re.I):
                    p.append(f"{sc['id']}: il diario parla della prova ({cosa}): solo ciò che ricorda lui, nel suo mondo")
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


def risolvi_controlli(o, S, storia=None):
    """{chiave: (valore, livello, bloccato)}. Un valore bloccato a un livello non si sovrascrive sotto."""
    out = {k: (v, "default", False) for k, (v, _) in CONTROLLI.items()}
    livelli = [("globale", manuale_globale(o).get("controlli", {})), ("campagna", S.get("controlli", {}))]
    if storia:
        c = next((x for x in S["storie"] if x["storia"] == storia), None)
        if c is None:
            sys.exit(f"storia non trovata: {storia}")
        livelli.append(("storia", c.get("controlli", {})))
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
        b.append("campagna: manca la domanda")
    if not S.get("storie"):
        b.append("campagna: nessuna storia (protagonista)")
    if len(S.get("storie", [])) > 5:
        b.append("campagna: più di 5 storie (oltre non si impara di più)")
    usate = [S.get("esterno"), S.get("scena")] + S.get("secondari", []) + [c["scheda"] for c in S.get("storie", [])]
    if not S.get("esterno"):
        b.append("campagna: manca la scheda del personaggio esterno")
    if not S.get("scena"):
        b.append("campagna: manca la scheda della scena")
    for sid in [x for x in usate if x]:
        if not versioni(s, sid):
            b.append(f"{sid}: scheda inesistente")
            continue
        sc = carica_scheda(s, sid)
        if sc["stato"] != "approvata":
            b.append(f"{sid}: in bozza (v{sc['versione']})")
        b += problemi_scheda(sc, extra_attivo(S, "saga"))
    for c in S.get("storie", []):
        ctrl = risolvi_controlli(o, S, c["storia"])
        for k, ammessi in VALORI.items():
            if valore(ctrl, k) not in ammessi:
                b.append(f"{c['storia']}: controllo {k}={valore(ctrl, k)!r} fuori da {ammessi}")
        if not versioni(s, c["scheda"]):
            continue
        p = carica_scheda(s, c["scheda"])
        if valore(ctrl, "casualita") == 2 and campo_vuoto(p["campi"].get("variazioni")):
            b.append(f"{c['storia']}: casualità 2 chiede le variazioni scritte nella scheda {c['scheda']} prima del giro")
        if valore(ctrl, "chi_decide") not in ("", "da solo") and not S.get("secondari"):
            b.append(f"{c['storia']}: chi_decide={valore(ctrl, 'chi_decide')!r} chiede una scheda secondaria (chi decide con lui)")
        if valore(ctrl, "severita") == "alta":
            testo = " ".join(str(x.get("valore", "")) for x in p["campi"].values()).lower()
            if not re.search(r"propost|preventiv|budget|soldi|tempo|concorren|brutt|fregat|delus", testo):
                a.append(f"{c['storia']}: severità alta ma la scheda non dice niente di proposte ricevute, budget, "
                         "tempo o esperienze cattive: la severità agisce solo da lì")
        for k in ("canale", "momento", "dimestichezza"):
            v = valore(ctrl, k)
            if v and v.lower() not in json.dumps(p, ensure_ascii=False).lower() + json.dumps(
                    carica_scheda(s, S["scena"]) if S.get("scena") and versioni(s, S["scena"]) else {}, ensure_ascii=False).lower():
                a.append(f"{c['storia']}: controllo {k}={v!r} non compare nelle schede: scrivilo nella scheda o togli il controllo")
        if valore(ctrl, "browser") and valore(ctrl, "chiamate") < valore(ctrl, "chiamate_browser_min"):
            a.append(f"{c['storia']}: browser con {valore(ctrl, 'chiamate')} chiamate per turno: ne servono almeno "
                     f"{valore(ctrl, 'chiamate_browser_min')} (prepara le alza)")
        if c.get("segue"):
            b += problemi_segue(s, S, c, p)
        if c.get("variante") and S.get("scena") and versioni(s, S["scena"]):
            if not variante_testo(carica_scheda(s, S["scena"]), c["variante"]):
                b.append(f"{c['storia']}: variante «{c['variante']}» assente in cosa_riceve della scena")
    att = S.get("controlli", {}).get("attivita_mondo", {}).get("valore")
    if att == "vivo" and not S.get("mazzo"):
        a.append("campagna: attività del mondo «vivo» ma il mazzo di eventi è vuoto")
    return b, a


def trova_storia_giocata(s, rif):
    """rif = GIRO/STORIA (stessa campagna) o CAMPAGNA/GIRO/STORIA (stesso argomento) → (cartella giro, nome, scheda giocata)."""
    parti = rif.strip("/").split("/")
    if len(parti) == 2:
        camp = s
    elif len(parti) == 3:
        arg = argomento_di(s)
        if not arg:
            return None, None, None, "un episodio di un'altra campagna si cerca solo dentro lo stesso argomento"
        camp = os.path.join(arg, "campagne", parti[0])
    else:
        return None, None, None, f"riferimento «{rif}»: GIRO/STORIA o CAMPAGNA/GIRO/STORIA"
    giro, nome = os.path.join(camp, "giri", parti[-2]), parti[-1]
    if not file_storia(giro, nome):
        return None, None, None, f"episodio «{rif}» non giocato (manca storia.json)"
    meta = leggi(os.path.join(giro, "giro-meta.json"), {})
    sch = next((x.get("scheda") for x in meta.get("storie_previste", []) if x["nome"] == nome), None)
    return giro, nome, sch, None


def problemi_segue(s, S, c, p):
    """A1: una storia che segue un episodio. Il diario passa solo dallo stesso protagonista (stessa scheda), mai da un altro."""
    b = []
    if not extra_attivo(S, "saga"):
        return [f"{c['storia']}: segue «{c['segue']}» ma l'extra «saga» è spento (campagne.py extra CAMP saga on)"]
    giro, nome, sch, err = trova_storia_giocata(s, c["segue"])
    if err:
        return [f"{c['storia']}: {err}"]
    if not sch or sch.split(" v")[0] != c["scheda"]:
        b.append(f"{c['storia']}: l'episodio «{c['segue']}» era di {sch or 'una scheda sconosciuta'}, non di {c['scheda']}: "
                 "una saga continua solo lo stesso protagonista")
    elif sch == f"{p['id']} v{p['versione']}":
        b.append(f"{c['storia']}: la scheda {c['scheda']} è la stessa versione dell'episodio: la sua vita è andata avanti "
                 "(aggiorna «adesso») e il diario va scritto (campagne.py diario)")
    if campo_vuoto(p["campi"].get("diario")):
        b.append(f"{c['storia']}: manca il diario di {c['scheda']} (campagne.py diario CAMP {c['scheda']} --da {c['segue']})")
    return b


def diario(o, S, s, sid, rif):
    """A1: richiesta (non spesa) per il diario nel personaggio, dalla partita di un episodio dello stesso protagonista."""
    if not extra_attivo(S, "saga"):
        sys.exit(f"extra «saga» spento: campagne.py extra {s} saga on")
    sc = carica_scheda(s, sid)
    if sc["tipo"] != "protagonista":
        sys.exit("il diario è solo del protagonista")
    giro, nome, sch, err = trova_storia_giocata(s, rif)
    if err:
        sys.exit(err)
    if not sch or sch.split(" v")[0] != sid:
        sys.exit(f"l'episodio «{rif}» era di {sch or 'una scheda sconosciuta'}: il diario passa solo dallo stesso protagonista")
    C = leggi(file_storia(giro, nome))
    partita = "\n".join(f"Momento {t['n']}: {t.get('master', '')}\nCosa ha fatto: {t.get('tester_fa', '')}\n"
                        f"Cosa ha concluso: {t.get('tester_conclusione', '')}" + (f"\nHa deciso: {t['decisione']}" if t.get("decisione") else "")
                        for t in C.get("turni", []) if t.get("tester_fa"))
    prima = (sc["campi"].get("diario") or {}).get("valore", "")
    prompt = (f"Sei {(sc['campi'].get('nome_eta_luogo') or {}).get('valore', 'il protagonista')}. Qualche mese fa ti è successo "
              f"quello che c'è sotto. Scrivi, in prima persona e con le tue parole, cosa ti è rimasto: chi hai incontrato, cosa "
              "ti ha colpito, cosa ti ha fatto storcere il naso, cosa hai deciso e perché, cosa ti è rimasto in sospeso. "
              "Ricordi come ricorda una persona: i dettagli piccoli si perdono, l'impressione resta. Al massimo 10 righe.\n"
              "Vietato: parlare di prove, simulazioni, turni, giri, valutazioni; dire cosa farai la prossima volta.\n"
              + (f"\nCosa ricordavi già da prima (tienilo, aggiungi):\n{prima}\n" if prima else "")
              + f"\nCom'è andata:\n{partita}\n\nRispondi solo con il testo del diario.")
    rq = {"tipo": "diario", "campagna": S["id"], "scheda": sid, "versione": sc["versione"], "da": rif, "creata": ora(),
          "stato": "in coda", "prompt": prompt}
    p = os.path.join(s, "richieste", f"diario-{sid}-{time.strftime('%Y%m%d-%H%M%S')}.json")
    scrivi(p, rq)
    print(f"richiesta in coda: {p}. La esegue chi coordina; poi: campagne.py scheda imposta {s} {sid} diario \"…\" "
          "--fonte GENERATO (l'autore lo legge, lo corregge e lo conferma)")
    return 0


def bivio(o, S, s, giro, nome, n, risposta):
    """A3: prepara la storia NOME rigiocata dal turno N con la risposta dell'autore. Non spende: scrive il comando."""
    if not extra_attivo(S, "bivi"):
        sys.exit(f"extra «bivi» spento: campagne.py extra {s} bivi on")
    giro = os.path.abspath(giro)
    f = file_storia(giro, nome)
    if not f:
        sys.exit(f"storia non giocata: {nome} in {giro}")
    C = leggi(f)
    if C.get("bivio"):
        nome0 = C["bivio"]["origine"]
        print(f"avviso: {nome} è già un bivio di {nome0}: il nuovo eredita anche il suo cambio")
    fatti = [t for t in C.get("turni", []) if t.get("tester_fa") and t["n"] < n]
    if n < 2 or len(fatti) != n - 1:
        sys.exit(f"dal turno {n} servono i turni 1..{n - 1} con un'azione del tester (ce ne sono {len(fatti)})")
    blocchi = open(os.path.join(giro, "comandi.sh"), encoding="utf-8").read().split('python3 "$C"')
    orig = next((b for b in blocchi[1:] if re.search(rf"--nome {re.escape(nome)}\b", b)), None)
    if orig is None:
        sys.exit(f"comando di {nome} non trovato in comandi.sh")
    orig = re.split(r"\n(?:wait|python3)", orig.rstrip().rstrip("&").rstrip())[0].rstrip().rstrip("&").rstrip()
    k = 1
    while os.path.exists(os.path.join(giro, f"{nome}-b{n}-{k}")) or os.path.exists(os.path.join(giro, "_prep", f"{nome}-b{n}-{k}")):
        k += 1
    nuovo = o.get("nome") or f"{nome}-b{n}-{k}"
    d = os.path.join(giro, "_prep", nuovo)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "risposta-bivio.txt"), "w", encoding="utf-8").write(risposta.strip() + "\n")
    cmd = re.sub(rf"--nome {re.escape(nome)}\b", f"--nome {nuovo}", orig)
    cmd = f'#!/bin/bash\nset -u\nC="{os.path.join(BASE, "storia.py")}"\npython3 "$C"{cmd} \\\n  --bivio "{f}" --dal-turno {n} --risposta "{d}/risposta-bivio.txt"\n'
    p = os.path.join(giro, f"comandi-{nuovo}.sh")
    open(p, "w", encoding="utf-8").write(cmd)
    os.chmod(p, 0o755)
    print(f"bivio {nuovo}: {nome} dal turno {n} con la risposta nuova → {p} (lo lancia chi coordina; poi: campagne.py confronta {giro} {nome} {nuovo})")
    return 0


def copilota_cmd(giro, nome=None, approva=False, correggi=None):
    """D1: elenca le risposte in attesa dell'autore, o ne approva/corregge una (la storia in corso la legge e riparte).
    Non spende: scrive solo il file copilota/turno-N.json della storia."""
    import glob
    giro = os.path.abspath(giro)
    files = sorted(glob.glob(os.path.join(giro, nome or "*", "copilota", "turno-*.json")),
                   key=lambda f: (os.path.dirname(f), int(re.search(r"turno-(\d+)", f).group(1))))
    attesa = [f for f in files if (leggi(f) or {}).get("stato") == "in attesa"]
    if not approva and correggi is None:
        if not attesa:
            print("nessuna risposta in attesa" + (f" in {nome}" if nome else ""))
        for f in attesa:
            d = leggi(f)
            print(f"== {d['storia']} · turno {d['turno']} · dal {d.get('scritta', '?')}"
                  + (f"\n   CORREZIONE RIFIUTATA: {d['rifiutata']}" if d.get("rifiutata") else ""))
            print(f"IL PROTAGONISTA HA FATTO:\n{d.get('tester_ha_fatto', '')}\n\nRISPOSTA PROPOSTA:\n{d['proposta']}\n")
        return 0
    if not nome:
        sys.exit("approva o correggi una storia: campagne.py copilota GIRO STORIA --approva | --correggi \"…\"")
    if not attesa:
        sys.exit(f"nessuna risposta in attesa in {nome}")
    f = attesa[0]
    d = leggi(f)
    if correggi is not None:
        testo = correggi.strip()
        if not testo:
            sys.exit("correzione vuota")
        sys.path.insert(0, BASE)
        import check_fuga
        pv = os.path.join(giro, "_prep", nome, "vietate.txt")
        vietate = check_fuga.carica(pv) if os.path.exists(pv) else []
        fuga = check_fuga.trova(testo, check_fuga.SEMPRE + vietate) + check_fuga.segnaposto(testo)
        if fuga:
            sys.exit("la correzione contiene parole che il tester non deve leggere: " + ", ".join(fuga))
        d.update(stato="corretta", testo=testo)
    else:
        d["stato"] = "approvata"
    d.pop("rifiutata", None)
    d["deciso"] = ora()
    tmp = f + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, f)
    print(f"{nome} turno {d['turno']}: {d['stato']} (la storia riparte da sola)")
    return 0


def allenamento_cmd(o, S, s, cosa=None):
    """D2: prepara un allenamento (non spende: scrive il comando), elenca quelli in attesa, o scrive la risposta dell'autore.
    Vive in CAMP/allenamenti/<nome>/: fuori dai giri, dalla memoria e da analisi (è un uso, non un collaudo)."""
    import glob
    base = os.path.join(os.path.abspath(s), "allenamenti")
    if cosa and os.path.isdir(os.path.join(base, cosa)) and not o.get("turni"):
        d = os.path.join(base, cosa)
        attesa = [f for f in sorted(glob.glob(os.path.join(d, "turno-*.json"))) if (leggi(f) or {}).get("stato") == "in attesa"]
        if o.get("rispondi") is None:
            for f in attesa:
                x = leggi(f)
                print(f"== {cosa} · turno {x['turno']} · dal {x.get('scritta', '?')}\nTI SCRIVE:\n{x['messaggio']}\n")
            A = leggi(os.path.join(d, "allenamento.json")) or {}
            print(f"{cosa}: {A.get('stato', 'non lanciato')}" + (f", esito {A['esito']}" if A.get("stato") == "finito" else ""))
            return 0
        if not attesa:
            sys.exit(f"nessun messaggio in attesa in {cosa}")
        r = o["rispondi"]
        r = (open(r[1:], encoding="utf-8").read() if r.startswith("@") else r).strip()
        if not r:
            sys.exit("risposta vuota")
        f = attesa[0]; x = leggi(f)
        x.update(stato="risposta", risposta=r, deciso=ora())
        tmp = f + ".tmp"
        json.dump(x, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, f)
        print(f"{cosa} turno {x['turno']}: risposta inviata (l'allenamento riparte da solo)")
        return 0
    if not cosa:
        for d in sorted(glob.glob(os.path.join(base, "*"))):
            A = leggi(os.path.join(d, "allenamento.json")) or {}
            n = sum((leggi(f) or {}).get("stato") == "in attesa" for f in glob.glob(os.path.join(d, "turno-*.json")))
            print(f"{os.path.basename(d)}: {A.get('stato', 'preparato, non lanciato')}" + (f" · {n} in attesa" if n else ""))
        return 0
    if not extra_attivo(S, "allenamento"):
        sys.exit(f"extra «allenamento» spento: campagne.py extra {s} allenamento on")
    c = next((x for x in S["storie"] if x["storia"] == cosa), None)
    if not c:
        sys.exit(f"storia sconosciuta: {cosa} (né allenamento esistente)")
    prot, scena = carica_scheda(s, c["scheda"]), carica_scheda(s, S["scena"])
    saga = bool(extra_attivo(S, "saga"))
    b = problemi_scheda(prot, saga) + problemi_scheda(scena, saga)
    if b:
        print("NON SI PREPARA, blocca:\n- " + "\n- ".join(b)); return 1
    k = 1
    while os.path.exists(os.path.join(base, f"{cosa}-a{k}")):
        k += 1
    nome = o.get("nome") or f"{cosa}-a{k}"
    d = os.path.join(base, nome)
    if os.path.exists(d):
        sys.exit(f"esiste già: {d}")
    os.makedirs(d)
    open(os.path.join(d, "protagonista.md"), "w", encoding="utf-8").write(blocco(prot, "CHI SEI", saga and bool(c.get("segue"))).split("\n", 1)[1])
    ricevuto = variante_testo(scena, c.get("variante"))
    apertura = "\n\n".join(x for x in [
        "PRIMA: " + prot["campi"]["prima"]["valore"], "ADESSO: " + prot["campi"]["adesso"]["valore"],
        "COME ARRIVA: " + scena["campi"]["come_arriva"]["valore"], "COSA RICEVI: " + (ricevuto or "")] if x)
    open(os.path.join(d, "apertura.txt"), "w", encoding="utf-8").write(apertura)
    cmd = (f'#!/bin/bash\nset -u\npython3 "{os.path.join(BASE, "allenamento.py")}" --dir "{d}" --protagonista "{d}/protagonista.md" '
           f'--apertura "{d}/apertura.txt" --turni {int(o.get("turni") or 6)} --chiamate {int(o.get("chiamate") or 6)}\n')
    p = os.path.join(d, "comando.sh")
    open(p, "w", encoding="utf-8").write(cmd)
    os.chmod(p, 0o755)
    scrivi(os.path.join(d, "meta.json"), {"storia": cosa, "scheda": f"{prot['id']} v{prot['versione']}",
                                          "scena": f"{scena['id']} v{scena['versione']}", "preparato": ora()})
    print(f"allenamento {nome}: {p} (lo lancia chi coordina; poi le risposte: campagne.py allenamento {s} {nome} --rispondi \"…\")")
    return 0


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
             "abitudini_ricerca": "Abitudini di ricerca", "cosa_sa_l_amico": "Cosa sa l'amico (i secondari) del personaggio esterno"}


def etichetta(n):
    return ETICHETTE.get(n) or n.replace("_", " ").capitalize()


def blocco(sc, titolo, saga=False):
    out = [f"== {titolo} ({sc['id']} v{sc['versione']}) =="]
    for n, _, nota in STRUTTURE[sc["tipo"]]:
        c = sc["campi"].get(n)
        if (n in RISERVATI and not saga) or campo_vuoto(c):
            continue
        out.append(("Cosa ricordi di quando l'hai già incontrato (tuo diario)" if n == "diario" else etichetta(n)) + f": {c['valore']}")
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
    comandi, meta_c = ["#!/bin/bash", f"# giro preparato {ora()} da campagne.py — campagna {S['id']}", "set -u",
                       f'C="{os.path.join(BASE, "storia.py")}"'], []
    seme0 = int(S.get("seme") or 1)
    for i, c in enumerate(S["storie"]):
        ctrl = risolvi_controlli(o, S, c["storia"])
        prot = carica_scheda(s, c["scheda"])
        turni = 2 if valore(ctrl, "livello") == 2 else int(valore(ctrl, "turni"))
        chiamate = int(valore(ctrl, "profondita_ricerca") or valore(ctrl, "chiamate"))
        if valore(ctrl, "browser"):
            chiamate = max(chiamate, int(valore(ctrl, "chiamate_browser_min")))
        rip = max(1, int(valore(ctrl, "ripetizioni")))
        for r in range(1, rip + 1):
            nome = c["storia"] + (f"-r{r}" if rip > 1 else "")
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
                blocco(prot, "PROTAGONISTA", bool(extra_attivo(S, "saga") and c.get("segue"))),
                "\n\n".join(blocco(x, "PERSONAGGIO SECONDARIO (lo interpreti tu, parla poco)") for x in sec)
                + ("\nSe il protagonista chiede a un secondario cosa sa del personaggio esterno: sa solo ciò che dice la scena "
                   "(«Cosa sa l'amico», se c'è)."
                   if sec else ""),
                "== REGOLE DELLA CAMPAGNA ==\n" + (regole_s or "- nessuna oltre le globali")
                + ("\nResta fuori dalla storia (rispondi in modo neutro): " + "; ".join(S["fuori_storia"]) if S.get("fuori_storia") else "")
                + ("\nSi può dire: " + "; ".join(S["si_puo_dire"]) if S.get("si_puo_dire") else ""),
                "== CONTROLLI ==\n" + "\n".join(ctrl_master),
            ] if x)
            open(os.path.join(d, "master.md"), "w", encoding="utf-8").write(contesto)
            apertura = "\n\n".join(x for x in [
                "PRIMA: " + prot["campi"]["prima"]["valore"], "ADESSO: " + prot["campi"]["adesso"]["valore"],
                ("COSA TI RICORDI DI QUANDO L'HAI GIÀ INCONTRATO: " + prot["campi"]["diario"]["valore"])
                if extra_attivo(S, "saga") and c.get("segue") and not campo_vuoto(prot["campi"].get("diario")) else "",
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
            if extra_attivo(S, "copilota"):
                cmd.append("--copilota")  # l'autore approva o corregge ogni risposta: una storia alla volta
            parallelo = 1 if extra_attivo(S, "copilota") else int(valore(ctrl, "parallelo"))
            fondo = not valore(ctrl, "browser") and parallelo > 1
            comandi.append(" \\\n  ".join(cmd) + (" &" if fondo else ""))
            if fondo and (len(meta_c) + 1) % parallelo == 0:
                comandi.append("wait")
            meta_c.append({"nome": nome, "storia": c["storia"], "ripetizione": r if rip > 1 else None,
                           "scheda": f"{prot['id']} v{prot['versione']}", "variante": c.get("variante"), "segue": c.get("segue"),
                           "eventi": eventi, "controlli": {k: {"valore": v, "livello": l} for k, (v, l, _) in ctrl.items()}})
    comandi += ["wait", f'python3 "$C" indice "{giro}"', ""]
    p = os.path.join(giro, "comandi.sh")
    open(p, "w", encoding="utf-8").write("\n".join(comandi))
    os.chmod(p, 0o755)
    meta = {"campagna": S["id"], "domanda": S["domanda"], "consegna": S.get("consegna"), "preparato": ora(),
            "schede": {x: f"v{carica_scheda(s, x)['versione']}" for x in [S["esterno"], S["scena"]] + S.get("secondari", [])},
            "storie_previste": meta_c, "confronto": S.get("confronto"), "avvisi": a}
    scrivi(os.path.join(giro, "giro-meta.json"), meta)
    # le schede usate restano legate a questo giro: una modifica successiva crea una versione nuova
    for sid in {S["esterno"], S["scena"], *S.get("secondari", []), *[c["scheda"] for c in S["storie"]]}:
        sc = carica_scheda(s, sid)
        if os.path.basename(giro) not in sc["giocata_in"]:
            sc["giocata_in"].append(os.path.basename(giro))
            scrivi(os.path.join(scheda_dir(s, sid), f"v{sc['versione']}.json"), sc)
    S.setdefault("giri", []).append({"giro": os.path.basename(giro), "cartella": giro, "preparato": ora()})
    S["stato"] = "preparata"
    scrivi(camp_file(s), S)
    print(f"preparato: {p} ({len(meta_c)} storie)" + ("\navvisi:\n- " + "\n- ".join(a) if a else ""))
    return 0


# ---------- dopo il giro ----------
def file_storia(giro, nome):
    """storia.json; campagna.json per i giri fatti prima della rinomina (14/11)."""
    for n in ("storia.json", "campagna.json"):
        f = os.path.join(giro, nome, n)
        if os.path.isfile(f):
            return f
    return None


def storie_giro(giro):
    out = []
    for d in sorted(os.listdir(giro)) if os.path.isdir(giro) else []:
        f = file_storia(giro, d) if d != "_prep" else None
        if f:
            out.append(leggi(f))
    return out


def quadro(o, S, s, giro):
    cs = storie_giro(giro)
    if not cs:
        print("nessuna storia nel giro"); return 1
    righe_t = ["| storia | esito | valida | turni | decisione | costo $ |", "|---|---|---|---|---|---|"]
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
    prompt = (f"Domanda della campagna: {S['domanda']}\n\nSotto ci sono le analisi delle storie di una campagna. Ogni "
              "storia è la storia di una persona diversa: non mediare, confronta. Scrivi in italiano, con queste sezioni:\n"
              "1) OBIEZIONI RICORRENTI (quante storie, con le parole dei protagonisti)\n2) DOVE SI FERMANO (punto preciso della consegna)\n"
              "3) ESITO PER TIPO DI PERSONA\n4) RISPOSTE DEL PERSONAGGIO ESTERNO CHE HANNO PESATO\n5) BUCHI COMUNI (domande per l'autore)\n"
              "6) STORIE NON VALIDE e perché (non contano negli esiti)\n7) COSA FARE ADESSO\n\n" + tabella + "\n\n" + "\n\n".join(parti))
    open(os.path.join(giro, "quadro-prompt.md"), "w", encoding="utf-8").write(prompt)
    open(os.path.join(giro, "quadro-tabella.md"), "w", encoding="utf-8").write(tabella + "\n")
    print(tabella + f"\n\nprompt per l'analisi trasversale: {os.path.join(giro, 'quadro-prompt.md')} "
          "(lo esegue chi coordina; la risposta va in quadro.md)")
    return 0


def confronta(giro, a, b):
    fa, fb = file_storia(giro, a), file_storia(giro, b)
    ca, cb = (leggi(fa) if fa else None), (leggi(fb) if fb else None)
    if not ca or not cb:
        sys.exit("storia mancante")
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
    for c in storie_giro(giro):
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
        print("nessuna storia ripetuta nel giro")
    return 0


def memoria(o, S, s, giro):
    """C2: memoria dell'argomento (ARG/memoria.json); fuori da un argomento accanto alla campagna."""
    mp = memoria_file(s)
    M = leggi(mp, MEMORIA_VUOTA)
    g = f"{S['id']}/{os.path.basename(os.path.abspath(giro))}"  # campagna/giro: i nomi dei giri si ripetono fra campagne
    if g in M["giri"]:
        print(f"giro {g} già in memoria"); return 0
    meta = leggi(os.path.join(giro, "giro-meta.json"), {})
    prev = {x["nome"]: x for x in meta.get("storie_previste", [])}
    for c in storie_giro(giro):
        if c.get("buchi"):
            M["domande_in_attesa"].append({"giro": g, "storia": c["nome"], "testo": c["buchi"], "stato": "aperta"})
        for m in c.get("motivi", []):
            M["motivi"].append({"giro": g, "storia": c["nome"], "motivo": m})
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
    prompt = (f"Scheda «{sc['tipo']}» per una simulazione. Domanda della campagna: {S.get('domanda', '')}\n"
              f"Campi già decisi (non cambiarli, restaci coerente):\n{json.dumps(pieni, ensure_ascii=False, indent=1)}\n\n"
              f"Proponi SOLO questi campi, concreti e realistici:\n" + "\n".join(f"- {n}: {struttura.get(n, 'campo personalizzato')}" for n in vuoti)
              + "\nVietato: esiti suggeriti (è interessato, comprerà), istruzioni di durezza. Ammesso un prior realistico."
              "\nRispondi solo con un oggetto JSON {campo: testo}.")
    rq = {"tipo": "genera", "campagna": S["id"], "scheda": sid, "versione": sc["versione"], "campi": vuoti,
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
              "da_campagna": os.path.basename(os.path.abspath(s)), "da_scheda": f"{sid} v{sc['versione']}"})
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
    S = carica_camp(s)
    d = os.path.join(lib_dir(o), "ricette", nome)
    if os.path.exists(d):
        sys.exit(f"ricetta già esistente: {nome}")
    r = {k: S.get(k) for k in ("domanda", "regole", "fuori_storia", "si_puo_dire", "controlli", "mazzo", "esterno", "scena", "secondari")}
    r["storie"] = [{k: v for k, v in c.items()} for c in S["storie"]]
    r.update({"nome": nome, "salvata": ora(), "da_campagna": S["id"]})
    os.makedirs(d)
    scrivi(os.path.join(d, "ricetta.json"), r)
    for sid in {S.get("esterno"), S.get("scena"), *S.get("secondari", []), *[c["scheda"] for c in S["storie"]]} - {None}:
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
    if os.path.exists(camp_file(s)):
        sys.exit(f"campagna già esistente: {s}")
    S = nuova_camp(os.path.basename(os.path.abspath(s)), r.get("domanda", ""))
    for k in ("regole", "fuori_storia", "si_puo_dire", "controlli", "mazzo", "esterno", "scena", "secondari", "storie"):
        if r.get(k) is not None:
            S[k] = r[k]
    S["origine"] = {"ricetta": nome}
    scrivi(camp_file(s), S)
    if os.path.isdir(os.path.join(d, "schede")):
        shutil.copytree(os.path.join(d, "schede"), os.path.join(s, "schede"), dirs_exist_ok=True)
    print(f"campagna {s} dalla ricetta {nome}: schede in bozza, da riapprovare")
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


def nuova_camp(sid, domanda):
    return {"id": sid, "creata": ora(), "stato": "bozza", "domanda": domanda, "consegna": {"link": "", "versione": ""},
            "esterno": None, "scena": None, "secondari": [], "storie": [], "regole": [], "fuori_storia": [],
            "si_puo_dire": [], "controlli": {}, "mazzo": [], "seme": 1, "giri": [], "confronto": None,
            # extra selezionabili, spenti finché la campagna non li sceglie (campagne.py extra)
            "extra": {k: False for k, v in EXTRA.items() if v[0] == "campagna"}}


# ---------- CLI ----------
def opzioni(a):
    pos, o = [], {}
    i = 0
    flag = {"blocca", "sblocca", "personalizzato", "anche-remoto", "controllato", "approva"}
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
    if cmd == "argomento":
        if pos[1] == "nuovo":
            return argomento_nuovo(pos[2], o.get("titolo"))
        if pos[1] == "stato":
            return argomento_stato(pos[2])
    if cmd == "analisi":
        return analisi(pos[1])
    if cmd == "extra":
        return extra_cmd(pos[1], pos[2] if len(pos) > 2 else None, pos[3] if len(pos) > 3 else None)
    if cmd == "esito-vero":
        return esito_vero(pos[1], o)
    if cmd == "esiti-veri":
        return esiti_veri_cmd(pos[1])
    if cmd == "nuova":
        s = pos[1]
        if os.path.exists(camp_file(s)):
            sys.exit(f"esiste già: {s}")
        if not argomento_di(s):
            print("avviso: campagna fuori da un argomento (campagne.py argomento nuovo DIR): la memoria starà accanto")
        S = nuova_camp(os.path.basename(os.path.abspath(s)), o.get("domanda", ""))
        S["consegna"] = {"link": o.get("consegna", ""), "versione": o.get("versione", "")}
        scrivi(camp_file(s), S); print(f"campagna {s}"); return 0
    if cmd in ("stato", "verifica", "imposta", "protagonista", "evento", "controllo", "controlli", "genera",
               "applica", "prepara", "quadro", "memoria", "diario", "bivio", "allenamento"):
        s = pos[1]; S = carica_camp(s)
    if cmd == "imposta":
        k, v = pos[2], pos[3]
        if k in ("riservato", "extra", "id", "giri"):
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
        scrivi(camp_file(s), S); print(f"{k} impostato"); return 0
    if cmd == "protagonista":
        camp, sid = pos[2], pos[3]
        if any(c["storia"] == camp for c in S["storie"]):
            sys.exit(f"storia già presente: {camp}")
        st = {"storia": camp, "scheda": sid, "variante": o.get("variante"), "controlli": {}}
        if o.get("segue"):
            if not extra_attivo(S, "saga"):
                sys.exit(f"--segue chiede l'extra «saga»: campagne.py extra {s} saga on")
            st["segue"] = o["segue"]
        S["storie"].append(st)
        scrivi(camp_file(s), S); print(f"storia {camp} → {sid}" + (f" (segue {o['segue']})" if o.get("segue") else "")); return 0
    if cmd == "evento":
        S["mazzo"] = [e for e in S["mazzo"] if e["id"] != pos[2]] + [
            {"id": pos[2], "testo": pos[3], "peso": float(o.get("peso", 1)), "dal_turno": int(o.get("dal-turno", 1))}]
        scrivi(camp_file(s), S); print(f"evento {pos[2]} nel mazzo ({len(S['mazzo'])})"); return 0
    if cmd == "controllo":
        k, v = pos[2], pos[3]
        if k not in CONTROLLI:
            sys.exit(f"controllo sconosciuto: {k} (noti: {', '.join(CONTROLLI)})")
        x = {"valore": converti(k, v), "bloccato": bool(o.get("blocca"))}
        if o.get("storia"):
            c = next((c for c in S["storie"] if c["storia"] == o["storia"]), None)
            if c is None:
                sys.exit("storia non trovata")
            c.setdefault("controlli", {})[k] = x
        else:
            S["controlli"][k] = x
        scrivi(camp_file(s), S)
        r = risolvi_controlli(o, S, o.get("storia"))[k]
        print(f"{k} = {r[0]!r} (vince: {r[1]})" + (" — bloccato più in alto, il tuo valore non vale" if r[1] != ("storia" if o.get("storia") else "campagna") else ""))
        return 0
    if cmd == "controlli":
        for k, (v, liv, bl) in risolvi_controlli(o, S, o.get("storia")).items():
            print(f"{k:24} {v!r:14} {liv}{' (bloccato)' if bl else ''} · agisce: {CONTROLLI[k][1]}")
        return 0
    if cmd in ("stato", "verifica"):
        b, av = verifica(o, S, s)
        if cmd == "stato":
            print(f"campagna {S['id']} · {S['stato']} · storie {len(S['storie'])} · giri {len(S.get('giri', []))}")
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
    if cmd == "bivio":
        if not o.get("dal-turno") or not o.get("risposta"):
            sys.exit("--dal-turno N --risposta \"testo\" (o @file)")
        return bivio(o, S, s, pos[2], pos[3], int(o["dal-turno"]),
                     open(o["risposta"][1:], encoding="utf-8").read() if o["risposta"].startswith("@") else o["risposta"])
    if cmd == "allenamento":
        return allenamento_cmd(o, S, s, pos[2] if len(pos) > 2 else None)
    if cmd == "copilota":
        corr = o.get("correggi")
        if corr is not None and corr.startswith("@"):
            corr = open(corr[1:], encoding="utf-8").read()
        return copilota_cmd(pos[1], pos[2] if len(pos) > 2 else None, bool(o.get("approva")), corr)
    if cmd == "diario":
        if not o.get("da"):
            sys.exit("--da GIRO/STORIA (o CAMPAGNA/GIRO/STORIA): l'episodio da cui nasce il diario")
        return diario(o, S, s, pos[2], o["da"])
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
            S = carica_camp(s)
            if sc["tipo"] in ("esterno", "scena"):
                S[sc["tipo"]] = sid
            elif sc["tipo"] == "secondario" and sid not in S["secondari"]:
                S["secondari"].append(sid)
            scrivi(camp_file(s), S)
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
            p = problemi_scheda(sc, extra_attivo(carica_camp(s), "saga"))
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
