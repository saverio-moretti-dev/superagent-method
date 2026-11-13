# Manuale delle campagne: regole e controlli

Tre livelli di regole. In caso di contrasto vince il livello più alto.
1. **Regole globali** (questa pagina + le regole non negoziabili di `SKILL.md`): valgono in ogni campagna.
2. **Regole della sessione**: scelte per un gruppo di campagne (sotto, modello), scritte nella sessione e approvate
   con le schede.
3. **Controlli** per sessione, sovrascrivibili per la singola campagna.

## Regole globali
1. La campagna racconta il protagonista; la consegna è un evento della sua storia (`campagna.md`).
2. Schede decise prima e approvate; il master non inventa fatti, persone, prezzi o condizioni.
3. Il master interpreta il personaggio esterno e il mondo, mai le decisioni del protagonista; non tifa, non rema contro.
4. La flessibilità dell'autore emerge solo se il protagonista la cerca.
5. Il protagonista decide da solo, fa le sue ricerche, dichiara `COSA FACCIO` e `A CHE CONCLUSIONE SONO ARRIVATO`;
   cita una fonte solo se l'ha aperta.
6. Processi separati, nessun canale fra campagne, nessun esito passato a un altro protagonista.
7. Tetto di turni e di chiamate scritto anche nei prompt; interruzione dal tetto o errore dell'API = non valida.
8. Ogni messaggio del master passa dal controllo di fuga (parole vietate) prima di arrivare al protagonista.
9. Il risultato è l'analisi (`campagna.md` § Analisi), non solo la decisione.
10. Un positivo è un filtro di errori, non una prova di riuscita; un negativo valido pesa molto.

## Regole della sessione (modello)
```
Domanda: <cosa si vuole capire>
Consegna e versione: <link o testo, data>
Campagne: <n> · protagonisti: <profili> · stesso personaggio esterno: <scheda v>
Cosa resta fuori dalla storia: <temi che il master non apre e a cui risponde in modo neutro>
Cosa si può dire: <es. prezzi dalla forbice, rate, tempi>
Controlli: <tabella sotto, con i valori scelti>
Tetto di spesa della sessione: <$ o % della settimana>
```

## Controlli
Ogni controllo dice **dove agisce**: sulle schede, sul prompt del master, sul programma che fa girare la campagna.
| Controllo | Valori | Default | Dove agisce |
|---|---|---|---|
| Intensità | turni massimi 2-8 | 6 (oggi in campagna.py) | programma (tetto turni) + prompt |
| Azioni per turno | chiamate a strumenti per turno | 12 (campagna.py); col browser servono almeno 25 (misurato: 10 e 20 non bastano a guardare un sito); livello 1: 30 (run_blind.sh) | programma (sorvegliante) + prompt |
| Casualità | 0 nessuna · 1 imprevisti piccoli del mondo · 2 anche tratti variati dentro limiti dati | 1 | 0-1 prompt del master; 2 schede (variazione decisa e scritta prima del giro, non dal master) |
| Severità | bassa · media · alta | media | **solo schede e mondo**: quante proposte riceve, esperienze cattive passate, budget, tempo, concorrenza. Mai un'istruzione «sii severo» |
| Fedeltà del personaggio esterno | quanto concede: dalla scheda (flessibilità) | dalla scheda | prompt del master |
| Campagne in parallelo | 1-5 | 2 | programma; **col browser una alla volta** |
| Modello | protagonista / master / controllo | sonnet / sonnet / haiku (haiku anche per le prove di fumo); a rischio alto un protagonista su un modello diverso (`dimensionare.md`) | programma |
| Browser | sì / no | sì se la consegna è un sito | programma + frase della scena copiata parola per parola |
| Tetto di spesa | $ o % per sessione | da dichiarare | coordinatore, prima del giro |

Note:
- **Severità**: non è dimostrato che una persona descritta come «severa» giudichi più severamente (`bias.md`).
  Per questo agisce sulla situazione del protagonista, che è verificabile, e il suo effetto **si misura** confrontando
  campagne a severità diversa con lo stesso profilo.
- **Casualità 2**: la variazione dei tratti si decide e si scrive nelle schede prima del giro (così resta tracciata e
  ripetibile); il master non tira dadi sui fatti del protagonista.
- Mai oltre 5 campagne per sessione: più varietà di prospettive, non più copie (`dimensionare.md`).
