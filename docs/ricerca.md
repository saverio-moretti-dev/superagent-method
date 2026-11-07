# La ricerca dietro i tester ciechi

Questa pagina riassume le ricerche su cui poggiano le skill `prova-cieca`, `collaudo` e `generale`: cosa dice la
letteratura sui giudici LLM e sulle persone simulate, come si rende davvero «cieco» un agente in Claude Code, quanto
costa, e come si decide se un test è valido.
Ricerche fatte a ottobre 2026, misure aggiornate a novembre 2026. Ogni numero ha la sua data: le versioni e i flag di
Claude Code cambiano in fretta, quindi va ricontrollato prima di fidarsene.

Legenda: **[V]** letto sulla fonte · **[T]** provato da me · **[D]** dedotto · **[?]** solo da sommari o risultati di
ricerca, da ricontrollare.

## 1. Perché un test positivo vale poco e uno negativo vale molto
- **Auto-preferenza.** I giudici LLM preferiscono testi *familiari* (bassa perplessità), anche se non li hanno scritti
  loro [V [arXiv 2410.21819](https://arxiv.org/abs/2410.21819)]. Nello screening di CV gli LLM preferiscono quelli
  scritti da LLM (67-82% nei confronti) [V abstract [arXiv 2509.00462](https://arxiv.org/abs/2509.00462)]. Un tester
  Claude che giudica una consegna scritta con Claude tende quindi a promuoverla [D].
- **Simulatori troppo gentili.** Su 2.790 conversazioni di vendita reali, i clienti simulati copiano bene chi compra ma
  sovrastimano l'interesse di chi non compra: resistenza espressa 25,1% nei reali contro 13,5% nei simulati
  [V abstract «Simulated Customers Never Walk Away», [arXiv 2606.20708](https://arxiv.org/abs/2606.20708)]. Dire al
  simulatore che può andarsene riduce il divario di circa 5 volte, ma non lo chiude.
- **Accondiscendenza** dei modelli addestrati con RLHF [V [arXiv 2310.13548](https://arxiv.org/abs/2310.13548)];
  bias di **posizione e verbosità** dei giudici [V Zheng et al., NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract.html).
- **Il verdetto non misura.** Nelle mie prove di novembre 2026, 22 tester su 22 hanno risposto FORSE: è l'uscita sicura
  del formato [T]. Si contano invece gli **errori concreti** (cose sbagliate, rotte, contraddittorie, con il testo
  copiato) e la risposta a «cosa faresti adesso».
- **Gli errori si trovano prima.** Nei giri di prove cieche su siti demo, circa 3 errori su 4 trovati dai tester erano
  trovabili prima con controlli economici (incoerenze fra pagine, percorsi rotti, domande del cliente senza risposta)
  [T]. Da qui il collaudo a gradini: prima si controlla da costruttori e da cliente, poi si paga un occhio esterno.
- **Falsi allarmi.** Circa il 16% delle segnalazioni dei tester era sbagliato: ogni segnalazione si verifica sul
  sorgente prima di correggerla [T].

Conseguenza pratica: un giro superato vuol dire «nessun difetto grave trovato in N prove», non «funziona». Quando il
mondo reale può giudicare (un cliente, un madrelingua, una candidatura vera), quel giudizio conta di più.

## 2. Quanti tester, e quanto diversi
- Pannelli di modelli diversi correlano con gli umani meglio di un giudice singolo grande [V [arXiv 2404.18796](https://arxiv.org/abs/2404.18796)],
  ma gli errori sono correlati: 9 giudici di 7 famiglie valgono circa **2,2 voti indipendenti**; oltre 5 giudici il
  guadagno è trascurabile [V preprint [arXiv 2605.29800](https://arxiv.org/abs/2605.29800), su compiti NLI].
- Anthropic, nel suo sistema di ricerca multi-agente, ha trovato più coerente una **singola chiamata giudice** con
  rubrica rispetto a più giudici; giudicare gli esiti, non i percorsi; la verifica umana resta indispensabile
  [V [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)].
- Un giudice per dimensione, con un'uscita «non so» ammessa; leggere i transcript; 0% di successo di solito vuol dire
  compito rotto, non agente incapace [V [Demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)].
- Ripetere con un secondo modello è un controllo utile: fra generazioni di modelli fino al 16% delle persone simulate
  cambia risposta [V [claude-persona](https://github.com/takechanman1228/claude-persona)].

Regola che ne viene [D]: **ruoli e prospettive diverse valgono più di tester in più**. 2-3 tester diversi (neutro,
diffidente, esperto del settore), mai oltre 5 per un esito.

## 3. Scrivere il ruolo
1. Ruolo concreto con vincoli veri: chi è, cosa rischia se sbaglia, quanto tempo ha, quante proposte simili ha già scartato.
2. Un prior realistico di scarto («ne scarti la maggior parte»), ma **non** «sii severo»: non ho trovato prove che
   un'istruzione generica di durezza riduca l'indulgenza, e può spostare il giudizio dalla parte opposta [V come lacuna].
3. Prima i fatti verificabili (ricerche sul mercato), poi la decisione in formato fisso; «non so» ammesso.
4. Niente indizi sulla risposta attesa, niente rivelazione che è un test né di come è stata prodotta la consegna.
5. Contesto inventato ma coerente: se cita un'azienda reale, il tester la cercherà.
6. Errori concreti e obiezioni in due voci separate: «nessun errore trovato» dev'essere una risposta ammessa.
7. «Rispondi in italiano» (o nella lingua voluta) in testa e in fondo: un ruolo straniero risponde altrimenti nella sua
   lingua (3 tester su 6 in una prova) [T].

## 4. Rendere cieco un agente in Claude Code (provato a ottobre 2026)
- **Un subagente standard non è cieco**: riceve i `CLAUDE.md` di tutta la gerarchia e, nella mia prova, anche l'indice
  della memoria automatica, contrariamente a quanto diceva la documentazione [T].
- **Processo separato in sola ricerca web** (scelta primaria):
  `claude -p --safe-mode --tools "WebSearch,WebFetch" --allowedTools "WebSearch,WebFetch" --disallowedTools "mcp__*" --model sonnet --max-turns N --no-session-persistence --output-format json`
  lanciato da una cartella vuota. Il tester dichiara solo i due strumenti web, nessun `CLAUDE.md`, nessuna memoria [T].
  `--safe-mode` disattiva `CLAUDE.md`, skill, plugin, hook, MCP, comandi, agenti e memoria, ma mantiene autenticazione
  e modello [V [CLI reference](https://code.claude.com/docs/en/cli-reference)].
- **Subagente con `omitClaudeMd: true` e solo strumenti web**: alternativa provata [T]. Allora c'era una issue aperta su
  `CLAUDE.md` di sottocartelle che rientrano dopo una lettura [?]: il tester non deve avere `Read`.
- **`--restricted` sconsigliato** per i ciechi: nella prova il tester vedeva anche i connettori dell'account (posta,
  calendario…) e costava molto di più [T].
- **`--bare`** sarebbe più pulito ma richiede una chiave API, quindi spesa a consumo [V].
- **Perdite residue**: l'email dell'account resta visibile al tester (il modello del ruolo gli dice di ignorarla:
  controllare nel transcript che non l'abbia cercata); il web è aperto, quindi una consegna già pubblica può essere
  trovata [T][D].
- **Contare le ricerche dal transcript**, non dal contatore del JSON finale: nella prova risultava 0 anche dopo una
  ricerca vera [T].
- **Con il browser**: Chrome sul Mac non scende sotto ~500 px, quindi il telefono si prova con schermate a pagina intera
  date nel prompt, non con il ridimensionamento della finestra; un tester col browser alla volta (schede condivise);
  zero schermate = prova non valida [T].
- Tester isolati: processi separati, nessuna cartella condivisa, nessun messaggio fra loro, nessun fork; il
  coordinatore non riporta a un tester i giudizi degli altri. Un tester ripreso non è più cieco.

## 5. Quando un test è valido (checklist)
Valido solo se tutte vere:
1. Cecità verificata nel transcript (nessun file locale, solo gli strumenti ammessi).
2. Ricerche fatte davvero e pertinenti (fonti citate, qualche URL aperto a campione).
3. Consegna letta intera (cita dettagli non banali).
4. Resta nel ruolo.
5. Verdetto coerente con le motivazioni.
6. Risponde nel formato chiesto.
7. Non si regge su fatti inventati.
8. Se due tester divergono, non si fa la media: si capisce perché (spesso la consegna è ambigua).
Un test non valido si scarta e si rifà, senza contarlo. Un negativo valido fa ripartire il ciclo.

## 6. Costi (misure di ottobre-novembre 2026, prezzi di listino)
| cosa | costo |
|---|---|
| tester minimo in sola lettura, nessuno strumento usato | ~0,02 $ |
| prova di fumo col browser, haiku | 0,004-0,02 $ |
| tester sonnet, solo web | ~0,28-0,39 $ |
| tester sonnet col browser | ~0,40-0,55 $ |
| giro di 3 tester su un CV, solo web | ~1% della settimana di un piano in abbonamento |
Con un abbonamento questi valori contano nei limiti d'uso, non in fattura. Leve principali: modello per ruolo (sonnet o
haiku per tester e compiti meccanici, il modello più forte solo per il coordinatore), prova di fumo prima di ogni giro
che costa, tetto ai turni, riuso delle ricerche già salvate, parte comune del prompt prima e parte variabile dopo (per
sfruttare la cache). Riferimento: i sistemi multi-agente usano circa 15 volte i token di una chat [V [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)].

## 7. Cosa esisteva già (ottobre 2026)
Pezzi del processo esistono: controller e implementer freschi con revisione e ciclo di correzione limitato
([obra/superpowers](https://github.com/obra/superpowers)), test di skill con baseline e confronto cieco
([skill-creator](https://github.com/anthropics/skills)), `claude plugin eval`
([docs](https://code.claude.com/docs/en/plugin-evals.md)), pannelli di persone in processi separati
([claude-persona](https://github.com/takechanman1228/claude-persona)), i pattern *orchestrator-workers* ed
*evaluator-optimizer* ([Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)).
Non ho trovato niente che li combinasse con ricerca salvata come conoscenza datata, un coordinatore che approva il piano,
collaudo a gradini e regole di validità per i tester ciechi: il contributo di questo metodo è il cablaggio, non i singoli pezzi.
