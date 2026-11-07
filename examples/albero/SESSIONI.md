# SESSIONI — registro delle sessioni (lo scrive solo il coordinatore)

Una riga per sessione viva. Prima di dare un ordine o un permesso: controllare qui che nessun'altra sessione tocchi
le stesse cose. Sessione chiusa (dopo `/passaggio`) → riga in «Chiuse». Id: `claude agents --json`.

## Aperte
| nome | id | cartella | compito | tocca | da |
|---|---|---|---|---|---|
| COORDINATORE | — | hub | coordinamento, non lavora | hub | AAAA-MM-GG |
| NEGOZIO | abc123 | `progetti/negozio` | pagina prezzi nuova | `progetti/negozio/` | AAAA-MM-GG HH:MM |

## Permessi dati
| data | a chi | cosa | deciso da |
|---|---|---|---|
| AAAA-MM-GG | NEGOZIO | push sul ramo `prezzi`; deploy no | coordinatore |

## Errori e soluzioni (una riga per voce, dagli agenti)
| data | chi | errore | soluzione |
|---|---|---|---|

## Chiuse
- AAAA-MM-GG · NOME (id) — esito in una riga
