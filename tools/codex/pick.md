You choose official pictures for one article of 「マイ夕刊」, a Japanese tech-news app and its public site.
Work ONLY with the files in the current folder. There is no internet.

Files here:
- story.jpg (attached to this message) — the candidate pictures, each with its number n in an orange box under it.
- info.md — the article (title, summary, text, source URLs, existing official picture count) and, for each candidate n:
  its size, the page it was found on, credit, alt text.

Choose all suitable official pictures up to 12, in order of how well they show the subject of the article.
Subtract the existing official picture count in info.md from 12 to know how many you can add (the user's decision 2026-11-20).
Choose none if the article already has 12 or more.
A picture fits only if ALL of these are true:
1. It comes from an official page: the company's or organization's own site, newsroom, blog, product or store page,
   or a press-release service (PR TIMES, @Press, Business Wire, PR Newswire...). Not a news site, blog, shop review,
   stock-photo site or social network. Check the page URL in info.md.
2. It shows something of THIS article: the product, the screen or feature, the game, the service, a diagram or chart
   about it, the place or event. Not a different product or an older unrelated item.
   Compare the candidate's page with the article's source URLs and text. A separate official page can fit if it is about the
   same news. Skip separate announcements about other events, even from the same company.
   A picture on the same page as the source must still show the article's specific feature or subject.
   「FAKE DATA」など、仮の数値を使ったと明記されたグラフは外す。
   人物が主役で、記事で扱う製品や機能が小さく写っているだけの写真は外す。
   Skip pictures of other features in the same announcement (e.g. search results in a story about stereo sound in calls).
   Not an older edition: if a banner or picture shows a date, check it fits the article's year (a weekday that does not
   match this year's date means it is from another year, e.g. a sale page from last year). Not the single products of a
   sale or shop page (food, daily goods...) unless the article is about that product.
3. It is not: a photo dominated by people's faces (a portrait, a speaker on stage, a headshot, a group around a table
   with large faces in view, or a video thumbnail made of a face and big text, e.g. YouTube); a generic stock or mood
   photo (hands, people at a laptop, an abstract "AI" image) that does not show the real product, screen or event, even if
   the people are far away or their faces are hidden; an image made up only of logos, wordmarks or icons,
   including a lineup of connected app icons; a screenshot that shows the actual feature can still fit;
   an ad, banner, campaign or coupon graphic that is mainly text (but a guide image that shows the article's own screen or
   feature may be chosen even if it has a lot of text); a generic site share image;
   a blurry, broken, mostly empty or "(could not load)" picture; a near-duplicate of a picture you
   already chose (then keep only the bigger one).
When in doubt, leave it out.

For each chosen picture write a caption in Japanese: what is shown, 10–40 characters, plain words, using the same names
as the article text (e.g. 「Pixel 10の新しい通話画面」). No URL, no 「公式画像」, no guesses about things you cannot see.
If a number is hard to tell from the picture, leave it out of the caption.

Output:
- ./pick.json — a JSON array, best picture first: [{"n": 2, "caption": "…"}, …]  (an empty array [] if none fits).
- ./why.txt — one short line in Japanese: which numbers you left out and why (e.g. 「3は顔写真、5はロゴだけ」).
