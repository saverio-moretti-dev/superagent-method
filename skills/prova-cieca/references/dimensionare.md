# Quanti tester e di che tipo

| Complessità × probabilità di non produrre l'effetto | Tester |
|---|---|
| Bassa, verificabile con script | 0 LLM: controlli deterministici |
| Media | 2: uno neutro + uno diffidente |
| Alta o «probabilistica» (CV, sito, offerta, testo persuasivo) | 3-4: neutro, diffidente, esperto del settore, + uno su altro modello |
| Alta posta e irreversibile | 3-4 + prova reale con l'umano prima della consegna |

Mai oltre 5: gli errori dei modelli sono correlati (9 giudici di 7 famiglie ≈ 2 voti indipendenti), oltre 5 il beneficio è trascurabile. Se vuoi più copertura, cambia la **prospettiva**, non il numero.
Un giudizio per dimensione solo se la rubrica ha dimensioni indipendenti. Dove si può, usa controlli deterministici (regex, script) al posto di un LLM.
Costo: sonnet, 10-20 ricerche = ordine di decine/centinaia di migliaia di token per tester (stima da misurare; annota la misura in `conoscenze/costi.md`).
