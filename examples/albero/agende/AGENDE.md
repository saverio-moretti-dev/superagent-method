# AGENDE — componente fondamentale del metodo (utente, 2026-11-08)

Richiesta testuale: the user request of 2026-11-08:
> «il superagente ha un'agenda con ogni agente che aggiornano entrambi e che serve ad entrambi come guida, cronologia, storico, regole, piani eccetra per proseguire i lavori a lungo termine senza perdere contesto, decisioni, regole, bug e soluzioni» · «applicala da subito, scrivi le agende INSIEME agli agenti, con le conoscenze che avete entrambi»

## Cos'è
- **Un file per agente**: `agende/<NOME>.md`, modello in `agende/_MODELLO.md`.
- È il **patto vivo** fra il SUPERAGENTE e quell'agente. Contiene:
  - le richieste dell'utente (testuali o col link);
  - il piano e le tappe con il loro stato;
  - i prossimi passi, con chi li fa;
  - le decisioni, le regole proprie, i permessi;
  - i bug con le soluzioni;
  - la cronologia e le domande aperte.
- Differenza con gli altri documenti:
  - la **nota di passaggio** (`/passaggio`) serve a una sessione sola e si consuma;
  - il **CLAUDE.md** è la regola della repo;
  - l'**agenda** vive per mesi e la scrivono **in due**.

## Regole
1. **La scrivono in due.** Il SUPERAGENTE mette ciò che sa: le parole dell'utente, le decisioni, i permessi, le priorità. L'agente mette ciò che sa: lo stato vero, le misure, i bug, le soluzioni, i rischi. Nessuno dei due la riscrive da solo: chi corregge l'altro lo segna in cronologia.
2. **Si legge per prima**: a ogni `/superagente`, `/riparti` e primo ordine. Costa poco, perché la parte alta è corta: cosa si fa, prossimi passi e cancelli stanno in cima, la cronologia in fondo.
3. **Si aggiorna a ogni voce chiusa**, con una riga in cronologia, e a ogni decisione, bug o soluzione. Alla fine della sessione si fa prima dell'aggiornamento della nota di passaggio.
4. **Scrittura** (se `git pull --rebase` dà «rebase su più branch»: `git fetch && git rebase --autostash origin/main`):
   - ogni agente ha il **permesso fisso** di modificare solo la propria agenda nella hub: `git fetch`, `git pull --rebase` sul solo file, poi commit e push. Mai `--force`, mai altri file della hub;
   - in caso di conflitto si tiene il testo di tutti e due e lo si segnala al SUPERAGENTE.
5. **Peso**:
   - parte alta (§ 1-4) al massimo ~60 righe;
   - cronologia con le ultime 30 voci; le più vecchie, intere, in `agende/storia/<NOME>-AAAA-MM.md`;
   - niente si cancella, si sposta soltanto.
6. **Le parole dell'utente** vanno testuali (o col link al file testuale), con la data. Un riassunto non sostituisce mai il testo.
7. **Fra due agenti** (es. METODO e PLUGIN) che lavorano sulle stesse cose: ognuno ha la sua agenda con il SUPERAGENTE, ma la § «Lavoro con altri agenti» dice chi scrive cosa e in quale turno. Le valutazioni comuni si scrivono in entrambe.
8. **Il SUPERAGENTE** a ogni giro legge le § 2-3 di tutte le agende. Un agente fermo con voci in coda nella sua agenda va segnalato all'utente (regola core 3).
