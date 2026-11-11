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

## Casi
| caso | n° | esito misurato |
|---|---|---|
| riproduzione: testo nella casella + /clear (vecchio script) | 1 | FALLITO come sul SUP: messaggio 'rit\n/clear', sid invariato |
