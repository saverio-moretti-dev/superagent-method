---
description: Mostra/nasconde nella barra del terminale la lista degli agenti al lavoro
allowed-tools: Bash
---
!`f="$HOME/.claude/consumo/.barra-agenti"; if [ -e "$f" ]; then rm "$f" && echo "Barra agenti: SPENTA"; else mkdir -p "$(dirname "$f")" && touch "$f" && echo "Barra agenti: ACCESA"; fi`

Rispondi solo con la riga qui sopra, nient'altro. Non usare strumenti.
