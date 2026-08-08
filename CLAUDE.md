# GH-300 practice app

A static, single-page practice and mock-exam tool for the **GH-300 GitHub
Copilot** certification. The question bank is baked into the page: no server, no
dependencies, no network calls. It is published with GitHub Pages and also works
by double-clicking `index.html` offline.

**Unofficial.** Not affiliated with, endorsed by, or reviewed by GitHub or
Microsoft. The bank is community-quality material of unverified provenance —
read the "Known data issues" section below before trusting any single answer.

Three modes:

| Mode | Behavior |
| --- | --- |
| `practice` | Grades each question inline the moment you check it; shows the correct answer and the explanation |
| `test` | Silent until the end, then a score and which numbers you missed — no answers |
| `mock` | Test mode plus a 65-question, 100-minute countdown that auto-submits at zero |

`isTest()` means "not practice" — it is the switch for every silent-mode branch.

---

## Repo layout

| File | Role |
| --- | --- |
| `questions.json` | **Source of truth for the question bank.** Humans edit this. |
| `index.html` | The whole app: markup, CSS, JS, and a generated copy of the bank. |
| `build.py` | Validates `questions.json` and injects it into `index.html`. |
| `CLAUDE.md` | This file. |
| `EXAM-APP-TEMPLATE.md` | The spec this repo was built from, for porting to another exam. |
| `.gitignore` | `__pycache__/`, `*.pyc`, `.DS_Store`, `Thumbs.db`, `.vscode/`, `.idea/` |

### The one rule

`index.html` contains a generated copy of the bank on a single line starting
`const BANK = `. **Never hand-edit that line.** Edit `questions.json`, then run
`python3 build.py`.

Both files are committed — `index.html` has to carry the data so the page stays
self-contained, and `questions.json` is what humans actually edit. Any change to
the bank is a two-file commit; a diff that touches `questions.json` and not
`index.html` means the build step was skipped.

`python3 build.py --check` validates `questions.json` only. It never opens
`index.html`, so it **cannot** tell you the two have drifted. A plain
`python3 build.py` is what reconciles them. To prove they match:

```bash
python3 - <<'PY'
import json, re, pathlib
src = json.loads(pathlib.Path("questions.json").read_text())
line = re.search(r"^const BANK = (.*);$", pathlib.Path("index.html").read_text(), re.M).group(1)
print("in sync" if json.loads(line) == src else "DRIFTED")
PY
```

---

## Question schema

```json
{
  "q": "What is zero-shot prompting?",
  "choices": [
    { "label": "A", "text": "Asking without providing examples." },
    { "label": "B", "text": "Providing several worked examples first." }
  ],
  "correct": ["A"],
  "multi": false,
  "topic": "Prompt engineering & context",
  "explanation": "Zero-shot prompting gives the model the task with no worked examples.",
  "corrected": "Optional. Present when this repo changed the answer key or the question text.",
  "review": "Optional. Present only when the stored answer is disputed."
}
```

- `q` — plain text, no markdown or HTML. It is inserted escaped, so tags render
  literally.
- `choices` — 2 to 10. Labels are conventionally `A`, `B`, `C`… but the app
  relabels sequentially at runtime, so source labels only need to be unique and
  to match `correct`.
- `correct` — array of labels. Order does not matter; grading is set equality.
- `multi` — **derived, never set by hand.** The build recomputes it as
  `len(correct) > 1` on every run.
- `topic` — auto-assigned by the build when absent. Set it manually to pin one;
  delete the field to re-auto-tag.
- `explanation` — optional. Shown in practice mode under the verdict on **both**
  correct and incorrect answers, and again in the answer review. Omit the field
  rather than setting `""`; the build rejects an empty string.
- `corrected` — optional. **Provenance marker: present whenever this repo
  changed the answer key or the question text from what the bank shipped.** It
  says what was changed and why, renders as an "Answer corrected" block in the
  accent color wherever the explanation renders, and must never be deleted to
  tidy up — it is the audit trail for edits that were not in the source
  material. Same empty-string rule.
- `review` — optional. Present only when the stored answer is doubtful. Renders
  as a "Needs review" caution block wherever the explanation renders. Same
  empty-string rule.

`corrected` and `review` mean opposite things: `corrected` says "this was wrong
and has been fixed", `review` says "this looks wrong and has *not* been fixed".

The file is written as `json.dumps(qs, indent=1, ensure_ascii=False) + "\n"`.

---

## `build.py`

Python 3 standard library only — `json, re, sys, collections, pathlib,
difflib`. No `package.json`, no bundler, ever.

```bash
python3 build.py                          # validate, tag, write both files
python3 build.py --check                  # validate only, write nothing, exit 1 on problems
python3 build.py --import raw.json        # merge a raw extraction batch, then build
python3 build.py --explanations raw.json  # backfill explanations and review flags
python3 build.py --dupes                  # audit for near-duplicate questions, write nothing
```

Pipeline order: `read → (--import) → (--explanations) → normalize → validate →
dedupe → report → write`. Validation runs after normalizing so derived fields
exist, and before writing so a malformed bank never reaches disk. Any problem
prints every issue found and exits 1 without writing.

`--dupes` only ever prints. `dedupe()` inside a normal build drops questions
whose normalized text matches **exactly**; the audit is the wider net, scoring
every pair on five lexical signals (`text`, `stem`, `choices`, `answer`,
`inverted`) for a human to judge. It is lexical, so two questions testing one
fact in different words score near zero on every signal — a clean run means "no
lexical twins", not "no duplicates". `BOILER` strips
`(Each answer presents a complete solution. Choose three.)`-style tails before
comparing; extend that pattern rather than raising the thresholds if new
phrasings show up.

### Topics

Nine buckets, derived from the **published GH-300 skills measured** (Microsoft
Learn, "as of August 7, 2026"), not from reading the questions. Six domains are
published; two of the large ones are split so the results meters say something
useful:

| Published domain (weight) | Bucket(s) here |
| --- | --- |
| Use GitHub Copilot responsibly (15–20%) | Responsible AI |
| Use GitHub Copilot features (25–30%) | Copilot in the IDE & CLI · Chat, agents & MCP · Plans, policies & administration |
| Understand GitHub Copilot data and architecture (10–15%) | Data handling & architecture |
| Apply prompt engineering and context crafting (10–15%) | Prompt engineering & context |
| Improve developer productivity with GitHub Copilot (10–15%) | Developer productivity · Testing & code quality |
| Configure privacy, content exclusions, and safeguards (10–15%) | Privacy & content exclusions |

Plus `General`, the fallback. `General` is a legitimate outcome, not a failure.

`auto_topic()` is a scored keyword match: question text counts **3×**, choice
text **1×**, highest score wins, and anything below `TOPIC_FLOOR = 4` becomes
`General`. Weights are 5–6 for terms that appear in essentially one domain, 2
for generic nouns. Note that `copilot` appears in nearly every question in this
bank and is deliberately absent from every pattern — it would be pure noise.

Tagging is approximate and the UI says so. A handful land in the wrong bucket;
fix those by pinning `topic` on the individual question rather than by
contorting the rules.

---

## `index.html`

One file. Three `<section>`s toggled by the `hidden` attribute: `#setup`,
`#quiz`, `#results`. No framework, no router, no build step for the JS.

```js
const $ = id => document.getElementById(id);
const LETTERS = "ABCDEFGHIJ";
const MOCK_N = 65, MOCK_SEC = 100 * 60;
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

let cfg = { mode:'practice', count:20, shufQ:true, shufC:true, onlyMulti:false };
let S = null;
```

Session state:

```js
S = { qs, i, picks, graded, t0, lastI, limit, tick }
```

- `qs` — the prepared questions for this run (shuffled, relabeled)
- `picks[i]` — array of chosen labels for question `i`
- `graded[i]` — practice mode only; true once the answer has been checked
- `limit` — countdown seconds; `0` means count up instead

### `prep(src)` — the important one

Shuffles choices and **relabels them sequentially A, B, C…**, remapping
`correct` to the new labels. This is why shuffling never breaks grading, and why
re-running a question through `prep` (the "Practice what I missed" path) is
safe.

⚠️ It rebuilds a fresh object from a fixed key list, so **any key not listed
there is silently dropped.** Adding a field to the schema means adding it to
`prep` too, or it will exist in the JSON and never reach the screen. The list is
currently `q, topic, choices, correct, multi, explanation, review, corrected` —
`corrected` was added later and needed exactly this, plus a render branch in
both `render()` and the results review.

### Other key functions

- `shuffle(a)` — Fisher–Yates on a copy.
- `eq(a, b)` — set equality.
- `esc(s)` — escapes `& < > "`. Every piece of bank text goes through this or
  `textContent`.
- `render()` — rebuilds the current question. It re-runs on every click, so the
  entry animation is gated on `S.lastI !== S.i`, with a per-row
  `animation-delay: ${n * 32}ms`.
- `pick(label)` — toggles for multi-answer, replaces for single. **Caps
  selections at `correct.length`.**
- `clock()` — counts up, or down when `S.limit`; adds `.warn` at ≤600s left;
  calls `finish()` at zero.
- `finish()` — scores with set equality, builds the map, groups by topic,
  renders the review, wires "Practice what I missed".
- `countUp(el, to)` — cubic ease-out over 650ms on the score numeral, skipped
  when `REDUCED`.

Keyboard: `1`–`9` and `a`–`j` select a choice; `Enter` fires the primary button.
Both are suppressed when `#quiz` is hidden or focus is in an `INPUT`. Rows are
`tabindex="0"` with `role="radio"` / `role="checkbox"` and `aria-checked`, and
respond to Space and Enter.

---

## Design conventions

The signature is the **diff gutter**: a graded question reads like a diff of
your answer against the correct one. Correct **and** picked → `.correct`, gutter
`+`. Picked and wrong → `.wrong`, gutter `−` (U+2212, not a hyphen). Correct and
missed → `.missed`, gutter `+` in a lighter treatment. Untouched → keeps its
letter. Keep it if you restyle — it is the one distinctive idea in the layout
and it carries the grading semantics.

**Never hard-code a color** in markup or JS; add a variable to `:root`. Anything
added there needs a dark counterpart **in the same commit** — the `--warn` trio
used by the "Needs review" block is the pattern to copy.

Accents for this exam: `--accent:#6E40C9` light, `#A371F7` dark. Everything else
in the token block is shared across the exam family and should not drift.

Type scale: body 18px/1.55, question stem 25px weight 550, choice text 18px,
score numeral 82px mono with tabular numerals, masthead code badge 46px mono,
eyebrows and buttons 11.5–14px mono uppercase with wide tracking. Monospace is
the display and utility face; body face is the system stack. The body size was
deliberately set large — **do not shrink it back to defaults.**

Layout: 820px max width, 52px gutter column (42px under 640px), sticky top bar,
3px progress track, mobile breakpoint at 640px. Motion is gated on `REDUCED` in
JS **and** `@media (prefers-reduced-motion:reduce)` in CSS; anything new that
animates gets the same treatment.

Copy: sentence case, plain verbs, no exclamation marks, buttons say what
happens. **American spelling throughout** — code, comments, docs, and UI copy.
The bank is American; mixing dialects between the chrome and the questions is
the failure mode.

---

## Hard constraints

- **No `localStorage`, `sessionStorage`, or cookies.** Sessions are deliberately
  ephemeral and the footer promises this.
- **No external requests.** No CDNs, no web fonts, no analytics, no images. It
  must work offline and from `file://`.
- **`index.html` stays self-contained.** Do not split CSS or JS into separate
  files, and do not make the page `fetch()` `questions.json` — that breaks under
  `file://`, which is exactly why the build step exists.
- **Python 3 standard library only.**
- Bank text is untrusted-ish input: everything goes through `esc()` or
  `textContent`. No `innerHTML` with raw bank strings.
- **No "you passed" line.** See the exam format facts below.

---

## Known data issues

Read this before trusting any single answer, and before "fixing" something that
looks odd.

**Provenance is unknown.** The bank arrived as a finished `questions.json` of
307 entries with answers and explanations already attached. No raw extraction
file, no source citation, and no verification metadata came with it, and none is
in this repo. Nothing has been checked against the official study guide. Treat
it as community-quality material.

**The explanations have been replaced.** As shipped, every one was a mechanical
restatement of the stored answer key — "This answer is correct because it
identifies …", "Together, the selected answers identify …" — generated from the
answer, and therefore worthless as confirmation of it. All of them were rewritten
against primary sources (see below). The answer keys themselves were **not**
touched, so an explanation and its key can still disagree; where they do, the
question carries a `review` flag saying so.

**Transcription artifacts.** The text shows signs of speech-to-text or OCR
capture: stray periods mid-sentence ("Use a. gitignore file"), doubled
boilerplate ("((Choose two.).)"), inconsistent capitalization of product names
("GitHub Copilot business"), and at least one choice with fragments of the
option list embedded in it (`[184]`, "code. b. c. by deleting existing tests.").
These are cosmetic and were left alone; the answer keys are what matter.

**What was changed here, and only this:**

- **Topics were re-derived.** The bank shipped with all 307 questions pinned to
  a 15-bucket taxonomy of unknown origin (`Copilot fundamentals`, `Copilot in
  the SDLC`, `Knowledge bases`, …) that did not match the exam's published
  domains. Every `topic` was removed so `auto_topic()` could re-tag against the
  nine buckets above. Nothing else in any entry was touched by that step.
- **Two verbatim duplicates were dropped**, both confirmed by hand from
  `--dupes` output, leaving 305:
  - the Copilot CLI install scenario appeared twice with the choices reordered;
    the copy with a garbled doubled stem ("You are a developer who frequently
    work You are a developer who frequently works from…") was dropped.
  - "How is GitHub Copilot Individual billed?" appeared twice with identical
    choices and the same answer; the copy with the malformed
    "((Choose two.).)." tail was dropped.
- **Every explanation was rewritten** against primary sources: the Microsoft
  Learn GH-300 study guide, the GitHub Copilot documentation (plans, content
  exclusion, code referencing, prompt engineering, code review, CLI, the
  responsible-use application cards), the Copilot REST API reference, and the
  Microsoft Learn responsible AI module. Each says *why* the keyed answer is
  right and, where it earns its place, why the tempting distractor is wrong.
  Question text, choices, and `correct` arrays were **not** modified.
- **33 bad answer keys were found, and 31 of them resolved.** Rewriting the
  explanations meant reading every item against the documentation, which
  surfaced far more bad keys than the duplicate audit had. The
  [Microsoft Learn study guide](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/gh-300)
  is the authority on scope; the Copilot product documentation is the authority
  on behavior. What was done:

  **Every edit is marked in the data.** All 25 changed questions carry a
  `corrected` field naming what was changed and why, which the app shows as an
  "Answer corrected" block next to the explanation. Nothing was altered
  silently, and a reader can always see where this repo departs from the source
  material. The six dropped questions are listed below rather than in the data,
  since there is no record left to attach a field to.

  - **19 keys corrected.** Eleven were corrupt multi-answer keys — every option
    marked correct, or two keyed options contradicting each other — collapsed to
    the defensible answer. (This is why the multi-answer count dropped from 57
    to 46; those were never real multi-answer questions.) The other eight
    contradicted the documentation: Copilot *does* suggest deprecated functions,
    it does *not* identify sensitive data, prompt collection is an
    individual-plan setting, and so on.
  - **6 questions edited.** Two had the wrong answer count in the stem. Three
    were built on `.copilotignore`, which is not a feature, and were rewritten
    to name content exclusions and their path patterns; one of those also stated
    its limitation backwards. One named a "GitHub Copilot for Azure DevOps"
    plan, corrected to Copilot Business.
  - **6 questions dropped** as unanswerable, leaving 299: one with no question
    text at all, one asking which item is *not* a Copilot feature where all four
    listed are features, and four where no option was correct (few-shot
    prompting, a chat slash command, Copilot Individual billing, and a
    "GitHub Productivity API" that does not exist).
  - **2 left flagged.** Both have a defensible keyed answer wrapped in wrong
    wording: one invents a Copilot "private mode", the other garbles the REST
    endpoint paths. Correcting them would mean rewriting the options into a
    different question, so they carry `review` notes instead. **A flagged
    question still grades against its stored key** — the app does not know the
    key is suspect.

**Duplicates that were kept.** `--dupes` reports around 390 candidate pairs.
Most are an artifact of the `answer` signal: dozens of plan questions have
one-token answers like "GitHub Copilot Enterprise", which score 1.00 against
each other while the questions are unrelated. The near-identical-wording band
(`text ≥ 0.80`) was reviewed pair by pair; apart from the two dropped above, the
rest are legitimate recall variants that ask the same thing with different
option pools ("Which IDEs support GitHub Copilot?" against "Which IDEs
officially support GitHub Copilot?", "primary goal" against "primary purpose").
Those were kept deliberately. The `choices ≥ 0.55` band was reviewed too and
contains no duplicates — only different questions drawing on the same pool of
plan names or responsible-AI principles.

**The lexical ceiling still applies.** Questions testing one fact in genuinely
different words are not reachable by `--dupes` at any threshold. Reading the
bank grouped by topic is the only way to find those. That reading has now
happened once, during the explanation rewrite, and it turned up the contradictory
pairs recorded above — but it was done for explanation accuracy, not as a
systematic duplicate hunt.

**What is still unverified.** The 272 questions without a `review` flag were
read against the documentation and their keys looked defensible, which is weaker
than saying each was confirmed against a citation. Product naming is the
likeliest source of residual error: the bank predates the plan rename (Copilot
Individual is now Copilot Pro) and the January 2026 feature additions, so items
about plans and features can be stale without being wrong in their own frame.

---

## Exam format facts and their sourcing

| Fact | Value | Source |
| --- | --- | --- |
| Objective domains | The six "skills at a glance" listed above | [Microsoft Learn study guide for Exam GH-300](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/gh-300), skills measured as of **August 7, 2026** |
| Passing score | 700 of 1000, **scaled** | Same page, via Microsoft's exam scoring and score reports |
| Question count | ~65 graded (plus unscored items) | Third-party exam guides only — **not published by Microsoft or GitHub** |
| Time limit | 100 minutes | Third-party exam guides only |

The mock preset uses **65 questions / 100 minutes** on that basis, and the
footer says the figures are approximate.

**Do not add a "you passed" line.** 700/1000 is a scaled score: it does not
correspond to any fixed percentage of questions answered correctly, and the
scaling is not published. The green/red score numeral in the results screen is
styling, not a verdict — green ≥75%, red <50%, neutral between.

The study guide's own "skills at a glance" list prints
`Use GitHub Copilot features (25–30%)` twice in slightly different wording,
which appears to be a documentation error rather than seven domains. The
per-domain sections below it list six. Older material (and much of the internet)
describes a **seven**-domain structure with different weights — that predates
the January 2026 revision that brought Agent Mode, MCP, Copilot Spaces, and
Copilot CLI into scope. This repo follows the current published version. If the
skills measured are revised again, `TOPIC_RULES` is the thing to update.

---

## Publishing

`index.html` at the repo root is served by GitHub Pages with no configuration —
Settings → Pages → Source: Deploy from a branch → `main` / `/` (root).

The provenance of this bank is unknown. If it ever turns out to have come from
screenshots of a real proctored exam rather than practice material, a public
repo is a risk under the certification agreement and it should be made private.
