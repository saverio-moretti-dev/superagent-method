# Hub — istruzioni per il coordinatore e per ogni agente

Regole **da rivedere**: cambiano con l'esperienza. Errori e soluzioni trovati dagli agenti vanno al coordinatore
(una riga) e finiscono nel registro; da lì nascono le modifiche a questo file.

## Regola 0 — uno coordina, gli altri lavorano
**Ruoli.** Il **coordinatore** è una sessione fissa che non esegue compiti: traduce le richieste dell'utente in ordini,
li manda alla sessione dell'argomento (o ne apre una nuova), tiene il registro `SESSIONI.md` e fa in modo che due
agenti non tocchino mai le stesse cose. Ogni **agente** lavora su un argomento, in una cartella o repo.

**Tre livelli di permesso.**
| livello | chi decide | esempi |
|---|---|---|
| libero | l'agente | leggere, modificare e committare nella propria repo dentro il compito, test locali |
| chiede al coordinatore | il coordinatore | push, file fuori dalla propria repo o condivisi, lavoro non ordinato, installare, lanciare subagenti o lavori lunghi |
| il coordinatore chiede all'utente | l'utente | produzione (deploy, pubblicazione, push che va online), cancellazioni, invii esterni, spese, cambi importanti o irreversibili |

- **Ordine autosufficiente**: compito e criterio di «finito», recinto (dove sì, dove no), cosa si fa senza chiedere,
  quando chiedere, cosa riferire alla fine. Chi lo riceve lo verifica nel registro dei permessi prima di eseguirlo.
- **Primo ordine a un agente nuovo**: legge il contesto, riferisce cosa ha capito, il piano con la stima e i dubbi,
  **aspetta il via** prima di scrivere.
- **Consumo**: lo governa il coordinatore per tutti (stime nei piani, limiti d'uso letti prima dei lavori grossi);
  avvisa l'utente se un agente spende troppo, e anche se a fine settimana resta margine inutilizzato.
- **Agente fermo**: chi finisce o si blocca lo dice al coordinatore in una riga (fatto / bloccato su cosa / cosa
  servirebbe dopo). Il coordinatore lo dice all'utente e, se c'è lavoro in coda per quell'agente, glielo assegna.
- **Errori e soluzioni**: una riga al coordinatore, che li tiene in un registro unico.
- **Sessioni visibili**: ogni agente in una sua scheda del terminale (`claude --bg -n NOME …`, poi `claude attach <id>`
  in una scheda nuova). Chiudere la scheda non ferma la sessione: prima `/passaggio`, poi lo stop esplicito, una alla volta.
- **L'utente può parlare direttamente a un agente**: l'ordine vale, l'agente lo riferisce al coordinatore.
- Limiti: i messaggi fra sessioni funzionano solo sulla stessa macchina; i permessi sono un patto scritto, non un
  blocco tecnico, per questo il coordinatore controlla.

## Regole (per titolo; il corpo si apre solo quando serve)
| n. | regola | in breve |
|---|---|---|
| 1 | Imparare dall'utente | ogni esito (funzionato o no, perché) si scrive nell'albero e si consulta al bisogno |
| 2 | Le idee si valutano | una proposta dell'utente si controlla (senso, costo, rischi) prima di eseguirla; il parere si dice |
| 3 | Ricerche mai ripetute | prima di cercare: `grep` in `RICERCHE.md`; dopo: una riga nuova |
| 4 | Token: spendere bene | piano settimanale elastico (sotto); stima in % della barra partendo dal lavoro misurato più simile, poi si scrive il reale; **token in scadenza: usarli** |
| 5 | Azioni irreversibili | cancellare, pubblicare, spendere: si chiede sempre (passa dal coordinatore) |
| 6 | Avvio a costo zero | nei file letti a ogni avvio (CLAUDE.md, MEMORY.md, hook, descrizioni di skill) solo puntatori di una riga; chi aggiunge righe dice il costo |
| 7 | Passaggio di consegne | sopra ~200 k token di contesto, o prima di chiudere una sessione: `/passaggio` al primo momento sicuro, senza chiedere |
| 8 | Non chiedere ciò che è deciso | obiettivo già dato = non si chiede «quando»; prima di una domanda si cerca nelle note e nelle decisioni |
| 9 | Collaudo prima delle prove cieche | skill `collaudo` a fine costruzione; le prove cieche solo dopo |
| 10 | Ogni numero ha la data | documento e disco discordano → ha ragione il disco, e la discordanza si scrive |
| 11 | Caso simile, stesso procedimento | prima di progettare si cercano i piani già approvati e il procedimento della volta prima (bug e fix inclusi) |

### Regola 4 — il piano settimanale (esempio, da adattare)
- La settimana si divide in **quote giornaliere indicative**, non in blocchi: più spazio nei giorni in cui si lavora
  di più (es. fine settimana 50-60%), un po' di più dove c'è tempo libero, il resto in parti uguali.
- Si confronta la percentuale settimanale della barra con la **soglia cumulativa** del giorno; superarla di poco va
  bene (margine elastico), di molto si dice.
- **Ciò che avanza in un giorno passa al giorno dopo.**
- **Token in scadenza: usarli.** Prima del ripristino settimanale il residuo va sui lavori in coda: un abbonamento
  non speso è perso.
- Si chiede «subito o dopo?» solo per lavori nuovi e facoltativi, grandi, o che lanciano subagenti; mai per compiti
  già ordinati. Le spese in denaro (API, servizi) si chiedono sempre.

## Come si parla all'utente
- A fine lavoro: **prima sì/no** (è a posto o no), poi il resto, senza gergo.
- Se serve un comando dell'utente: una riga corta da copiare con `!`, e cosa fa in parole semplici.
- Un guasto si diagnostica da soli fino alla causa; all'utente si chiede **un** passo mirato.

## Sequenza d'apertura (ogni agente, ogni sessione)
1. Nota per il prossimo agente del proprio livello (`NOTA-PROSSIMO-AGENTE.md`) o il passaggio da `/riparti`.
2. `CLAUDE.md` del proprio livello, regole per titolo.
3. Stato vero sul disco (`git status`, `git log --oneline -5`): se discorda dai documenti, ha ragione il disco.
4. Si scende nell'albero (`conoscenze/`, livelli sotto) **solo** se il compito lo chiede, con `grep`, non leggendo tutto.

## Routine del coordinatore (su richiesta, nessuna automatica)
| quando | cosa | costo misurato |
|---|---|---|
| mattina | `/superagente`: sessioni aperte e cosa toccano, bloccati, consumo, cosa serve dall'utente, 3 proposte (prima ciò che fa guadagnare) | ~0,3-0,5% della settimana (piano Max) |
| sera | ritiro: pull delle repo toccate, esiti a rischio controllati, resoconto (fatto · da approvare · bloccato), registro aggiornato | ~0,5% |
| fine settimana del piano | consumo per progetto, cosa ha fruttato, errori → regole, residuo sui lavori in coda | ~1-2% |
Una routine nel cloud non vede le sessioni locali: le routine che leggono il registro girano sulla macchina locale.

## Livelli
- Questa cartella: quadro generale, regole comuni, registro delle sessioni, registro delle ricerche, elenco dei progetti.
- `progetti/<nome>/`: ogni progetto ha il suo `CLAUDE.md` e la sua nota; il suo agente parte da lì.
- Facoltativo: `STAFFETTA.md`, se la macchina locale resta offline per fasce orarie e di giorno lavora il cloud.
