You choose official pictures for one article of 「マイ夕刊」, a Japanese tech-news app and its public site.
Work ONLY with the files in the current folder. There is no internet.

Files here:
- story.jpg (attached to this message) — the candidate pictures, each with its number n in an orange box under it.
- info.md — the article (title, summary, text) and, for each candidate n: its size, the page it was found on, credit, alt text.

Choose EVERY candidate that fits (the user's rule: use all suitable official pictures), and none that does not.
A picture fits only if ALL of these are true:
1. It comes from an official page: the company's or organization's own site, newsroom, blog, product or store page,
   or a press-release service (PR TIMES, @Press, Business Wire, PR Newswire...). Not a news site, blog, shop review,
   stock-photo site or social network. Check the page URL in info.md.
2. It shows something of THIS article: the product, the screen or feature, the game, the service, a diagram or chart
   about it, the place or event. Not a different product or an older unrelated item.
3. It is not: a photo whose main subject is a person's face (a portrait, a speaker on stage, a headshot); a logo or
   wordmark alone; an icon or app icon alone; an ad, banner, campaign or coupon graphic that is mainly text; a generic
   site share image; a blurry, broken, mostly empty or "(could not load)" picture; a near-duplicate of a picture you
   already chose (then keep only the bigger one).
When in doubt, leave it out.

For each chosen picture write a caption in Japanese: what is shown, 10–40 characters, plain words, using the same names
as the article text (e.g. 「Pixel 10の新しい通話画面」). No URL, no 「公式画像」, no guesses about things you cannot see.

Output:
- ./pick.json — a JSON array, best picture first: [{"n": 2, "caption": "…"}, …]  (an empty array [] if none fits).
- ./why.txt — one short line in Japanese: which numbers you left out and why (e.g. 「3は顔写真、5はロゴだけ」).
