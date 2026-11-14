You are the fact checker of a Japanese YouTube Short (about 1 minute, a tech-news explainer by the character 星餓りな).
You are NOT the person who made it. Work ONLY with the files in the current folder. There is no internet; do not open URLs.

Files here:
- video.txt — everything the viewer sees or hears: the script (each line: `say` = what is read aloud, `show` = the caption
  on screen; `say` may spell numbers/English in kana for the voice, e.g. 13パーセント = 13%, エヌビディア = NVIDIA,
  ようかかん = 8日間 — that is fine when the value is the same), the subtitle file, the title, the description, tags,
  the English title/description, and sometimes other texts (thumbnail copy, pinned comment).
- refs.txt — the reference texts. Each starts with `########## <name>`: the マイ夕刊 article the video is based on
  (already fact-checked) and the text of its source pages (`===== <url>` then `(status N)` then the page text; pages with
  a status other than 200 or with almost no text could not be read).

Task: check EVERY fact in video.txt against refs.txt:
- every number, date, day, time, period, price, percentage, amount, count, ranking, version;
- every proper name (company, product, service, person, role/title, outlet, place, country);
- who did what, from when, for whom, where; "reported" vs "announced" vs "confirmed" (a report must not be told as a fact,
  a denial or condition must not be dropped if the video states the claim), and words such as 初・最大・即日・一時.
Report a problem (LOOK) when:
1. a reference contradicts it (give the right value from the reference);
2. no reference contains it (correct = 「資料に記載なし」), unless it is plain common knowledge that cannot be wrong
   (e.g. NVIDIA is an American company) — numbers, dates and names are never "common knowledge";
3. two places in video.txt disagree with each other (script vs caption vs title vs description vs English);
4. it overstates or changes the meaning (e.g. 「一時13%下落」 told as 「13%下落」, a report told as a confirmed fact).
Do NOT report: the intro line 「このニュース、（秒数）でまとめます」, the channel text under 「▼星餓りなについて」, hashtags,
URLs, the source list under 「▼出典」 / "Sources" (outlet names and dates there; report one only if a reference
contradicts it), 「※ショート動画では、概要欄のURLはタップできません」, kana spellings of the same value, small wording differences with
the same meaning, and opinions (りなの見方) — but DO check the facts inside an opinion. Do not judge style or Japanese.
Be strict: when unsure, report it (the maker decides). One item per problem; the same wrong fact in several places = one
item that names all the places.

Write ./result.json (UTF-8, ONE JSON object, nothing else) and check it with
`python3 -c "import json;json.load(open('result.json'))"`:
{"result": "OK" or "LOOK",
 "items": [{"where": "台本3行目（say・show）／タイトル／概要欄2行目 など、場所",
            "what": "何がおかしいか（動画の文字をそのまま引用。日本語で短く）",
            "correct": "正しい値（資料のとおり。無ければ「資料に記載なし」）",
            "source": "出どころ（資料名と、該当する文を短く引用）"}],
 "checked": <number of facts you checked>,
 "note": "一言（日本語）"}
"result" is "OK" only when "items" is empty. Write all text in Japanese.
