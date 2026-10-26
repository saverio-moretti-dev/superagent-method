# Valutare resoconto e piano

L'agente ne sa di più sull'argomento; tu sai di più sull'utente, sulle sue richieste e sul quadro. Decidete insieme.

Domande da farti:
1. Il piano risponde alla richiesta testuale dell'utente, o a una versione più comoda?
2. Contraddice regole o decisioni già prese (CLAUDE.md, note del progetto)?
3. Le fonti sono primarie e recenti? Le affermazioni chiave hanno URL? Cosa è solo dedotto?
4. Rischi e costi sono dichiarati? Il piano è la soluzione più semplice che regge?
5. L'agente ha esteso il compito (scope creep) o ne ha lasciato fuori un pezzo?
6. Esiste già qualcosa di equivalente da riusare?
7. Come si capirà che la consegna funziona (criteri di prova, anche per i ciechi)?

Esito:
- **Approvo** (con eventuali modifiche scritte e numerate) → fase 2.
- **Rimando**: dire cosa manca o cosa ritieni sbagliato e perché; l'agente (ripreso con `SendMessage`) integra. Ripeti finché sei convinto. Se l'agente gira a vuoto, applica «due giri senza progresso = cambia approccio».
- Una proposta dell'utente non è oro colato: se c'è un motivo concreto contro, dillo con la misura e proponi l'alternativa; l'ultima parola di prodotto resta all'utente.
