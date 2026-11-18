#!/usr/bin/env python3
"""Gera os SVGs dinâmicos do perfil: projetos, estatísticas e contribuições.

Usa só a biblioteca padrão do Python. Variáveis de ambiente:
  GH_TOKEN  token do GitHub (no Actions: secrets.GITHUB_TOKEN)
  GH_USER   usuário do GitHub (no Actions: github.repository_owner)

Só lê dados PÚBLICOS. Não envia nada para fora do GitHub.
Uso local para testar o visual (dados falsos, NÃO publicar):
  python gerar_perfil.py --demo --out ./demo
"""
import argparse
import datetime as dt
import html
import json
import os
import random
import sys
import textwrap
import urllib.request

API = "https://api.github.com"
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
BG = "#0d1117"
BAR = "#0d1117"
BORDER = "#30363d"
TXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#8fb6e0"
GREEN = ACCENT
PURPLE = "#c9d1d9"
BLUE = ACCENT
ORANGE = "#c9d1d9"
YELLOW = "#c9d1d9"
LEVELS = {
    "NONE": "#161b22",
    "FIRST_QUARTILE": "#1c3350",
    "SECOND_QUARTILE": "#2b5282",
    "THIRD_QUARTILE": "#4a7fb8",
    "FOURTH_QUARTILE": "#8fb6e0",
}
LANG_COLORS = {}
FALLBACK = ["#8fb6e0", "#6f94bd", "#8b949e", "#6e7681", "#505a68", "#3a424e"]


def e(s):
    return html.escape(str(s), quote=False)


def now_br():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=-3)))


def window(w, h, title):
    return f"""<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="8" fill="{BG}" stroke="{BORDER}"/>
<line x1="1" y1="40" x2="{w-1}" y2="40" stroke="{BORDER}"/>
<text x="20" y="25" font-size="12" fill="{MUTED}" font-family="{FONT}">{e(title)}</text>"""


def svg(w, h, body, title, desc):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t d">
<title id="t">{e(title)}</title>
<desc id="d">{e(desc)}</desc>
{body}
</svg>
"""


def stamp(w, h):
    d = now_br().strftime("%d/%m/%Y %H:%M")
    return f'<text x="{w-16}" y="{h-10}" text-anchor="end" font-size="10" fill="#484f58" font-family="{FONT}">atualizado em {d}</text>'


# ----------------------------------------------------------------- API
def http(url, token, data=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "perfil-readme-gerador",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def graphql(query, variables, token):
    out = http(API + "/graphql", token, json.dumps({"query": query, "variables": variables}).encode())
    if out.get("errors"):
        raise RuntimeError(f"GraphQL: {out['errors']}")
    return out["data"]


GQL = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}
"""


def fetch_repos(user, token):
    repos = http(f"{API}/users/{user}/repos?per_page=100&sort=pushed&type=owner", token)
    return [r for r in repos if not r.get("fork") and not r.get("private") and r["name"].lower() != user.lower()]


def fetch_languages(repos, token):
    total = {}
    for r in repos:
        try:
            for lang, n in http(r["languages_url"], token).items():
                total[lang] = total.get(lang, 0) + n
        except Exception as exc:  # um repositório com erro não derruba o resto
            print(f"aviso: linguagens de {r['name']}: {exc}", file=sys.stderr)
    return total


def fetch_profile(user, token):
    return http(f"{API}/users/{user}", token)


def streaks(days):
    longest = cur = 0
    for _, c in days:
        if c > 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:  # o dia de hoje ainda pode estar em andamento
        i -= 1
    current = 0
    while i >= 0 and days[i][1] > 0:
        current += 1
        i -= 1
    return current, longest


# ----------------------------------------------------------------- render
def lang_dot(color, x, y, r=5):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'


def render_projects(repos):
    shown = repos[:4]
    W, CW, CH, GAP = 900, 438, 170, 20
    if not shown:
        body = window(W, 140, "~/projetos")
        body += f'<text x="32" y="86" font-size="14" fill="{MUTED}" font-family="{FONT}">// nenhum repositório público ainda</text>'
        return svg(W, 140, body, "Projetos", "Nenhum repositório público ainda."), 140
    rows = (len(shown) + 1) // 2
    H = rows * CH + (rows - 1) * GAP + 22
    body = ""
    for i, r in enumerate(shown):
        x = (i % 2) * (CW + 24)
        y = (i // 2) * (CH + GAP)
        desc = (r.get("description") or "// sem descrição ainda").strip()
        lines = textwrap.wrap(desc, 50)[:2]
        if len(textwrap.wrap(desc, 50)) > 2:
            lines[1] = lines[1][:47].rstrip() + "..."
        lang = r.get("language") or "—"
        color = LANG_COLORS.get(lang, MUTED)
        g = window(CW, CH, "~/projetos")
        g += f'<text x="24" y="76" font-size="16" font-weight="700" fill="{GREEN}" font-family="{FONT}">./{e(r["name"])}</text>'
        for j, ln in enumerate(lines):
            g += f'<text x="24" y="{102 + j*20}" font-size="12.5" fill="{MUTED}" font-family="{FONT}">{e(ln)}</text>'
        g += lang_dot(color, 30, 148) + f'<text x="42" y="152" font-size="12" fill="{MUTED}" font-family="{FONT}">{e(lang)}</text>'
        g += (f'<text x="{CW-24}" y="152" text-anchor="end" font-size="12" fill="{MUTED}" font-family="{FONT}">'
              f'★ {r.get("stargazers_count", 0)}   ·   forks {r.get("forks_count", 0)}</text>')
        body += f'<g transform="translate({x},{y})">{g}</g>'
    body += stamp(W, H)
    return svg(W, H, body, "Projetos", "Repositórios públicos mais recentes."), H


def render_stats(s):
    W, H = 900, 420
    CW = 438
    # --- janela esquerda: stats.sh
    left = window(CW, 270, "stats.sh")
    left += f'<text x="24" y="76" font-size="14" font-family="{FONT}"><tspan fill="{GREEN}">$ </tspan><tspan fill="{TXT}">git stats --ultimo-ano</tspan></text>'
    items = [
        ("commits:", s["commits"], BLUE), ("pull_requests:", s["prs"], BLUE),
        ("issues:", s["issues"], PURPLE), ("repositorios:", s["repos"], GREEN),
        ("estrelas:", s["stars"], YELLOW), ("seguidores:", s["followers"], ORANGE),
    ]
    for i, (k, v, c) in enumerate(items):
        col, row = i % 2, i // 2
        x0 = 24 + col * 206
        y = 128 + row * 46
        left += f'<text x="{x0}" y="{y}" font-size="12.5" fill="{MUTED}" font-family="{FONT}">{k}</text>'
        left += f'<text x="{x0+180}" y="{y}" text-anchor="end" font-size="16" font-weight="700" fill="{TXT}" font-family="{FONT}">{v}</text>'
        left += f'<line x1="{x0}" y1="{y+10}" x2="{x0+180}" y2="{y+10}" stroke="{BORDER}"/>'
    # --- janela direita: linguagens.json
    right = window(CW, 270, "linguagens.json")
    right += f'<text x="24" y="76" font-size="14" font-family="{FONT}"><tspan fill="{GREEN}">$ </tspan><tspan fill="{TXT}">linguist --top 6</tspan></text>'
    langs = s["langs"]
    bx, bw = 24, CW - 48
    right += f'<clipPath id="bar"><rect x="{bx}" y="98" width="{bw}" height="8" rx="4"/></clipPath><g clip-path="url(#bar)">'
    pos = bx
    for i, (name, pct) in enumerate(langs):
        c = LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])
        wdt = bw * pct / 100
        right += f'<rect x="{pos:.1f}" y="98" width="{wdt:.1f}" height="8" fill="{c}"/>'
        pos += wdt
    right += "</g>"
    if not langs:
        right += f'<text x="24" y="150" font-size="12.5" fill="{MUTED}" font-family="{FONT}">// sem dados de linguagem ainda</text>'
    for i, (name, pct) in enumerate(langs):
        col, row = i % 2, i // 2
        x0 = 24 + col * 206
        y = 146 + row * 38
        c = LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])
        right += lang_dot(c, x0 + 5, y - 4)
        right += f'<text x="{x0+18}" y="{y}" font-size="12" fill="{TXT}" font-family="{FONT}">{e(name)}</text>'
        right += f'<text x="{x0+180}" y="{y}" text-anchor="end" font-size="12" fill="{MUTED}" font-family="{FONT}">{pct:.1f}%</text>'
    body = left + f'<g transform="translate({CW+24},0)">{right}</g>'
    # --- linha de baixo: total | sequência atual | maior sequência
    y0 = 300
    body += f'<rect x="0.5" y="288.5" width="{W-1}" height="111" rx="8" fill="{BG}" stroke="{BORDER}"/>'
    body += f'<line x1="300" y1="{y0}" x2="300" y2="{y0+90}" stroke="{BORDER}"/><line x1="600" y1="{y0}" x2="600" y2="{y0+90}" stroke="{BORDER}"/>'
    body += f'<text x="150" y="{y0+44}" text-anchor="middle" font-size="40" font-weight="800" fill="{TXT}" font-family="{FONT}">{s["total"]}</text>'
    body += f'<text x="150" y="{y0+72}" text-anchor="middle" font-size="12" fill="{MUTED}" font-family="{FONT}">contribuições no último ano</text>'
    body += f'<circle cx="450" cy="{y0+38}" r="34" fill="none" stroke="#21262d" stroke-width="6"/>'
    body += f'<circle cx="450" cy="{y0+38}" r="34" fill="none" stroke="{GREEN}" stroke-width="6" stroke-dasharray="190 24" stroke-linecap="round" transform="rotate(-90 450 {y0+38})"/>'
    body += f'<text x="450" y="{y0+49}" text-anchor="middle" font-size="30" font-weight="800" fill="{TXT}" font-family="{FONT}">{s["current"]}</text>'
    body += f'<text x="450" y="{y0+90}" text-anchor="middle" font-size="12" fill="{MUTED}" font-family="{FONT}">dias de sequência atual</text>'
    body += f'<text x="750" y="{y0+44}" text-anchor="middle" font-size="40" font-weight="800" fill="{TXT}" font-family="{FONT}">{s["longest"]}</text>'
    body += f'<text x="750" y="{y0+72}" text-anchor="middle" font-size="12" fill="{MUTED}" font-family="{FONT}">maior sequência (dias)</text>'
    body += stamp(W, H)
    return svg(W, H, body, "Estatísticas do GitHub",
               "Commits, pull requests, issues, repositórios, estrelas, seguidores, linguagens e sequências de contribuição."), H


def render_contrib(weeks, total, user):
    W, H = 900, 270
    body = window(W, H, f"contribuicoes.bin — compilando @{user}")
    body += f'<text x="24" y="70" font-size="13" font-family="{FONT}"><tspan fill="{GREEN}">$ </tspan><tspan fill="{TXT}">git log --since="1 ano" | compilar --binario</tspan></text>'
    ox, oy, step, cell = 60, 112, 15, 12
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    last_month = None
    for wi, wk in enumerate(weeks):
        days = wk["contributionDays"]
        if days:
            d = dt.date.fromisoformat(days[0]["date"])
            if d.month != last_month and wi < len(weeks) - 1:
                body += f'<text x="{ox + wi*step}" y="102" font-size="10" fill="{MUTED}" font-family="{FONT}">{meses[d.month-1]}</text>'
                last_month = d.month
        for day in days:
            c = LEVELS.get(day["contributionLevel"], LEVELS["NONE"])
            body += f'<rect x="{ox + wi*step}" y="{oy + day["weekday"]*step}" width="{cell}" height="{cell}" rx="3" fill="{c}"/>'
    for label, row in (("seg", 1), ("qua", 3), ("sex", 5)):
        body += f'<text x="24" y="{oy + row*step + 10}" font-size="10" fill="{MUTED}" font-family="{FONT}">{label}</text>'
    body += (f'<text x="24" y="242" font-size="13" font-family="{FONT}" style="white-space:pre">'
             f'<tspan fill="{GREEN}">✓ </tspan><tspan fill="{TXT}">{total} contribuições compiladas</tspan>'
             f'<tspan fill="{MUTED}"> · 0 erros · 0 warnings</tspan></text>')
    body += stamp(W, H)
    return svg(W, H, body, "Contribuições", f"Calendário de contribuições de @{user} no último ano."), H


def placeholder(title, msg, h=140):
    W = 900
    body = window(W, h, title)
    body += f'<text x="32" y="86" font-size="14" fill="{MUTED}" font-family="{FONT}">{e(msg)}</text>'
    return svg(W, h, body, title, msg)


# ----------------------------------------------------------------- dados
def build_stats(user, token):
    prof = fetch_profile(user, token)
    repos = fetch_repos(user, token)
    gql = graphql(GQL, {"login": user}, token)["user"]
    cc = gql["contributionsCollection"]
    cal = cc["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort()
    cur, lon = streaks(days)
    langs_raw = fetch_languages(repos, token)
    tot = sum(langs_raw.values()) or 1
    top = sorted(langs_raw.items(), key=lambda kv: kv[1], reverse=True)[:6]
    langs = [(k, v * 100 / tot) for k, v in top]
    stats = {
        "commits": cc["totalCommitContributions"], "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"], "repos": prof.get("public_repos", len(repos)),
        "stars": sum(r.get("stargazers_count", 0) for r in repos),
        "followers": gql["followers"]["totalCount"], "total": cal["totalContributions"],
        "current": cur, "longest": lon, "langs": langs,
    }
    return stats, repos, cal["weeks"]


def demo_data():
    rnd = random.Random(7)
    start = dt.date.today() - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # domingo
    weeks, d = [], start
    while d <= dt.date.today():
        days = []
        for _ in range(7):
            if d > dt.date.today():
                break
            n = rnd.choice([0, 0, 0, 0, 1, 2, 4, 7]) if d.month in (8, 9, 10, 11) else 0
            lvl = "NONE" if n == 0 else ["FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"][min(3, (n - 1) // 2)]
            days.append({"date": d.isoformat(), "weekday": (d.weekday() + 1) % 7, "contributionCount": n, "contributionLevel": lvl})
            d += dt.timedelta(days=1)
        weeks.append({"contributionDays": days})
    flat = [(x["date"], x["contributionCount"]) for w in weeks for x in w["contributionDays"]]
    cur, lon = streaks(flat)
    stats = {"commits": 123, "prs": 4, "issues": 1, "repos": 3, "stars": 2, "followers": 5,
             "total": sum(c for _, c in flat), "current": cur, "longest": lon,
             "langs": [("TypeScript", 52.3), ("Python", 24.1), ("HTML", 12.8), ("Swift", 6.4), ("Shell", 3.1), ("CSS", 1.3)]}
    repos = [
        {"name": "tryv-backend", "description": "Backend e app do Tryv Fit: treino, saúde e Vitalidade para iOS.", "language": "TypeScript", "stargazers_count": 0, "forks_count": 0},
        {"name": "projeto-sem-descricao", "description": None, "language": "Python", "stargazers_count": 1, "forks_count": 0},
    ]
    return stats, repos, weeks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    user = os.environ.get("GH_USER", "usuario")
    token = os.environ.get("GH_TOKEN", "")
    errors = []

    def write(name, content):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.write(content)
        print("escrito", name)

    if a.demo:
        stats, repos, weeks = demo_data()
        user = "danielcollazo1305"
    else:
        try:
            stats, repos, weeks = build_stats(user, token)
        except Exception as exc:
            print(f"ERRO ao buscar dados: {exc}", file=sys.stderr)
            sys.exit(1)

    for name, fn in (
        ("projects.svg", lambda: render_projects(repos)[0]),
        ("stats.svg", lambda: render_stats(stats)[0]),
        ("contributions.svg", lambda: render_contrib(weeks, stats["total"], user)[0]),
    ):
        try:
            write(name, fn())
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            print(f"ERRO ao gerar {name}: {exc}", file=sys.stderr)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
