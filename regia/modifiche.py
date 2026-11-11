"""Richieste modificate dopo l'invio.

In coda.jsonl la modifica è una riga in più con lo stesso id: {"id", "sessione", "modifica": true, "testo", "ora"}.
Sta nella coda (e non in un file a parte) perché il Monitor del SUP guarda coda.jsonl: una modifica lo sveglia
come un messaggio nuovo. unisci() fonde le righe: testo = l'ultima versione, "prima" = le versioni precedenti
(la più vecchia per prima), "modificata" = ora dell'ultima modifica. Chi legge la coda passa sempre da qui.
"""


def unisci(righe):
    per, out = {}, []
    for r in righe:
        rid = r.get("id")
        if r.get("modifica"):
            b = per.get(rid)
            if b is not None:  # modifica senza la richiesta: ignorata
                b["prima"] = b.get("prima", []) + [b.get("testo", "")]
                b["testo"], b["modificata"] = r.get("testo", ""), r.get("ora")
            continue
        if rid in per:
            continue  # stessa richiesta scritta due volte: vale la prima
        per[rid] = dict(r)
        out.append(per[rid])
    return out


def da_vedere(q, s):
    """La modifica più recente non l'ha ancora vista il SUP (s = voce di richieste.json)."""
    return bool(q.get("modificata")) and (s.get("mod_vista") or "") < q["modificata"]


def ha_risposta(s):
    return s.get("stato") == "grigio" or any(x.get("stato") == "risposta" for x in s.get("storia") or [])
