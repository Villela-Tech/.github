"""Gera os cards de estatísticas da organização Villela-Tech, incluindo os
repositórios privados, sem expor nomes de repositório, código ou mensagens.

  org-stats.svg      repositórios, commits, PRs aceitos e projetos ativos (12 meses)
  org-languages.svg  linguagens mais usadas

Uso: GITHUB_TOKEN=... python3 .github/scripts/org_stats.py [pasta_de_saida]
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

ORG = "Villela-Tech"
TOKEN = os.environ["GITHUB_TOKEN"]
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
SINCE = datetime.now(timezone.utc) - timedelta(days=365)
LIMIT = 8

# Cópias de projetos de terceiros: distorceriam os números do que é feito aqui.
SKIP_REPOS = {"Chat-woot", "krayin"}
SKIP_LANGUAGES = {"Dockerfile", "Makefile", "Procfile", "Batchfile"}
BOTS = ("[bot]",)

COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5",
    "PHP": "#4F5D95", "HTML": "#e34c26", "CSS": "#663399", "Shell": "#89e051",
    "C++": "#f34b7d", "Ruby": "#701516", "Blade": "#f7523f", "PLpgSQL": "#336790",
    "Vue": "#41b883", "SCSS": "#c6538c", "Java": "#b07219", "Go": "#00ADD8",
    "C#": "#178600", "Hack": "#878787", "TSQL": "#e38c00",
}

FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
BLUE = "#2F80ED"
GRAY = "#8b949e"


def get(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp), resp.headers.get("Link", "")
    except urllib.error.HTTPError as e:
        if e.code == 409:  # repositório vazio
            return [], ""
        raise


def paginate(url):
    items = []
    while url:
        page, link = get(url)
        items += page
        url = next((p.split(";")[0].strip("<> ") for p in link.split(",")
                    if 'rel="next"' in p), None)
    return items


def collect():
    repos = [r for r in paginate(f"https://api.github.com/orgs/{ORG}/repos?type=all&per_page=100")
             if not r["fork"] and r["name"] not in SKIP_REPOS]
    since = SINCE.strftime("%Y-%m-%dT%H:%M:%SZ")
    commits, prs, active, languages = 0, 0, 0, {}

    for repo in repos:
        name = repo["full_name"]
        repo_commits = 0
        for c in paginate(f"https://api.github.com/repos/{name}/commits?since={since}&per_page=100"):
            login = (c.get("author") or {}).get("login") or ""
            if not login.endswith(BOTS):
                repo_commits += 1
        commits += repo_commits
        active += repo_commits > 0

        for pr in paginate(f"https://api.github.com/repos/{name}/pulls?state=closed&sort=updated"
                           f"&direction=desc&per_page=100"):
            if pr["merged_at"] and pr["merged_at"] >= since:
                prs += 1

        langs, _ = get(repo["languages_url"])
        for lang, size in (langs or {}).items():
            if lang not in SKIP_LANGUAGES:
                languages[lang] = languages.get(lang, 0) + size

    return {
        "repos": len(repos),
        "private": sum(r["private"] for r in repos),
        "commits": commits,
        "prs": prs,
        "active": active,
        "languages": languages,
    }


def fmt(n):
    return f"{n:,}".replace(",", ".")


def stats_svg(s):
    tiles = [
        ("Repositórios", fmt(s["repos"]), f'{s["private"]} privados'),
        ("Commits", fmt(s["commits"]), "últimos 12 meses"),
        ("Pull requests aceitos", fmt(s["prs"]), "últimos 12 meses"),
        ("Projetos ativos", fmt(s["active"]), "com commits nos últimos 12 meses"),
    ]
    cells = []
    for i, (label, value, note) in enumerate(tiles):
        x = 20 + (i % 2) * 230
        y = 62 + (i // 2) * 78
        cells.append(
            f'<text x="{x}" y="{y}" class="label">{escape(label)}</text>'
            f'<text x="{x}" y="{y + 34}" class="value">{value}</text>'
            f'<text x="{x}" y="{y + 54}" class="note">{escape(note)}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="230" viewBox="0 0 480 230">
<style>
  .title {{ font: 600 16px {FONT}; fill: {BLUE}; }}
  .label {{ font: 400 14px {FONT}; fill: {GRAY}; }}
  .value {{ font: 700 30px {FONT}; fill: {BLUE}; }}
  .note {{ font: 400 12px {FONT}; fill: {GRAY}; }}
</style>
<text x="20" y="32" class="title">Villela Tech em números</text>
{"".join(cells)}
</svg>
'''


def languages_svg(languages):
    total = sum(languages.values()) or 1
    rows = [(lang, size / total * 100)
            for lang, size in sorted(languages.items(), key=lambda kv: kv[1], reverse=True)[:LIMIT]]
    bar_w, pad = 440, 20
    height = 92 + ((len(rows) + 1) // 2) * 26
    shown = sum(p for _, p in rows) or 1
    parts, x = [], pad
    for lang, pct in rows:
        w = bar_w * pct / shown
        parts.append(f'<rect x="{x:.2f}" y="52" width="{w:.2f}" height="10" '
                     f'fill="{COLORS.get(lang, "#959da5")}"/>')
        x += w
    legend = []
    for i, (lang, pct) in enumerate(rows):
        lx, ly = pad + (i % 2) * 220, 92 + (i // 2) * 26
        legend.append(
            f'<circle cx="{lx + 6}" cy="{ly - 4}" r="5" fill="{COLORS.get(lang, "#959da5")}"/>'
            f'<text x="{lx + 18}" y="{ly}" class="lang">{escape(lang)}</text>'
            f'<text x="{lx + 200}" y="{ly}" class="pct" text-anchor="end">{pct:.1f}%</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="{height}" viewBox="0 0 480 {height}">
<style>
  .title {{ font: 600 16px {FONT}; fill: {BLUE}; }}
  .lang {{ font: 400 14px {FONT}; fill: {GRAY}; }}
  .pct {{ font: 600 14px {FONT}; fill: {GRAY}; }}
</style>
<text x="{pad}" y="32" class="title">Linguagens mais usadas</text>
<clipPath id="bar"><rect x="{pad}" y="52" width="{bar_w}" height="10" rx="5"/></clipPath>
<g clip-path="url(#bar)">{"".join(parts)}</g>
{"".join(legend)}
</svg>
'''


def main():
    s = collect()
    with open(os.path.join(OUT_DIR, "org-stats.svg"), "w") as f:
        f.write(stats_svg(s))
    with open(os.path.join(OUT_DIR, "org-languages.svg"), "w") as f:
        f.write(languages_svg(s["languages"]))
    print({k: v for k, v in s.items() if k != "languages"})


if __name__ == "__main__":
    main()
