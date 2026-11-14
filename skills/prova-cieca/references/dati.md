# Dati delle campagne (formato dei file)

Li scrive e li legge `scripts/campagne.py`; `scripts/campagna.py` gioca una campagna dai file che `prepara` produce.
Tutto è JSON leggibile, salvabile e recuperabile: niente sta solo in memoria.

## Dove stanno
```
<progetto>/campagne/                 dati del progetto (nella sua repo)
  memoria.json                       C2: domande in attesa per l'autore, motivi, esiti per profilo, obiezioni, profili consumati
  <sessione>/
    sessione.json                    domanda, consegna, schede usate, campagne, regole, controlli, mazzo, giri
    schede/<id>/v<N>.json            una scheda per cartella, una versione per file
    richieste/genera-*.json          richieste di generazione in coda (chi coordina le esegue)
    giri/<giro>/                     un giro preparato e giocato
      comandi.sh · giro-meta.json    preparati da `prepara` (comandi per campagna.py, controlli risolti, eventi estratti)
      _prep/<campagna>/              master.md · apertura.txt · copia.txt · vietate.txt · eventi.json
      <campagna>/campagna.json …     prodotti da campagna.py (partita, resoconto, controlli per turno)
      quadro-prompt.md · quadro.md   C1 · confronto-*.md (A2) · stabilita.json (A4)
<libreria>/                          globale, riusata fra progetti ($CAMPAGNE_LIB)
  manuale.json                       regole globali in più, parole vietate sempre, controlli globali
  profili/<nome>/v<N>.json           profili riusabili (scheda protagonista senza scena)
  ricette/<nome>/                    sessioni intere salvate come modello
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
- **Riservati** (previsti, non attivi finché l'autore non decide): `diario` (saghe), `cosa_sa_dell_esterno` (secondario).

## Sessione
```json
{"id": "s1", "stato": "bozza|preparata", "domanda": "…", "consegna": {"link": "…", "versione": "v1"},
 "esterno": "est", "scena": "sc", "secondari": ["moglie"],
 "campagne": [{"campagna": "c1", "scheda": "p-gino", "variante": "forno", "controlli": {"ripetizioni": {"valore": 2}}}],
 "regole": [], "fuori_storia": [], "si_puo_dire": [],
 "controlli": {"severita": {"valore": "alta", "bloccato": true}},
 "mazzo": [{"id": "commissioni", "testo": "…", "peso": 2, "dal_turno": 1}], "seme": 1,
 "confronto": {"tipo": "versioni", "consegne": [{"versione": "v1", "link": "…"}, {"versione": "v2", "link": "…"}]},
 "giri": [{"giro": "g1", "preparato": "…"}],
 "riservato": {"saga": null, "bivi": null, "taratura": null, "copilota": null}}
```
`riservato`: posti per funzioni non ancora decise (saghe, bivi, taratura col mondo reale, copilota). Restano `null`.

## Controlli: tre livelli
globale (`manuale.json`) → sessione → campagna. Il livello più basso vince, **salvo** un valore `bloccato` più in alto.
`campagne.py controlli SESS [--campagna C]` mostra il valore e il livello che vince. Elenco, default e dove agiscono:
`CONTROLLI` in `campagne.py` (programma · master · schede). I controlli che agiscono sulle schede (severità, canale,
momento, chi decide, dimestichezza) non diventano istruzioni: `verifica` controlla che le schede li dicano.

## Eventi del mondo (B2) e tempo (B3)
`prepara` estrae dal mazzo, **prima del giro**, quali eventi e in che turno (seme della sessione: ripetibile; le
ripetizioni A4 hanno lo stesso mazzo). Fermo = nessun evento; normale = uno; vivo = circa uno ogni due turni.
`campagna.py` dà l'evento al master solo nel turno previsto e lo segna nel turno (`eventi_dopo`). Il ritardo fra
azione e risposta (`--ritardo`) va messo in scena dal master.

## Memoria del progetto (C2)
`campagne.py memoria SESS GIRO`: i buchi diventano domande in attesa per l'autore; i motivi di invalidità si contano;
gli esiti si registrano per profilo; un profilo con lo stesso esito nelle ultime 3 campagne valide è **consumato**
(rigiocarlo non insegna niente). Le obiezioni ricorrenti arrivano dal `quadro.md` (C1).
