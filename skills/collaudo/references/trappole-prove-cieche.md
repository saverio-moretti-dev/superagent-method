# Trappole delle prove cieche già incontrate (controllo a mano prima del giro)

Le prime sei le controlla anche `scripts/controlla_prompt.py`.

## Procedura e strumenti
1. **Browser non collegato** → giro a vuoto con `check_blind.py` che dice comunque CIECO. Prima: `list_connected_browsers`
   non vuoto + fumo haiku (apri, una schermata, titolo, chiudi). Dopo: schermate > 0, altrimenti non valido.
2. **`tabs_context_mcp` obbligatorio** prima di `tabs_create_mcp` (da 11/2026).
3. **`resize_window` non fa il telefono**: Chrome sul Mac non scende sotto ~500 px. Il telefono si dà con schermate 390
   a pagina intera dentro il messaggio (stream-json con immagini).
4. **Ruolo in lingua straniera → risposta in quella lingua** (3 olandesi su 6). «Rispondi in italiano» anche in testa
   al ruolo, non solo in fondo.
5. Segnaposto non sostituiti (`__URL__`, `<...>`) e prompt che svelano il test o l'esito atteso.
6. Regola anti-invenzione: ogni critica = indirizzo + testo copiato + dove visto; «manca» solo dopo aver ricontrollato;
   calcoli segnati «mio calcolo»; web solo con URL. Ha ridotto le allucinazioni ma non a zero (4 errori su 6 tester il
   6/11): **ogni segnalazione si verifica sul sorgente**.
7. **WebFetch riassume** il testo e non esegue i moduli: con solo web il tester dice «non c'è il modulo» o cita male.
   Per siti: Chrome o schermate nel messaggio.
8. **Estensione Claude rotta** («Script injection timed out»): reinstallarla, poi rifare il fumo.
9. `curl | grep -q` con `pipefail` = falso «porta giù» (SIGPIPE): controlli di porta con `[[ "$(curl …)" == *…* ]]`. (idem)
10. Tester Chrome **uno alla volta** (schede condivise); avvisare l'utente che usa il suo Chrome e di chiudere le schede personali.
11. Schermate a pagina intera: foto `loading=lazy` vuote e barre fisse a metà → `loading='eager'`, `decode()`, nascondere
    la barra; PNG lentissimo su pagine granulose → JPEG 95.
12. Demo con disponibilità casuale: verificare che le date dei ruoli siano davvero libere, altrimenti i tester si fermano
    al passo 2 (2 su 3, browser 2/11).

## Prompt: perché esce sempre FORSE e cosa fare

- Il FORSE è l'uscita sicura del formato: 22 tester su 22. **Non usarlo come misura.** Chiedere invece in modo separato:
  (a) cosa faresti **adesso** (mando la richiesta / chiamo / chiudo la pagina), (b) **errori concreti** (sbagliato,
  contraddittorio, rotto) con testo copiato, (c) obiezioni su fiducia/prezzo, (d) cosa manca. Si conta (b) e (d).
- Non dare al ruolo condizioni che la demo per definizione non può soddisfare («si fida solo se il proprietario esiste
  davvero» + «i nomi sono di esempio»). O si toglie, o si scrive come limite noto da non contare.
- Obiezioni sulla demo e sulla proposta (foto IA, recensioni finte, preventivo, siti veri): chiederle in una voce a parte,
  così non coprono gli errori veri.
- «Le 3 obiezioni più forti» produce sempre 3 obiezioni: va bene, ma «nessun errore concreto trovato» deve essere una
  risposta ammessa e scritta nel formato.
- Non «sii severo»: non è dimostrato che serva (skill `prova-cieca`, `references/persona-template.md`).
- I tester guardano ciò che il ruolo chiede: frasi rotte su pagine «di servizio» le saltano (3 proprietari su 3 non hanno
  visto «Mandate a Anna settimana» il 5/11). La rilettura frase per frase resta compito nostro (gradino 2).
