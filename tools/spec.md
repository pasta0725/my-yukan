# Task spec (shared by all workers)

You collect news stories for a personal Japanese news app "マイ夕刊". Today is {TODAY} (Japan time).

## Avoid repeats
Do NOT use any article (or the same event) listed in {WORKDIR}/used.txt.


## How to reach pages (IMPORTANT: avoids permission prompts)
- NEVER type a URL into WebFetch from memory or from this instruction text. A URL may be fetched only if it came from a WebSearch result or from a page you already fetched with WebFetch.
- To open a site's listing page: first WebSearch for it (e.g. "家電 Watch 最新ニュース", "ITmedia AI+ 新着", "メルカリ ニュースルーム"), then WebFetch the URL exactly as the search result gives it.
- To find a company's official announcement/product page: WebSearch for it (company + product + "ニュースリリース" / "製品"), then fetch the result URL. Or follow a link the news article itself contains.
- If WebFetch returns PROVENANCE_REQUIRED or any permission error, do not retry that URL; find it via WebSearch instead, or skip it.

## Method
- Search engines are weak for fresh Japanese news: open your assigned sites' new-article listing pages with WebFetch and pick stories there.
- Open each article body with WebFetch and verify facts. Never guess. Check the real publish date in the article body.
- Period: AI and kaden = published within the last 72 hours. fukugyo = within the last 7 days.
- Skip thin PR pieces. If you use sponsored (PR) content, say so in the body.

## Read up to 5 articles per story (user's request: more information)
- After you pick a story, WebSearch the same event (company/product + key words, also the official name) and find other outlets' articles and the official announcement about it. Read up to 5 in total (the first article included), from different sites. Fewer is fine when there are no more.
- Combine the facts from all of them: what happened, concrete details (prices, dates, specs, numbers, who is affected), background / why it matters, what each outlet added that the others did not, and what happens next.
- If outlets disagree, say so plainly ("〇〇は△△と伝えています").
- Write it all in YOUR OWN WORDS as one new explanation. Never copy sentences, never follow one article's paragraph order closely, never quote more than a few words.
- List every article you actually read in "refs".
- Write as a news explainer: no first person (「私は」「私が読んだ」), no notes about your search process. If an important point could not be confirmed, say it neutrally (「〇〇は明らかにされていません」「△△によると」).

## Images (user's rule: ALL official images, at most 2 news-site photos per story)
- Official images (kind "press"): find the company/organization's own announcement for the same news (press release, newsroom, product page, official blog, official notice). Collect all relevant images there (product shots, screens, diagrams, charts), up to 12.
- News-site photos (kind "ogp"): from the news article itself, at most 2 in total.
- Ask WebFetch to list every image URL on the page (absolute https) with what it shows (alt/caption/surrounding text), including og:image. Use ONLY URLs WebFetch actually returned. Never guess or construct URLs.
- Skip: photos where a person's face is the main subject, logos alone, icons, ads/banners, site-generic share images, tiny thumbnails (prefer the large version).
- No image is OK.

## Writing
Easy Japanese for a non-engineer, in YOUR OWN WORDS (never copy sentences). Avoid jargon (if a technical word is needed, explain it in a few words). For fukugyo, the "point" block says what an individual seller should do or note.
Do NOT drop necessary information (user's request): keep every important fact you read — numbers, prices, dates, conditions, who is affected, what to do, what changes. Length: the "p" blocks together are usually 700–1500 Japanese characters, up to about 2000 when there are many facts, in 4–8 paragraphs of 2–5 sentences. Stories with little information may be shorter; never pad. Still your own words only.

## Output: a JSON array, each item:
{"id":"<category>-<short ascii slug>","category":"ai|kaden|fukugyo","title":"見出し30字前後","summary":"一言要約50字以内",
 "image":{"src":"https://...","kind":"press|ogp","credit":"提供元","page":"https://found-on page"},   ← best thumbnail (official product image preferred); omit if none
 "visual":{"icon":"one of: ai, chip, phone, pc, tv, appliance, camera, audio, game, cart, yen, box, globe, chart, doc, lock, car, spark","kicker":"全角8字以内"},
 "body":[{"type":"p","text":"2〜4文"},
         {"type":"img","src":"https://...","kind":"press|ogp","credit":"...","caption":"何が写っているか","page":"https://..."},   ← the 2nd-best image, if any
         {"type":"p","text":"..."},
         {"type":"stat","items":[{"value":"全角10字以内","label":"全角15字以内"}]},   ← exactly one, 2–3 items, numbers from the source only
         {"type":"gallery","title":"公式の画像","items":[{"src":"...","kind":"press|ogp","credit":"...","caption":"...","page":"..."}]},   ← all remaining images, if any (title "そのほかの画像" if it contains ogp)
         {"type":"point","items":["ポイント1","ポイント2","ポイント3"]}],   ← optional
 "source_name":"サイト名","source_url":"https://article","published":"YYYY-MM-DD",
 "refs":[{"name":"サイト名","url":"https://..."}]}   ← every article you read for this story (max 5, source_url first), URLs exactly as fetched
Text blocks (p/stat/point): 6–10 (p 4–8 + one stat + optional point). No image URL may appear twice in one story. News-site (ogp) images ≤ 2 per story counting image+img+gallery.
Validate with python3 json.load. Final reply: count, titles, image counts (press/ogp), problems.
