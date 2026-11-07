# Salvare la conoscenza

Ogni file nella cartella delle conoscenze (default `./conoscenze/`), in Markdown:
- Intestazione: data, autore (agente), stato (`valido` | `da ricontrollare`).
- Fonti con URL e data di lettura.
- Contrassegni: **[V]** verificato su fonte letta · **[T]** testato · **[D]** dedotto · **[?]** non verificato.
- Un `INDICE.md` con una riga per file.
Prima di una ricerca nuova si consulta l'indice (grep). Le informazioni scadute si rifanno; il resto si riusa.
Se il progetto ha un registro delle ricerche, aggiungere una riga `RICERCA: argomento · parole chiave · percorso · conclusione`.

## Riusare ciò che è già stato fatto
- **Piani approvati**: prima di proporre una struttura o un'architettura si cercano i piani e le decisioni già
  approvati (`grep` nella cartella dei piani e nelle decisioni del progetto). Ciò che è approvato non si riprogetta.
- **Caso simile, stesso procedimento**: se il compito somiglia a uno già fatto, si segue passo per passo il
  procedimento della volta prima, compresi i bug incontrati e i fix, invece di ripartire da zero.
- **Ogni numero ha la data** e la fonte; se documento e disco discordano vince il disco.
