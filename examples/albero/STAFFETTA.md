# STAFFETTA — passaggio quotidiano locale ↔ cloud (modulo facoltativo)

Per chi ha la macchina locale **offline per fasce orarie** (es. 9:00-18:00) e di giorno fa lavorare il cloud.
Il cloud vede **solo ciò che è su GitHub** e i connettori dell'account; tutto il resto aspetta la sera.

Ritmo:
1. **Prima della fascia** (locale): `/passaggio` nelle sessioni aperte, **push di tutto** (nessuna repo con commit non
   pushati o file utili non committati), poi si riscrive il blocco OGGI AL CLOUD.
2. **Durante la fascia** (cloud): una sessione o una routine legge OGGI AL CLOUD, esegue solo quella coda, push dopo
   ogni compito, scrive FATTO DAL CLOUD. Fuori dalla coda, o produzione / cancellazioni / invii / spese → chiede
   all'utente o scrive in PER STASERA.
3. **Dopo la fascia** (locale): pull delle repo toccate, lettura di FATTO DAL CLOUD, controllo degli esiti a rischio,
   lavori di PER STASERA.

Solo in locale, di solito: app del computer (posta, musica, browser dell'utente), telefono via cavo, build per il
sistema operativo locale, file non pushati o ignorati da git, messaggi fra sessioni locali.

## OGGI AL CLOUD — scritto da: locale, AAAA-MM-GG HH:MM
| compito | repo | recinto | da solo può | lascia al locale | finito quando | budget |
|---|---|---|---|---|---|---|
| | | | | | | % settimana |

## FATTO DAL CLOUD — scritto da: cloud
| compito | esito | commit | serve dal locale / dall'utente |
|---|---|---|---|

## PER STASERA
- 
