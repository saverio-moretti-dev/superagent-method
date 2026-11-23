---
description: Allinea il coordinatore locale con quello in cloud, nei due sensi — ritira il lavoro del cloud, porta al cloud il lavoro locale di tutti gli agenti, ritira i rami cloud/*, prepara la coda di domani (OGGI AL CLOUD)
argument-hint: "[nota facoltativa da passare al cloud]"
---
Allinea **locale ↔ cloud** nei due sensi (modulo facoltativo: serve solo con la staffetta, `examples/albero/STAFFETTA.md`).
Il cloud lavora sulle stesse repo GitHub: ciò che non è pushato, per lui non esiste; ciò che lui ha pushato (anche su rami
`cloud/*` o `claude/*`), in locale non esiste finché non si ritira.

**Hub** = la cartella indicata da `$SUPERAGENT_HUB`; se non è impostata, la cartella di lavoro attuale.
Nota extra dell'utente per il cloud: $ARGUMENTS

Regole fisse: mai `--force`, mai `reset`, mai cancellare rami; conflitto o copia sporca che non sai sistemare → **fermati e
segnala**. Comandi indipendenti nello stesso turno. Leggi solo ciò che serve (`git log`, `sed -n`, `grep`).

## 1. Cloud → locale
1. **Staffetta**: in `STAFFETTA.md` della hub leggi i blocchi **FATTO DAL CLOUD** e **PER STASERA**.
2. **Hub e repo nominate in FATTO DAL CLOUD**: `git fetch --all --prune`, `git status -sb`.
   - Pulita e indietro → `git rebase -q --autostash origin/main`. File non committati non tuoi → segnala, non toccarli.
   - Rami remoti diversi da `main` aggiornati negli ultimi 7 giorni
     (`git branch -r --sort=-committerdate --format='%(refname:short) %(committerdate:relative) %(subject)'`):
     per ognuno `git log --oneline main..<ramo>`, controllo degli esiti a rischio; se si unisce in fast-forward o senza
     conflitti, unisci su `main`, altrimenti segnala ramo e commit.
   - Repo che pubblicano da sole (sito, Pages, Vercel): l'unione su `main` è una pubblicazione → **chiedi all'utente** prima.
3. **Cosa ha fatto il cloud** (solo il nuovo dall'ultimo allineamento): `git log --since=<data dell'ultimo blocco locale>
   --format='%h %ad %s' --date=format-local:%d/%m-%H:%M` (ora locale: il cloud scrive in UTC). Se il cloud chiede
   qualcosa al locale, eseguilo se rientra nelle regole, altrimenti riferiscilo all'utente (dal coordinatore, un solo canale).

## 2. Locale → cloud
4. **Cosa hanno fatto gli agenti locali** dall'ultimo blocco locale della staffetta:
   `python3 "${CLAUDE_PLUGIN_ROOT}/tools/passaggi.py" elenco` (note non lette, per nome) e le note `.letta` più recenti;
   commit non pushati e file non committati nelle repo della coda.
5. **Committa e pusha la hub**: prima fetch + rebase, poi commit delle note e dei documenti modificati, poi `git push`.
   Codice o file che non riconosci → non committarli, segnalali. Sulle altre repo non si pusha da qui (un push può
   pubblicare): si segnalano.
6. **Prepara OGGI AL CLOUD di domani**:
   - fonti: richieste dell'utente, coda dei lavori pianificati, agenti fermi con lavoro in coda, note di passaggio, nota
     extra ($ARGUMENTS). Solo compiti che il cloud può fare (niente app del computer, telefono, file non pushati);
   - **prima** controlla che ogni repo della coda sia pushata; se non lo è, quella riga non entra;
   - una riga per compito, autosufficiente, nel formato della tabella di `STAFFETTA.md` (repo, base
     `git rev-parse --short origin/main`, ramo `cloud/<data>`, compito, criterio verificabile, NON fare, taglia);
     in testa la data di domani, l'ora e il budget del giorno;
   - FATTO DAL CLOUD e PER STASERA già ritirati → svuotali (una riga di sintesi nella storia).
   - Coda vuota: scrivi «nessuna coda» con la data, così la routine si ferma senza spendere.
   Commit + push subito.

## 3. Resoconto all'utente (massimo 6 righe, senza gergo)
- **Dal cloud**: fatto · da approvare · bloccato · PER STASERA (o «niente di nuovo»).
- **Al cloud**: cosa è su GitHub e la coda di domani (n. compiti, taglie, budget).
- **Da guardare**: conflitti, rami non uniti, copie sporche, domande del cloud. Se è tutto a posto, dirlo per primo.
