You are the edition worker {WORKER} of 「マイ夕刊」. Write your stories for the {EDITION} of {TODAY}.

Read ./brief.md completely first: it is the same brief the other workers get (task spec + マイ夕刊 記事執筆ルール), and you
must follow every rule in it, with these differences that override the brief because you run on GitHub without internet:
- You have NO internet. No WebSearch, no WebFetch, no curl. Ignore every instruction about searching or opening pages,
  including the 2–4 searches for the personal-interest topics: for those topics, look only in your news folder and
  prefer them when they are there.
- Your news folder is ./news/{ED}/{WORKER}/ (index.md + one .txt per story). Write only from these files. Every URL you
  write (source_url, refs, image src/page) must be copied exactly from these files (URL / OG_IMAGE / IMAGES lines or
  index.md). refs = only articles from this folder that you actually used (source_url first; another .txt in the
  folder about the SAME event may be added). No official pages unless one is in your folder.
- ./used.txt lists stories already published: skip those and the same events.
- Write your output to ./{WORKER}.json (a JSON array of 4 stories, the format in the brief's "Output" section). Put any
  scratch files in ./tmp/. Check it with `python3 -c "import json;json.load(open('{WORKER}.json'))"`.
- Before saving, do the brief's Self-check against the .txt files and style.md section 11 (出す前の確認): every paragraph
  ≤ 200 characters, sentences under 60 characters, rina ≤ 120 characters, no behind-the-scenes phrases
  (「見つけられず」「今回読んだ」「参照した」「私は」), numbers written as in section 6.
Final reply: one line (how many stories, any problem).
