---
name: prova-cieca
description: Lancia tester «ciechi» (agenti senza memoria, CLAUDE.md né file locali, solo ricerca web) che giudicano o vivono una consegna nei panni di un personaggio inventato (titolare, cliente diffidente…), da soli o in partita con un «master» che interpreta l'autore della consegna e il mondo; poi verifica che il test sia valido. Da usare quando si deve collaudare un CV, un sito, una proposta, un testo o qualunque consegna il cui effetto è incerto, o dentro la skill generale.
argument-hint: "[consegna] [livello 1-3] [ruolo]"
---

# Prova cieca

Il coordinatore è il superagente Claude, o l'agente del progetto che ha fatto la consegna. Questa skill dà il metodo per collaudare una consegna con tester isolati e per capire se i loro verdetti valgono qualcosa.

## Regole (non negoziabili)
1. **Un positivo non prova che funzioni**: è un filtro di errori. I tester Claude sono più indulgenti di un umano e preferiscono i testi in stile Claude. I **negativi validi pesano molto**; i positivi poco.
2. **Se il mondo reale può giudicare** la consegna (CV a un'agenzia, sito a un cliente), la prova reale vale più dei ciechi e la consegna all'umano lo dice.
3. **Un tester vive solo dentro la propria campagna**: la sua sessione si riprende solo per il turno successivo della stessa partita, mai fuori da essa e mai dopo il verdetto. Mai fork, nessun canale fra tester, nessun file condiviso, nessun giudizio di un tester passato a un altro.
4. **Un solo test valido e negativo fa ripartire il ciclo** (decide il coordinatore: riprendere l'agente costruttore o ripartire da zero).
5. **Il tester conosce solo sé stesso.** Non riceve l'esito atteso, né chi ha fatto la consegna, né come è stata prodotta, né la situazione dell'autore: sa solo chi è lui e come gli è arrivata la proposta («te lo manda un amico di un amico»). Può cercare sul web la persona o l'azienda giudicata (lo farebbe uno vero); gli è vietato leggere qualunque contesto locale.
6. **La situazione reale dell'autore va solo al master** (livelli 2-3), mai ai tester. Il master non tocca file: riceve il suo contesto come testo.

## Livelli di intensità
| Livello | Come gira | Per cosa | Costo indicativo |
|---|---|---|---|
| 1 Semplice | un tester, un colpo, prompt da `references/persona-template.md` | testi, CV, controlli rapidi | 1× |
| 2 Scena | il master apre con la storia dalla scheda approvata → il tester agisce → il master risponde una volta → il tester decide | proposte, pagine singole | ~2× |
| 3 Simulazione | più turni alternati (tetto per campagna, es. 6) finché il tester decide: compra / lascia (contattare l'autore è un'azione della partita, non la fine) | siti per clienti, offerte vendibili | ~3-5× |

Si sceglie dal costo di sbagliare (`references/dimensionare.md`); il livello 3 solo per consegne che devono vendere o convincere davvero.

## Ruoli (livelli 2-3)
- **Agente del progetto**: scrive il **contesto del master** dal modello `references/master-template.md`, applicando le regole del suo progetto (prima volta). Se gli mancano informazioni sull'autore, le chiede prima del giro attraverso il proprio coordinatore, senza bloccare la sessione. Lancia il giro, legge i resoconti e scrive le **conclusioni** applicando di nuovo le regole del progetto (seconda volta). Il contesto del master sta nella repo del progetto, mai in questa skill.
- **Master**: apre la campagna con la **storia di partenza** presa dalla scheda approvata del protagonista (`references/storia-tester.md`; non la inventa), poi diventa un **giocatore rivale alla pari**: interpreta l'autore fedelmente (né tifoso né ostile) e il mondo (risposte che arrivano, tempi, imprevisti realistici). Non decide mai se una cosa «va bene». Dove non sa cosa farebbe l'autore **non inventa**: risponde in modo neutro e lo segna come **buco**. A fine campagna scrive il resoconto.
- **Tester**: cieco come al livello 1; conosce solo la propria storia; sceglie liberamente cosa fare (scrivere, telefonare, chiedere modifiche o sconti, sparire…) e lo dice al master; fa ricerche libere. Non vede gli altri tester: ogni campagna è una partita a due.

## Campagne (livelli 2-3)
Una campagna racconta la storia del **protagonista** (era X, è Y, arriva la situazione, va Z); la consegna è un evento della sua storia e l'autore un personaggio esterno incontrato per caso. **Schede decise prima** con l'autore (protagonista, personaggio esterno con la fonte di ogni riga, scena), un **manuale** di regole globali e di sessione, **controlli** (intensità, casualità, severità solo come tratti e mondo, campagne in parallelo, tetti), una **libreria di profili** riusabili o derivabili. Il risultato è un'**analisi** di come è andata, non un voto.
`references/campagna.md` (arco, turni, prezzi, analisi) · `references/schede.md` (schede e profili) · `references/manuale.md` (regole e controlli)

## Procedura
1. **Dimensiona** (`references/dimensionare.md`): livello, numero di tester (0 per verifiche deterministiche; 2 rischio medio; 3-4 rischio alto; **mai oltre 5**), tester **diversi** per ruolo e ostilità e, per rischio alto, uno con modello diverso. Otto tester uguali valgono circa due.
2. **Stima il costo** in % (sessione e settimana) e dichiaralo prima del giro. Livelli 2-3: tetto di turni per campagna e tetto di chiamate per processo, scritti anche nei prompt.
3. **Scrivi i prompt**. Livello 1: `references/persona-template.md`. Livelli 2-3: prima le schede approvate (`references/schede.md`), poi il contesto del master da `references/master-template.md`, con le **parole vietate** (ciò che il tester non deve mai leggere); la storia di partenza viene dalla scheda del protagonista. Salva ogni prompt in un file e controllalo con `python3 <base>/../collaudo/scripts/controlla_prompt.py <prompt.txt>` finché passa.
4. **Lancia**. Livello 1: `<base>/scripts/run_blind.sh <prompt.txt> <cartella-output> [modello] [max-turni]` per ogni tester (processi separati, in parallelo, `run_in_background`). Livelli 2-3: una campagna per tester con `<base>/scripts/campagna.py` (master e tester in processi separati; ogni messaggio del master passa dal controllo di fuga prima di arrivare al tester). Modello di default: sonnet; haiku per prove di fumo. **`max-turni` = tetto di CHIAMATE a strumenti** (default 30), garantito da un sorvegliante che ferma il processo alla chiamata successiva (`--max-turns` della CLI da solo conta le risposte, e una risposta può fare molte chiamate in parallelo). Tester fermato → file `INTERROTTO`, uscita 3, `risposta.txt` con la nota: vale come incompleto, non come giudizio. Costo misurato ~0,008 $ a chiamata (sonnet, Chrome) → `max-turni` ≈ tetto $ / 0,008. **Il tetto va scritto anche nel prompt** (es. «massimo 22 azioni; dopo la 18ª smetti di esplorare e scrivi la decisione», con `max-turni` qualche chiamata sopra): senza, il tester esplora fino al taglio e il giro si perde.
5. **Controlla** ogni transcript di tester con `python3 <base>/scripts/check_blind.py <cartella-output>`: deve dire CIECO e riportare le ricerche fatte. Livelli 2-3: anche nessuna fuga nei messaggi del master, e il **controllo del master** (ha promesso cose non scritte nel suo contesto? è stato più morbido o più duro del vero?).
6. **Giudica la validità** con `references/validita.md`. Un test non valido si scarta e si rifà, non conta come esito.
7. **Leggi transcript e resoconti**, non solo i verdetti. Se due tester divergono non fare la media: capisci perché (spesso la consegna è ambigua). I **buchi** del master diventano domande per l'autore prima del giro successivo.
8. **Conclusioni** (l'agente del progetto, con le regole del progetto): cosa ha funzionato, cosa no, cosa migliorare, domande per il giro dopo. Tutti validi e senza difetti gravi → consegna con la dicitura della regola 1. Anche un solo negativo valido → si riparte.
9. **Superato** = un giro valido **senza errori concreti nuovi** (incoerenze, cose rotte) rispetto al giro prima. Un FORSE da solo non misura niente: contano «errori concreti» e «cosa faresti adesso» (livello 1), o l'esito della campagna e i suoi dubbi (livelli 2-3).

## Con il browser (Chrome dell'utente)
Per siti e pagine web, dove conta **come si vede e come si usa** (telefono, bottoni, moduli), non solo il testo.
- Si lancia con `CHROME=1 …/run_blind.sh …` (vale anche per il tester di una campagna). Il tester può: aprire pagine, fare schermate, cliccare, leggere, compilare moduli, ridimensionare la finestra. **Non può**: elencare o leggere le altre schede, eseguire javascript, leggere rete o console, caricare file, cambiare browser.
- **È il Chrome vero dell'utente**: prima del giro diglielo, e chiedigli di chiudere le schede personali. Il tester lavora in un gruppo di schede suo e lo chiude alla fine.
- **Un tester Chrome alla volta**, mai in parallelo (stesso browser: potrebbero vedersi). Le campagne senza Chrome possono girare in parallelo.
- `resize_window` sposta la finestra vera dell'utente: avvisalo.
- **Il telefono non si prova così**: sul Mac Chrome non scende sotto ~500 px (con 390×844 la pagina è rimasta larga 596-858 px). Per il telefono servono schermate headless (Chrome `--headless` con l'emulazione del dispositivo), da dare nel prompt.
- Nel prompt: «apri le pagine con navigate, guarda con le schermate, chiudi la scheda **prima** di scrivere la risposta» (la risposta è l'ultima cosa che scrive: prova CASA 14/11, scheda chiusa dopo → risposta persa). `campagna.py --chrome` lo aggiunge da solo alle regole del tester; `risposta.py` comunque prende il messaggio col formato se dopo c'è un'altra azione.
- Controllo: `check_blind.py <out> --siti host1,host2`. Host **senza porta** (`127.0.0.1`, non `127.0.0.1:8799`): con la porta un sito ammesso esce SOSPETTO. Diventa SOSPETTO se il tester apre pagine fuori da quegli host o usa uno strumento vietato. I tentativi rifiutati vengono elencati, ma senza dati ricevuti non invalidano la prova.
- **Schermate > 0 obbligatorie**: un tester col browser che non ha fatto nessuna schermata non ha guardato il sito → prova non valida. Prima del giro: browser collegato e un tester di fumo (haiku) che apre una pagina e fa una schermata.
- Le ricerche web restano consentite. Una prova solo col browser è valida anche senza ricerche, se la consegna è il sito.

## Riferimenti
`<base>` = la «Base directory» di questa skill, indicata quando la skill si carica: gli script stanno in `<base>/scripts/`.
`references/dimensionare.md` · `references/persona-template.md` (livello 1) · `references/master-template.md` · `references/storia-tester.md` (livelli 2-3) · `references/validita.md` · `references/bias.md`
Meccanica: i tester girano come `claude -p --safe-mode --tools "WebSearch,WebFetch"` da una cartella vuota temporanea; il master come `claude -p` senza strumenti di file. Riserva: agente `tester-cieco` (con `omitClaudeMd`).
Campagne: `campagna.py --giro <dir> --nome t1 --master MASTER.md --tester "…" --vietate parole.txt [--livello 3] [--turni 6] [--chiamate 12] [--controllo haiku]` → `<dir>/t1/` con `campagna.json`, `partita.md`, `resoconto.md` e i transcript; `<dir>/giro.json` (riassunto per chi lo mostra; metadati da `giro-meta.json`, conclusioni da `conclusioni.md`). Sessioni salvate della CLI cancellate a fine campagna. Prove a vuoto con haiku: il meccanismo regge, ma haiku come tester resta passivo (non contatta mai) e cita fonti mai aperte: per i giri veri sonnet.
Limite noto: l'email dell'account resta visibile al tester; il template lo dice. Controlla che non l'abbia usata.
**Messaggi fra sessioni**: un `claude -p` può ricevere i messaggi che un'altra sessione manda «a tutti» (12/11/2026: un messaggio del coordinatore è entrato in un processo di controllo dopo il suo risultato e gli ha fatto fare un secondo turno). Il sorvegliante chiude il processo al primo risultato e `check_blind.py` segna SOSPETTO ogni transcript in cui ne è entrato uno; durante un giro, il coordinatore non manda messaggi a sessioni senza nome.
