# Fase 2 — costruzione e cicli di correzione

- Lancia `costruttore` con: il piano approvato (modifiche incluse), i file di conoscenza da consultare, cosa consegnare, dove, e il criterio di fatto. Se la consegna è codice, valuta un worktree separato.
- Il costruttore consegna e **si ferma**; il rapporto lungo va su file, nel contesto torna lo stato.
- Valutazione: confronta con il piano e con i criteri; verifica a campione (apri i file, esegui, leggi). Niente «sembra a posto».
- Cicli di correzione (massimo 3 giri con lo stesso agente):
  - Correzione puntuale → `SendMessage` allo stesso agente: «è andata male, perché, correggi».
  - Contesto in un vicolo cieco o bias → agente nuovo con brief aggiornato.
  - Terzo giro fallito → cambia approccio (modello più forte, piano diverso) o chiedi all'umano.
- Ogni correzione è seguita da una nuova valutazione; mai rivalutare solo la parte corretta se tocca altre.
