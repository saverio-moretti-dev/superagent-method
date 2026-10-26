# Hub — istruzioni per il superagente e per ogni agente

## Regole (per titolo; il corpo si apre solo quando serve)
| n. | regola | in breve |
|---|---|---|
| 1 | Imparare dall'utente | ogni esito (funzionato o no, perché) si scrive nell'albero e si consulta al bisogno |
| 2 | Le idee si valutano | una proposta dell'utente si controlla (senso, costo, rischi) prima di eseguirla |
| 3 | Ricerche mai ripetute | prima di cercare: `grep` in `RICERCHE.md`; dopo: una riga nuova |
| 4 | Token razionati | compito dispendioso → stima in % di sessione e settimana prima di partire |
| 5 | Azioni irreversibili | cancellare, pubblicare, spendere: si chiede sempre |

## Sequenza d'apertura (ogni agente, ogni sessione)
1. Nota per il prossimo agente del proprio livello (`NOTA-PROSSIMO-AGENTE.md`).
2. `CLAUDE.md` del proprio livello, regole per titolo.
3. Stato vero sul disco (`git status`, `git log --oneline -5`): se discorda dai documenti, ha ragione il disco.
4. Si scende nell'albero (`conoscenze/`, livelli sotto) **solo** se il compito lo chiede, con `grep`, non leggendo tutto.

## Livelli
- Questa cartella: quadro generale, regole comuni, registro delle ricerche, elenco dei progetti.
- `progetti/<nome>/`: ogni progetto ha il suo `CLAUDE.md` e la sua nota; il suo agente parte da lì.
