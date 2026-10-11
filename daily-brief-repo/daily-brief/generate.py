#!/usr/bin/env python3
"""Builds docs/index.html and docs/summary.json for the daily brief.

Usage:
  python generate.py          # live run (needs ANTHROPIC_API_KEY and FINNHUB_API_KEY)
  python generate.py --demo   # sample data, no network, to preview the design
"""
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text())
DEMO = "--demo" in sys.argv
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
FH_KEY = os.environ.get("FINNHUB_API_KEY", "")
TZ = ZoneInfo(CFG.get("timezone", "America/New_York"))
NOW = dt.datetime.now(TZ)
TODAY = NOW.date()
STATE_PATH = ROOT / "data" / "state.json"


def log(*a):
    print(*a, file=sys.stderr)


# ---------------------------------------------------------------- data sources
def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "daily-brief/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def finnhub(path, **params):
    params["token"] = FH_KEY
    url = "https://finnhub.io/api/v1/" + path + "?" + urllib.parse.urlencode(params)
    return json.loads(http_get(url))


def quote(sym):
    try:
        q = finnhub("quote", symbol=sym)
        if q.get("c"):
            return float(q["c"]), float(q.get("dp") or 0)
    except Exception as ex:
        log("quote failed", sym, ex)
    return None


def company_headlines(sym):
    try:
        start = (TODAY - dt.timedelta(days=3)).isoformat()
        items = finnhub("company-news", symbol=sym, **{"from": start, "to": TODAY.isoformat()})
        return [{"h": i["headline"], "s": i.get("source", ""), "u": i.get("url", "")} for i in items[:3]]
    except Exception as ex:
        log("company news failed", sym, ex)
        return []


def general_headlines():
    try:
        items = finnhub("news", category="general")
        return [{"h": i["headline"], "s": i.get("source", ""), "u": i.get("url", "")} for i in items[:6]]
    except Exception as ex:
        log("general news failed", ex)
        return []


def earnings_this_week(symbols):
    try:
        end = (TODAY + dt.timedelta(days=7)).isoformat()
        cal = finnhub("calendar/earnings", **{"from": TODAY.isoformat(), "to": end})
        rows = [{"t": r["symbol"], "date": r["date"]} for r in cal.get("earningsCalendar", []) if r.get("symbol") in symbols]
        return sorted(rows, key=lambda r: r["date"])
    except Exception as ex:
        log("earnings failed", ex)
        return []


def rss(url, n=4):
    try:
        root = ET.fromstring(http_get(url))
        out = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            if title and link:
                out.append({"h": title, "s": "", "u": link})
            if len(out) >= n:
                break
        return out
    except Exception as ex:
        log("rss failed", url, ex)
        return []


def weather():
    loc = CFG.get("location") or {}
    if loc.get("lat") is None or loc.get("lon") is None:
        return None
    unit = loc.get("unit", "fahrenheit")
    try:
        url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": loc["lat"], "longitude": loc["lon"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "temperature_unit": unit, "timezone": "auto", "forecast_days": 1})
        d = json.loads(http_get(url))["daily"]
        return {"hi": round(d["temperature_2m_max"][0]), "lo": round(d["temperature_2m_min"][0]),
                "rain": d["precipitation_probability_max"][0], "unit": "F" if unit == "fahrenheit" else "C"}
    except Exception as ex:
        log("weather failed", ex)
        return None


# ------------------------------------------------------------------- Claude
SYSTEM = """You write the daily lessons and commentary for a personal morning dashboard.
You receive JSON context: today's date, the reader's goals and tasks, market movers with recent headlines,
general headlines, and lists of recent topics already covered.

Return ONLY one JSON object, no markdown fences, with exactly these keys:
{
 "message": "1-2 sentence original motivational message to start the day. Specific and grounded, no cliches.",
 "focus": "the single most valuable task today, chosen from the tasks given",
 "goal_link": "one sentence connecting today's tasks to the reader's goals",
 "mover_notes": {"TICKER": "one short line on why it moved"},
 "news_brief": "2-3 sentence overview of what matters in markets today",
 "history": {"title": "Month Day", "items": ["2 or 3 interesting events that happened on this calendar day, with years"]},
 "psychology": {"title": "", "body": "3-4 sentences teaching one psychology concept", "why": "how it applies to daily life or investing"},
 "vocab": {"word": "", "pos": "", "pron": "", "def": "", "example": "one natural example sentence"},
 "mental_model": {"title": "", "body": "2-3 sentences"},
 "finance": {"title": "", "body": "3-4 sentences teaching one personal finance or investing concept", "try": "a small example or exercise"},
 "business": {"title": "", "body": "3-4 sentences teaching one entrepreneurship concept", "challenge": "one small action for today"}
}

Rules:
- mover_notes: use ONLY the provided headlines. If the headlines do not explain a move, leave that ticker out. Never invent causes.
- news_brief: only summarize the provided headlines. Do not invent facts or figures.
- history: only well-documented events you are confident about, with the correct year.
- Do not repeat anything in recent_topics. Vocabulary should be useful, not obscure for its own sake.
- finance and business lessons should build gradually from fundamentals toward more advanced ideas, using recent_topics to see how far along the reader is.
- Teach concepts. Never tell the reader to buy or sell any security.
- Plain punctuation, warm and direct tone."""


def ask_claude(ctx):
    import anthropic
    client = anthropic.Anthropic()
    r = client.messages.create(model=MODEL, max_tokens=3500, system=SYSTEM,
                               messages=[{"role": "user", "content": json.dumps(ctx, ensure_ascii=False)}])
    text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


# --------------------------------------------------------------------- state
def load_state():
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def update_state(state, ai):
    recent = state.setdefault("recent", {})
    picks = {
        "psychology": (ai.get("psychology") or {}).get("title"),
        "vocab": (ai.get("vocab") or {}).get("word"),
        "finance": (ai.get("finance") or {}).get("title"),
        "business": (ai.get("business") or {}).get("title"),
        "mental_model": (ai.get("mental_model") or {}).get("title"),
    }
    for k, v in picks.items():
        if v:
            recent[k] = (recent.get(k, []) + [v])[-60:]
    v = ai.get("vocab") or {}
    if v.get("word") and v.get("def"):
        state["last_vocab"] = {"word": v["word"], "def": v["def"]}
    STATE_PATH.write_text(json.dumps(state, indent=1))


# ---------------------------------------------------------------------- build
def live_data(state):
    stocks = []
    for w in CFG["watchlist"]:
        q = quote(w["t"])
        if q:
            stocks.append({"t": w["t"], "n": w["n"], "p": q[0], "pct": q[1]})
    indices = []
    for i in CFG.get("indices", []):
        q = quote(i["symbol"])
        if q:
            indices.append({"name": i["name"], "price": q[0], "pct": q[1]})

    movers = sorted(stocks, key=lambda s: abs(s["pct"]), reverse=True)[:6]
    mover_news = {m["t"]: company_headlines(m["t"]) for m in movers}
    general = general_headlines()
    groups = [{"tag": "Markets", "items": general[:5]}]
    flat = [{"h": f'{t}: {n["h"]}', "s": n["s"], "u": n["u"]} for t, items in mover_news.items() for n in items[:2]]
    groups.append({"tag": "Your movers", "items": flat[:8]})
    for feed in CFG.get("rss", []):
        groups.append({"tag": feed["tag"], "items": rss(feed["url"])})

    ctx = {
        "date": TODAY.strftime("%A, %B %-d, %Y"),
        "name": CFG["name"],
        "goals": CFG["goals"],
        "tasks": CFG["tasks"],
        "movers": [{"t": m["t"], "name": m["n"], "pct": m["pct"], "headlines": [n["h"] for n in mover_news[m["t"]]]} for m in movers],
        "general_headlines": [g["h"] for g in general],
        "recent_topics": state.get("recent", {}),
    }
    try:
        ai = ask_claude(ctx)
    except Exception as ex:
        log("Claude call failed:", ex)
        ai = {}
    return stocks, indices, groups, ai


def demo_data():
    sample = {"MRVL": (275.28, .25), "LITE": (1103.36, 5.22), "SNDK": (1581.82, -1.72), "MU": (1029.00, -.66),
              "TTWO": (213.44, 1.94), "BIRD": (2.93, 1.74), "SPCX": (162.57, 1.25), "TSLA": (382.70, 2.05),
              "PPTA": (20.64, 2.64), "DELL": (586.06, 2.00), "PL": (17.18, -.06), "UAMY": (3.68, -1.08),
              "UUUU": (9.96, .20), "XOM": (168.94, .26), "QCOM": (175.50, -.29), "OXY": (60.11, -.28),
              "SRFM": (.946, 1.75), "INTC": (104.70, -2.22), "IBM": (227.13, .23), "SPCE": (2.84, -3.40),
              "AIP": (22.44, -1.75), "ORCL": (141.40, 4.59), "AMD": (608.10, -2.03), "AVGO": (361.54, .39),
              "RKLB": (68.21, -.28)}
    stocks = [{"t": w["t"], "n": w["n"], "p": sample[w["t"]][0], "pct": sample[w["t"]][1]} for w in CFG["watchlist"]]
    indices = [{"name": "Dow Jones", "price": 51654.95, "pct": .83}, {"name": "S&P 500", "price": 7811.54, "pct": .59}]
    groups = [{"tag": "Markets", "items": [{"h": "Demo headline: this is where live market news appears", "s": "Demo", "u": "https://example.com"}]}]
    ai = {
        "message": "Small steps, taken every day, are how big things get built. Start with the first one.",
        "focus": CFG["tasks"][0], "goal_link": "Reviewing movers and learning a word both feed your daily-learning goals.",
        "mover_notes": {"ORCL": "Demo note: a reason for the move appears here."},
        "news_brief": "Demo overview: a short summary of what matters in markets today appears here.",
        "history": {"title": "October 11", "items": ["1968: Apollo 7 launched, the first crewed Apollo flight.", "1984: Kathryn Sullivan became the first American woman to walk in space."]},
        "psychology": {"title": "Loss aversion", "body": "People feel a loss more strongly than an equal gain. Kahneman and Tversky found losses tend to hurt roughly twice as much as equal gains feel good.", "why": "It pushes investors to hold losers too long and sell winners too early."},
        "vocab": {"word": "perspicacious", "pos": "adjective", "pron": "per-spuh-KAY-shus", "def": "Having a sharp ability to notice and understand things.", "example": "A perspicacious investor read the footnotes and spotted the risk."},
        "mental_model": {"title": "Circle of competence", "body": "Know which topics you understand well enough to judge, and be honest about where that circle ends."},
        "finance": {"title": "Compound growth and the rule of 72", "body": "Compounding means earning returns on earlier returns. Divide 72 by the yearly return to estimate years to double.", "try": "At 8% a year, money doubles in about 9 years."},
        "business": {"title": "Start with the problem, not the idea", "body": "Most failed businesses solved a problem nobody cared enough about. Talk to people who have the problem first.", "challenge": "Ask one person what annoys them most about their week."},
    }
    return stocks, indices, groups, ai


def main():
    state = load_state()
    stocks, indices, groups, ai = demo_data() if DEMO else live_data(state)

    data = {
        "name": CFG["name"],
        "date": TODAY.isoformat(),
        "date_label": NOW.strftime("%A, %B %-d"),
        "generated": NOW.strftime("%Y-%m-%d %H:%M %Z"),
        "message": ai.get("message", ""),
        "focus": CFG.get("focus") or ai.get("focus", ""),
        "goal_link": ai.get("goal_link", ""),
        "indices": indices,
        "stocks": stocks,
        "mover_notes": ai.get("mover_notes") or {},
        "news_brief": ai.get("news_brief", ""),
        "news": groups,
        "earnings": [] if DEMO else earnings_this_week({w["t"] for w in CFG["watchlist"]}),
        "weather": None if DEMO else weather(),
        "goals": CFG["goals"],
        "tasks": CFG["tasks"],
        "habits": CFG["habits"],
        "history": ai.get("history"),
        "psychology": ai.get("psychology"),
        "vocab": ai.get("vocab"),
        "recall": state.get("last_vocab") if not DEMO else {"word": "lucid", "def": "Clear and easy to understand."},
        "mental_model": ai.get("mental_model"),
        "finance": ai.get("finance"),
        "business": ai.get("business"),
    }

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    html = (ROOT / "template.html").read_text().replace("__DATA__", payload)
    out = ROOT / "docs"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(html)

    # short text for the phone notification
    if stocks:
        top = max(stocks, key=lambda s: s["pct"])
        low = min(stocks, key=lambda s: s["pct"])
        parts = [f'{indices[0]["name"].split(" (")[0]} {indices[0]["pct"]:+.1f}%'] if indices else []
        parts.append(f'Up: {top["t"]} {top["pct"]:+.1f}%')
        parts.append(f'Down: {low["t"]} {low["pct"]:+.1f}%')
        parts.append(f'{len(CFG["tasks"])} tasks today')
        body = " | ".join(parts)
    else:
        body = "Your brief is ready."
    repo = os.environ.get("GITHUB_REPOSITORY", "owner/repo")
    owner, name = repo.split("/")
    summary = {"title": f'Good morning, {CFG["name"]}', "body": body, "url": f"https://{owner}.github.io/{name}/"}
    (out / "summary.json").write_text(json.dumps(summary))

    if not DEMO and ai:
        update_state(state, ai)
    print("Built docs/index.html")


if __name__ == "__main__":
    main()
