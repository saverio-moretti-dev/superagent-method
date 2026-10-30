# superagent-method

The way I work with Claude Code, packaged as a plugin: **fewer tokens per task and better work**, because every agent starts from the right, small context and every result is checked before it reaches me.

The texts of the skills and commands are in Italian (the language I work in); this README is in English and Italian.

## What's inside

| piece | what it does | why it saves tokens or raises quality |
|---|---|---|
| **Knowledge tree** (`examples/albero/`) | knowledge split in levels: a hub with common rules, research log and project list; one folder per project with its own rules and handoff note | each agent starts at its project level and goes down only if the task needs it, with `grep`, never reading everything |
| **`/superagente`** | rebuilds the coordinator in a clean session: hub state, open questions, usage, optional project context; then waits | the coordinator knows the big picture, routes tasks to project agents and checks deliveries |
| **`/passaggio`** | writes a handoff note before `/clear`: task, verified vs assumed state, exact next step, decisions, questions already answered, the agent's own mistakes | a session can be cleared at any time without losing what the user said or decided |
| **`/riparti`** | resumes from that note, checks it against the disk (the disk wins), digs into the vague points, then acts | no re-asking answered questions, no repeating corrected mistakes |
| **`generale` skill** + agents `ricercatore`, `costruttore` | phased process: research saved as dated knowledge → report and plan → coordinator approves or sends back → build → blind tests → delivery | research is done once and reused; a plan is approved before tokens go into building |
| **`prova-cieca` skill** + `scripts/run_blind.sh`, `check_blind.py`, agent `tester-cieco` | blind testers: `claude -p --safe-mode` from an empty folder, web tools only, playing an invented role (a sceptical employer, a client); a checker confirms each run was really blind | a valid negative restarts the loop; positives are treated as an error filter, not as proof |
| **Status line** (`statusline/statusline-consumo.py`) + `/agenti` | 5-hour and weekly usage bars with reset times, context size of the session with a plain warning ("heavy session, restart"), optional list of busy agents | you see when a session got too expensive and hand it off instead of dragging it on |

Rules the method enforces (see `examples/albero/CLAUDE.md`): learn from every outcome and write it down; evaluate the user's ideas before executing them; never repeat a research already in the log; estimate costly tasks in % of session and week before starting; always ask before deleting, publishing or spending.

## Install

```
/plugin marketplace add saverio-moretti-dev/superagent-method
/plugin install superagent-method@superagent-method
```

Then:
- copy `examples/albero/` where you want your hub, and set `SUPERAGENT_HUB` to that folder (or start Claude Code from it);
- status line (optional, not installed automatically): in `~/.claude/settings.json`
  `"statusLine": {"type": "command", "command": "python3 /path/to/statusline/statusline-consumo.py", "refreshInterval": 20}`.
  It also writes `~/.claude/consumo/limiti.csv`, the usage log read by `/superagente` and by
  [dont-waste-your-token](https://github.com/saverio-moretti-dev/dont-waste-your-token);
- blind tests need the `claude` CLI on the PATH.

Handoff notes are saved in `~/.claude/passaggi/`.

## Limits
- The blind testers still see the account email in their environment; the persona template tells them to ignore it; read the transcript to check they did not use it.
- Claude testers are kinder than people: a passed blind test means "no serious defect found in N runs", not "it works". When the real world can judge the result (a CV sent to a company), that judgement counts more.

---

## Italiano

Il mio modo di lavorare con Claude Code, in un plugin: **meno token per compito e lavoro migliore**. Conoscenze ad albero lette per livelli, un superagente che coordina e controlla, passaggio di consegne fra sessioni (`/passaggio`, `/riparti`), processo a fasi con ricerca salvata e piano approvato (`generale`), tester ciechi per collaudare le consegne (`prova-cieca`), barra del consumo nel terminale. Installazione: i due comandi `/plugin` qui sopra.

## License

MIT, see [LICENSE](LICENSE).
