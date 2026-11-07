# STAFFETTA — passaggio quotidiano locale ↔ cloud (modulo facoltativo)

Per chi ha la macchina locale **offline per fasce orarie** (es. 9:00-18:00) e di giorno fa lavorare il cloud.
Il cloud vede **solo ciò che è su GitHub** e i connettori dell'account; tutto il resto aspetta la sera.

Ritmo:
1. **La sera prima, o prima della fascia** (locale): `/passaggio` nelle sessioni aperte, **push di tutto** (nessuna repo con commit non
   pushati o file utili non committati), poi si riscrive il blocco OGGI AL CLOUD.
2. **Durante la fascia** (cloud): una sessione o una routine legge OGGI AL CLOUD, esegue solo quella coda, push dopo
   ogni compito, scrive FATTO DAL CLOUD. Fuori dalla coda, o produzione / cancellazioni / invii / spese → chiede
   all'utente o scrive in PER STASERA.
3. **Dopo la fascia** (locale): pull delle repo toccate, lettura di FATTO DAL CLOUD, controllo degli esiti a rischio,
   lavori di PER STASERA.

Routine giornaliera nel cloud: **sessione nuova a ogni giro** (non persistente, così il contesto non cresce), nessun
connettore che il prompt non usa; ogni modifica che il cloud fa a questo file (stato di una riga, FATTO DAL CLOUD) va
**verificata con `grep`** prima del commit: una sostituzione di testo può non avere effetto senza dare errore.

Solo in locale, di solito: app del computer (posta, musica, browser dell'utente), telefono via cavo, build per il
sistema operativo locale, file non pushati o ignorati da git, messaggi fra sessioni locali.

## OGGI AL CLOUD — AAAA-MM-GG (scritto dal locale alle HH:MM) · budget del giorno: ~N% della settimana
| n | repo | base | ramo | compito | finito quando | NON fare | taglia | stato |
|---|---|---|---|---|---|---|---|---|
| C1 | owner/repo | abc1234 | cloud/AAAA-MM-GG | autosufficiente: file da leggere, cosa produrre | criterio verificabile (test, build, file) | es. niente deploy | S | da fare |

- **base**: commit che il locale garantisce pushato; il cloud controlla che esista (`git cat-file -e`), se manca →
  `bloccato: base vecchia`.
- **ramo**: il cloud non pusha mai su `main` delle repo che pubblicano da sole (siti, Pages, deploy automatici): lavora
  su `cloud/AAAA-MM-GG`, la sera il locale guarda e unisce. `main` solo se la riga lo scrive.
- **taglia**: S ≈ 30 min, M ≈ 1-2 h, L ≈ mezza giornata; superata di molto o 3 tentativi falliti → `bloccato`.
- **stato**: `da fare` → `in corso` → `fatto` | `bloccato: <motivo>` | `da approvare: <cosa>`.

## FATTO DAL CLOUD — AAAA-MM-GG
| n | esito | commit / ramo | serve dal locale o dall'utente |
|---|---|---|---|

## PER STASERA
- 
