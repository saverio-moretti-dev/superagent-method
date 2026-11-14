# Dati di argomenti, campagne e storie (formato dei file)

Li scrive e li legge `scripts/campagne.py`; `scripts/storia.py` gioca una storia dai file che `prepara` produce.
Tutto è JSON leggibile, salvabile e recuperabile: niente sta solo in memoria.
Gerarchia: **argomento** (una cartella/repo) > **campagna** (N storie) > **storia** (un tester). Fino al 14/11 la campagna
si chiamava «sessione» (`sessione.json`) e la storia «campagna» (`campagna.py`, `campagna.json`): per un giro `campagna.py`
inoltra a `storia.py`, accanto a `storia.json` c'è il collegamento `campagna.json` e `giro.json` ha anche la chiave `campagne`.

## Dove stanno
```
<argomento>/                         una cartella per argomento (repo locale: `argomento nuovo` fa git init, niente remoto)
  argomento.json · LEGGIMI.md        id, titolo, creato
  memoria.json                       C2: domande in attesa, motivi, esiti per profilo, obiezioni, profili consumati (tutte le campagne)
  analisi-prompt.md · analisi.md     `analisi`: tutte le campagne a confronto, ognuna nel suo contesto
 campagne/<campagna>/
    campagna.json                    domanda, consegna, schede usate, storie, regole, controlli, mazzo, giri
    schede/<id>/v<N>.json            una scheda per cartella, una versione per file
    richieste/genera-*.json          richieste di generazione in coda (chi coordina le esegue)
    giri/<giro>/                     un giro preparato e giocato
      comandi.sh · giro-meta.json    preparati da `prepara` (comandi per storia.py, controlli risolti, eventi estratti)
      _prep/<storia>/                master.md · apertura.txt · copia.txt · vietate.txt · eventi.json
      <storia>/storia.json …         prodotti da storia.py (partita, resoconto, controlli per turno)
      quadro-prompt.md · quadro.md   C1 · confronto-*.md (A2) · stabilita.json (A4)
<libreria>/                          globale, riusata fra argomenti ($CAMPAGNE_LIB)
  manuale.json                       regole globali in più, parole vietate sempre, controlli globali
  profili/<nome>/v<N>.json           profili riusabili (scheda protagonista senza scena)
  ricette/<nome>/                    campagne intere salvate come modello
```

## Scheda
```json
{"id": "p-gino", "tipo": "protagonista|esterno|scena|secondario", "versione": 2, "stato": "bozza|approvata",
 "giocata_in": ["g1"], "origine": {"profilo": "fornaio-diffidente", "versione": 3},
 "campi": {"tratti": {"valore": "…", "fonte": "AUTORE|FATTO|COORDINATORE|DEDOTTO|GENERATO", "data": "…", "bloccato": true}},
 "personalizzati": ["campo aggiunto dall'utente"]}
```
- Campi e obbligatori: `STRUTTURE` in `campagne.py` (gli stessi di `schede.md`).
- **Approvare** richiede: obbligatori pieni, nessuna fonte `DEDOTTO`/`GENERATO` non confermata, nessun esito suggerito o
  istruzione di durezza nel protagonista, campi riservati vuoti.
- **Versioni**: una scheda usata in un giro non cambia più; la modifica crea `v<N+1>` in bozza. `scheda versioni` le affianca.
- **Bloccato**: «genera» non tocca il campo. **Personalizzati**: campi fuori struttura, passano al master come gli altri.
- **Riservati**: `diario` (saghe, opzione da scegliere per campagna). «Cosa sa l'amico» è un campo della scena (`cosa_sa_l_amico`).

## Campagna
```json
{"id": "s1", "stato": "bozza|preparata", "domanda": "…", "consegna": {"link": "…", "versione": "v1"},
 "esterno": "est", "scena": "sc", "secondari": ["moglie"],
 "storie": [{"storia": "c1", "scheda": "p-gino", "variante": "forno", "controlli": {"ripetizioni": {"valore": 2}}}],
 "regole": [], "fuori_storia": [], "si_puo_dire": [],
 "controlli": {"severita": {"valore": "alta", "bloccato": true}},
 "mazzo": [{"id": "commissioni", "testo": "…", "peso": 2, "dal_turno": 1}], "seme": 1,
 "confronto": {"tipo": "versioni", "consegne": [{"versione": "v1", "link": "…"}, {"versione": "v2", "link": "…"}]},
 "giri": [{"giro": "g1", "preparato": "…"}],
 "riservato": {"saga": null, "bivi": null, "taratura": null, "copilota": null}}
```
`riservato`: posti per funzioni non ancora decise (saghe, bivi, taratura col mondo reale, copilota). Restano `null`.

## Controlli: tre livelli
globale (`manuale.json`) → campagna → storia. Il livello più basso vince, **salvo** un valore `bloccato` più in alto.
`campagne.py controlli CAMP [--storia C]` mostra il valore e il livello che vince. Elenco, default e dove agiscono:
`CONTROLLI` in `campagne.py` (programma · master · schede). I controlli che agiscono sulle schede (severità, canale,
momento, chi decide, dimestichezza) non diventano istruzioni: `verifica` controlla che le schede li dicano.

## Eventi del mondo (B2) e tempo (B3)
`prepara` estrae dal mazzo, **prima del giro**, quali eventi e in che turno (seme della campagna: ripetibile; le
ripetizioni A4 hanno lo stesso mazzo). Fermo = nessun evento; normale = uno; vivo = circa uno ogni due turni.
`storia.py` dà l'evento al master solo nel turno previsto e lo segna nel turno (`eventi_dopo`). Il ritardo fra
azione e risposta (`--ritardo`) va messo in scena dal master.

## Memoria dell'argomento (C2)
`campagne.py memoria CAMP GIRO`: i buchi diventano domande in attesa per l'autore; i motivi di invalidità si contano;
gli esiti si registrano per profilo; un profilo con lo stesso esito nelle ultime 3 storie valide è **consumato**
(rigiocarlo non insegna niente). Le obiezioni ricorrenti arrivano dal `quadro.md` (C1).
