#!/usr/bin/env python3
"""
Sync the question banks into index.html.

    python3 build.py                 # validate, tag, inject every bank into index.html
    python3 build.py --check         # validate only, change nothing (exit 1 on problems)
    python3 build.py --import raw.json         # merge a raw screenshot-format batch, then build
    python3 build.py --explanations raw.json   # backfill explanations and review flags onto the bank
    python3 build.py --dupes                  # audit for near-duplicate questions, write nothing
    python3 build.py --bank supplemental ...  # scope any of the above to one bank

There are two banks and they are kept strictly separate — the app never mixes
them in a session, and neither does this script: validation, deduping and the
duplicate audit all run per bank. `--bank` scopes a command to one of them;
without it, build/check/dupes cover every bank, while --import and
--explanations default to the legacy bank they were written for.

Each bank's .json is the source of truth. index.html carries a generated copy of
each so the page stays a single self-contained file. Never hand-edit a copy.

Requires nothing but the Python 3 standard library.
"""

import json, re, sys, collections, pathlib, difflib

ROOT = pathlib.Path(__file__).parent
PAGE = ROOT / "index.html"


class Bank:
    """One question bank: a source file and the `const` it is injected into."""

    def __init__(self, name, filename, const):
        self.name = name
        self.path = ROOT / filename
        self.const = const
        self.anchor = re.compile(r"^const %s = .*;$" % re.escape(const), re.M)

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, qs):
        self.path.write_text(json.dumps(qs, indent=1, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    def inject(self, page, qs):
        if len(self.anchor.findall(page)) != 1:
            print(f"\nCould not find exactly one `const {self.const} = ...;` line "
                  f"in index.html — aborting.")
            sys.exit(1)
        line = f"const {self.const} = " + json.dumps(qs, ensure_ascii=False) + ";"
        return self.anchor.sub(lambda m: line, page, count=1)


BANKS = [
    Bank("legacy", "questions.json", "BANK"),
    Bank("supplemental", "supplemental.json", "BANK_SUPP"),
    Bank("refactored", "questions-refactored.json", "BANK_REFAC"),
]

# ---------------------------------------------------------------- topics
# Scored keyword match: question text counts triple, answer choices single.
# Highest score wins; anything below the floor falls back to "General".
#
# The buckets come from the published GH-300 skills measured (Microsoft Learn,
# "as of August 7, 2026"). Six domains are published; two of them are split here
# because they are large and the bank leans on them heavily:
#
#   Use GitHub Copilot responsibly ................. Responsible AI
#   Use GitHub Copilot features .................... Copilot in the IDE & CLI
#                                                    Chat, agents & MCP
#                                                    Plans, policies & administration
#   Understand Copilot data and architecture ....... Data handling & architecture
#   Apply prompt engineering and context crafting .. Prompt engineering & context
#   Improve developer productivity ................. Developer productivity
#                                                    Testing & code quality
#   Configure privacy, content exclusions, safeguards  Privacy & content exclusions
#
# "copilot" itself is deliberately absent from every pattern — it appears in
# nearly every question in this bank and would score nothing but noise.
TOPIC_RULES = {
    "Responsible AI": [
        (r"responsible (ai|use)|ethical|\bbias(ed|es)?\b|fairness|hallucinat|societal|discriminat|\bharms?\b|accountab|transparen|human (oversight|review|in the loop)|over-?rel|blindly (accept|trust)|misinformation", 6),
        (r"limitations of (generative |large )?(ai|language)|validate (the |ai |generated )?output|verify (the |ai |generated )?(output|suggestion|code)|ethics|trustworth", 4),
        (r"\brisks?\b|\breview the\b", 2)],
    "Copilot in the IDE & CLI": [
        (r"\bvs ?code\b|visual studio|jetbrains|intellij|pycharm|neovim|\bvim\b|\bxcode\b|eclipse|azure data studio|command palette|status (bar|icon)|keyboard shortcut|\btab key\b|alt\+|ctrl\+|cmd\+|ghost text|copilot cli|gh copilot|\bcli\b|terminal|shell command|\bextension\b|marketplace|install(ing|ation)?\b|sign in", 6),
        (r"inline (suggestion|completion)|editor|ide\b|accept (a |the )?suggestion|cycle through|next suggestion", 4),
        (r"\bsuggestion", 2)],
    "Chat, agents & MCP": [
        (r"copilot chat|chat (window|panel|view|participant|interface)|slash command|/explain|/fix|/tests|/doc|/help|@workspace|@terminal|@vscode|agent mode|copilot edits|coding agent|sub-?agent|\bmcp\b|model context protocol|copilot spaces|copilot spark|copilot workspace|knowledge base|pull request summar|code review|instructions file|prompt file", 6),
        (r"\bchat\b|multi-?turn|conversation|follow-?up question|inline chat", 4),
        (r"\bagent\b|\bsummar", 2)],
    "Plans, policies & administration": [
        (r"copilot (free|pro\+?|individual|business|enterprise)|copilot for (business|individuals)|subscription|\bseats?\b|\blicens|\bbilling|\bpricing|per user per month|organization owner|enterprise account|policy setting|policy management|audit log|rest api|\bapi endpoint|assign(ing)? a licen|entitlement|\bsso\b|\bsaml\b|usage (metrics|report)|copilot metrics", 6),
        (r"organization (settings|policies|admin)|admin(istrator)?\b|\bplans?\b|\bupgrade\b|manage (access|users|members)", 4),
        (r"\bowner\b|\borganization\b|\benterprise\b", 2)],
    "Data handling & architecture": [
        (r"proxy (server|service|filter)|data (flow|retention|residency|handling|usage)|prompt building|context (assembly|gathering)|post-?processing|telemetry|code snippets? (are |is )?(collect|retain|store)|suggestion lifecycle|life ?cycle of|toxic(ity)? filter|\bllm\b|large language model|training data|model training|inference|neighboring tabs|transmitted|\bendpoint\b", 6),
        (r"how (does |the )?.*(work|process)|architecture|retained|stored|discarded|sent to", 4),
        (r"\bmodel\b|\bcontext\b|\bdata\b", 2)],
    "Prompt engineering & context": [
        (r"prompt (engineering|crafting|structure|design|process|flow)|zero-?shot|few-?shot|one-?shot|chain of thought|context window|chat history|effective prompts?|specific(ity)? (in |of )?(the )?prompt|iterate on|rephras|refine (the |your )?prompt|prompt best practice", 6),
        (r"\bprompts?\b|natural language (comment|description|instruction)|meaningful (variable |function )?names|provide (an )?examples?|break (it |the task )?down", 4),
        (r"\bcomments?\b|\bcontextual\b", 2)],
    "Developer productivity": [
        (r"refactor|legacy code|moderniz|translat(e|ing) (the )?code|convert (the )?code|sample data|\bboilerplate\b|documentation|docstring|\bcomments? for\b|explain (the |this |existing )?code|reduce context switching|onboard|learn(ing)? a new (language|framework)|code review feedback|commit message", 6),
        (r"productivity|generate (code|a function|documentation)|autocomplete|repetitive|developer experience|software development life ?cycle|\bsdlc\b", 4),
        (r"\bgenerate\b|\bwrite a\b", 2)],
    "Testing & code quality": [
        (r"unit test|integration test|\btest cases?\b|edge case|\bassertion|test coverage|\bmocking\b|test suite|\btdd\b|debug(ging)?\b|error handling|performance optimi|security (improvement|vulnerab|flaw|issue)|vulnerab|code smell|code qualit|quality of (the )?code", 6),
        (r"\btests?\b|\bbugs?\b|\bfix(ing)? (the |a )?(bug|error|issue)", 4),
        (r"\bvalidate\b", 2)],
    "Privacy & content exclusions": [
        (r"content exclusion|excluded? (file|path|repositor|content)|copilotignore|content_exclusion|matching public code|duplicat(e|ion) detection|public code (filter|suggestion)|blocking suggestions|\bgdpr\b|personal data|\bpii\b|intellectual property|indemnif|ownership of (the )?(output|suggestion|code)|privacy (setting|fundamental|statement)|opt.?out|secret|credential", 6),
        (r"\bprivacy\b|\bexclusions?\b|\bfilter(ing|s)?\b|sensitive", 4),
        (r"\bsettings\.json\b|\byaml\b", 2)],
}
TOPIC_FLOOR = 4


def auto_topic(q):
    qt = q["q"].lower()
    ct = " ".join(c["text"] for c in q["choices"]).lower()
    best, score = "General", 0
    for topic, pats in TOPIC_RULES.items():
        s = sum(w * 3 for p, w in pats if re.search(p, qt)) + \
            sum(w for p, w in pats if re.search(p, ct))
        if s > score:
            best, score = topic, s
    return best if score >= TOPIC_FLOOR else "General"


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower()).rstrip(".?:")


# ---------------------------------------------------------------- validate
def validate(qs):
    problems = []
    for i, q in enumerate(qs):
        where = f"[{i}] {str(q.get('q', ''))[:60]!r}"
        if not q.get("q", "").strip():
            problems.append(f"{where}: empty question text")
        ch = q.get("choices") or []
        if len(ch) < 2:
            problems.append(f"{where}: needs at least 2 choices")
        labels = [c.get("label") for c in ch]
        if len(set(labels)) != len(labels):
            problems.append(f"{where}: duplicate choice labels {labels}")
        if any(not str(c.get("text", "")).strip() for c in ch):
            problems.append(f"{where}: a choice has empty text")
        correct = q.get("correct") or []
        if not correct:
            problems.append(f"{where}: no correct answer")
        for l in correct:
            if l not in labels:
                problems.append(f"{where}: correct answer {l!r} is not one of {labels}")
        if len(set(correct)) != len(correct):
            problems.append(f"{where}: correct answer repeated")
        if len(ch) > 10:
            problems.append(f"{where}: more than 10 choices (the app labels A-J)")
        for field in ("explanation", "review", "corrected"):
            val = q.get(field)
            if val is None:
                continue
            if not isinstance(val, str):
                problems.append(f"{where}: {field} must be a string")
            elif not val.strip():
                problems.append(f"{where}: {field} is empty (omit the field instead)")
    return problems


# ---------------------------------------------------------------- duplicates
# dedupe() only catches questions whose normalized text matches exactly. This
# audit is the wider net: it scores every pair on five signals and prints the
# candidates for a human to judge. It never deletes anything.
#
# It is lexical, and that is its ceiling. Two questions testing the same fact in
# different words — "What are the two main reasons to fork a repository?" against
# "How do forks facilitate collaboration?" — score near zero on every signal, and
# no threshold reaches them without returning hundreds of false positives. Those
# have to be found by reading the bank. Treat a clean run as "no lexical twins",
# not "no duplicates".
STOP = set("""a an the of to in for on with and or is are was were be been do does did
what which how many can you your as at by from that this these those it its not
following best describes used use using each answer presents complete solution
choose two three all apply select correct purpose""".split())


def _words(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    return {w for w in s.split() if w not in STOP and len(w) > 2}


def _jaccard(a, b):
    return len(a & b) / len(a | b) if (a or b) else 0.0


# "(Each answer presents a complete solution. Choose three.)" and friends appear
# on most multi-answer stems. Left in, that boilerplate makes every pair of them
# look similar, so it comes off before anything is compared.
BOILER = re.compile(r"\((?:[^)]*?(?:complete solution|choose \w+|select \w+)[^)]*)\)|"
                    r"\bselect (?:two|three|four|all that apply)\b", re.I)


def _stem(q):
    return norm(BOILER.sub("", q))


def find_duplicates(qs):
    """Score every pair; return candidates worth a human look, strongest first."""
    out = []
    prepped = []
    for q in qs:
        ans = " ".join(c["text"] for c in q["choices"] if c["label"] in q["correct"])
        prepped.append((_stem(q["q"]), _words(BOILER.sub("", q["q"])), ans, _words(ans),
                        {norm(c["text"]) for c in q["choices"]}))
    for i in range(len(qs)):
        for j in range(i + 1, len(qs)):
            (sA, wA, aA, awA, cA), (sB, wB, aB, awB, cB) = prepped[i], prepped[j]
            sig = {
                # near-identical wording, boilerplate removed
                "text": difflib.SequenceMatcher(None, sA, sB).ratio(),
                # shared vocabulary in the stem, order-independent
                "stem": _jaccard(wA, wB),
                # same option pool, reordered or lightly reworded
                "choices": _jaccard(cA, cB),
                # same fact asserted, however the stem is phrased. Token-based:
                # a raw ratio scores short answers like "Git repository" and
                # "repository" far too high.
                "answer": _jaccard(awA, awB),
                # the inverted pair — one question's answer restates the other's stem
                "inverted": max(_jaccard(wA, awB), _jaccard(wB, awA)),
            }
            strong = (sig["answer"] >= .55 or sig["inverted"] >= .50
                      or sig["choices"] >= .55 or sig["text"] >= .78)
            supported = sig["stem"] >= .40 and max(sig["answer"], sig["inverted"],
                                                   sig["choices"], sig["text"]) >= .35
            if strong or supported:
                out.append((max(sig.values()), i, j, sig))
    out.sort(reverse=True)
    return out


def report_duplicates(qs):
    cands = find_duplicates(qs)
    print(f"\n{len(cands)} duplicate candidate(s) among {len(qs)} questions "
          f"— judge these by hand, nothing was changed\n")
    for score, i, j, sig in cands:
        bits = " · ".join(f"{k} {v:.2f}" for k, v in sig.items())
        print(f"  [{i}] + [{j}]   {bits}")
        for k in (i, j):
            print(f"      {qs[k]['q'][:88]}")
        print()
    return cands


def dedupe(qs):
    seen, out, dropped = {}, [], []
    for q in qs:
        k = norm(q["q"])
        if k in seen:
            dropped.append(q["q"][:70])
            continue
        seen[k] = True
        out.append(q)
    return out, dropped


def normalize(qs):
    """Fill in derived fields. multi and topic are always recomputed unless topic is pinned."""
    for q in qs:
        q["correct"] = [str(c).strip() for c in q["correct"]]
        q["multi"] = len(q["correct"]) > 1
        if not q.get("topic"):
            q["topic"] = auto_topic(q)
        for field in ("explanation", "review", "corrected"):
            if isinstance(q.get(field), str):
                q[field] = q[field].strip()
    return qs


# ---------------------------------------------------------------- import
def convert_raw(raw):
    """Convert the original screenshot-extraction shape into the app shape.

    Raw entries look like:
      {"question": "...", "answer_choices": {"A": "...", "B": "..."},
       "correct_answer_letter": "A, C", "correct_answer_text": "...", "filename": "..."}
    Entries with a null/blank answer are skipped and reported.
    """
    out, skipped = [], []
    for r in raw:
        letters = r.get("correct_answer_letter")
        if not letters:
            skipped.append(r.get("question", "")[:70])
            continue
        ch = r.get("answer_choices") or {}
        correct = [x.strip() for x in str(letters).split(",") if x.strip()]
        if any(c not in ch for c in correct):
            skipped.append(r.get("question", "")[:70] + "  (answer letter not in choices)")
            continue
        entry = {
            "q": r["question"].strip(),
            "choices": [{"label": k, "text": v} for k, v in ch.items()],
            "correct": correct,
        }
        exp = (r.get("explanation") or "").strip()
        if exp:
            entry["explanation"] = exp
        out.append(entry)
    return out, skipped


def backfill_notes(qs, raw):
    """Attach explanations and review flags from a raw batch onto the bank.

    Matches on normalized question text. A raw entry marked needs_review becomes
    a `review` field holding the note, which the app surfaces as a warning.
    Existing values are left alone, so this is safe to re-run.
    """
    src = {}
    for r in raw:
        key = norm(r.get("question", ""))
        if key in src:
            continue
        flagged = r.get("verification_status") == "needs_review"
        src[key] = {
            "explanation": (r.get("explanation") or "").strip(),
            "review": (r.get("verification_note") or "").strip() if flagged else "",
        }
    filled = collections.Counter()
    missing = 0
    for q in qs:
        hit = src.get(norm(q["q"]))
        if not hit:
            missing += 1
            continue
        for field in ("explanation", "review"):
            if hit[field] and not q.get(field):
                q[field] = hit[field]
                filled[field] += 1
    return filled, missing


# ---------------------------------------------------------------- main
def select_banks(args, default_one=None):
    """Resolve --bank NAME. Without it: every bank, or the named default."""
    if "--bank" in args:
        want = args[args.index("--bank") + 1]
        hit = [b for b in BANKS if b.name == want]
        if not hit:
            print(f"unknown bank {want!r} — expected one of "
                  f"{', '.join(b.name for b in BANKS)}")
            sys.exit(1)
        return hit
    if default_one:
        return [b for b in BANKS if b.name == default_one]
    return list(BANKS)


def main():
    args = sys.argv[1:]
    check_only = "--check" in args
    dupes_only = "--dupes" in args

    if dupes_only:
        for bank in select_banks(args):
            print(f"\n=== {bank.name} ({bank.path.name}) ===")
            report_duplicates(bank.read())
        return

    # --import and --explanations act on one bank; they default to the legacy one.
    edited = select_banks(args, default_one="legacy")[0] if (
        "--import" in args or "--explanations" in args) else None

    # Process every bank in full before writing anything, so a problem in one
    # bank leaves both files untouched.
    staged, problems = [], []
    for bank in select_banks(args):
        qs = bank.read()
        before = len(qs)

        if edited is bank and "--import" in args:
            path = pathlib.Path(args[args.index("--import") + 1])
            raw = json.loads(path.read_text(encoding="utf-8"))
            added, skipped = convert_raw(raw)
            print(f"import: {len(added)} usable, {len(skipped)} skipped from {path.name}")
            for s in skipped:
                print("   skipped:", s)
            qs += added

        if edited is bank and "--explanations" in args:
            path = pathlib.Path(args[args.index("--explanations") + 1])
            raw = json.loads(path.read_text(encoding="utf-8"))
            filled, missing = backfill_notes(qs, raw)
            print(f"from {path.name}: {filled['explanation']} explanations, "
                  f"{filled['review']} review flags · {missing} bank questions had no match")

        qs = normalize(qs)
        problems += [f"{bank.name}: {p}" for p in validate(qs)]
        staged.append((bank, qs, before))

    if problems:
        print(f"\n{len(problems)} problem(s) — nothing was written:\n")
        for p in problems:
            print("  ", p)
        sys.exit(1)

    deduped = []
    for bank, qs, before in staged:
        # Deduping is per bank on purpose: the two banks are kept separate, and a
        # supplemental question restating a legacy one is not a duplicate here.
        qs, dropped = dedupe(qs)
        deduped.append((bank, qs, before))
        for d in dropped:
            print("   duplicate dropped:", d)

        explained = sum(1 for q in qs if q.get("explanation"))
        flagged = sum(1 for q in qs if q.get("review"))
        corrected = sum(1 for q in qs if q.get("corrected"))
        print(f"\n{bank.name}: {len(qs)} questions ({before} before) · "
              f"{sum(q['multi'] for q in qs)} multi-answer"
              f" · {explained} with explanations · {flagged} flagged for review"
              f" · {corrected} with corrected answers")
        for t, n in collections.Counter(q["topic"] for q in qs).most_common():
            print(f"   {n:4}  {t}")

    staged = deduped
    if check_only:
        print("\n--check: valid, nothing written")
        return

    page = PAGE.read_text(encoding="utf-8")
    for bank, qs, _ in staged:
        bank.write(qs)
        page = bank.inject(page, qs)
    PAGE.write_text(page, encoding="utf-8")
    print(f"\nwrote {', '.join(b.path.name for b, _, _ in staged)} and injected into "
          f"index.html ({PAGE.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
