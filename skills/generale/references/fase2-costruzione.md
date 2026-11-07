# Fase 2 — costruzione e cicli di correzione

- Lancia `costruttore` con: il piano approvato (modifiche incluse), i file di conoscenza da consultare, cosa consegnare, dove, e il criterio di fatto. Se la consegna è codice, valuta un worktree separato.
- Il costruttore consegna e **si ferma**; il rapporto lungo va su file, nel contesto torna lo stato.
- Valutazione: confronta con il piano e con i criteri; verifica a campione (apri i file, esegui, leggi). Niente «sembra a posto».
- Cicli di correzione (massimo 3 giri con lo stesso agente):
  - Correzione puntuale → `SendMessage` allo stesso agente: «è andata male, perché, correggi».
  - Contesto in un vicolo cieco o bias → agente nuovo con brief aggiornato.
  - Terzo giro fallito → cambia approccio (modello più forte, piano diverso) o chiedi all'umano.
- Ogni correzione è seguita da una nuova valutazione; mai rivalutare solo la parte corretta se tocca altre.

## Criterio di «fatto» (indagine 2026-11-07: ~3/4 degli errori trovati dai ciechi erano trovabili prima)
- **Domande del cliente finale**: prima di costruire, lista delle domande che un vero cliente si fa (prezzo totale, caparra, annullamento, chi è il titolare, cosa è incluso…); fatto = ogni domanda ha risposta nella consegna. Modello: `references/domande-cliente.md` della skill `collaudo`.
- **Fatti incrociati**: un dato = una fonte sola, ed è uguale su ogni pagina, lingua e modulo (prezzi, date, nomi, orari). Controllarlo a programma, non a occhio.
- **Fase 3 (prove) con la skill `collaudo`**: gradini dal più economico (build/test → percorsi → Chrome e telefono → prove cieche con fumo prima). I ciechi partono solo quando i gradini prima sono puliti.
