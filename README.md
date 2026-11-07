# superagent-method

The way I work with Claude Code, packaged as a plugin: **one coordinator, many agents that never collide, and every result checked before it reaches me**. Fewer tokens per task, because each agent starts from a small, correct context; better work, because nothing is delivered untested.

The texts of the skills and commands are in Italian (the language I work in); this README is in English and Italian.

## What's inside (in order of how much I use it)

| piece | what it does | why it matters |
|---|---|---|
| **Coordinator rule** (`examples/albero/CLAUDE.md`, rule 0) + `SESSIONI.md` + `/superagente` | one fixed session coordinates and does no work itself; agents work one topic each. Three permission levels: free (read, edit and commit inside the task), ask the coordinator (push, shared files, installs, subagents, unplanned work), the coordinator asks the user (production, deletions, outside messages, spending, big changes). A register lists live sessions, what each touches and the permissions given | two agents never touch the same files; the user talks to one place; risky actions always pass through a human |
| **`/passaggio`** and **`/riparti`** | handoff note before `/clear` or before closing a session (also automatically above ~200k tokens of context): task, verified vs assumed state, exact next step, decisions, questions already answered, the agent's own mistakes. `/riparti` resumes from it and checks it against the disk | a session can be cleared at any time without losing what the user said or decided |
| **Knowledge tree** (`examples/albero/`) | a hub with common rules, session register, research log and project list; one folder per project with its own rules and handoff note | each agent starts at its level and goes down only if the task needs it, with `grep` |
| **`generale` skill** + agents `ricercatore`, `costruttore` | phased process: research saved as dated knowledge → report and plan → coordinator approves or sends back → build → test → delivery | research is done once and reused; a plan is approved before tokens go into building |
| **`collaudo` skill** + `skills/collaudo/scripts/controlla_prompt.py` | staged testing before delivery, cheapest first: client questions written before building → build and automatic checks → full paths and cross-checked facts → real browser and phone → blind tests → more rounds only if the user wants | about 3 in 4 defects that blind testers found could have been found earlier, for less |
| **`prova-cieca` skill** + `skills/prova-cieca/scripts/run_blind.sh`, `check_blind.py`, agent `tester-cieco` | blind testers: `claude -p --safe-mode` from an empty folder, web tools only, playing an invented role; a checker confirms each run was really blind | a valid negative restarts the loop; positives are an error filter, not proof |
| **Status line** (`statusline/statusline-consumo.py`) + `/agenti` | 5-hour and weekly usage bars with reset times, context size with a plain warning, optional list of busy agents | you see when a session got too heavy and hand it off |

## Rules the template enforces
Rule 0 (coordinator) plus: learn from every outcome and write it down; evaluate the user's ideas before executing them; never repeat research already logged; **spend tokens well** (an elastic weekly plan split into daily shares, leftovers roll over to the next day, and what is left before the weekly reset gets used, not wasted); ask before deleting, publishing or spending; keep startup files to one-line pointers; hand off above ~200k tokens; don't ask what is already decided; test before blind tests; every number has a date, and the disk wins over documents; for a similar case, reuse the procedure that worked last time; finish a product before starting work on top of it; numbers and thresholds are fixed in the order, before work starts. Agents get a long queue of approved items and work continuously; repeated jobs stop after each round for a spot check; one folder, one agent.

All rules are marked "to be revised": agents report errors and fixes to the coordinator, and the rules change from that log.

## Routines (on request, none automatic)
Morning: the coordinator reports sessions, blocked work, usage against the day's share, three proposals (measured cost: ~0.3-0.5% of a Max week). Evening: pull what changed, check risky results, report done / to approve / blocked. End of the plan week: usage per project, what paid off, errors turned into rules, leftover budget spent on the queue. A cloud routine cannot see local sessions, so routines that read the register run locally.

### Optional: local machine offline during fixed hours
If your computer is offline during the day and the cloud works instead, `examples/albero/STAFFETTA.md` is a daily handoff with three blocks: *today for the cloud* (written before going offline, after pushing everything), *done by the cloud*, *for tonight* (work that needs the local machine: desktop apps, phone, local builds, unpushed files).

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

Without installing the plugin you can also link single skills as personal skills: scripts are referenced relative to each skill's folder, so a symlink works (`ln -s /path/to/superagent-method/skills/prova-cieca ~/.claude/skills/prova-cieca`; `collaudo` expects `prova-cieca` next to it).

## Limits
- Messages between sessions work only for sessions on the same machine; when it is offline, the local coordinator does not answer.
- Visible sessions: the first time a session opens in a folder, Claude Code asks to trust it, and a background session waits there; point at a terminal tab by its id, never "front window"; closing the view does not stop the session.
- Permissions are a written agreement, not a technical lock: an agent can ignore them, which is why the coordinator checks risky work.
- The blind testers still see the account email in their environment; the persona template tells them to ignore it; read the transcript to check they did not use it.
- Claude testers are kinder than people: a passed blind test means "no serious defect found in N runs", not "it works". When the real world can judge the result, that judgement counts more.

---

## Italiano

Il mio modo di lavorare con Claude Code, in un plugin. Al centro un **coordinatore** che non lavora: smista i compiti agli agenti, tiene il registro delle sessioni, dà i permessi e chiede all'utente solo per produzione, cancellazioni, invii, spese e cambi importanti. Intorno: passaggio di consegne fra sessioni (`/passaggio`, `/riparti`), conoscenze ad albero lette per livelli, processo a fasi (`generale`), collaudo a gradini (`collaudo`) e tester ciechi (`prova-cieca`), barra del consumo nel terminale, piano settimanale dei token elastico («token in scadenza: usarli»). Facoltativo: staffetta quotidiana col cloud per chi ha il computer offline di giorno. Installazione: i due comandi `/plugin` qui sopra.

## Research
The evidence behind the blind testers (LLM judge biases, simulated users, how to make an agent really blind in Claude Code, validity checklist, measured costs), with sources: [docs/ricerca.md](docs/ricerca.md) (Italian).

## Credits
Built on published patterns, not invented from scratch: Anthropic's *orchestrator-workers* and *evaluator-optimizer* ([Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)) and the lead-plus-subagents research setup ([multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)); the controller, fresh implementer and bounded fix loop of [obra/superpowers](https://github.com/obra/superpowers) (MIT); the separate `claude -p --safe-mode` process per persona of [claude-persona](https://github.com/takechanman1228/claude-persona) (MIT). What is added here is the wiring: research saved as dated knowledge, a coordinator with permission levels, staged testing, and validity rules for blind testers.

## License

MIT, see [LICENSE](LICENSE).
