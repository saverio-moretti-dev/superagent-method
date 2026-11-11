#!/usr/bin/env python3
"""Regia — canale del SUPERAGENTE verso l'app. Scrive SOLO in regia/.

  sup.py nuove                          richieste non ancora prese (da coda.jsonl); le segna «letta dal SUP»
                                        e scrive il battito sup-ascolto.json (riga «SUP in ascolto» nell'app)
  sup.py prendi <id> [--a SESSIONE] ["nota"]
                                        VERDE: il SUP l'ha presa; con --a l'app mostra «girata a SESSIONE»
  sup.py giallo <id> ["nota"]           GIALLO: in mano all'agente, il SUP aspetta
  sup.py grigio <id> ["nota"]           GRIGIO: consegnata, valutata, soddisfatta
  sup.py conferma <id> ["cosa"]         SERVE CONFERMA: produzione/cancellazione/invio esterno, il SUP chiede in chat
  sup.py risposta <SESSIONE|SUP> "testo" [--id <id>]
                                        messaggio nel filo della sessione (o nel filo SUP); con --id l'app
                                        segna quella richiesta «risposta» (l'id lo stampa sup.py nuove);
                                        senza --id segna le richieste aperte di quel filo (ultime 6 h)
  sup.py giro                           = nuove (nome breve per il giro del Monitor/Cron)
  sup.py rispondi <id> "testo" [--a SESSIONE] [--grigio]
                                        TUTTO IN UNO: risposta nel filo
                                        di quella richiesta + «risposta»; con --a anche «girata a SESSIONE» (verde);
                                        con --grigio anche consegnata. Sostituisce prendi + risposta + grigio
  sup.py sospeso                        elenco del riquadro «In sospeso» (fonte unica)
  sup.py sospeso aggiungi "testo" [SESSIONE]
                                        link nel testo: [parola](http://…) → parola cliccabile; anche URL nudi
  sup.py sospeso togli <n>
  sup.py sospeso cambia <n> "testo"
  sup.py permesso "cosa"                il SUP aspetta un permesso nel terminale (segnale nell'app)
  sup.py permesso via                   segnale spento
  sup.py pausa ["motivo"]               SUP IN PAUSA (es. passaggio): riga fissa nell'app, i messaggi dell'utente restano
                                        nell'app (attesa.jsonl); destinatari = solo chi lavora o ha un ordine aperto
  sup.py riprendi                       SUP RIPARTITO: riga tolta, messaggi trattenuti in coda, avviso agli stessi + chi lavora
  sup.py sessione                       sessioni in pausa
  sup.py sessione pausa NOME ["motivo"] sessione IN PAUSA: in fondo nell'app, fuori da avvisi, destinatari, contesti.py;
                                        esce da sola se l'utente le scrive dalla Regia o torna a lavorare (riga nel filo)
  sup.py sessione via NOME              pausa tolta a mano (anche rispondi/prendi --a NOME la tolgono)
"""
import json, os, re, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attesa import rilascia  # noqa: E402
from modifiche import unisci, da_vedere  # noqa: E402
import pausa_sessioni  # noqa: E402

QUI = os.path.dirname(os.path.abspath(__file__))
QUI = os.environ.get("PLANCIA_DATI", QUI)  # cartella dati: diversa solo nei test
CODA, RICH = os.path.join(QUI, "coda.jsonl"), os.path.join(QUI, "richieste.json")
RISP, SOSP, PERM = os.path.join(QUI, "risposte.jsonl"), os.path.join(QUI, "insospeso.json"), os.path.join(QUI, "permesso.json")
PAUSA, ASCOLTO = os.path.join(QUI, "pausa.json"), os.path.join(QUI, "sup-ascolto.json")
STATI = {"prendi": "verde", "giallo": "giallo", "grigio": "grigio", "conferma": "conferma"}
ORA = lambda: time.strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731


def avviso_prova():
    """Regie di prova accese (server.py con PLANCIA_DATI diverso): messaggi nelle loro code che non sono nella vera.
    Il giro del SUP li vede anche se il server di prova è vecchio o la copia automatica non è partita."""
    if os.environ.get("PLANCIA_DATI"):
        return  # sup.py stesso in prova: niente da cercare
    try:
        ps = subprocess.run(["ps", "-A", "-E", "-ww", "-o", "command="], capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return
    vere = {r["id"] for r in coda()}
    persi = []
    for riga in ps.splitlines():
        if "server.py" not in riga or "PLANCIA_DATI=" not in riga:
            continue
        m = re.search(r"PLANCIA_DATI=(.*?)(?= [A-Za-z_][A-Za-z0-9_]*=|$)", riga)
        cartella = m and m.group(1).strip()
        if not cartella or os.path.realpath(cartella) == os.path.realpath(QUI):
            continue
        for r in coda(os.path.join(cartella, "coda.jsonl")):
            if r.get("id") not in vere and not str(r.get("testo", "")).lower().startswith("prova"):
                persi.append((cartella, r))
    if persi:
        print("⚠ MESSAGGI NELLA REGIA DI PROVA (non sono nella coda vera: l'utente li ha scritti lì)")
        for cartella, r in persi:
            print(f"   {r.get('id')}  {str(r.get('sessione', '')):14} {str(r.get('ora', ''))[11:16]}  {r.get('testo')}   [{cartella}]")
        print()


def esci(msg, codice=1):
    print(msg, file=sys.stderr if codice else sys.stdout)
    sys.exit(codice)


def leggi_json(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except ValueError:
        esci(f"{os.path.basename(p)} rotto: correggerlo a mano prima di riscriverlo")


def scrivi_json(p, dati):  # scrittura atomica: l'app non legge mai un file a metà
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def coda(p=None):
    righe = []
    try:
        for l in open(p or CODA, encoding="utf-8"):
            try:
                righe.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return unisci(righe)  # una richiesta modificata = una voce sola, testo = l'ultima versione


def agenti_vivi():
    """{NOME: stato} delle sessioni vive tranne il SUP (stessa fonte dell'app: claude agents --json)."""
    try:
        out = subprocess.run(["claude", "agents", "--json"], capture_output=True, text=True, timeout=30).stdout
        vivi = {}
        for x in json.loads(out or "[]"):
            n = (x.get("name") or "").upper()
            if n and n not in ("SUPERAGENTE", "SUP") and x.get("status"):
                vivi[n] = "busy" if x.get("status") == "busy" or vivi.get(n) == "busy" else x.get("status")
        return vivi
    except Exception:  # noqa: BLE001
        return None


def con_ordine_aperto(ore=24):
    """Agenti a cui il SUP ha girato una richiesta (verde/giallo) nelle ultime `ore`, ancora senza risposta:
    devono riferire al SUP, quindi vanno avvisati della pausa."""
    limite = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - ore * 3600))
    nomi = set()
    for v in leggi_json(RICH, {}).values():
        if v.get("stato") in ("verde", "giallo") and (v.get("ora") or "") >= limite and v.get("a") \
                and not any(x.get("stato") == "risposta" for x in v.get("storia") or []):
            nomi.add(v["a"].upper())
    return nomi


def destinatari(gia=()):
    """Solo chi lavora (busy) o ha un ordine aperto verso il SUP, più `gia` (avvisati della pausa) se ancora vivi
   ."""
    vivi = agenti_vivi()
    if vivi is None:
        return None, "claude agents non risponde: controlla ListAgents"
    pause = pausa_sessioni.aggiorna(QUI, vivi, coda())  # chi è tornato a lavorare esce dalla pausa e torna fra i destinatari
    busy = {n for n, s in vivi.items() if s == "busy"}
    scelti = (busy | con_ordine_aperto() | set(gia)) & set(vivi) - set(pause)
    fermi = sorted(set(vivi) - scelti - set(pause))
    nota = f"non avvisati (fermi, niente da riferire): {', '.join(fermi) or 'nessuno'}"
    return sorted(scelti), nota + (f" · in pausa, saltati: {', '.join(sorted(set(pause) & set(vivi)))}" if set(pause) & set(vivi) else "")


def avviso(testo, nomi, nota):
    if nomi is None:
        print(f"⚠ {nota}")
    else:
        print(f"Da mandare con SendMessage a {len(nomi)} agenti: {', '.join(nomi) or '(nessuno)'}")
        print(nota)
    print(f"Testo: {testo}")


def togli_opzione(a, nome):
    """Toglie «--nome valore» da a (ovunque sia) e ne restituisce il valore, o None."""
    if nome in a:
        i = a.index(nome)
        if i + 1 >= len(a):
            esci(f"{nome} vuole un valore")
        v = a[i + 1]
        del a[i:i + 2]
        return v
    return None


def segna(r, rid, stato, **altro):
    """Stato corrente + storia (l'app mostra la fila inviata → letta → girata → risposta, con le ore)."""
    voce = r.get(rid, {})
    storia = voce.get("storia", [])
    storia.append({"stato": stato, "ora": ORA(), **{k: v for k, v in altro.items() if v}})
    voce.update(storia=storia[-12:], ora=ORA())
    if stato != "risposta":
        voce["stato"] = stato
    r[rid] = voce


def main(a):
    if not a or a[0] in ("-h", "--help", "aiuto"):
        esci(__doc__, 0)
    cmd = a[0]
    if cmd == "giro":
        cmd = "nuove"
    if cmd == "rispondi":
        dest = togli_opzione(a, "--a")
        grigio = "--grigio" in a
        a = [x for x in a if x != "--grigio"]
        if dest is not None and not re.match(r"^[A-Za-z0-9_-]{1,40}$", dest):
            esci("--a vuole il nome di una sessione")
        if len(a) < 3 or not " ".join(a[2:]).strip():
            esci('uso: sup.py rispondi <id> "testo" [--a SESSIONE] [--grigio]')
        q = next((x for x in coda() if x["id"] == a[1]), None)
        if not q:
            esci(f"id {a[1]} non è in coda.jsonl")
        filo = (q.get("sessione") or "SUP").upper()
        with open(RISP, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessione": filo, "testo": " ".join(a[2:]).strip(), "ora": ORA(), "id": a[1]},
                               ensure_ascii=False) + "\n")
        r = leggi_json(RICH, {})
        if r.get(a[1], {}).get("stato", "nuova") == "nuova":
            segna(r, a[1], "letta")
        if dest:
            segna(r, a[1], "verde", a=dest.upper())
            r[a[1]]["a"] = dest.upper()
            if pausa_sessioni.togli(QUI, dest, "il SUP le ha girato un ordine"):
                print(f"{dest.upper()} era in pausa: pausa tolta")
        segna(r, a[1], "risposta", a=filo)
        if grigio:
            segna(r, a[1], "grigio")
        scrivi_json(RICH, r)
        esci(f"{a[1]}: risposta nel filo {filo}" + (f", girata a {dest.upper()}" if dest else "") + (", consegnata" if grigio else ""), 0)
    if cmd == "nuove":
        avviso_prova()
        if os.path.exists(PAUSA) and "--anche-in-pausa" not in a:
            # giro del cron muto durante la pausa del SUP (passaggio): i messaggi dell'utente sono trattenuti, niente da
            # fare; un turno corto tiene la sessione «busy» il meno possibile e non ostacola riavvia.py
            sys.exit(0)  # niente output: il prompt del cron dice «se è vuoto, nessuna risposta»
        n = rilascia(QUI)  # pausa tolta senza «riprendi»: i trattenuti partono comunque
        if n:
            print(f"({n} messaggi trattenuti durante la pausa: ora in coda)")
        fatte = leggi_json(RICH, {})
        tutte = coda()
        nuove = [r for r in tutte if fatte.get(r["id"], {}).get("stato", "nuova") in ("nuova", "letta")]
        for r in nuove:
            gia = fatte.get(r["id"], {}).get("stato") == "letta"
            mod = "   (MODIFICATA dall'utente)" if da_vedere(r, fatte.get(r["id"], {})) and gia else ""
            print(f"{r['id']}  {r['sessione']:14} {r['ora'][11:16]}  {r['testo']}{'   (già letta, non ancora presa)' if gia and not mod else ''}{mod}")
            if not gia:
                segna(fatte, r["id"], "letta")
        # richieste già girate/prese che l'utente ha modificato dall'app: il SUP le rivede
        mod = [r for r in tutte if r not in nuove and da_vedere(r, fatte.get(r["id"], {}))]
        for r in mod:
            f = fatte.get(r["id"], {})
            dove = f"girata a {f['a']}" if f.get("a") else f.get("stato", "")
            print(f"MODIFICA {r['id']}  {r['sessione']:14} {str(r['modificata'])[11:16]}  ({dove}) ora dice: {r['testo']}")
            print(f"         prima diceva: {(r.get('prima') or [''])[-1]}")
        for r in nuove + mod:
            if r.get("modificata"):
                fatte.setdefault(r["id"], {})["mod_vista"] = r["modificata"]
        if nuove or mod:
            scrivi_json(RICH, fatte)
        scrivi_json(ASCOLTO, {"ora": ORA()})
        esci(f"({len(nuove)} nuove{f', {len(mod)} modificate' if mod else ''})  →  sup.py rispondi <id> \"testo\" [--a SESSIONE] [--grigio]  (un colpo solo)", 0)
    if cmd in STATI:
        dest = togli_opzione(a, "--a") if cmd == "prendi" else None
        if dest is not None and not re.match(r"^[A-Za-z0-9_-]{1,40}$", dest):
            esci("--a vuole il nome di una sessione")
        if len(a) < 2:
            esci(f"uso: sup.py {cmd} <id> [\"nota\"]" if cmd != "prendi" else 'uso: sup.py prendi <id> [--a SESSIONE] ["nota"]')
        ids = {r["id"] for r in coda()}
        if a[1] not in ids:
            esci(f"id {a[1]} non è in coda.jsonl")
        r = leggi_json(RICH, {})
        segna(r, a[1], STATI[cmd], a=dest.upper() if dest else None)
        r[a[1]]["nota"] = " ".join(a[2:]).strip()
        if dest:
            r[a[1]]["a"] = dest.upper()
            if pausa_sessioni.togli(QUI, dest, "il SUP le ha girato un ordine"):
                print(f"{dest.upper()} era in pausa: pausa tolta")
        scrivi_json(RICH, r)
        esci(f"{a[1]} → {STATI[cmd]}{' (girata a ' + dest.upper() + ')' if dest else ''}", 0)
    if cmd == "risposta":
        rid = togli_opzione(a, "--id")
        if rid is not None and rid not in {r["id"] for r in coda()}:
            esci(f"id {rid} non è in coda.jsonl")
        if len(a) < 3 or not re.match(r"^[A-Za-z0-9_-]{1,40}$", a[1]) or not " ".join(a[2:]).strip():
            esci('uso: sup.py risposta <SESSIONE|SUP> "testo"')
        with open(RISP, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessione": a[1].upper(), "testo": " ".join(a[2:]).strip(), "ora": ORA(),
                                **({"id": rid} if rid else {})}, ensure_ascii=False) + "\n")
        r = leggi_json(RICH, {})
        dest = a[1].upper()
        if rid:
            ids = [rid]
        else:
            # senza --id: si segnano le richieste ancora aperte
            # di quel filo nelle ultime 6 h (mandate alla sessione o girate a lei, prese o lette, senza risposta)
            limite = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 6 * 3600))
            ids = [q["id"] for q in coda()
                   if (q.get("sessione", "").upper() == dest or (r.get(q["id"], {}).get("a") or "").upper() == dest)
                   and r.get(q["id"], {}).get("stato") in ("letta", "verde", "giallo")
                   and not any(x.get("stato") == "risposta" for x in r.get(q["id"], {}).get("storia", []))
                   and str(q.get("ora", "")) >= limite]
        for i in ids:
            segna(r, i, "risposta", a=dest)
        if ids:
            scrivi_json(RICH, r)
        esci(f"risposta nel filo {dest}" + (f" (segnate risposta: {', '.join(ids)})" if ids else " (nessuna richiesta aperta da segnare)"), 0)
    if cmd == "sospeso":
        voci = leggi_json(SOSP, [])
        sub = a[1] if len(a) > 1 else "elenco"
        if sub == "elenco":
            ferme = pausa_sessioni.leggi(QUI)
            for i, v in enumerate(voci, 1):
                ses = (v.get("sessione") or "").upper()
                print(f"{i}. {('[' + v['sessione'] + (' in pausa' if ses in ferme else '') + '] ') if v.get('sessione') else ''}{v['testo']}  ({v['ora'][5:16]})")
            esci(f"({len(voci)} in sospeso)", 0)
        if sub == "aggiungi" and len(a) >= 3 and a[2].strip():
            voci.append({"testo": a[2].strip(), "sessione": a[3].upper() if len(a) > 3 else "", "ora": ORA()})
        elif sub in ("togli", "cambia") and len(a) >= 3 and a[2].isdigit() and 1 <= int(a[2]) <= len(voci):
            n = int(a[2]) - 1
            if sub == "togli":
                voci.pop(n)
            elif len(a) >= 4 and a[3].strip():
                voci[n].update(testo=a[3].strip(), ora=ORA())
            else:
                esci('uso: sup.py sospeso cambia <n> "testo"')
        else:
            esci('uso: sup.py sospeso [aggiungi "testo" [SESSIONE] | togli <n> | cambia <n> "testo"]  (n da 1 a %d)' % len(voci))
        # in cima le fisse, poi le voci con link (cose da aprire e decidere), poi le altre; ordine stabile
        voci.sort(key=lambda v: (not v.get("fissa"), not re.search(r"\]\(|https?://|(?:~|/Users/)\S[^\n]*?\.(?:png|jpe?g|gif|webp|svg|pdf|html?|md|txt|mp4|mov)\b", v["testo"])))
        scrivi_json(SOSP, voci)
        esci(f"in sospeso: {len(voci)} voci", 0)
    if cmd == "permesso":
        if len(a) < 2 or not " ".join(a[1:]).strip():
            esci('uso: sup.py permesso "cosa" | permesso via')
        if a[1] == "via":
            if os.path.exists(PERM):
                os.remove(PERM)
            esci("segnale permesso spento", 0)
        scrivi_json(PERM, {"cosa": " ".join(a[1:]).strip(), "ora": ORA()})
        esci("segnale permesso acceso", 0)
    if cmd == "sessione":
        sessione(a)
    if cmd == "pausa":
        motivo = " ".join(a[1:]).strip() or "passaggio"
        nomi, nota = destinatari()
        scrivi_json(PAUSA, {"motivo": motivo, "ora": ORA(), "avvisati": nomi or []})
        print(f"SUP in pausa ({motivo}): riga accesa nell'app; i messaggi dell'utente restano nell'app fino a «riprendi»")
        avviso(f"SUPERAGENTE: PAUSA MESSAGGI ({motivo}). NON mandarmi messaggi finché non ricevi «SUP RIPARTITO»; "
               "continua il tuo ordine e annota in agenda ciò che vorresti dirmi.", nomi, nota)
        sys.exit(0)
    if cmd == "riprendi":
        p = leggi_json(PAUSA, None)
        if os.path.exists(PAUSA):
            os.remove(PAUSA)
        n = rilascia(QUI)
        print("SUP ripartito: riga spenta" + (f" (pausa dalle {p['ora'][11:16]})" if p else " (non era in pausa)")
              + (f"; {n} messaggi dell'utente trattenuti ora in coda: li vedi con sup.py nuove" if n else ""))
        nomi, nota = destinatari((p or {}).get("avvisati", []))
        avviso("SUP RIPARTITO: fine della pausa. Mandami ora consegne, push pronti e richieste accumulate.", nomi, nota)
        sys.exit(0)
    esci(f"comando sconosciuto: {cmd}\n{__doc__}")


def sessione(a):
    """sup.py sessione [pausa NOME ["motivo"] | via NOME]"""
    sub = a[1] if len(a) > 1 else "elenco"
    if sub == "elenco":
        v = pausa_sessioni.leggi(QUI)
        for n, p in sorted(v.items()):
            print(f"{n:14} in pausa dalle {p['ora'][11:16]} ({p['ora'][5:10]}){'  · ' + p['motivo'] if p.get('motivo') else ''}")
        esci(f"({len(v)} in pausa)", 0)
    if sub not in ("pausa", "via") or len(a) < 3 or not re.match(r"^[A-Za-z0-9_-]{1,40}$", a[2]):
        esci('uso: sup.py sessione pausa NOME ["motivo"]  |  sup.py sessione via NOME')
    nome = a[2].upper()
    if nome in ("SUP", "SUPERAGENTE"):
        esci("il SUP non si mette in pausa con questo comando: sup.py pausa")
    if sub == "via":
        esci(f"{nome}: pausa tolta" if pausa_sessioni.togli(QUI, nome) else f"{nome} non era in pausa", 0)
    vivi = agenti_vivi() or {}
    if nome not in vivi:
        print(f"⚠ {nome} non risulta fra le sessioni vive: la pausa resta scritta e vale quando riapre col nome {nome}")
    p = pausa_sessioni.metti(QUI, nome, " ".join(a[3:]).strip(), busy=vivi.get(nome) == "busy")
    esci(f"{nome} in pausa dalle {p['ora'][11:16]}: in fondo nell'app, fuori da avvisi e destinatari; "
         "esce da sola se l'utente le scrive dalla Regia o torna a lavorare", 0)


if __name__ == "__main__":
    main(sys.argv[1:])
