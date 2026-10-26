# Fase 1 — il brief al ricercatore

## Cosa scrivere nel lancio (agente `ricercatore`, model sonnet)
1. **Contesto generale** (chi è l'utente nel progetto, scopo, vincoli come zero spese) e **specifico** (il compito preciso).
2. **Obiettivo**: conoscenza il più possibile universale e aggiornata, non una ricerca veloce. Fonti primarie, ogni affermazione con URL e data di lettura.
3. **Cartella dove salvare** i file di conoscenza e come (vedi `conoscenza.md`).
4. **Prima** cercare nell'archivio; ricerche nuove solo su ciò che manca o è «da ricontrollare».
5. **Scalatura dello sforzo**: fatto semplice = 1 agente 3-10 chiamate; confronto = 2-4 sotto-ricerche 10-15 chiamate; compito complesso = più angoli, ma mai agenti per query banali.
6. **Arresto**: tetto di turni indicato; stop dopo due giri consecutivi senza fatti nuovi; stop se le fonti sono sufficienti.
7. **Cosa restituire**: resoconto completo (cosa ha trovato, fonti chiave, cosa è verificato e cosa dedotto), rischi, e il **piano**: su cosa punta, cosa farebbe, come agirebbe, alternative scartate. Non costruire fino all'approvazione.
8. Dire all'agente di **fermarsi** a fine ricerca.

## Dopo
Controlla che i file di conoscenza esistano e siano datati. Se manca la fonte di un'affermazione importante, rimanda.
