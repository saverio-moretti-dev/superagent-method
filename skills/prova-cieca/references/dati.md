# Dati di argomenti, campagne e storie (formato dei file)

Li scrive e li legge `scripts/campagne.py`; `scripts/storia.py` gioca una storia dai file che `prepara` produce.
Tutto è JSON leggibile, salvabile e recuperabile: niente sta solo in memoria.
Gerarchia: **argomento** (una cartella/repo) > **campagna** (N storie) > **storia** (un tester). Fino al 14/11 la campagna
si chiamava «sessione» (`sessione.json`) e la storia «campagna» (`campagna.py`, `campagna.json`): per un giro `campagna.py`
inoltra a `storia.py`, accanto a `storia.json` c'è il collegamento `campagna.json` e `giro.json` ha anche la chiave `campagne`.

## Dove stanno
```
<argomento>/                         una cartella per argomento (repo locale: `argomento nuovo` fa git init, niente remoto)
  argomento.json · LEGGIMI.md        id, titolo, creato, extra dell'argomento (`taratura`)
  esiti-veri.json                    C3 (solo se `taratura` è acceso): esiti di persone vere, anonimi, MAI fuori da questa repo
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
 "extra": {"saga": false, "bivi": false, "copilota": false, "allenamento": false}}
```
`extra`: funzioni selezionabili della campagna, spente finché non si accendono (`campagne.py extra CAMP NOME on`).
Le campagne vecchie con `riservato` si leggono come tutte spente.

## Extra selezionabili
Mai attivi da soli: si accendono per argomento o per campagna, e cosa non è acceso non cambia niente nei giri.
| extra | livello | cosa fa |
|---|---|---|
| `taratura` (C3) | argomento | esiti di persone vere accanto a quelli delle storie (sotto) |
| `saga` (A1) | campagna | lo stesso protagonista torna in una storia nuova con il suo diario |
| `bivi` (A3) | campagna | si rigioca una storia da un turno N con un'altra risposta del personaggio esterno |
| `copilota` (D1) | campagna | l'autore approva o corregge le risposte del personaggio esterno |
| `allenamento` (D2) | campagna | ruoli invertiti: il master fa il protagonista, l'autore risponde |

## Saghe (A1, extra `saga`)
Lo stesso protagonista torna mesi dopo in una storia nuova (stessa campagna o un'altra dello stesso argomento):
```
campagne.py extra CAMP saga on
campagne.py protagonista CAMP ep2 p-gino --segue g1/ep1          # o --segue c1/g1/ep1 da un'altra campagna dell'argomento
campagne.py diario CAMP p-gino --da g1/ep1                       # richiesta (non spende): il diario dalla partita
campagne.py scheda imposta CAMP p-gino diario "…" --fonte GENERATO   # poi l'autore lo corregge e lo conferma
campagne.py scheda imposta CAMP p-gino adesso "…"                # la sua vita è andata avanti
```
`verifica` blocca se: saga spenta, episodio non giocato, episodio di un'altra scheda, scheda alla stessa versione
dell'episodio, diario vuoto o con parole della prova (test, turno, giro, esiti…). Il diario entra solo nelle storie
con `segue`: nel contesto del master e nell'apertura del tester («cosa ti ricordi di quando l'hai già incontrato»).
I profili non portano il diario: appartiene a una sola linea di episodi.

## Bivi (A3, extra `bivi`)
«E se avessi risposto diversamente?»: si rigioca una storia dal turno N cambiando solo la risposta del personaggio esterno.
```
campagne.py extra CAMP bivi on
campagne.py bivio CAMP GIRO ep1 --dal-turno 3 --risposta "Le posso proporre tre rate."   # o --risposta @file.txt
bash GIRO/comandi-ep1-b3-1.sh          # lo lancia chi coordina (spende come una storia, dal turno N in poi)
campagne.py confronta GIRO ep1 ep1-b3-1
```
`storia.py --bivio ORIGINE/storia.json --dal-turno N --risposta FILE`: i turni 1..N-1 si copiano con `"ereditato": true`,
tester e master partono in sessioni nuove con quei turni come ricordo; la risposta passa da check_fuga (non dal
controllo del turno: cambiare le condizioni è lo scopo). `storia.json` ha `"bivio": {da, origine, dal_turno, risposta,
esito_origine}`. I bivi non entrano negli esiti per profilo della memoria (non sono storie previste dal giro).

## Esiti veri (C3, extra `taratura`)
Quando una persona vera risponde alla consegna, l'esito si registra nell'argomento e si confronta con le storie:
```
campagne.py esito-vero ARG --esito LASCIA --chi "titolare di forno, 60 anni, poco digitale" --come titolare-diffidente \
  --canale passaparola --quando 2026-11 --motivo "prezzo troppo alto per lui"
```
```json
{"esiti": [{"n": 1, "quando": "2026-11", "chi": "titolare di forno, 60 anni, poco digitale", "come": "titolare-diffidente",
  "canale": "passaparola", "esito": "LASCIA", "motivo": "prezzo troppo alto per lui", "versione": "", "campagna": "",
  "registrato": "…"}]}
```
- **Anonimo**: `chi` è un tipo di persona, mai un nome; `quando` solo il mese. Il comando rifiuta email, indirizzi web,
  profili social, numeri lunghi e possibili nomi e cognomi (`--controllato` solo per un falso allarme verificato).
- **Solo locale**: rifiuta un argomento dentro la skill e una repo dell'argomento con un remoto (`--anche-remoto` solo
  se l'autore ha scelto di pubblicarla). Nella skill e negli esempi restano solo comando e formato, con dati inventati.
- `--come` collega l'esito a una scheda o a un profilo: `esiti-veri ARG` e `analisi ARG` mettono gli esiti veri
  accanto a quelli delle storie valide dello stesso profilo (sezione TARATURA). Gli esiti veri valgono più delle storie.

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
