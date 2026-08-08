# Exam practice app — build template

Hand this file to Claude along with a `questions.json` (or raw material to make
one from) and it has everything it needs to stand up the same app for a
different certification.

The reference implementation is the GH-900 repo. Everything below is either
**fixed** (copy it exactly — it is what makes the app work and look the way it
does) or **parameterized** (marked `«LIKE THIS»` — swap it per exam).

---

## 0. How to use this

**If the GH-900 repo is available on this machine**, do not write from scratch.
Copy `index.html` and `build.py`, then apply only the substitutions in §1 and
rewrite `TOPIC_RULES` (§5) and the question bank. That path is faithful and
fast. Verify with §10 either way.

**If it is not available**, build from this spec. Every number that matters is
here.

Either way: the exam-specific surface is small. It is the masthead lockup, the
mock-exam constants, the topic rules, the footer disclaimer, and the bank. The
CSS, the state machine, the grading, and the diff-gutter design are the same
app every time.

---

## 1. Fill this in first

```
«EXAM_CODE»       short code on the masthead badge, e.g. "GH-900", "AZ-900", "SAA-C03"
«EXAM_NAME»       full name, e.g. "GitHub Foundations", "Azure Fundamentals"
«VENDOR»          who owns the cert, e.g. "GitHub or Microsoft", "Amazon Web Services"
«ACCENT_HEX»      one brand-ish accent, light mode, e.g. #4C4FD1
«ACCENT_HEX_DARK» its dark-mode counterpart, e.g. #9092F5
«MOCK_N»          questions in the mock preset, e.g. 60
«MOCK_MIN»        minutes in the mock preset, e.g. 100
«TOPICS»          6–10 buckets derived from the exam's published objective domains
```

If the real exam's format is disputed across sources, pick the most credible
figures, say so in the footer, and **do not invent a pass/fail threshold.** See
§9.

---

## 2. What you are building

A static, single-page practice and mock-exam tool with the question bank baked
in. No server, no dependencies, no network calls. It is published with GitHub
Pages and also works by double-clicking `index.html` offline.

Three modes:

| Mode | Behavior |
| --- | --- |
| `practice` | Grades each question inline the moment you check it; shows the correct answer and the explanation |
| `test` | Silent until the end, then a score and which numbers you missed — no answers |
| `mock` | Test mode plus a «MOCK_N»-question, «MOCK_MIN»-minute countdown that auto-submits at zero |

`isTest()` means "not practice" — it is the switch for every silent-mode branch.

---

## 3. Repo layout

| File | Role |
| --- | --- |
| `questions.json` | **Source of truth for the question bank.** Humans edit this. |
| `index.html` | The whole app: markup, CSS, JS, and a generated copy of the bank. |
| `build.py` | Validates `questions.json` and injects it into `index.html`. |
| `CLAUDE.md` | Project contract. Write one — see §11. |
| `.gitignore` | `__pycache__/`, `*.pyc`, `.DS_Store`, `Thumbs.db`, `.vscode/`, `.idea/` |

### The one rule

`index.html` contains a generated copy of the bank on a single line starting
`const BANK = `. **Never hand-edit that line.** Edit `questions.json`, then run
`python3 build.py`.

Both files are committed — `index.html` has to carry the data so the page stays
self-contained, and `questions.json` is what humans actually edit. Any change to
the bank is a two-file commit; a diff that touches `questions.json` and not
`index.html` means the build step was skipped.

---

## 4. Question schema

```json
{
  "q": "Which of the following are available statuses of a pull request?",
  "choices": [
    { "label": "A", "text": "Draft" },
    { "label": "B", "text": "Closed" },
    { "label": "C", "text": "Rebasing" }
  ],
  "correct": ["A", "B"],
  "multi": true,
  "topic": "Collaboration: PRs, issues, projects",
  "explanation": "Draft and closed are real pull request states; rebasing is not.",
  "review": "Optional. Present only when the answer is disputed."
}
```

- `q` — plain text, no markdown or HTML. It is inserted with `textContent` /
  escaped, so tags render literally.
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
- `review` — optional. Present only when the stored answer is doubtful. Renders
  as a "Needs review" caution block wherever the explanation renders. Same
  empty-string rule.

The file is written as `json.dumps(qs, indent=1, ensure_ascii=False) + "\n"`.

---

## 5. `build.py`

Python 3 standard library only — `json, re, sys, collections, pathlib,
difflib`. No `package.json`, no bundler, ever.

```bash
python3 build.py                          # validate, tag, write both files
python3 build.py --check                  # validate only, write nothing, exit 1 on problems
python3 build.py --import raw.json        # merge a raw extraction batch, then build
python3 build.py --explanations raw.json  # backfill explanations and review flags
python3 build.py --dupes                  # audit for near-duplicate questions, write nothing
```

`--check` validates `questions.json` only. It never opens `index.html`, so it
**cannot** tell you the two have drifted — a plain `python3 build.py` is what
reconciles them. Say this in `CLAUDE.md`; it is an easy thing to claim falsely.

### Anchor and injection

```python
ANCHOR = re.compile(r"^const BANK = .*;$", re.M)
```

Refuse to write unless `len(ANCHOR.findall(page)) == 1`. Then:

```python
line = "const BANK = " + json.dumps(qs, ensure_ascii=False) + ";"
PAGE.write_text(ANCHOR.sub(lambda m: line, page, count=1), encoding="utf-8")
```

### Pipeline order

`read → (--import) → (--explanations) → normalize → validate → dedupe → report → write`

Validate *after* normalizing so derived fields exist, and *before* writing so a
malformed bank never reaches disk.

### `validate(qs)` — collect all problems, print them, `sys.exit(1)`, write nothing

- empty question text
- fewer than 2 choices
- duplicate choice labels
- a choice with empty text
- no correct answer
- a `correct` label that is not among the choices
- a repeated entry in `correct`
- more than 10 choices (the app labels A–J)
- `explanation` / `review` present but not a string, or present and blank

### `normalize(qs)`

Strip `correct` labels; recompute `multi`; auto-assign `topic` only when absent
or falsy; strip `explanation` and `review` when they are strings.

### `auto_topic(q)` — «TOPICS»

Scored keyword match. Question text counts **3×**, choice text **1×**, highest
score wins, below `TOPIC_FLOOR = 4` falls back to `General`.

```python
TOPIC_RULES = {
    "«Topic name»": [
        (r"«high-signal regex — exact commands, product names, service names»", 6),
        (r"«medium-signal regex — domain phrases»", 4),
        (r"«weak regex — generic nouns»", 2)],
    # …
}
```

Derive the buckets from the exam's **published objective domains**, not from
reading the questions. Weight 5–6 for terms that appear in essentially one
domain, 2 for generic nouns that appear everywhere.

Tagging is approximate and the UI says so. A handful will land in the wrong
bucket — fix those by pinning `topic` on the individual question rather than by
contorting the rules. `General` is a legitimate outcome, not a failure.

### `dedupe(qs)`

Drops questions whose normalized text (`re.sub(r"\s+", " ", s.strip().lower())`
then `.rstrip(".?:")`) matches exactly. Prints each drop.

### `convert_raw(raw)` — for `--import`

Converts an extraction shape (`question` / `answer_choices` object /
`correct_answer_letter` string like `"A, C"`) into the app shape. Skips and
reports entries with a null answer or an answer letter not present in the
choices. **Carries `explanation` across** — dropping it here is the single
easiest bug to ship, and it is silent.

### `backfill_notes(qs, raw)` — for `--explanations`

Matches on normalized question text. Fills **only empty fields**, so it is safe
to re-run and will not clobber hand-written text. Turns any raw entry marked
`verification_status: needs_review` into a `review` field holding that entry's
`verification_note`. Reports counts filled and how many bank questions had no
match.

### `find_duplicates(qs)` / `report_duplicates(qs)` — for `--dupes`

`dedupe` only collapses exact normalized matches. This is the wider net: score
every pair on five signals and print candidates for a human to judge. **It never
deletes.**

```python
BOILER = re.compile(r"\((?:[^)]*?(?:complete solution|choose \w+|select \w+)[^)]*)\)|"
                    r"\bselect (?:two|three|four|all that apply)\b", re.I)
```

| Signal | What it catches |
| --- | --- |
| `text` | `difflib.SequenceMatcher` on the boilerplate-stripped stem — near-identical wording |
| `stem` | Jaccard over stem vocabulary — order-independent rewording |
| `choices` | Jaccard over the normalized choice set — same option pool, reordered |
| `answer` | Jaccard over **tokens** of the correct-answer text — same fact asserted |
| `inverted` | `max(jaccard(stemA, ansB), jaccard(stemB, ansA))` — one question's answer restates the other's stem |

```python
strong = (sig["answer"] >= .55 or sig["inverted"] >= .50
          or sig["choices"] >= .55 or sig["text"] >= .78)
supported = sig["stem"] >= .40 and max(sig["answer"], sig["inverted"],
                                       sig["choices"], sig["text"]) >= .35
```

Two limits worth knowing before trusting a clean run:

- **It is lexical.** Questions testing one fact in different words score near
  zero on every signal. No threshold reaches them without hundreds of false
  positives. Reading the bank grouped by topic is the only way to find those.
- **Boilerplate skews it.** `(Each answer presents a complete solution. Choose
  three.)` appears on most multi-answer stems; left in, every pair of them looks
  similar. `BOILER` strips it before comparison — **extend that pattern** if the
  new exam phrases it differently, rather than raising the thresholds.

Use a token Jaccard for `answer`, not a raw ratio: a raw ratio scores short
answers like "Git repository" against "repository" at 0.83.

Reversed pairs are the common shape. Both directions are legitimate recall, so a
candidate is a question to answer, not an automatic deletion.

### Summary line

```
N questions (M before) · K multi-answer · E with explanations · F flagged for review
```
followed by the per-topic counts, most common first.

---

## 6. `index.html`

One file. Three `<section>`s toggled by the `hidden` attribute: `#setup`,
`#quiz`, `#results`. No framework, no router, no build step for the JS.

### Head

```html
<title>«EXAM_CODE» · «EXAM_NAME» practice</title>
<meta name="description" content="An unofficial practice and mock-exam tool for the «EXAM_CODE» «EXAM_NAME» certification.">
<meta name="color-scheme" content="light dark">
```

Favicon is an inline data-URI SVG — a rounded rect in «ACCENT_HEX» with a white
`+` glyph in the mono stack. It must not be an external file.

### Constants

```js
const $ = id => document.getElementById(id);
const LETTERS = "ABCDEFGHIJ";
const MOCK_N = «MOCK_N», MOCK_SEC = «MOCK_MIN» * 60;
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

let cfg = { mode:'practice', count:20, shufQ:true, shufC:true, onlyMulti:false };
let S = null;
```

### Setup screen

Masthead lockup: `«EXAM_CODE»` in a dark badge (`.code`), then `«EXAM_NAME»`
with a small-caps subtitle "Practice & mock exam". Three stats read live off
`BANK`: total questions, multi-answer count, distinct topics.

Length chips are generated: `[10, 20, 30, 50, BANK.length]`, with the last
rendered as `All N`. Default 20. The chip field is hidden in mock mode and
replaced by a fixed line: `«MOCK_N» questions · «MOCK_MIN»-minute countdown ·
auto-submits at zero`.

Three options, all checkboxes: shuffle question order (on), shuffle answer
choices (on, with the aside "so you can't memorize 'the answer is C'"),
multi-answer questions only (off, showing the count in the bank).

### Session state

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
re-running a question through `prep` (the "practice what I missed" path) is
safe.

```js
function prep(src){
  const choices = cfg.shufC ? shuffle(src.choices) : src.choices.slice();
  const correct = [];
  const out = choices.map((c, i) => {
    const label = LETTERS[i];
    if (src.correct.includes(c.label)) correct.push(label);
    return { label, text: c.text };
  });
  return { q: src.q, topic: src.topic, choices: out, correct, multi: src.multi,
           explanation: src.explanation, review: src.review };
}
```

⚠️ It rebuilds a fresh object, so **any key not listed here is silently
dropped.** Adding a field to the schema means adding it here too, or it will
exist in the JSON and never reach the screen. This has bitten the reference
repo.

### Other key functions

- `shuffle(a)` — Fisher–Yates on a copy.
- `eq(a, b)` — set equality: `a.length === b.length && a.every(x => b.includes(x))`.
- `esc(s)` — escapes `& < > "`. Every piece of bank text goes through this or
  `textContent`.
- `render()` — rebuilds the current question. It re-runs on every click, so the
  entry animation is gated on `S.lastI !== S.i` (`fresh`), with a per-row
  `animation-delay: ${n * 32}ms`.
- `pick(label)` — toggles for multi-answer, replaces for single. **Caps
  selections at `correct.length`** — you cannot select more than the answer
  needs.
- `clock()` — counts up, or down when `S.limit`; adds `.warn` at ≤600s left;
  calls `finish()` at zero.
- `finish()` — scores with set equality, builds the map, groups by topic,
  renders the review, wires "Practice what I missed".
- `countUp(el, to)` — cubic ease-out over 650ms on the score numeral, skipped
  when `REDUCED`.

### Grading render — the diff gutter

For a graded row: correct **and** picked → `.correct`, gutter `+`. Picked and
wrong → `.wrong`, gutter `−` (U+2212, not a hyphen). Correct and missed →
`.missed`, gutter `+` in a lighter treatment. Untouched → keeps its letter.

Verdict block, practice mode:

```js
v.innerHTML = (ok ? 'Correct' : 'Incorrect <em>— answer: ' + esc(q.correct.join(', ')) + '</em>')
  + (q.explanation ? '<span class="why">' + esc(q.explanation) + '</span>' : '');
```

Followed by a separate `<p class="flag" id="qFlag" hidden>` that shows only when
`done && q.review`, rendering `'<b>Needs review</b>' + esc(q.review)`.

### Keyboard

`1`–`9` and `a`–`j` select a choice; `Enter` fires the primary button. Both
suppressed when `#quiz` is hidden or focus is in an `INPUT`. Rows are
`tabindex="0"` with `role="radio"` / `role="checkbox"` and `aria-checked`, and
respond to Space and Enter.

### Results

Score numeral (green ≥75%, red <50%, neutral between — **cosmetic only, not a
pass/fail claim**), fraction, elapsed time and seconds-per-question, a grid of
numbered cells, per-topic meters sorted worst-first, and:

- **practice** → full answer review with the diff gutter, explanations, and any
  review flags; map cells become buttons that scroll to their review item.
- **test / mock** → just the list of missed numbers, plus the "Practice what I
  missed" button which re-runs those questions through `prep` in practice mode.

---

## 7. Design system

The signature is the **diff gutter**: a graded question reads like a diff of
your answer against the correct one. Keep it if you restyle — it is the one
distinctive idea in the layout and it carries the grading semantics.

### Tokens — copy verbatim, swap only the two accents

```css
:root{
  --canvas:#FAFBFD;  --panel:#FFFFFF;   --raise:#F4F7FA;
  --ink:#0F1419;     --muted:#59636E;   --faint:#818C99;
  --rule:#D6DDE5;    --rule-soft:#E7ECF1;
  --add:#1A7F37;     --add-tint:#E7F6EC; --add-edge:#A2D6B3;
  --del:#B42318;     --del-tint:#FDECE9; --del-edge:#F0B2AB;
  --accent:«ACCENT_HEX»; --accent-soft:#EDEDFC; --accent-edge:#BFC0F2;
  --warn:#8A6100;    --warn-tint:#FDF6DC; --warn-edge:#E0C169;
  --shadow:0 1px 2px rgba(15,20,25,.05), 0 8px 24px -12px rgba(15,20,25,.14);
  --font-body:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --font-mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
  --gutter:52px;     --maxw:820px;
}
@media (prefers-color-scheme:dark){
  :root{
    --canvas:#0C1016;  --panel:#141A22;   --raise:#1A222C;
    --ink:#E6EDF5;     --muted:#9AA7B4;   --faint:#6E7C8B;
    --rule:#2A333E;    --rule-soft:#212933;
    --add:#4CC46A;     --add-tint:#12291A; --add-edge:#2C5F3C;
    --del:#F2685C;     --del-tint:#2E1512; --del-edge:#6B2E28;
    --accent:«ACCENT_HEX_DARK»; --accent-soft:#1B1D3A; --accent-edge:#3B3E7A;
    --warn:#E0B341;    --warn-tint:#241E0E; --warn-edge:#5C4A1E;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -14px rgba(0,0,0,.7);
  }
}
```

**Never hard-code a color** in markup or JS; add a variable. Anything added to
`:root` needs a dark counterpart **in the same commit** — the `--warn` trio,
used by the "Needs review" block, is the pattern to copy.

### Type scale

| Element | Size |
| --- | --- |
| body | 18px / 1.55 |
| question stem | 25px, weight 550, `letter-spacing:-.014em` |
| choice text | 18px |
| score numeral | 82px mono, `font-variant-numeric:tabular-nums` |
| masthead code badge | 46px mono |
| eyebrows / labels / buttons | 11.5–14px mono, `letter-spacing:.1em`–`.16em`, uppercase |

Monospace is the display and utility face — eyebrows, labels, buttons, numbers.
Body face is the system stack. It was deliberately set large; **do not shrink it
back to defaults.**

### Layout

820px max width, 52px gutter column (42px under 640px). Sticky top bar with
mode pill, position, live score (practice only), clock, and a 3px progress
track. Mobile breakpoint at 640px collapses the mode grid to one column, drops
the keyboard hint, and makes buttons full width.

### Motion

Gated on `REDUCED` in JS **and** a media query in CSS:

```css
@media (prefers-reduced-motion:reduce){*{animation:none !important;transition:none !important}}
```

Anything new that animates gets the same treatment.

---

## 8. Hard constraints

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

---

## 9. Copy rules

- Sentence case, plain verbs, no exclamation marks.
- Buttons say what happens: "Check answer", "Practice what I missed".
- **American spelling throughout** — code, comments, docs, and UI copy. Match
  the bank; mixing dialects between the chrome and the questions is the failure
  mode. (The reference repo shipped "Practise what I missed" over an entirely
  American bank before this was written down.)
- Footer, adapted per exam:

  > **Unofficial.** Not affiliated with, endorsed by, or reviewed by «VENDOR».
  > Answers come from the bundled question bank and have not been verified
  > against the official study guide — check anything that looks wrong. Exam
  > figures are approximate. Nothing is saved — closing the tab clears your
  > session.

- **Do not add a "you passed" line** unless the vendor publishes an actual
  passing percentage. Third-party sources contradict each other constantly on
  question counts, time limits, and cut scores. Show the score; let the user
  judge. The green/red numeral is styling, not a verdict.

---

## 10. Acceptance checklist

Run all of these before calling it done.

```bash
python3 build.py --check     # exits 0, reports the counts you expect
python3 build.py             # writes both files
git diff --stat              # MUST show questions.json AND index.html
python3 build.py --dupes     # review candidates by hand
```

Then confirm the baked copy really matches the source:

```bash
python3 - <<'PY'
import json, re, pathlib
src = json.loads(pathlib.Path("questions.json").read_text())
line = re.search(r"^const BANK = (.*);$", pathlib.Path("index.html").read_text(), re.M).group(1)
print("in sync" if json.loads(line) == src else "DRIFTED")
PY
```

In the browser (`file://` is the real target; if a tool blocks it, serve with
`python3 -m http.server` — the app itself still makes no requests):

- [ ] Practice: answer correctly → green `+` gutter, "Correct", **explanation shown**
- [ ] Practice: answer wrong → red `−` on your pick, green `+` on the answer, explanation shown
- [ ] A question with `review` shows the "Needs review" block; one without does not
- [ ] Multi-answer: caps selection at the answer count; grades only on an exact set match
- [ ] Shuffle choices on → the correct answer moves position across runs and still grades right
- [ ] Test mode: no verdict, no answers, missed numbers listed at the end
- [ ] Mock: clock counts down, turns red at 10:00, auto-submits at zero
- [ ] "Practice what I missed" re-runs only the missed questions, in practice mode
- [ ] Results: topic meters sum to the session length; map cells jump to review
- [ ] Keyboard: `1`–`9` selects, `Enter` advances
- [ ] Dark mode: every surface, gutter, and the "Needs review" block are legible
- [ ] 375px wide: nothing overflows, buttons are full width
- [ ] Reduced motion: no animation anywhere, score numeral appears at its final value

---

## 11. Ship it

Write a `CLAUDE.md` for the new repo before finishing. It is the contract that
stops the next session from hand-editing the `const BANK` line. It must cover:
what this is and that it is unofficial; the repo layout table; **the one rule**;
the schema; the topic list and how tagging works; the app architecture and state
shape; the design conventions including the diff gutter and the no-hard-coded-
color rule; the constraints in §8; a **Known data issues** section; and the exam
format facts with their sourcing.

The "Known data issues" section is not optional and not boilerplate. Record what
you actually know about the bank's provenance — where the raw data came from and
whether it is in the repo, how many entries were dropped and why, which answers
were corrected against which sources, and which duplicates you found but chose
to keep. An explanation extracted from the same source as its answer is **not**
independent confirmation of that answer; where one contradicts the other, trust
neither until you have checked. Treat the bank as community-quality and say so
in the footer.

Publishing: `index.html` at the repo root is served by GitHub Pages with no
configuration — Settings → Pages → Source: Deploy from a branch → `main` / `/`
(root). **If the bank came from screenshots of a real proctored exam rather than
a practice course, a public repo is a risk under the certification agreement —
host it private.**
