---
description: Scrive la nota di passaggio per il prossimo agente (contesto minimo e completo), poi si fa /clear e /riparti
argument-hint: "[compito da passare — vuoto = compito attuale]"
---
Prepara il passaggio di consegne. Dopo, l'utente farà `/clear` e il prossimo agente lancerà `/riparti`.

**Quando, senza aspettare che lo chieda l'utente**: sopra ~200 k token di contesto, al primo momento sicuro (lavoro
salvato e committato, nessun agente a metà di una scrittura); e sempre prima di chiudere una sessione.

**Compito da passare**: $ARGUMENTS
(se vuoto: il compito su cui stai lavorando adesso)

**Dove**: `~/.claude/passaggi/<cartella>.md`, dove `<cartella>` = percorso della cartella di lavoro attuale con `/` e spazi
sostituiti da `-` (es. `-Users-me-projects-shop.md`). Se il file esiste già, prima spostalo in
`<cartella>.prec.md` (sovrascrivendo il `.prec` precedente). Crea la cartella se manca.
Due sessioni nella stessa cartella condividono il nome della nota: **una sola alla volta** fa `/passaggio`.

**Obiettivo della nota**: il prossimo agente deve lavorare bene come te **senza perdere niente** di ciò che l'utente ha
detto, deciso o corretto. **La completezza vince sulla brevità** (utente, 26/10: «piuttosto con più token utilizzati, ma è
meglio che perdere informazioni»). Nessun tetto fisso: tipicamente 2.000-5.000 token.

**Prima di scrivere — giro di raccolta obbligatorio (è il punto in cui si perdeva informazione):**
1. Ripercorri **ogni messaggio dell'utente** della sessione, dal primo all'ultimo. Per ognuno: cosa ha chiesto, deciso,
   corretto, risposto, rimproverato. Ognuno deve finire in una riga della nota o in un file su disco citato dalla nota.
2. Ciò che vive **solo nella conversazione** (risposte dell'utente, descrizioni a parole sue, numeri detti a voce) va
   **prima salvato su disco nella repo** (testo integrale, non riassunto) e committato; nella nota si mette il puntatore.
3. Le correzioni al **comportamento** dell'agente (es. «non chiedere cose note», «non chiedere se farlo adesso») vanno anche
   in memoria (`~/.claude/projects/.../memory/`) se valgono oltre il compito.

Regole di scrittura:
- **Puntatori per i file, testo integrale per le parole dell'utente**: `percorso:riga` per ciò che sta già su disco; le
  frasi dell'utente che vincolano il lavoro si citano **testuali**, non parafrasate.
- Distingui **verificato** (misurato, testato, con fonte) da **supposto**. Niente di supposto scritto come fatto.
- **Già risposto dall'utente**: ogni domanda già fatta e la sua risposta. Il prossimo agente non la rifà.
- **Errori dell'agente in questa sessione** e come l'utente li ha corretti: sono la cosa che più spesso si ripete.
- Elenca esplicitamente ciò che è **vago o da approfondire**.
- Nessuna cronologia narrativa, nessun saluto.

**Schema fisso** (sezioni vuote: ometti):
```
# PASSAGGIO — <data ora> — <repo/cartella>
## Compito
<1-3 righe: cosa va fatto e il criterio di "finito">
## Contesto globale (da leggere, in ordine)
- <file>: <perché serve, quale sezione>   ← solo quelli che decidono; max 5
## Stato
- Fatto e verificato: …
- Fatto non verificato: …
- Non committato / non pushato: …
## Prossimo passo esatto
<il primo comando o la prima modifica da fare>
## Decisioni (non rimettere in discussione)
- <decisione> — perché
## Già provato / trappole
- …
## Ricerche già fatte
- <argomento> → <percorso>   (non rifarle)
## Da approfondire prima di partire
- <punto vago> — dove guardare
## Già chiesto e già risposto (NON richiedere)
- <domanda> → <risposta dell'utente, testuale o puntatore al file>
## Errori dell'agente e correzioni dell'utente
- <cosa ho sbagliato> → «<parole dell'utente>» → <come si fa ora>
## Modo di lavorare voluto dall'utente in questo compito
- <es. procedere senza chiedere conferme; cosa va chiesto e cosa no>
## Vincoli dell'utente (testuali)
- «<citazione>»
```

Poi:
0. **Agenda prima della nota**: se hai `agende/<NOME>.md` nella hub, aggiornala (tappe, prossimi passi, decisioni, bug e soluzioni, una riga di cronologia), commit e push del solo file. La nota la cita come primo file del contesto.
1. Se il lavoro ha cambiato lo stato del progetto e la repo ha una sua nota per il prossimo agente / staffetta
   (vedi il suo `CLAUDE.md`), aggiorna anche quella in breve, come da regole della repo. Commit + push se è una repo git.
2. Se c'è un coordinatore (regola 0 della hub): mandagli una riga (fatto / bloccato su cosa / cosa servirebbe dopo,
   più il percorso della nota), così aggiorna il registro delle sessioni.
3. **Controllo finale**: rileggi la lista dei messaggi dell'utente del giro di raccolta e spunta che ognuno sia coperto.
   Se uno manca, aggiungilo.
4. Rispondi all'utente con **una riga**: percorso della nota, token stimati della nota, e «ora `/clear` e poi `/riparti`».
