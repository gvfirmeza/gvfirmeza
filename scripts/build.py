"""Builds assets/card.svg for the GitHub profile README.

Standard library only, run by hand: `python scripts/build.py`.
With a token in GH_TOKEN it first refreshes data/stats.json (company,
location, top languages) from the GitHub API; without one it uses the saved file.
"""

import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

LOGIN = "gvfirmeza"
ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "data" / "stats.json"
ICONS = ROOT / "scripts" / "icons.json"
SPRITE = ROOT / "assets" / "computer-sheet.png"  # 36 frames side by side
FRAMES, FW, FH = 36, 322, 284
OUT = ROOT / "assets" / "card.svg"

# ---------------------------------------------------------------- data

def graphql(token, query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-readme-builder"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch(token):
    base = graphql(token, """
      query($login: String!) {
        user(login: $login) {
          createdAt company location
          followers { totalCount }
          repositories(ownerAffiliations: OWNER, isFork: false, first: 100, privacy: PUBLIC) {
            totalCount
            nodes {
              stargazerCount
              languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                edges { size node { name } }
              }
            }
          }
        }
      }""", {"login": LOGIN})["user"]

    # commits: one contributionsCollection per year since the account was created
    start = int(base["createdAt"][:4])
    now = datetime.now(timezone.utc)
    parts = []
    for y in range(start, now.year + 1):
        to = now.strftime("%Y-%m-%dT%H:%M:%SZ") if y == now.year else f"{y}-12-31T23:59:59Z"
        parts.append(
            f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{to}") '
            "{ totalCommitContributions restrictedContributionsCount }"
        )
    years = graphql(token, f'query {{ user(login: "{LOGIN}") {{ {" ".join(parts)} }} }}')["user"]
    commits = sum(v["totalCommitContributions"] + v["restrictedContributionsCount"] for v in years.values())

    sizes = {}
    for repo in base["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            sizes[e["node"]["name"]] = sizes.get(e["node"]["name"], 0) + e["size"]
    total = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    langs = [[name, round(size * 100 / total)] for name, size in top]

    return {
        "created_at": base["createdAt"],
        "company": (base["company"] or "").lstrip("@").strip(),
        "location": (base["location"] or "").strip(),
        "repos": base["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in base["repositories"]["nodes"]),
        "commits": commits,
        "followers": base["followers"]["totalCount"],
        "languages": langs,
    }


# ---------------------------------------------------------------- svg

W, H = 860, 586
BG, PANEL, LINE, DOT = "#0a0a0a", "#0f0f0f", "#262626", "#3a3a3a"
TEXT, TEXT2, TEXT3 = "#ededed", "#a1a1a1", "#6b6b6b"
MONO = "'Geist Mono','JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"


def t(x, y, s, fill=TEXT2, size=13.5, anchor="start", weight=400, mask=True, extra=""):
    halo = f' stroke="{PANEL}" stroke-width="10" paint-order="stroke"' if mask else ""
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{halo}{extra}>{escape(str(s))}</text>')


def row(x0, x1, y, label, value):
    return (f'<line x1="{x0}" y1="{y - 4}" x2="{x1}" y2="{y - 4}" stroke="{DOT}" stroke-dasharray="1 4"/>'
            + t(x0, y, f". {label}:", TEXT3) + t(x1, y, value, TEXT2, anchor="end"))


def heading(x0, x1, y, label):
    return (f'<line x1="{x0}" y1="{y - 5}" x2="{x1}" y2="{y - 5}" stroke="{LINE}"/>'
            + t(x0, y, label, TEXT, weight=500))


# 1-bit patterns, one density per language
PATTERNS = [
    '<rect width="4" height="4" fill="{c}"/>',
    '<rect width="2" height="2" fill="{c}"/><rect x="2" y="2" width="2" height="2" fill="{c}"/>',
    '<rect width="4" height="2" fill="{c}"/>',
    '<rect width="2" height="2" fill="{c}"/>',
    '<rect width="2" height="4" fill="{c}"/>',
    '<rect width="1" height="1" fill="{c}"/><rect x="2" y="2" width="1" height="1" fill="{c}"/>',
    '<rect width="1" height="1" fill="{c}"/>',
]


def build(stats):
    icons = json.loads(ICONS.read_text())
    sprite = base64.b64encode(SPRITE.read_bytes()).decode()
    out = []
    add = out.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'font-family="{MONO}">')
    add('<style>.cur{animation:b 1.1s steps(1) infinite}@keyframes b{50%{opacity:0}}'
        f'.spr{{animation:spr 6s steps({FRAMES}) infinite}}@keyframes spr{{to{{transform:translateX(-{FRAMES * FW}px)}}}}'
        '@media (prefers-reduced-motion:reduce){.cur,.spr{animation:none}}</style>')
    add('<defs>')
    for i, p in enumerate(PATTERNS):
        add(f'<pattern id="p{i}" width="4" height="4" patternUnits="userSpaceOnUse">{p.format(c=TEXT)}</pattern>')
    add('</defs>')
    add(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{BG}" stroke="{LINE}"/>')

    # ---- terminal panel
    px, py, pw, ph = 16, 16, W - 32, 352
    add(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="10" fill="{PANEL}" stroke="{LINE}"/>')
    add(f'<svg x="28" y="50" width="{FW}" height="{FH}" viewBox="0 0 {FW} {FH}" overflow="hidden">'
        f'<g class="spr"><image width="{FRAMES * FW}" height="{FH}" href="data:image/png;base64,{sprite}" '
        'style="image-rendering:pixelated"/></g></svg>')

    x0, x1 = 366, W - 40
    y = 58
    add(heading(x0, x1, y, "gvfirmeza@github"))
    y += 26
    info = [
        ("Role", "Software & AI Engineer"),
        ("Company", stats.get("company")),
        ("Location", stats.get("location")),
        ("Coding since", "2023"),
        ("Stack", "Angular, React, Java, Python"),
    ]
    for label, value in info:
        if value:
            add(row(x0, x1, y, label, value))
            y += 21
    y += 14
    add(heading(x0, x1, y, "Focus"))
    y += 26
    add(row(x0, x1, y, "Building", "Web apps, data pipelines, LLM agents"))
    y += 35
    add(heading(x0, x1, y, "Contact"))
    y += 26
    add(row(x0, x1, y, "GitHub", "github.com/gvfirmeza"))
    y += 21
    add(row(x0, x1, y, "LinkedIn", "in/guilherme-firmeza"))
    y += 34
    add(t(x0, y, ">", TEXT, mask=False) + f'<rect class="cur" x="{x0 + 14}" y="{y - 11}" width="8" height="13" fill="{TEXT}"/>')

    # ---- languages
    by = py + ph + 12
    bh = H - by - 16
    lw = 540
    add(f'<rect x="{px}" y="{by}" width="{lw}" height="{bh}" rx="10" fill="{PANEL}" stroke="{LINE}"/>')
    add(t(px + 24, by + 32, "[ TOP LANGUAGES ]", TEXT3, size=11.5, mask=False, extra=' letter-spacing="2"'))
    langs = stats["languages"]
    total = sum(p for _, p in langs) or 1
    bx, bw, barY = px + 24, lw - 48, by + 50
    cx = bx
    for i, (name, pct) in enumerate(langs):
        seg = bw * pct / total
        add(f'<rect x="{cx:.1f}" y="{barY}" width="{max(seg - 3, 2):.1f}" height="12" fill="url(#p{i % len(PATTERNS)})"/>')
        cx += seg
    for i, (name, pct) in enumerate(langs):
        col, r = i % 2, i // 2
        lx, ly = bx + col * (bw // 2), barY + 44 + r * 24
        add(f'<rect x="{lx}" y="{ly - 10}" width="11" height="11" fill="url(#p{i % len(PATTERNS)})" '
            f'stroke="{DOT}" stroke-width="0.5"/>')
        add(t(lx + 20, ly, name, TEXT, size=13, mask=False) + t(lx + 20 + 9 * len(name), ly, f"{pct}%", TEXT3, size=12, mask=False))

    # ---- stack
    sx = px + lw + 12
    sw = W - 16 - sx
    add(f'<rect x="{sx}" y="{by}" width="{sw}" height="{bh}" rx="10" fill="{PANEL}" stroke="{LINE}"/>')
    add(t(sx + 24, by + 32, "[ STACK ]", TEXT3, size=11.5, mask=False, extra=' letter-spacing="2"'))
    cols, tile, gap = 6, 36, 8
    gx = sx + (sw - (cols * tile + (cols - 1) * gap)) / 2
    gy = by + 48
    for i, ic in enumerate(icons):
        c, r = i % cols, i // cols
        tx, ty = gx + c * (tile + gap), gy + r * (tile + gap)
        add(f'<g><title>{escape(ic["name"])}</title>'
            f'<rect x="{tx:.1f}" y="{ty}" width="{tile}" height="{tile}" rx="8" fill="#141414" stroke="{LINE}"/>'
            f'<svg x="{tx + 9:.1f}" y="{ty + 9}" width="18" height="18" viewBox="0 0 24 24">'
            f'<path d="{ic["path"]}" fill="#b5b5b5"/></svg></g>')

    add("</svg>")
    return "".join(out)


def main():
    stats = json.loads(STATS.read_text())
    token = os.environ.get("GH_TOKEN")
    if token:
        try:
            stats = fetch(token)
            STATS.write_text(json.dumps(stats, indent=2) + "\n")
            print("stats refreshed")
        except Exception as e:  # keep the last good numbers
            print(f"could not refresh stats, keeping cached ones: {e}", file=sys.stderr)
    OUT.write_text(build(stats))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
