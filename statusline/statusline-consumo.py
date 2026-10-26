#!/usr/bin/env python3
# Claude Code status line — "consumo" template.
#
# Line 1:  ━━━━────── 42% 5h 18:00   ━─────── 13% 7d mer 22:00   85K token/sessione - sessione leggera
# Lines 2+ (only when ~/.claude/consumo/.barra-agenti exists, toggled by /agenti):
#          ● name — short task ………  120K      (● busy, ○ idle)
#
# Also keeps the plan-usage log dont-waste-your-token reads (github.com/saverio-moretti-dev/dont-waste-your-token):
#   ~/.claude/consumo/limiti-ultimo.json   latest reading
#   ~/.claude/consumo/limiti.csv           one row each time a value changes
# No network, no model calls. Settings: {"type":"command","command":"python3 <this file>","refreshInterval":20}
import datetime, glob, json, os, sys

HOME = os.path.expanduser('~')
CONSUMO = os.environ.get('SB_CONSUMO_DIR') or os.path.join(HOME, '.claude', 'consumo')
FLAG_AGENTI = os.path.join(CONSUMO, '.barra-agenti')

# Context-size scale (tokens re-sent every turn). Baseline after /clear here is ~70-80K
# (system prompt + tools + CLAUDE.md), so the steps start above it; past 200K the request
# enters the long-context tier (billed higher). Rationale in the README.
SCALA = [  # (upper bound, 256-color, phrase)
    (100_000, 70,  'sessione leggera'),
    (130_000, 148, 'sessione normale'),
    (160_000, 220, 'sessione media'),
    (200_000, 208, 'sessione pesante, riparti'),
    (None,    196, 'STOP: la sessione consuma troppo, devi ripartire'),
]
COL_5H, COL_7D, COL_VUOTO, COL_TENUE = 75, 141, 239, 245
LARGHEZZA = 10
GIORNI = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom']


def c(code, s):
    return f'\033[38;5;{code}m{s}\033[0m'


def barra(pct, colore):
    pieni = max(0, min(LARGHEZZA, round(pct / 100 * LARGHEZZA)))
    return c(colore, '━' * pieni) + c(COL_VUOTO, '─' * (LARGHEZZA - pieni))


def gradino(tokens):
    for limite, colore, frase in SCALA:
        if limite is None or tokens < limite:
            return colore, frase


def k(tokens):
    return f'{round(tokens / 1000)}K'


def tokens_da_transcript(path):
    """Context size of the last assistant turn = input + cache_creation + cache_read."""
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 400_000))
            righe = f.read().decode('utf-8', 'ignore').splitlines()
    except OSError:
        return None
    for r in reversed(righe):
        if '"usage"' not in r:
            continue
        try:
            u = json.loads(r)['message']['usage']
        except (ValueError, KeyError, TypeError):
            continue
        return (u.get('input_tokens') or 0) + (u.get('cache_creation_input_tokens') or 0) \
            + (u.get('cache_read_input_tokens') or 0)
    return None


def tokens_contesto(inp):
    cu = (inp.get('context_window') or {}).get('current_usage') or {}
    if cu:
        return (cu.get('input_tokens') or 0) + (cu.get('cache_creation_input_tokens') or 0) \
            + (cu.get('cache_read_input_tokens') or 0)
    tp = inp.get('transcript_path')
    return tokens_da_transcript(tp) if tp else None


def num(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def registra_limiti(inp, five, week):
    """Same files and format read by dont-waste-your-token."""
    try:
        os.makedirs(CONSUMO, exist_ok=True)
        ora = datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')
        tmp = os.path.join(CONSUMO, 'limiti-ultimo.json.tmp')
        with open(tmp, 'w') as f:
            json.dump({'ora': ora, 'rate_limits': inp.get('rate_limits'), 'session_id': inp.get('session_id')},
                      f, separators=(',', ':'))
        os.replace(tmp, os.path.join(CONSUMO, 'limiti-ultimo.json'))
        chiave_f = os.path.join(CONSUMO, '.limiti-chiave')
        chiave = f'{num(five) if five is not None else ""}|{num(week) if week is not None else ""}'
        try:
            vecchia = open(chiave_f).read()
        except OSError:
            vecchia = None
        if chiave != vecchia:
            csv = os.path.join(CONSUMO, 'limiti.csv')
            rl = inp.get('rate_limits') or {}
            r5 = (rl.get('five_hour') or {}).get('resets_at', '')
            r7 = (rl.get('seven_day') or {}).get('resets_at', '')
            nuovo = not os.path.exists(csv)
            with open(csv, 'a') as f:
                if nuovo:
                    f.write('ora,sessione_5h_pct,settimana_7d_pct,ripristino_5h,ripristino_7d\n')
                f.write(f'{ora},{chiave.replace("|", ",")},{num(r5)},{num(r7)}\n')
            with open(chiave_f, 'w') as f:
                f.write(chiave)
    except OSError:
        pass


def orario(epoch, con_giorno):
    try:
        d = datetime.datetime.fromtimestamp(float(epoch))
    except (TypeError, ValueError):
        return ''
    return f'{GIORNI[d.weekday()]} {d:%H:%M}' if con_giorno else f'{d:%H:%M}'


def pezzo_limite(lim, etichetta, colore, con_giorno):
    if not lim or lim.get('used_percentage') is None:
        return None
    pct = float(lim['used_percentage'])
    reset = orario(lim.get('resets_at'), con_giorno)
    return f'{barra(pct, colore)} {round(pct)}% {c(COL_TENUE, etichetta + (" " + reset if reset else ""))}'


def righe_agenti(mio_id):
    righe = []
    for f in glob.glob(os.path.join(HOME, '.claude', 'sessions', '*.json')):
        try:
            s = json.load(open(f))
            os.kill(int(s['pid']), 0)  # alive?
        except (OSError, ValueError, KeyError, TypeError):
            continue
        sid = s.get('sessionId', '')
        tr = glob.glob(os.path.join(HOME, '.claude', 'projects', '*', sid + '.jsonl'))
        tokens = tokens_da_transcript(tr[0]) if tr else None
        # task label: written by the agent itself (etichetta-compito.py hook), else Claude Code's
        # auto title; never the raw prompt
        try:
            compito = open(os.path.join(CONSUMO, 'compiti', sid + '.txt')).read()
        except OSError:
            compito = ''
        if not compito and tr:
            try:
                with open(tr[0], 'rb') as fh:
                    fh.seek(0, 2)
                    fh.seek(max(0, fh.tell() - 400_000))
                    for r in reversed(fh.read().decode('utf-8', 'ignore').splitlines()):
                        if '"ai-title"' in r:
                            compito = json.loads(r).get('aiTitle', '')
                            break
            except (OSError, ValueError):
                pass
        compito = ' '.join(compito.split())
        if len(compito) > 40:
            compito = compito[:39] + '…'
        nome = s.get('name') or os.path.basename(s.get('cwd', '')) or sid[:8]
        attivo = s.get('status') == 'busy'
        simbolo = c(70, '●') if attivo else c(COL_TENUE, '○')
        tok = c(gradino(tokens)[0], k(tokens)) if tokens else c(COL_TENUE, '—')
        io = c(COL_TENUE, ' (tu)') if sid == mio_id else ''
        righe.append((not attivo, nome.lower(),
                      f'{simbolo} {nome}{io} {c(COL_TENUE, "— " + compito) if compito else ""}  {tok}'))
    if not righe:
        return [c(COL_TENUE, 'nessun agente attivo')]
    return [r[2] for r in sorted(righe)]


def main():
    try:
        inp = json.loads(sys.stdin.read() or '{}')
    except ValueError:
        inp = {}
    rl = inp.get('rate_limits') or {}
    five = (rl.get('five_hour') or {}).get('used_percentage')
    week = (rl.get('seven_day') or {}).get('used_percentage')
    if five is not None or week is not None:
        registra_limiti(inp, five, week)

    pezzi = [p for p in (pezzo_limite(rl.get('five_hour'), '5h', COL_5H, False),
                         pezzo_limite(rl.get('seven_day'), '7d', COL_7D, True)) if p]
    tok = tokens_contesto(inp)
    if tok:
        colore, frase = gradino(tok)
        pezzi.append(c(colore, f'{k(tok)} token/sessione - {frase}'))
    print('   '.join(pezzi) if pezzi else c(COL_TENUE, 'consumo: in attesa del primo messaggio'))
    if os.path.exists(FLAG_AGENTI):
        for r in righe_agenti(inp.get('session_id')):
            print(r)


if __name__ == '__main__':
    main()
