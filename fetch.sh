#!/bin/bash
# モータースポーツ RSS を取得して data.js にまとめる
# 使い方: ./fetch.sh            （取得のみ）
#         ./fetch.sh --open     （取得後にブラウザで開く）
set -u
cd "$(dirname "$0")"

# id|カテゴリ|言語|表示名|URL
# カテゴリ "auto" はタイトル・タグから自動でカテゴリ分けする総合フィード
# "auto:f1" はどのカテゴリにも当たらなかった記事を F1 に入れる
FEEDS=$(cat <<'EOF'
msjp-f1|f1|ja|Motorsport.com 日本版|https://jp.motorsport.com/rss/f1/news/
asweb-f1|f1|ja|auto sport web|https://www.as-web.jp/f1/feed
f1gate|f1|ja|F1-Gate.com|https://f1-gate.com/feed
ms-f1|f1|en|Motorsport.com|https://www.motorsport.com/rss/f1/news/
as-f1|f1|en|Autosport|https://www.autosport.com/rss/f1/news/
crash-f1|f1|en|Crash.net|https://www.crash.net/rss/f1
planetf1|f1|en|PlanetF1|https://www.planetf1.com/rss
gpfans|f1|en|GPFans|https://www.gpfans.com/en/rss.xml
msjp-sgt|supergt|ja|Motorsport.com 日本版|https://jp.motorsport.com/rss/supergt/news/
asweb-sgt|supergt|ja|auto sport web|https://www.as-web.jp/supergt/feed
msjp-sf|superformula|ja|Motorsport.com 日本版|https://jp.motorsport.com/rss/super-formula/news/
msjp-motogp|motogp|ja|Motorsport.com 日本版|https://jp.motorsport.com/rss/motogp/news/
ms-motogp|motogp|en|Motorsport.com|https://www.motorsport.com/rss/motogp/news/
as-motogp|motogp|en|Autosport|https://www.autosport.com/rss/motogp/news/
crash-motogp|motogp|en|Crash.net|https://www.crash.net/rss/motogp
msjp-wec|wec|ja|Motorsport.com 日本版|https://jp.motorsport.com/rss/wec/news/
ms-wec|wec|en|Motorsport.com|https://www.motorsport.com/rss/wec/news/
as-wec|wec|en|Autosport|https://www.autosport.com/rss/wec/news/
racer-imsa|wec|en|RACER|https://racer.com/category/imsa/feed/
msjp-wrc|wrc|ja|Motorsport.com 日本版|https://jp.motorsport.com/rss/wrc/news/
ms-wrc|wrc|en|Motorsport.com|https://www.motorsport.com/rss/wrc/news/
as-wrc|wrc|en|Autosport|https://www.autosport.com/rss/wrc/news/
dirtfish|wrc|en|DirtFish|https://dirtfish.com/feed/
ms-indy|indy|en|Motorsport.com|https://www.motorsport.com/rss/indycar/news/
racer-indy|indy|en|RACER|https://racer.com/category/indycar/feed/
ms-fe|fe|en|Motorsport.com|https://www.motorsport.com/rss/formula-e/news/
asweb-all|auto|ja|auto sport web|https://www.as-web.jp/feed
therace|auto|en|The Race|https://www.the-race.com/feed/
racefans|auto|en|RaceFans|https://www.racefans.net/feed/
topnews|auto:f1|ja|TopNews|https://www.topnews.jp/feed
EOF
)

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

echo "フィードを取得中..."
while IFS='|' read -r id cat lang name url; do
  [ -z "$id" ] && continue
  ( code=$(curl -sL -A "$UA" --max-time 20 -o "$TMP/$id.xml" -w "%{http_code}" "$url")
    echo "$code" > "$TMP/$id.code" ) &
done <<< "$FEEDS"
wait

esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

OUT=data.js.tmp
{
  printf 'window.FEED_DATA={generated:"%s",feeds:[\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  while IFS='|' read -r id cat lang name url; do
    [ -z "$id" ] && continue
    code=$(cat "$TMP/$id.code" 2>/dev/null || echo 000)
    if [ "$code" = "200" ] && [ -s "$TMP/$id.xml" ]; then
      ok=true; b64=$(base64 < "$TMP/$id.xml" | tr -d '\n')
    else
      ok=false; b64=""
    fi
    printf '{id:"%s",cat:"%s",lang:"%s",name:"%s",url:"%s",status:"%s",ok:%s,b64:"%s"},\n' \
      "$id" "$cat" "$lang" "$(esc "$name")" "$(esc "$url")" "$code" "$ok" "$b64"
    [ "$ok" = true ] && echo "  ✓ $name ($cat)" >&2 || echo "  ✗ $name ($cat) HTTP $code" >&2
  done <<< "$FEEDS"
  printf ']};\n'
} > "$OUT" && mv "$OUT" data.js

echo "完了: data.js を更新しました"

echo "レース日程を取得中..."
python3 fetch_schedule.py || echo "  ✗ 日程を取得できませんでした（前回の schedule.js を使います）"
if [ "${1:-}" = "--open" ]; then open index.html; fi
