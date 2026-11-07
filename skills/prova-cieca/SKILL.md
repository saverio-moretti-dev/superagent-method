---
name: prova-cieca
description: Lancia tester «ciechi» (agenti senza memoria, CLAUDE.md né file locali, solo ricerca web) che giudicano una consegna fingendo un ruolo inventato (titolare, cliente diffidente…), e verifica che il test sia valido. Da usare quando si deve collaudare un CV, un sito, una proposta, un testo o qualunque consegna il cui effetto è incerto, o dentro la skill generale.
argument-hint: "[consegna] [ruolo]"
---

# Prova cieca

Il coordinatore è il superagente Claude. Questa skill dà il metodo per collaudare una consegna con tester isolati e per capire se i loro verdetti valgono qualcosa.

## Regole (non negoziabili)
1. **Un positivo non prova che funzioni**: è un filtro di errori. I tester Claude sono più indulgenti di un umano e preferiscono i testi in stile Claude. I **negativi validi pesano molto**; i positivi poco.
2. **Se il mondo reale può giudicare** la consegna (CV a un'agenzia, sito a un cliente), la prova reale vale più dei ciechi e la consegna all'umano lo dice.
3. **Tester mai ripresi** (non sarebbero più ciechi), mai fork, nessun canale fra tester, nessun file condiviso, nessun giudizio di un tester passato a un altro.
4. **Un solo test valido e negativo fa ripartire il ciclo** (decide il coordinatore: riprendere l'agente costruttore o ripartire da zero).
5. Il tester **non riceve** l'esito atteso, né chi ha fatto la consegna, né come è stata prodotta. Può cercare sul web anche la persona/l'azienda giudicata (è ciò che farebbe un vero titolare); gli è vietato leggere qualunque contesto locale.

## Procedura
1. **Dimensiona** (`references/dimensionare.md`): da complessità × probabilità che la consegna non produca l'effetto. 0 tester per verifiche deterministiche; 2 per rischio medio; 3-4 per rischio alto; **mai oltre 5**. Tester **diversi** per ruolo e ostilità (neutro, diffidente, esperto) e, per rischio alto, uno con modello diverso. Otto tester uguali valgono circa due.
2. **Stima il costo** in % (sessione e settimana) e dichiaralo prima del giro.
3. **Scrivi i prompt** dal modello `references/persona-template.md`: ruolo concreto, contesto inventato dettagliato, materiale, compito con ricerche, formato di decisione fisso. Salva ogni prompt in un file. Poi controllalo con `python3 <base>/../collaudo/scripts/controlla_prompt.py <prompt.txt>` e correggi finché passa.
4. **Lancia** ogni tester con `<base>/scripts/run_blind.sh <prompt.txt> <cartella-output> [modello] [max-turni]` (processi separati, in parallelo, `run_in_background`). Modello di default: sonnet; haiku per prove di fumo.
5. **Controlla** ogni transcript con `python3 <base>/scripts/check_blind.py <cartella-output>`: deve dire CIECO e riportare le ricerche fatte.
6. **Giudica la validità** con la checklist in `references/validita.md` (8 punti). Un test non valido si scarta e si rifà, non conta come esito.
7. **Leggi i transcript**, non solo i verdetti. Se due tester divergono non fare la media: capisci perché (spesso la consegna è ambigua).
8. **Esito**: tutti validi e senza difetti gravi → consegna con la dicitura della regola 1. Anche un solo negativo valido → si riparte.
9. **Superato** = un giro valido **senza errori concreti nuovi** (incoerenze, cose rotte) rispetto al giro prima. Un FORSE da solo non misura niente (22/22 FORSE nelle prove di novembre): contano la voce «errori concreti» e «cosa faresti adesso».

## Con il browser (Chrome dell'utente)
Per siti e pagine web, dove conta **come si vede e come si usa** (telefono, bottoni, moduli), non solo il testo.
- Si lancia con `CHROME=1 …/run_blind.sh …`. Il tester può: aprire pagine, fare schermate, cliccare, leggere, compilare moduli, ridimensionare la finestra. **Non può**: elencare o leggere le altre schede, eseguire javascript, leggere rete o console, caricare file, cambiare browser.
- **È il Chrome vero dell'utente**: prima del giro diglielo, e chiedigli di chiudere le schede personali. Il tester lavora in un gruppo di schede suo e lo chiude alla fine.
- **Un tester Chrome alla volta**, mai in parallelo: le schede stanno nello stesso browser e due tester potrebbero vedersi.
- `resize_window` sposta la finestra vera dell'utente: avvisalo.
- **Il telefono non si prova così**: sul Mac Chrome non scende sotto ~500 px. Con 390×844 la pagina è rimasta larga 596-858 px (prova del 2/11). Per il telefono servono schermate headless (Chrome `--headless` con l'emulazione del dispositivo), da dare nel prompt.
- Nel prompt: «apri le pagine con navigate, guarda con le schermate, chiudi la scheda alla fine». Il telefono si dà con schermate headless nel prompt, non con `resize_window` (vedi sopra).
- Controllo: `check_blind.py <out> --siti host1,host2`. Diventa SOSPETTO se il tester apre pagine fuori da quegli host o usa uno strumento vietato. I tentativi rifiutati vengono elencati, ma senza dati ricevuti non invalidano la prova.
- **Schermate > 0 obbligatorie**: un tester col browser che non ha fatto nessuna schermata non ha guardato il sito → prova non valida, si rifà. Prima del giro: browser collegato e un tester di fumo (haiku) che apre una pagina e fa una schermata.
- Le ricerche web restano consentite. Una prova solo col browser è valida anche senza ricerche, se la consegna è il sito.

## Riferimenti
`<base>` = la «Base directory» di questa skill, indicata quando la skill si carica: gli script stanno in `<base>/scripts/`.
`references/dimensionare.md` · `references/persona-template.md` · `references/validita.md` · `references/bias.md`
Meccanica: i tester girano come `claude -p --safe-mode --tools "WebSearch,WebFetch"` da una cartella vuota temporanea. Riserva: agente `tester-cieco` (con `omitClaudeMd`).
Limite noto: l'email dell'account resta visibile al tester; il template lo dice. Controlla che non l'abbia usata.
