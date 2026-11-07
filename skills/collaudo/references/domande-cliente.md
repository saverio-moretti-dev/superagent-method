# Scheda delle domande del cliente finale (gradino 0)

Si scrive **prima di costruire**, si verifica al gradino 2, diventa il COMPITO dei tester al gradino 4.
Una scheda per ruolo. Per ogni domanda, alla verifica: `indirizzo · frase copiata` oppure `MANCA`.

## 1. Modello
```
Ruolo: <chi è davvero, cosa deve decidere, su che dispositivo, in che lingua, quanta fretta>
Decisione che deve prendere: <prenotare / chiamare / comprare / assumere / usare l'app ogni giorno>
Domande (10-20), in ordine di peso:
1. ...                                    → <indirizzo · frase> | MANCA
Cosa lo fa smettere di fidarsi: ...
Cosa non può sapere da solo e il sito deve dirgli: ...
```
Fonti delle domande: le prove passate dello stesso tipo (cerca nei vecchi ESITO: «da decidere», «obiezioni»), il piano
del tipo, e i ruoli già usati nei prompt dei tester (il loro COMPITO è una lista di domande pronta).

## 2. Domande che sono tornate in più giri (partire da qui)
Dalle prove dell'autore (siti di strutture ricettive e CV, ottobre-novembre 2026). Il numero è quanti tester l'hanno sollevata.

**Chi prenota un soggiorno (casa, agriturismo, B&B, struttura)**
- Quanto pago in tutto, voce per voce (affitto, pulizie, biancheria, tassa, cauzione, extra), e quando pago cosa? (3/6)
- Caparra: percentuale **di cosa** e quanti euro? (3/6)
- Annullamento: prima della soglia, dopo, malattia, cambio date, assicurazione. (5/6)
- **A chi mando i soldi**: nome del titolare, contratto scritto, conto intestato a lui, codice della struttura. (5/6)
- Cosa succede dopo la richiesta: chi risponde, entro quando, conferma scritta. (3/3, due giri)
- Disponibilità vera per le **mie** date, e cosa mi dice se non c'è.
- Letti per persona (letti ≥ ospiti), bagni, scale, accessibilità, culla.
- Bambini: piscina (profondità, recinzione), fino a che età pagano meno, menu.
- Diete e allergie: cosa fate davvero (non «ditecelo»).
- Arrivare: aeroporti con tempi, senza auto (treni, passaggio andata **e ritorno**), parcheggio.
- In che lingue risponde chi risponde.
- Aria condizionata, wifi, cucina e dotazione, pronto soccorso più vicino.
- Pasti: quali sere, cosa è incluso, prezzo bambini coerente tra pagina e modulo.

**Titolare che valuta di comprare il sito/servizio**
- Quanto costa, una tantum e dopo; di chi è il dominio. (ogni giro)
- Chi aggiorna, quanto ci metto io dal telefono. (3/3)
- Come arriva la gente (Google, vecchi ospiti) rispetto ai portali. (3/3)
- Un sito vero da vedere / qualcuno da chiamare. (ogni giro)
- Si collega al calendario che uso già (Booking, Airbnb, agenzia)? — solo se verificato.

**Selezionatore / titolare che legge un CV o portfolio**
- I numeri sono gli stessi ovunque (CV, portfolio, README, sito)? (CV 25/10, 28/10)
- Date coerenti («dal 2025» ovunque). (3/4)
- Cosa posso verificare (codice pubblico, link che funzionano, referenze).
- Ci sono dati riservati dell'azienda in vista? (2/3)
- Parole che capisco senza essere tecnico. (3-4/4)

**Utente di un'app**
- Cosa faccio al primo avvio, senza istruzioni? Cosa vedo con zero dati?
- Cosa succede se sbaglio, se manca la rete, se torno indietro?
- I miei dati dove finiscono, posso cancellarli?

## 3. Residui quando si riusa un tipo/modello
Per ogni pagina, campo, testo e valore predefinito ereditato: **vale per questo tipo?** Esempi veri (casa nata dal B&B,
5-6/11): pannello del B&B (menu, camere, notte per notte), «Cena: no» nel riepilogo, «camere libere» invece di
«settimane», messaggio «non libera» invece di «massimo 12 persone», partenza proposta +2 notti invece del minimo del mese.
Se un pezzo del piano è «non fatto», **non si manda in prova cieca**: lo si dice all'utente e lo si esclude dal giro.
