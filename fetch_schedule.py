"""今後のレース日程を集めて schedule.js にまとめる

F1（Jolpica F1 API）と MotoGP（MotoGP 公式 API）はセッション時刻まで自動で取得し、
それ以外のシリーズは schedule-manual.json の日程を使う。
使い方: python3 fetch_schedule.py   （fetch.sh から呼ばれる）
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (motorsport-rss schedule)"}
NOW = datetime.now(timezone.utc)
# 終わったばかりのレースも少しの間は残す
CUTOFF = (NOW - timedelta(days=1)).date().isoformat()

F1_NAMES = {
    "Australian": "オーストラリア", "Chinese": "中国", "Japanese": "日本", "Bahrain": "バーレーン",
    "Saudi Arabian": "サウジアラビア", "Miami": "マイアミ", "Emilia Romagna": "エミリア・ロマーニャ",
    "Monaco": "モナコ", "Spanish": "スペイン", "Barcelona-Catalunya": "バルセロナ", "Canadian": "カナダ",
    "Austrian": "オーストリア", "British": "イギリス", "Belgian": "ベルギー", "Hungarian": "ハンガリー",
    "Dutch": "オランダ", "Italian": "イタリア", "Madrid": "マドリード", "Azerbaijan": "アゼルバイジャン",
    "Singapore": "シンガポール", "United States": "アメリカ", "Mexico City": "メキシコシティ",
    "São Paulo": "サンパウロ", "Las Vegas": "ラスベガス", "Qatar": "カタール", "Abu Dhabi": "アブダビ",
    "Portuguese": "ポルトガル", "Turkish": "トルコ", "French": "フランス", "German": "ドイツ",
}
MOTOGP_NAMES = {
    "THAILAND": "タイ", "QATAR": "カタール", "BRAZIL": "ブラジル", "THE AMERICAS": "アメリカズ",
    "ARGENTINA": "アルゼンチン", "SPAIN": "スペイン", "FRANCE": "フランス", "ITALY": "イタリア",
    "GREAT BRITAIN": "イギリス", "ARAGON": "アラゴン", "NETHERLANDS": "オランダ", "THE NETHERLANDS": "オランダ",
    "GERMANY": "ドイツ", "CZECHIA": "チェコ", "AUSTRIA": "オーストリア", "HUNGARY": "ハンガリー",
    "CATALUNYA": "カタルーニャ", "SAN MARINO": "サンマリノ", "SAN MARINO AND THE RIMINI RIVIERA": "サンマリノ",
    "JAPAN": "日本", "INDONESIA": "インドネシア", "AUSTRALIA": "オーストラリア", "MALAYSIA": "マレーシア",
    "PORTUGAL": "ポルトガル", "VALENCIA": "バレンシア", "KAZAKHSTAN": "カザフスタン", "INDIA": "インド",
    "EMILIA-ROMAGNA": "エミリア・ロマーニャ", "THE UNITED STATES": "アメリカ", "UNITED STATES": "アメリカ", "CATALONIA": "カタルーニャ",
}


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def f1_events():
    events = []
    year = NOW.year
    for season in (str(year), str(year + 1)):
        try:
            races = get_json(f"https://api.jolpi.ca/ergast/f1/{season}/races/")["MRData"]["RaceTable"]["Races"]
        except Exception as e:
            print(f"  ✗ F1 {season}: {e}", file=sys.stderr)
            continue
        for r in races:
            if r["date"] < CUTOFF:
                continue
            sessions = []
            for key, label in [("FirstPractice", "FP1"), ("SecondPractice", "FP2"), ("ThirdPractice", "FP3"),
                               ("SprintQualifying", "スプリント予選"), ("Sprint", "スプリント"), ("Qualifying", "予選")]:
                s = r.get(key)
                if s and s.get("time"):
                    sessions.append({"name": label, "time": f"{s['date']}T{s['time']}"})
            if r.get("time"):
                sessions.append({"name": "決勝", "time": f"{r['date']}T{r['time']}"})
            sessions.sort(key=lambda s: s["time"])
            base = r["raceName"].replace(" Grand Prix", "")
            events.append({
                "series": "f1",
                "name": (F1_NAMES[base] + "GP") if base in F1_NAMES else r["raceName"],
                "round": f"Rd.{r['round']}",
                "venue": r["Circuit"]["circuitName"],
                "start": r.get("FirstPractice", {}).get("date", r["date"]),
                "end": r["date"],
                "sessions": sessions,
            })
        print(f"  ✓ F1 {season}: {len(races)} races", file=sys.stderr)
    return events


def motogp_session_name(b):
    name, kind = b.get("name", ""), b.get("kind")
    if kind == "RACE":
        return "スプリント" if "Sprint" in name else "決勝"
    if kind == "QUALIFYING":
        m = re.search(r"(\d)", name)
        return f"Q{m.group(1)}" if m else "予選"
    if kind == "PRACTICE":
        m = re.search(r"Nr\. ?(\d)", name)
        return f"FP{m.group(1)}" if m else "プラクティス"
    if kind == "WARM_UP":
        return "ウォームアップ"
    return None


def motogp_events():
    events = []
    year = NOW.year
    for season in (year, year + 1):
        try:
            data = get_json(f"https://api.pulselive.motogp.com/motogp/v1/events?seasonYear={season}")
        except Exception as e:
            print(f"  ✗ MotoGP {season}: {e}", file=sys.stderr)
            continue
        gps = [e for e in data if e.get("kind") == "GP"]
        gps.sort(key=lambda e: e["date_start"])
        for i, e in enumerate(gps, 1):
            end = e["date_end"][:10]
            if end < CUTOFF:
                continue
            sessions = []
            for b in e.get("broadcasts") or []:
                if (b.get("category") or {}).get("acronym") != "MGP":
                    continue
                label = motogp_session_name(b)
                if label and b.get("date_start"):
                    t = _fix_tz(b["date_start"])
                    sessions.append({"name": label, "time": t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
            sessions.sort(key=lambda s: s["time"])
            raw = re.sub(r"\s+", " ", e["name"]).strip().upper()
            m = re.search(r"GRAND PRIX OF (.+)$", raw)
            key = m.group(1).strip() if m else raw
            events.append({
                "series": "motogp",
                "round": f"Rd.{i}",
                "name": (MOTOGP_NAMES[key] + "GP") if key in MOTOGP_NAMES else e["name"].strip().title(),
                "venue": (e.get("circuit") or {}).get("name", ""),
                "start": e["date_start"][:10],
                "end": end,
                "sessions": sessions,
            })
        print(f"  ✓ MotoGP {season}: {len(gps)} GPs", file=sys.stderr)
    return events


def _fix_tz(s):
    # "2026-11-27T10:45:00+0100" のようにコロンのないタイムゾーンを Python 3.9 でも読めるようにする
    m = re.match(r"(.*[T ]\d\d:\d\d(?::\d\d)?)([+-]\d\d)(\d\d)$", s)
    if m:
        s = f"{m.group(1)}{m.group(2)}:{m.group(3)}"
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main():
    manual = json.load(open(os.path.join(HERE, "schedule-manual.json"), encoding="utf-8"))
    events = f1_events() + motogp_events()
    events += [dict(e, manual=True) for e in manual["events"] if e["end"] >= CUTOFF]
    events.sort(key=lambda e: (e["start"], e["series"]))
    out = {
        "generated": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manualUpdated": manual["updated"],
        "broadcastNote": manual["broadcastNote"],
        "broadcasts": manual["broadcasts"],
        "sources": manual["sources"],
        "events": events,
    }
    path = os.path.join(HERE, "schedule.js")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write("window.SCHEDULE_DATA=" + json.dumps(out, ensure_ascii=False) + ";\n")
    os.replace(path + ".tmp", path)
    # iPhone アプリなど、ブラウザ以外から読むための JSON
    with open(os.path.join(HERE, "schedule.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"  ✓ 日程: {len(events)} 件 → schedule.js", file=sys.stderr)


if __name__ == "__main__":
    main()
