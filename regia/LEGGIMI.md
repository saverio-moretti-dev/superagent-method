# Regia — app locale per seguire le sessioni e parlare col coordinatore

Pagina web locale (più app Mac facoltativa) che mostra tutte le sessioni Claude Code al lavoro e fa da casella unica
per scrivere al coordinatore (SUP). Solo libreria standard di Python, nessuna build, nessun servizio esterno.
Il codice e i testi sono in italiano, come il resto del metodo.

## Avvio
    python3 regia/server.py          # → http://127.0.0.1:8765   (altra porta: python3 regia/server.py 8799)
Ascolta solo su 127.0.0.1 e accetta solo Host/Origin locali. Scrive solo i file dati della propria cartella
(`coda.jsonl`, `attesa.jsonl`, …). Non tocca le schede del terminale, `~/.claude` né le regole.

## Cosa legge (sola lettura)
| fonte | a cosa serve | variabile per cambiarla |
|---|---|---|
| `claude agents --json` e trascrizioni `~/.claude/projects/` | sessioni vive, stato, chat a 0 token | `PLANCIA_TRASCRIZIONI` (scheda Token) |
| cartella hub con `SESSIONI.md` e `agende/<NOME>.md` | le 2 righe «di cosa si occupa / a che punto è» | `PLANCIA_HUB` (predefinita: cartella madre di `regia/`) |
| `tools/passaggi.py elenco` di questa repo | note di passaggio da leggere | `PLANCIA_PASSAGGI` |
| `~/.claude/consumo/limiti.csv` (lo scrive la barra di stato) | consumo 5 h e 7 giorni | `PLANCIA_LIMITI` |
| `dont-waste-your-token` (modulo `ctm`) | scheda Token; se manca la scheda lo dice e il resto funziona | `PLANCIA_CTM` (predefinita: cartella accanto a questa repo) |

Senza hub o senza note la pagina funziona lo stesso: quelle righe restano vuote.

## Pezzi
| file | chi lo usa | cosa fa |
|---|---|---|
| `server.py` | utente | pagina e API: `/api/stato`, `/api/messaggi` (ETag, ogni 2 s), `/api/chat`, `/api/token`, `POST /api/richiesta`, `POST /api/modifica`; si riavvia da solo quando cambia il codice |
| `raccogli.py` | server | istantanea in JSON di sessioni, agende, passaggi, consumo |
| `chat.py` | server | chat di una sessione ricostruita dalla trascrizione, senza chiamare modelli |
| `consumi.py` | server | scheda Token |
| `sup.py` | coordinatore | `nuove`, `prendi <id> [--a NOME]`, `giallo/grigio/conferma <id>`, `risposta <NOME|SUP> "…" [--id <id>]`, `sospeso elenco/aggiungi/togli`, `permesso "…"`/`permesso via`, `pausa`/`riprendi` |
| `attesa.py`, `modifiche.py` | server, sup | messaggi trattenuti mentre il SUP si riavvia; richieste modificate dopo l'invio |
| `web/` | browser | pagina senza build, installabile come PWA (icone in `web/icone/`, sorgente `regia.svg`) |
| `app-mac/` | utente | app Mac facoltativa (vedi sotto) |
| `avvio/local.regia.server.plist` | utente | modello per l'avvio automatico all'accesso |

File dati (in `.gitignore`, contengono messaggi): `coda.jsonl`, `attesa.jsonl`, `richieste.json`, `risposte.jsonl`,
`insospeso.json`, `permesso.json`, `sup-ascolto.json`, `pausa.json`.

## Ciclo di una richiesta
utente scrive nella casella → `coda.jsonl` (**nuova**) → il SUP con `sup.py nuove` la legge (**letta**) → ordina all'agente,
`sup.py prendi <id> --a NOME` (**girata**) → l'agente lavora (`sup.py giallo <id>`) → consegna, il SUP valuta,
`sup.py grigio <id> "esito"` + `sup.py risposta NOME "…" --id <id>` (**risposto**).
Produzione, cancellazioni, invii esterni: `sup.py conferma <id> "cosa"` e il SUP chiede in chat. L'app non dà permessi.

Sveglia del SUP (consigliata): un Monitor su `tail -n0 -F regia/coda.jsonl`, così ogni riga nuova lo sveglia.

## SUP in riavvio
Con `pausa.json` (lo scrive `sup.py pausa`) le richieste vanno in `attesa.jsonl` invece che in `coda.jsonl`: il SUP che
sta per fare `/clear` non le vede e non le perde. `sup.py riprendi` le sposta in coda con lo stesso id.

## Prove con dati finti
- Server di prova: `PLANCIA_DATI=<cartella temporanea> python3 regia/server.py <porta diversa da 8765>`. Mostra la
  fascia rossa «SERVER DI PROVA» e si spegne da solo dopo 30 min (`PLANCIA_PROVA_MIN`).
- Sessioni finte: `PLANCIA_STATO_FINTO=<file.json>` (chiavi `stato`, `chat`, `token`), vale solo col server di prova.
- Un messaggio che non comincia con «prova» va anche nella coda vera: un messaggio scritto per sbaglio nella pagina di
  prova non si perde. Finita la prova: scheda chiusa e server spento.

## App Mac (facoltativa, senza firma)
Sorgente in `app-mac/` (Swift + WKWebView). `regia/app-mac/costruisci.sh --installa` → `~/Applications/Regia.app`.
**Firma ad-hoc, nessun account Apple**: l'app non è firmata né autenticata da Apple, va costruita sul proprio Mac
(macOS può chiedere conferma alla prima apertura). Apre la pagina di 127.0.0.1:8765; a server spento mostra «La Regia non
risponde» e riprova da sola ogni 5 s. Notifiche e numero sul Dock solo dopo il permesso di macOS.
Prove: `REGIA_URL=http://127.0.0.1:<porta>/ regia/app-mac/build/Regia.app/Contents/MacOS/Regia`.

## Avvio automatico (facoltativo)
`avvio/local.regia.server.plist` è un **modello**: sostituire `__CARTELLA_REGIA__` (percorso assoluto di questa cartella)
e `__HOME__` (la propria home), controllare il percorso di `python3`, poi:

    cp regia/avvio/local.regia.server.plist ~/Library/LaunchAgents/
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.regia.server.plist

Togliere: `launchctl bootout gui/$(id -u)/local.regia.server && rm ~/Library/LaunchAgents/local.regia.server.plist`.
`ProcessType` deve restare `Standard`: in `Background` macOS rallenta il server di molte volte.

## Limiti
- «in attesa?» è una stima: sessione occupata con l'ultima chiamata a strumento senza risposta da almeno 2 min.
- Solo macOS provato (il pulsante «Apri terminale» usa Terminal; l'app è per Mac). La pagina gira dove gira Python 3.
- Allineamento con la versione privata dell'autore: a mano.
