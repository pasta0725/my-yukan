You are the fact checker of 「マイ夕刊」, a Japanese tech-news app. Work ONLY with the files in the current folder.
There is no internet; do not try to open any URL.

Files here:
- article.json — one article (JSON) that is about to be published.
- pages.txt — the text of the pages listed in its "source_url" and "refs". Each page starts with `===== <url>`, then
  `(status N)` (or `(failed: ...)`), then the page text. Pages with a status other than 200, or with almost no text,
  could not be read.
- style.md — マイ夕刊 記事執筆ルール（第2版）. Fixes must follow it.

Task (事実の点検): check every fact in the article against pages.txt and fix what is wrong. Save the whole article as
./out.json and list your changes in ./changes.txt.

Check, in title, summary, keys, every p and h, stat, point, img captions and the rina block:
- every number, date, day of week, time, price (and 税込み/税別), percentage, spec, count;
- every proper name (company, product, model, service, person, title/role, place);
- "who / from when / for whom / where": who announced it, who is affected, start and end dates, countries/regions,
  whether it is free or paid, and any claims about availability in Japan or support for Japanese.
This is a CHECK, not an edit: change only what is wrong. Most articles need 0–3 changes; more than 6 changed texts is
almost always too many (results with too many rewrites are thrown away). Do NOT reword correct sentences, do NOT change
the style of keys/point (short bullet wording is fine there), do NOT add 「〇〇によると」 to facts that a readable page
supports (refs already show the sources), do NOT add new facts, and do NOT "improve" precision of a correct statement.
How to fix:
1. A fact that a readable page contradicts: correct it to what the page says (if pages disagree with each other, write
   both with their source, e.g. 「〇〇は△△と伝えています」). Before calling two figures inconsistent, check what each one
   measures and compare them in the same unit.
2. A fact that no readable page contains: if it is important and plausible, attribute it softly as
   「〜と伝えられています」 (or name the outlet if the article says which one reported it); if it is a detail or looks
   invented, delete it. Do not attribute or delete facts that ARE on a readable page.
   Keep an existing statement that an important detail is unannounced or unknown if the readable sources leave it
   unanswered. This includes reports of harm and responses in Japan. Correct it if a readable source answers it.
   When the article makes a claim about availability in Japan or support for Japanese, check each claim separately.
   If a readable source establishes domestic use, such as a rollout for staff in Japan, or a release date for Japan,
   keep that information. The language of a news article alone does not establish the release region or language support.
   Add 「発表されていません」 only to correct an existing claim about a relevant detail the readable sources leave unanswered.
   Do not add a caveat just because the article omits availability in Japan or support for Japanese. For example, an article
   about a company expanding its AI consulting team does not need a caveat about the launch of a product in Japan.
3. If no page could be read for this article, only fix internal contradictions (title vs body, stat vs body, wrong
   day-of-week for a date, different numbers for the same thing) and do not delete facts just because pages failed.
4. stat: every number must appear in the body with its meaning; fix or remove stat items that do not.
5. rina block: it may contain opinion, but every fact in it must be in the body and correct. Fix it if not.
   Keep it 2–3 sentences, ≤ 120 characters, no 「私」.
6. Keep the article's structure, length and wording except where a fix is needed; change only the words that are wrong. Fixed text must follow style.md
   (です・ます, paragraph ≤ 200 characters, numbers as in section 6, no behind-the-scenes phrases of section 8 such as
   「見つけられず」「今回読んだ」「参照した」「私は」, never mention pages or files).
7. Never change "id", "category", "image", "source_url", "source_name", "published", "visual", "refs" (you may only
   remove a ref whose page is clearly about another event), and never add/remove/change pictures ("img", "gallery").
8. If everything is correct, write out.json identical to article.json and write 「直すところなし」 in changes.txt.

Output:
- ./out.json — ONE valid JSON object with the same keys as article.json (check with `python3 -c "import json;json.load(open('out.json'))"`).
- ./changes.txt — Japanese, one line per change: `- 場所（例：p2・stat・rina）：「前」→「後」（理由：どのページに何とあるか／確認できず削除）`.
