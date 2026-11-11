---
description: Riparte dalla nota lasciata da /passaggio — recupera il contesto con sicurezza, poi esegue
argument-hint: "[indicazioni aggiuntive, facoltative]"
---
Riparti dal passaggio di consegne lasciato dall'agente precedente.

Indicazioni aggiuntive dell'utente: $ARGUMENTS

1. **Trova la TUA nota — per nome, non per cartella**:
   - se la prima parola delle indicazioni è un nome (es. `/riparti coordinatore`): `python3 "${CLAUDE_PLUGIN_ROOT}/tools/passaggi.py" nome <parola>`; altrimenti `python3 "${CLAUDE_PLUGIN_ROOT}/tools/passaggi.py" nome`.
     La prima riga è la chiave: la nota è `~/.claude/passaggi/<chiave>.md`. Il resto delle indicazioni resta «indicazioni aggiuntive».
   - Leggi **solo** quella. Riga 2 della nota `nome: X`: se X non è la tua chiave → **fermati** e dillo in una riga.
   - Se lo script stampa «ALTRA NOTA di cartella non letta»: **non aprirla**, segnalala in una riga al coordinatore (è di un altro).
   - Se la nota non c'è: dillo in una riga e segui la normale sequenza d'avvio (nota di repo, `CLAUDE.md`, stato git).
   Se è più vecchia di 48 ore, avvisa: può essere superata.
1-ter. **Solo per il coordinatore**: appena ripartito, rilascia i messaggi trattenuti durante la pausa (se il progetto li trattiene) e avvisa che sei pronto **solo gli agenti al lavoro o con un ordine aperto verso di te**, non tutti: chi è fermo e non ti deve niente non va disturbato.
1-bis. **Agenda**: se la sessione ha un nome e c'è `agende/<NOME>.md` nella hub, leggila (§ 1-9) prima della nota: decisioni e permessi vincono sulla nota; la discordanza va in cronologia dell'agenda.
2. **Contesto globale**: leggi solo i file della sezione «Contesto globale», nell'ordine e nelle sezioni indicate.
   Il `CLAUDE.md` della repo vale comunque e vince sulla nota.
3. **Verifica lo stato sul disco** contro la sezione «Stato» (`git status`, `git log --oneline -5`, i file citati).
   Se discordano ha ragione il disco: annota la differenza.
4. **Approfondisci prima di partire** — è il punto che conta:
   - ogni voce di «Da approfondire»;
   - ogni punto della nota che risulta vago, contraddittorio o che non torna col disco;
   - prima di qualunque ricerca, cerca se è già stata fatta: sezione «Ricerche già fatte» della nota e
     nel registro delle ricerche del progetto (es. `RICERCHE.md`, con `grep <parole>`), se esiste.
   Approfondisci quanto basta per lavorare sicuro, non di più: si cerca (`grep`, sezione precisa), non si legge tutto.
   Se un dubbio resta e riguarda una scelta dell'utente o un'azione irreversibile: chiedi in una riga, non indovinare.
5. **Rispetta** «Decisioni», «Vincoli dell'utente», «Già chiesto e già risposto» (quelle domande non si rifanno: prima di
   chiedere qualunque cosa all'utente, cerca la risposta lì e nei file citati) ed «Errori dell'agente» (non ripeterli): non si rimettono in discussione senza un motivo concreto nuovo
   (in quel caso lo si dice all'utente, con la ragione).
6. Segna la nota come letta: `python3 "${CLAUDE_PLUGIN_ROOT}/tools/passaggi.py" leggi <chiave>` (→ `<chiave>.letta.md`; la `.letta` precedente va in `archivio/`). Niente rinomine a mano.
7. Scrivi all'utente **massimo 3 righe**: compito, cosa hai verificato/approfondito, primo passo. Poi **esegui** dal
   «Prossimo passo esatto», senza aspettare conferma (salvo i casi del punto 4).
