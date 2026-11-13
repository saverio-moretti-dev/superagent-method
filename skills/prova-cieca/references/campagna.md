# Campagne (livelli 2-3): la storia del protagonista

Una campagna non «testa una consegna». **Racconta un pezzo della vita di una persona** (il protagonista) e
guarda cosa succede quando, per caso, la consegna entra nella sua storia. La consegna è un evento della
storia, non il suo argomento. Il risultato è l'analisi di come è andata, non un voto.

## Le parole
- **Sessione di campagne**: un gruppo di campagne preparate insieme, con la stessa domanda, le stesse regole di
  sessione e lo stesso personaggio esterno. Esempio: «tre titolari diversi ricevono lo stesso link».
- **Campagna**: una partita a due, master e protagonista, in processi separati. Un protagonista per campagna.
- **Protagonista**: il tester. Decide da solo; conosce solo la propria storia.
- **Personaggio esterno**: l'autore della consegna come compare nella storia (chi propone il sito, il servizio, il
  testo). Lo interpreta il master, solo dalla sua scheda. Il protagonista lo incontra per caso.
- **Master**: interpreta il personaggio esterno e il mondo (tempi, imprevisti, terze persone). Mai il protagonista.
- **Schede**: decise **prima** della sessione, mai improvvisate dal master (`schede.md`).
- **Manuale**: regole globali (sempre) + regole della sessione + controlli (`manuale.md`).

## L'arco di ogni campagna
| Momento | Cosa contiene | Chi lo scrive |
|---|---|---|
| **Prima** (era X) | la vita del protagonista fino a ieri: lavoro, scelte, soldi, esperienze buone e cattive | scheda del protagonista |
| **Adesso** (è Y) | cosa lo preoccupa oggi, cosa vorrebbe, cosa ha già provato, quanto tempo e quanti soldi ha | scheda del protagonista |
| **La situazione** | come la consegna gli arriva: chi gliela porta, con quali parole, cosa riceve (un link, un foglio) | scheda della scena |
| **Svolgimento** | i turni: il protagonista agisce, il mondo e il personaggio esterno rispondono | protagonista e master |
| **Esito** (andrà Z) | dove arriva la storia: decide, aspetta, lascia perdere | protagonista |

La storia di partenza deve essere **fatta bene**: concreta, coerente, con una vita propria anche senza la
consegna. Il personaggio esterno nella storia di partenza occupa una riga (il canale), non un paragrafo.

## Preparazione (prima di spendere per giocare)
1. **Domanda della sessione**: cosa si vuole capire (es. «un titolare che non ha mai pensato a un sito, davanti
   a questa demo, cosa fa?»). La domanda resta al coordinatore e al master, mai al protagonista.
2. **Schede**: una per protagonista, una del personaggio esterno, una della scena (`schede.md`). Il coordinatore
   le prepara con l'autore e con gli agenti coinvolti; si possono generare a pezzi, ma si approvano tutte.
3. **Regole della sessione e controlli** (`manuale.md`).
4. **Controllo di completezza**: una scheda in bozza, con campi obbligatori vuoti o con frasi dedotte non
   confermate dall'autore, blocca la sessione. Si gioca solo con schede approvate.
5. **Stima del costo** dichiarata prima del giro (come per ogni prova cieca).

## I turni
1. **Turno 1, il master apre**: manda al protagonista la storia scritta dalla sua scheda (Prima + Adesso) e la
   situazione della scena, **parola per parola dove la scheda lo chiede** (es. il link, il messaggio dell'amico,
   l'indicazione di usare il browser). Può solo mettere in scena l'arrivo; non cambia i fatti della scheda.
2. **Il protagonista agisce**: cerca, guarda, prova, ragiona, poi dichiara
   `COSA FACCIO` (l'azione concreta: il testo della mail, cosa chiede, cosa cerca) e
   `A CHE CONCLUSIONE SONO ARRIVATO` (due righe, dette dal personaggio). Contattare chi propone è un'azione.
3. **Il master risponde**: come il personaggio esterno (dalla sua scheda) e come il mondo. Risponde **solo a ciò
   che il protagonista ha fatto**: la flessibilità dell'autore (sconti, rate, cose su misura, alternative) entra
   nella storia solo se il protagonista la cerca. Dove la scheda non basta: risposta neutra e **buco**.
4. **Si ripete** fino a `DECISIONE: COMPRO | LASCIO` o al tetto di turni (`DECISIONE: ASPETTO` + cosa manca).
5. **Il master chiude** con le note private e il resoconto; il coordinatore scrive l'analisi.

## Prezzi e condizioni
Il master li dà **solo dalla scheda del personaggio esterno**: forbice, minimo accettabile, cosa è possibile
(rate, sconti, lavori su misura) e cosa no. Se la scheda dice che il prezzo lo propone il master, lo propone dentro
la forbice, coerente con ciò che il protagonista ha chiesto, e lo segna nelle note. Mai prezzi o condizioni che la
scheda non dà. Il protagonista valuta i prezzi con le sue ricerche, come farebbe davvero.

## L'analisi finale (formato fisso)
La scrive il coordinatore (o l'agente del progetto) da partita, note private e resoconto del master.
1. **La storia in breve**: era X, era Y, è arrivata la situazione, è andata Z (decisione e turno).
2. **Punti di svolta**: turno, cosa è successo, perché il protagonista ha cambiato idea (con le sue parole).
3. **Cosa della consegna ha pesato**, a favore e contro, con il punto preciso.
4. **Cosa del personaggio esterno ha pesato**: risposte, tempi, prezzo, flessibilità chiesta e concessa.
5. **Domande e dubbi del protagonista** che sono rimasti aperti.
6. **Le informazioni sull'autore sono bastate?** Buchi: cosa la scheda del personaggio esterno non diceva → domande
   all'autore prima del prossimo giro (con l'esperienza di più giri la scheda si affina).
7. **Fedeltà del master**: ha promesso cose fuori scheda? più morbido o più duro del vero?
8. **Validità** (`validita.md`) e, per il browser, schermate fatte.
9. **Cosa avrebbe cambiato l'esito**: ipotesi, segnate come ipotesi.
10. **Cosa fare adesso**: correzioni alla consegna, domande all'autore, campagne da rifare.

Più campagne della stessa sessione non si mediano: si confrontano le storie (perché uno ha contattato e l'altro no).

## Più avanti (non ora)
`scripts/campagna.py` va ancora allineato: oggi il suo prompt del primo turno chiede al master di scrivere la storia;
finché non è aggiornato, il contesto del master deve contenere le schede e la regola «non cambi i fatti delle schede».

Campagne interattive: dopo ogni turno l'autore stesso risponde al posto del master, da una pagina dedicata.

## Regole già valide che restano
- Un tester vive solo nella propria campagna; master e protagonista in processi separati; nessun canale fra campagne.
- **Stesso master per più campagne** = stessa scheda e stesso contesto, ma un processo per campagna.
- Campagna interrotta dal tetto di chiamate o da un errore dell'API = **non valida**, non un esito.
- Ogni chiamata a strumenti conta nel tetto; il tetto è scritto anche nel prompt.
- Il protagonista non sa di essere in una prova e non riceve nulla della situazione reale dell'autore.
