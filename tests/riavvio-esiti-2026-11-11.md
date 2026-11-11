# riavvia.py — esiti delle prove (2026-11-11)

Prove solo su sessioni usa e getta (PROVA-RIAVVIO-*), mai su quelle vive. Ore lette con `date` o dai log.

## Causa del fallimento delle 19:40 (dimostrata)

Sequenza (ore locali, dal log riavvii, dal blocco ttys002.json e dalla trascrizione della sessione):
- 19:40:37.760 il cron «Giro Regia» inietta un prompt (scheduled_task_fire); turno finito 19:40:45.875.
- 19:40:46 guardie verdi, blocco scritto (t=19:40:46), `do script "/clear"` nella scheda.
- 19:40:46.403 nella trascrizione arriva una voce utente `rit/clear` (promptSource typed): messaggio normale, nessun /clear.
- 19:40:58 `/riparti superagente` arriva come comando vero, ma nella stessa sessione (stesso sessionId, contesto vecchio).
- Il log scrive «RIAVVIATO» perché `scrivi()` controlla solo che AppleScript abbia trovato la scheda, non l'esito.

Meccanismo: `do script` di Terminal scrive il testo + invio nella casella così com'è. Se nella casella c'è già
del testo (qui «rit», non mandato da riavvia.py: nel log c'è solo '/clear'), il risultato è «testo/clear»,
che non è un comando e parte come messaggio. L'origine di «rit» non si ricava dai log (non c'è registro dei tasti);
history.jsonl non ha voci per la sessione fra 19:24 e 19:40:46: era testo scritto e non inviato.

Riproduzione (sessione PROVA-RIAVVIO-1, ttys005): 19:45:35 casella con «rit» + `do script "/clear"`
→ voce utente `'rit\n/clear'` nella trascrizione, sessionId invariato (dc2412e6). Riprodotto.

## Fatti misurati sul campo d'ingresso di Claude Code (v2.1.322)
- Ctrl-K + Ctrl-U ripetuti svuotano la casella anche multi-riga con il cursore in mezzo, ed escono dal modo shell «!».
- Invio su casella vuota non fa niente (nessuna voce in trascrizione).
- Un blocco di tasti troppo lungo in un solo `do script` (≥ ~60 caratteri) viene preso come INCOLLA:
  i tasti di controllo diventano testo e l'invio non manda (misurato: 20 coppie + 3 car. ok, 30 coppie no).
  Quindi blocchi corti (8 coppie = 16 car.).
- Dopo un /clear vero `claude agents --json` dà un sessionId nuovo entro ~1 s e nasce un nuovo
  `<sessionId>.jsonl` con la voce `<command-name>/clear</command-name>` (prova 19:48:43).

## Fix
Commit 46ebba1 (tools/riavvia.py + tests/test_riavvia.py, 35 test verdi). Criterio «contesto svuotato»:
sessionId nuovo sul processo di quel tty in `claude agents --json` E nella trascrizione nuova la voce
`<command-name>/clear</command-name>` con ora ≥ invio; in più, se nella trascrizione vecchia arriva un messaggio
normale che finisce con «/clear», è il guasto delle 19:40 e si ritenta (una volta), poi uscita 4 senza /riparti.
/riparti verificato con la voce `<command-name>/riparti</command-name>` nella trascrizione nuova.
Controllo indipendente dopo ogni prova: script che legge le due trascrizioni (vecchia: nessun messaggio
dell'utente dopo il lancio; nuova: voci comando /clear e /riparti).

Nota: ~/.claude.json NON toccato. Le prove girano in /private/tmp/prova-riavvio (cartella già fidata,
nessuna domanda di fiducia: schermo letto, sessione partita), sessione PROVA-RIAVVIO-1 su ttys005,
rilanciata alle 19:53 con --disallowedTools SendMessage AskUserQuestion CronCreate (non può scrivere ad altri).

## Casi
| caso | n° | esito misurato |
|---|---|---|
| riproduzione: testo nella casella + /clear (vecchio script) | 1 | FALLITO come sul SUP: messaggio 'rit\n/clear', sid invariato |
| fix, avanzo «rit⏎» nella casella + riavvia.py --sup (19:54:05) | 1 | OK in 8 s: sid 3f5c3164 → ddc61a39, vecchia senza messaggi, nuova con /clear e /riparti comando |
| avanzo multi-riga, cursore in mezzo, modo shell «! ls -la» (19:54:53) | 1 | OK in 8 s: ddc61a39 → ce20e0f2; «!ls» non eseguito, vecchia senza messaggi |
| sessione occupata (messaggio fra sessioni appena arrivato), senza --attendi (19:55:24) | 1 | RIFIUTATO uscita 2, niente scritto (avanzo «rit» rimasto intatto) |
| messaggio iniettato + --attendi 3 (19:55:42) | 1 | ATTESA finché occupata, poi OK alle 19:56:02: ce20e0f2 → 3dc286c2 |
| «utente» scrive nella casella subito dopo il segno (19:56:27) | 1 | segno non solo → secondo blocco di pulizia → OK: 3dc286c2 → 6d639c8d |
| «utente» scrive fra la lettura dello schermo e /clear (19:56:47): il guasto delle 19:40 rifatto dal vivo | 1 | tentativo 1: «QZXRIAVVIO/clear» messaggio normale, rilevato (CLEAR NON RIUSCITO); /riparti NON mandato; tentativo 2 OK 6d639c8d → 69febf06, poi /riparti |
| dopo il caso sopra: il blocco del comando passa da 3 a 8 coppie Ctrl-K/Ctrl-U (cancella anche quel testo) | — | test unitari 38/38 verdi |
