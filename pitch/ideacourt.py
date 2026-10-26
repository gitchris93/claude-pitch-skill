#!/usr/bin/env python3
"""Bookkeeping for the pitch skill: twelve jurors invent business ideas, debate them,
independent assessors score a shortlist, a judge picks the winner and a product architect turns it
into a plan.

The skill's orchestrator (Claude) drives the run with these commands. Every sub-agent reads a brief
this script writes and writes one output file; this script checks the files, computes the weighted
scores and renders the final report. All state lives in .ideacourt/<run>/ in the current directory.

    ideacourt.py plan [--quick]
    ideacourt.py init --request-file PATH [--research-file PATH] [--lang de|en] [--quick]
                      [--weights market=20,revenue=20,...]
    ideacourt.py next
    ideacourt.py prompts <phase>
    ideacourt.py check <phase>
    ideacourt.py score
    ideacourt.py render

Phases, in order: ideas, debate, shortlist, scoring, verdict, plan (--quick skips debate).
"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = ".ideacourt"
LATEST = os.path.join(ROOT, "LATEST")
PHASES = ["ideas", "debate", "shortlist", "scoring", "verdict", "plan"]
SCORERS = 3
QUICK_SCORERS = 1
WAVE = 12  # all jurors at once: they never see each other, so waves only cost time
TIE_MARGIN = 3.0
SKIPPED = "SKIPPED"
CRITERIA = [("market", 20), ("revenue", 20), ("reach", 15), ("feasibility", 15),
            ("edge", 10), ("cost", 10), ("risk", 10)]
CREDIT = ("_Built on the /court skill by Alex Chen (https://github.com/alexyc9381/court-skill, MIT). "
          "The jurors, assessors and judge are roles simulated by one AI model, not independent experts._")

LABELS = {
    "en": {
        "language": "English",
        "idea": "IDEA",
        "fields": [("summary", "Summary"), ("problem", "Problem"), ("customer", "Target customer"),
                   ("solution", "Solution"), ("model", "Business model"), ("pricing", "Pricing"),
                   ("edge", "Competitive edge"), ("effort", "Build effort"), ("cost", "Startup cost"),
                   ("risks", "Key risks"), ("test", "Demand test"), ("assumptions", "Assumptions")],
        "criteria": {"market": "Market need", "revenue": "Revenue potential", "reach": "Reachability",
                     "feasibility": "Feasibility", "edge": "Differentiation", "cost": "Startup cost",
                     "risk": "Risk"},
        "discussion": "Discussion",
        "winner": "Winner",
        "plan": [("product", "Product concept"), ("business", "Business model"),
                 ("tech", "Technical plan"), ("validation", "Validation strategy"),
                 ("roadmap", "Step-by-step roadmap"), ("risks", "Risks and open questions"),
                 ("next", "Next actions")],
        "report": {
            "title": "Idea Court",
            "request": "The request",
            "s1": "Executive summary", "s2": "What you actually want", "s3": "The twelve ideas",
            "s4": "What the jury debate decided", "s5": "Scoring", "s6": "Winner",
            "juror": "Juror", "idea_col": "Idea", "summary_col": "In short", "points": "Jury points",
            "rank": "Rank", "candidate": "Candidate", "score": "Score", "ko": "KO",
            "no_idea": "_no idea submitted_",
            "shortlist": "Shortlist",
            "weights": "Weights",
            "formula": "Score = sum of (mean rating / 10 x weight). 'Startup cost' and 'Risk': higher = cheaper / safer.",
            "assessors": "assessor(s), ratings averaged",
            "reasons": "Assessors' reasons",
            "vote_note": "Jury points: TOP-3 votes from the debate (3/2/1), counted for the source ideas. They are shown for transparency; the decision follows the weighted score.",
            "knocked": "knocked out by a majority of assessors",
            "disclaimer": "A high score is a structured decision aid, not a guarantee of commercial success. Numbers marked as estimates or hypotheses are not researched facts.",
            "override": "The judge chose %s over the top score %s because they are within %.0f points.",
            "full": "The full run is in %s: every idea, debate statement, score sheet and brief.",
        },
    },
    "de": {
        "language": "German",
        "idea": "IDEE",
        "fields": [("summary", "Kurzbeschreibung"), ("problem", "Problem"), ("customer", "Zielgruppe"),
                   ("solution", "Lösung"), ("model", "Geschäftsmodell"), ("pricing", "Preisgestaltung"),
                   ("edge", "Wettbewerbsvorteil"), ("effort", "Entwicklungsaufwand"),
                   ("cost", "Startkosten"), ("risks", "Risiken"), ("test", "Nachfragetest"),
                   ("assumptions", "Annahmen")],
        "criteria": {"market": "Marktbedarf", "revenue": "Umsatzpotenzial", "reach": "Erreichbarkeit",
                     "feasibility": "Umsetzbarkeit", "edge": "Differenzierung", "cost": "Startkosten",
                     "risk": "Risiko"},
        "discussion": "Diskussion",
        "winner": "Gewinner",
        "plan": [("product", "Produktkonzept"), ("business", "Geschäftsmodell"),
                 ("tech", "Technischer Umsetzungsplan"), ("validation", "Validierungsstrategie"),
                 ("roadmap", "Schritt-für-Schritt-Roadmap"), ("risks", "Risiken und offene Fragen"),
                 ("next", "Sofortmaßnahmen")],
        "report": {
            "title": "Idea Court",
            "request": "Die Anfrage",
            "s1": "Executive Summary", "s2": "Interpretation des Nutzerwunsches", "s3": "Die zwölf Ideen",
            "s4": "Ergebnis der Jury-Diskussion", "s5": "Bewertungstabelle", "s6": "Gewinner",
            "juror": "Juror", "idea_col": "Idee", "summary_col": "Kurz", "points": "Jury-Punkte",
            "rank": "Rang", "candidate": "Kandidat", "score": "Score", "ko": "KO",
            "no_idea": "_keine Idee abgegeben_",
            "shortlist": "Shortlist",
            "weights": "Gewichtung",
            "formula": "Score = Summe aus (Durchschnittsbewertung / 10 x Gewicht). 'Startkosten' und 'Risiko': höher = günstiger / sicherer.",
            "assessors": "Gutachter, Bewertungen gemittelt",
            "reasons": "Begründungen der Gutachter",
            "vote_note": "Jury-Punkte: TOP-3-Stimmen aus der Debatte (3/2/1), den Ursprungsideen zugerechnet. Sie dienen der Transparenz; entschieden wird nach dem gewichteten Score.",
            "knocked": "von der Mehrheit der Gutachter ausgeschlossen (KO)",
            "disclaimer": "Ein hoher Score ist eine strukturierte Entscheidungshilfe, keine Garantie für wirtschaftlichen Erfolg. Als Schätzung oder Hypothese markierte Zahlen sind keine recherchierten Fakten.",
            "override": "Der Richter hat %s statt des Score-Ersten %s gewählt, weil beide innerhalb von %.0f Punkten liegen.",
            "full": "Der vollständige Lauf liegt in %s: jede Idee, jede Debattenaussage, jede Bewertung und jedes Briefing.",
        },
    },
}


def labels(state):
    return LABELS.get(state.get("lang"), LABELS["en"])


def language_name(state):
    lang = state.get("lang", "en")
    return LABELS[lang]["language"] if lang in LABELS else "the language with ISO code %r" % lang


# ---------- io ----------

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ---------- state ----------

def load_jurors():
    return json.loads(read(os.path.join(HERE, "jurors.json")))


def run_dir():
    if not os.path.exists(LATEST):
        sys.exit("ideacourt: no run yet. Run: ideacourt.py init --request-file .ideacourt/request.md")
    return read(LATEST).strip()


def load_state(rd=None):
    return json.loads(read(os.path.join(rd or run_dir(), "state.json")))


def save_state(state):
    write(os.path.join(state["dir"], "state.json"), json.dumps(state, indent=2, ensure_ascii=False))


def parse_weights(text):
    if not text:
        return dict(CRITERIA)
    weights = {}
    for part in text.split(","):
        key, _, val = part.partition("=")
        key = key.strip()
        if key not in dict(CRITERIA):
            sys.exit("ideacourt: unknown criterion %r (criteria: %s)" % (key, ", ".join(k for k, _ in CRITERIA)))
        try:
            weights[key] = float(val)
        except ValueError:
            sys.exit("ideacourt: weight for %s is not a number: %r" % (key, val))
    if set(weights) != set(dict(CRITERIA)):
        sys.exit("ideacourt: --weights must name all seven criteria")
    if abs(sum(weights.values()) - 100) > 0.01:
        sys.exit("ideacourt: weights must add up to 100 (they add up to %g)" % sum(weights.values()))
    return weights


def phases(state):
    return [p for p in PHASES if not (p == "debate" and state.get("quick"))]


def _abs(state, *parts):
    return os.path.abspath(os.path.join(state["dir"], *parts))


def jid(i):
    return "J%02d" % (i + 1)


# ---------- jobs ----------

def jobs(state, phase):
    """Each job: id, brief path, output path."""
    if phase in ("ideas", "debate"):
        ids = ["juror-%02d" % (i + 1) for i in range(len(state["jury"]))]
    elif phase == "scoring":
        ids = ["assessor-%d" % (i + 1) for i in range(state["scorers"])]
    elif phase in ("shortlist", "verdict", "plan"):
        ids = [{"shortlist": "foreperson", "verdict": "judge", "plan": "architect"}[phase]]
    else:
        sys.exit("ideacourt: unknown phase %r (phases: %s)" % (phase, ", ".join(PHASES)))
    return [{"id": j,
             "brief": _abs(state, "briefs", "%s-%s.md" % (phase, j)),
             "output": _abs(state, phase, "%s.md" % j)} for j in ids]


def output_text(job):
    p = job["output"]
    return read(p) if os.path.exists(p) else ""


def problems(state, phase, job):
    """Why an output is not acceptable yet; an empty list means it is done."""
    text = output_text(job).strip()
    if not text:
        return ["missing"]
    if text == SKIPPED and phase in ("ideas", "debate", "scoring"):
        return []
    if phase == "ideas":
        return validate_idea(state, text)
    if phase == "debate":
        return [] if parse_debate(text)["top"] else ["no 'TOP 3:' line with juror ids like J04"]
    if phase == "shortlist":
        return validate_shortlist(state, text)
    if phase == "scoring":
        return validate_scores(state, text)
    if phase == "verdict":
        return validate_verdict(state, text)
    if phase == "plan":
        return validate_plan(state, text)
    return []


def missing(state, phase):
    return [j for j in jobs(state, phase) if problems(state, phase, j)]


# ---------- parsing ----------

def field_re(label):
    return re.compile(r"^\s*[-*]?\s*(?:\*\*)?\s*%s\s*(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.*)$" % re.escape(label),
                      re.I | re.M)


IDEA_HEAD_RE = re.compile(r"^#{1,3}\s*(?:IDEA|IDEE)\s*:\s*(.+)$", re.I | re.M)
SECTION_RE = re.compile(r"^##(?!#)\s*(.+)$", re.M)
SL_HEAD_RE = re.compile(r"^S(\d+)\s*[:.\-]\s*(.+)$", re.I)
JREF_RE = re.compile(r"\bJ(\d{1,2})\b", re.I)


def sections(text):
    """Split markdown on level-2 headings: [(heading, body)], body without the heading line."""
    out = []
    marks = list(SECTION_RE.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1).strip().strip("*").strip(), text[m.end():end].strip()))
    return out


def norm(heading):
    return re.sub(r"^[\s\d.:)\-]+", "", heading).strip().strip("*").casefold()


def find_section(secs, title):
    want = title.casefold()
    for head, body in secs:
        if norm(head).startswith(want) or want in norm(head):
            return body
    return None


def parse_idea(state, text):
    m = IDEA_HEAD_RE.search(text)
    out = {"name": m.group(1).strip().strip("*").strip() if m else ""}
    for key, label in labels(state)["fields"]:
        f = field_re(label).search(text)
        out[key] = f.group(1).strip() if f else ""
    return out


def validate_idea(state, text):
    idea = parse_idea(state, text)
    errs = [] if idea["name"] else ["no '## %s: <name>' heading" % labels(state)["idea"]]
    errs += ["no '**%s:**' line" % label for key, label in labels(state)["fields"] if not idea[key]]
    return errs


def parse_debate(text):
    def line(name):
        m = re.search(r"^\s*\**%s\**\s*:\s*(.*)$" % name, text, re.I | re.M)
        return m.group(1).strip() if m else ""
    top = ["J%02d" % int(n) for n in JREF_RE.findall(line(r"TOP\s*3"))][:3]
    return {"top": top, "why": line("WHY"), "objection": line("OBJECTION"), "improve": line("IMPROVE"),
            "combine": line("COMBINE"), "drop": line("DROP")}


def parse_shortlist(state, text):
    cands = []
    for head, body in sections(text):
        m = SL_HEAD_RE.match(head)
        if not m:
            continue
        src = re.search(r"^\s*\**SOURCE\**\s*:\s*(.*)$", body, re.I | re.M)
        refs = ["J%02d" % int(n) for n in JREF_RE.findall(src.group(1))] if src else []
        summary = field_re(dict(labels(state)["fields"])["summary"]).search(body)
        cands.append({"id": "S%d" % int(m.group(1)), "name": m.group(2).strip().strip("*").strip(),
                      "sources": refs, "summary": summary.group(1).strip() if summary else "",
                      "body": body})
    return cands


def validate_shortlist(state, text):
    errs = []
    if find_section(sections(text), labels(state)["discussion"]) is None:
        errs.append("no '## %s' section" % labels(state)["discussion"])
    cands = parse_shortlist(state, text)
    if not 2 <= len(cands) <= 5:
        errs.append("needs 2 to 5 candidates headed '## S1: <name>', found %d" % len(cands))
    ids = [c["id"] for c in cands]
    if len(set(ids)) != len(ids):
        errs.append("candidate ids repeat: %s" % ", ".join(ids))
    for c in cands:
        if not c["sources"]:
            errs.append("%s has no 'SOURCE: Jxx' line" % c["id"])
        if not c["summary"]:
            errs.append("%s has no '**%s:**' line" % (c["id"], dict(labels(state)["fields"])["summary"]))
    return errs


SCORE_RE = re.compile(r"^\s*\**SCORE\s+(S\d+)\**\s*:\s*(.+)$", re.I | re.M)
PAIR_RE = re.compile(r"([a-z]+)\s*=\s*(\d+(?:[.,]\d+)?)", re.I)


def parse_scores(text):
    """-> {S1: {"scores": {criterion: float}, "why": str, "ko": str}}"""
    out = {}
    for m in SCORE_RE.finditer(text):
        sid = m.group(1).upper()
        pairs = {k.lower(): float(v.replace(",", ".")) for k, v in PAIR_RE.findall(m.group(2))}
        out[sid] = {"scores": pairs, "why": "", "ko": ""}
    for key in ("why", "ko"):
        for m in re.finditer(r"^\s*\**%s\s+(S\d+)\**\s*:\s*(.+)$" % key, text, re.I | re.M):
            sid = m.group(1).upper()
            if sid in out:
                out[sid][key] = m.group(2).strip()
    return out


def validate_scores(state, text):
    errs = []
    sheet = parse_scores(text)
    for c in shortlist(state):
        row = sheet.get(c["id"])
        if not row:
            errs.append("no 'SCORE %s:' line" % c["id"])
            continue
        for key, _ in CRITERIA:
            v = row["scores"].get(key)
            if v is None:
                errs.append("%s: no %s=N" % (c["id"], key))
            elif not 0 <= v <= 10:
                errs.append("%s: %s=%g is outside 0..10" % (c["id"], key, v))
    return errs


def parse_winner(text):
    m = re.search(r"^\s*\**WINNER\**\s*:\s*\**\s*(S\d+)", text, re.I | re.M)
    return m.group(1).upper() if m else None


def validate_verdict(state, text):
    errs = []
    win = parse_winner(text)
    if not win:
        errs.append("no 'WINNER: Sx' line")
    elif win not in allowed_winners(state):
        errs.append("WINNER %s is not allowed; choose one of %s" % (win, ", ".join(allowed_winners(state))))
    secs = sections(text)
    for title in ("Executive Summary", labels(state)["winner"]):
        if find_section(secs, title) is None:
            errs.append("no '## %s' section" % title)
    return errs


def validate_plan(state, text):
    secs = sections(text)
    return ["no '## %s' section" % title for _, title in labels(state)["plan"] if find_section(secs, title) is None]


# ---------- shortlist, votes and scores ----------

def shortlist(state):
    job = jobs(state, "shortlist")[0]
    return parse_shortlist(state, output_text(job))


def ideas(state):
    rows = []
    for i, (job, juror) in enumerate(zip(jobs(state, "ideas"), state["jury"])):
        text = output_text(job).strip()
        idea = parse_idea(state, text) if text and text != SKIPPED else None
        rows.append({"id": jid(i), "juror": juror, "idea": idea})
    return rows


def votes(state):
    """Borda points from the debate's TOP 3 lines: 3, 2, 1 per juror."""
    points = {jid(i): 0 for i in range(len(state["jury"]))}
    if state.get("quick"):
        return points
    for job in jobs(state, "debate"):
        text = output_text(job).strip()
        if not text or text == SKIPPED:
            continue
        for rank, ref in enumerate(parse_debate(text)["top"]):
            if ref in points:
                points[ref] += 3 - rank
    return points


def weighted(means, weights):
    return round(sum(means[k] / 10.0 * weights[k] for k in weights), 1)


def compute(state):
    weights = state["weights"]
    sheets = []
    for job in jobs(state, "scoring"):
        text = output_text(job).strip()
        if text and text != SKIPPED and not validate_scores(state, text):
            sheets.append((job["id"], parse_scores(text)))
    pts = votes(state)
    rows = []
    for c in shortlist(state):
        means = {}
        for key, _ in CRITERIA:
            vals = [s[c["id"]]["scores"][key] for _, s in sheets if c["id"] in s]
            means[key] = round(sum(vals) / len(vals), 2) if vals else 0.0
        kos = [s[c["id"]]["ko"] for _, s in sheets if c["id"] in s and s[c["id"]]["ko"]]
        rows.append({"id": c["id"], "name": c["name"], "sources": c["sources"], "means": means,
                     "score": weighted(means, weights) if sheets else 0.0,
                     "why": [(a, s[c["id"]]["why"]) for a, s in sheets if c["id"] in s and s[c["id"]]["why"]],
                     "ko": kos, "knocked_out": bool(sheets) and len(kos) * 2 > len(sheets),
                     "jury_points": sum(pts.get(r, 0) for r in set(c["sources"]))})
    # knocked-out candidates sink to the bottom; ties break on jury points, then shortlist order
    order = sorted(rows, key=lambda r: (r["knocked_out"], -r["score"], -r["jury_points"]))
    for rank, r in enumerate(order):
        r["rank"] = rank + 1
    result = {"weights": weights, "assessors": [a for a, _ in sheets], "ranking": order}
    write(os.path.join(state["dir"], "scores.json"), json.dumps(result, indent=2, ensure_ascii=False))
    return result


def allowed_winners(state):
    ranking = [r for r in compute(state)["ranking"] if not r["knocked_out"]]
    if not ranking:  # every candidate knocked out: the judge still has to name the least bad one
        ranking = compute(state)["ranking"]
    top = ranking[0]["score"] if ranking else 0
    return [r["id"] for r in ranking if top - r["score"] <= TIE_MARGIN]


def winner(state):
    allowed = allowed_winners(state)
    chosen = parse_winner(output_text(jobs(state, "verdict")[0]))
    return chosen if chosen in allowed else (allowed[0] if allowed else None)


def ranking_text(state):
    lines = []
    for r in compute(state)["ranking"]:
        lines.append("%d. %s %s: %.1f / 100%s" % (r["rank"], r["id"], r["name"], r["score"],
                                                  " (KNOCKED OUT: %s)" % "; ".join(r["ko"]) if r["knocked_out"] else ""))
    return "\n".join("    " + line for line in lines)


# ---------- briefs ----------

def head(state, job):
    research = _abs(state, "research.md")
    if os.path.exists(research):
        src = ("Research notes with sourced facts: %s\nWhen you use one of these facts, keep its source URL "
               "next to it." % research)
    else:
        src = ("There is no research file: no market facts were researched for this run, so every market "
               "size, price or competitor detail you give is an estimate unless you look it up and cite it.")
    return ("You are one part of an idea court run by the pitch skill. You cannot see the user's "
            "conversation: everything you know is in the files named below. The court is a structured "
            "simulation of perspectives by one AI model, not a panel of independent experts; never claim "
            "otherwise.\n\n"
            "Write in %s, the language of the user's request. Never invent facts, statistics, market sizes, "
            "prices of real products, quotes or sources. Mark every number you did not take from a source as "
            "an estimate or as a hypothesis to test. Never promise or imply guaranteed income or success.\n\n"
            "Write your answer to exactly this file and nothing else:\n\n    %s\n\n"
            "The user's request and the court's interpretation of it (goal, constraints, assumptions): %s\n\n"
            "%s\n\n" % (language_name(state), job["output"], _abs(state, "request.md"), src))


def field_lines(state):
    hints = {
        "summary": "one or two sentences: what it is",
        "problem": "the specific, painful problem it solves",
        "customer": "who exactly pays; the ideal first customer",
        "solution": "how it works, concretely",
        "model": "how money comes in",
        "pricing": "a price point or range, marked as an estimate or hypothesis",
        "edge": "why someone would choose this over existing alternatives",
        "effort": "estimated build effort for this user (weeks, skills needed)",
        "cost": "estimated cash needed to reach a first test, and to launch",
        "risks": "the 2 or 3 most important technical, legal, economic or operational risks",
        "test": "the fastest cheap way to check that people will pay",
        "assumptions": "the 1 to 3 assumptions that must hold, and how uncertain each one is",
    }
    return "\n".join("**%s:** %s" % (label, hints[key]) for key, label in labels(state)["fields"])


def idea_template(state, words):
    return ("## %s: <short name>\n%s\n\n%d words at most. Use the labels exactly as written, in this order.\n"
            % (labels(state)["idea"], field_lines(state), words))


def idea_paths(state):
    return "\n".join("    %s (%s, %s)" % (j["output"], jid(i), state["jury"][i]["name"])
                     for i, j in enumerate(jobs(state, "ideas")))


def search_rule(juror):
    # Searches are the slowest part of the idea round, so only the jurors whose lens depends on
    # live market facts get one; everyone else works from the research file.
    if juror.get("searches"):
        return ("You may run at most %d web search, and only if one fact would change your idea (for example "
                "whether a direct competitor exists and what it charges). Cite the URL next to the fact."
                % juror["searches"])
    return ("Do not run web searches. Use the research file for market facts; anything else about "
            "competitors or prices is an estimate, so say so.")


def brief_text(state, phase, job):
    h = head(state, job)
    if phase == "ideas":
        idx = int(job["id"].split("-")[1]) - 1
        juror = state["jury"][idx]
        return h + (
            "You are JUROR %d of %d: %s. %s\n\n"
            "Develop ONE concrete business idea that serves the user's actual goal, which may differ from the "
            "solution the user named. You will never see the other jurors' ideas, so do not play it safe or "
            "generic: argue from your own perspective. 'Build an AI app' is not an idea; name the specific "
            "customer, the specific problem, and why they would pay.\n\n"
            "Respect the constraints in the request file (budget, time, skills, team size). If the request "
            "expects something unrealistic, such as guaranteed income or a fixed profit within a short time, "
            "do not play along: design an idea whose core hypothesis can be tested cheaply, and say so under "
            "the assumptions.\n\n"
            "%s\n\n"
            "Write exactly this structure:\n\n%s"
            % (idx + 1, len(state["jury"]), juror["name"], juror["lens"], search_rule(juror),
               idea_template(state, 320)))
    if phase == "debate":
        idx = int(job["id"].split("-")[1]) - 1
        juror = state["jury"][idx]
        return h + (
            "You are JUROR %d of %d: %s. %s\n\n"
            "Each of the %d jurors has proposed one idea independently. Read all of them:\n\n%s\n\n"
            "Your own idea is %s. Now debate them from your perspective. Be critical: no politeness, no "
            "automatic agreement. Do not favour an idea because it is clever or technically exciting; weigh "
            "the upside against effort, risk and the realistic chance it works for THIS user. Rank your own "
            "idea only if you would honestly bet on it over the others.\n\n"
            "Write exactly these lines and nothing else. Refer to ideas by juror id, like J04.\n\n"
            "TOP 3: Jxx, Jxx, Jxx (best first)\n"
            "WHY: one or two sentences on why your first choice beats your second\n"
            "OBJECTION: Jxx: the strongest objection against your first choice or against the idea you "
            "expect the others to love\n"
            "IMPROVE: Jxx: one concrete change that would make it clearly stronger\n"
            "COMBINE: Jxx + Jxx: what the combination would be and why it beats either alone, or 'none'\n"
            "DROP: Jxx: an idea that looks attractive but should be discarded, and why\n\n"
            "160 words at most.\n"
            % (idx + 1, len(state["jury"]), juror["name"], juror["lens"], len(state["jury"]),
               idea_paths(state), jid(idx)))
    if phase == "shortlist":
        if state.get("quick"):
            debate = ("There was no separate debate round (quick mode), so you run it yourself: for each idea, "
                      "think through how these perspectives would attack and improve it:\n\n%s\n\n"
                      % "\n".join("    %s: %s" % (j["name"], j["lens"]) for j in state["jury"]))
        else:
            debate = ("Read every juror's debate statement (TOP 3, WHY, OBJECTION, IMPROVE, COMBINE, DROP):\n\n%s\n\n"
                      % "\n".join("    " + j["output"] for j in jobs(state, "debate")))
        summary_label = dict(labels(state)["fields"])["summary"]
        return h + (
            "You are the FOREPERSON of the jury. You have no idea of your own. Read the request and every "
            "idea:\n\n%s\n\n%s"
            "Turn the debate into a shortlist of 3 to 5 candidates (2 only if fewer are viable):\n\n"
            "- Compare the ideas, expose weak or unrealistic assumptions, and discard ideas whose risk or poor "
            "odds outweigh their appeal, however exciting they sound.\n"
            "- Improve the strongest candidates with the jurors' improvements. A candidate may combine ideas "
            "when that makes a better product.\n"
            "- The TOP 3 votes are one input, not the decision. Do not score the candidates: independent "
            "assessors score them after you.\n"
            "- Ideas marked SKIPPED or missing do not exist.\n\n"
            "Write exactly this structure, 900 words at most. Keep every label of every candidate, but "
            "write one tight line per label: the assessors score from these lines, so cut decoration, not "
            "facts, numbers or assumptions.\n\n"
            "## %s\n"
            "5 to 8 bullets: the key arguments, objections and improvements, naming the jurors who raised "
            "them. Then one line per discarded idea: Jxx: why it was dropped.\n\n"
            "## S1: <name>\n"
            "SOURCE: Jxx (+ Jxx when combined)\n"
            "then the refined idea, with every label of the idea format:\n\n%s\n\n"
            "## S2: <name>\n...and so on. The candidate heading must start with S and its number; each "
            "candidate needs its SOURCE line and a **%s:** line.\n"
            % (idea_paths(state), debate, labels(state)["discussion"],
               field_lines(state), summary_label))
    if phase == "scoring":
        idx = int(job["id"].split("-")[1])
        return h + (
            "You are ASSESSOR %d of %d. You are independent: you never see the other assessors. Score every "
            "candidate in the shortlist against the user's situation in the request file:\n\n    %s\n\n"
            "Rubric, 0 to 10 per criterion, whole numbers:\n\n"
            "- market (market need, customer problem): 0 = nobody has this problem; 5 = real but nice-to-have "
            "or unproven; 10 = urgent, frequent problem that people already pay to solve.\n"
            "- revenue (revenue and profit potential): 0 = no plausible way to get paid; 5 = modest, low "
            "prices or one-off sales; 10 = strong margins and recurring or high-value revenue. Market size "
            "belongs under market, not here.\n"
            "- reach (reachability of the target group): 0 = no known channel to buyers; 10 = buyers gather "
            "in channels this user can reach cheaply this month.\n"
            "- feasibility (technical and operational): for THIS user's skills, time and team size. 0 = needs "
            "capabilities they do not have; 10 = a first version within weeks with what they have.\n"
            "- edge (competitive advantage, differentiation): 0 = commodity with many equal alternatives; "
            "10 = a clear, defensible reason to choose it.\n"
            "- cost (startup cost, capital need): HIGHER = CHEAPER. 0 = needs capital far beyond the user's "
            "budget; 10 = can start for almost nothing. If the request names a budget, a candidate that cannot "
            "reach a first test within it scores 3 or less.\n"
            "- risk (risks and regulation): HIGHER = SAFER. 0 = serious legal, privacy, platform-dependency "
            "or liability risk; 10 = few, manageable risks.\n\n"
            "Count each weakness once: high cost belongs under cost, not also under feasibility, unless it "
            "separately blocks building it. Do not reward an idea for being clever or new. If a candidate "
            "breaks a hard constraint in the request even in its smallest form (a budget, a solo limit, a "
            "legal line), add a KO line for it.\n\n"
            "Write exactly these lines for every candidate, and nothing else:\n\n"
            "SCORE S1: market=N, revenue=N, reach=N, feasibility=N, edge=N, cost=N, risk=N\n"
            "WHY S1: one or two sentences giving the reasons for the highest and the lowest rating\n"
            "KO S1: the hard constraint it breaks (only when it does)\n"
            % (idx, state["scorers"], jobs(state, "shortlist")[0]["output"]))
    if phase == "verdict":
        allowed = allowed_winners(state)
        tie = ("" if len(allowed) < 2 else
               " The top is a near tie: check whether combining them is better, choose the one you would "
               "start with, and say what information would settle it.")
        return h + (
            "You are the JUDGE. Read the request, the shortlist with the jury's discussion (%s) and the score "
            "sheet (%s). The weighted ranking, computed by script from the independent assessors:\n\n%s\n\n"
            "Choose %s unless the margin is narrow: you may choose any candidate within %.0f points of the "
            "top, which is %s. Knocked-out candidates cannot win.%s\n\n"
            "Write exactly this, 450 words at most. The first line:\n\n"
            "WINNER: Sx\n\n"
            "## Executive Summary\n"
            "3 to 5 sentences: the recommended idea, for whom, how it makes money, and the first test. "
            "No guarantees.\n\n"
            "## %s\n"
            "Answer briefly: why this is the best fit for the request; which customer problem it solves better "
            "than the alternatives; why the customer would pay; how the first version stays small; how to test "
            "demand before spending real money; how it differs from existing offers; what must be true for the "
            "business model to work; which alternatives were dropped and why (name them). End with the main "
            "remaining uncertainty.\n"
            % (jobs(state, "shortlist")[0]["output"], _abs(state, "scores.json"), ranking_text(state),
               allowed[0] if allowed else "the top candidate", TIE_MARGIN, ", ".join(allowed), tie,
               labels(state)["winner"]))
    if phase == "plan":
        win = winner(state)
        name = next((c["name"] for c in shortlist(state) if c["id"] == win), win)
        heads = dict(labels(state)["plan"])
        return h + (
            "You are the PRODUCT ARCHITECT. The court chose %s: %s. Read the request, the shortlist entry %s in "
            "%s, and the judge's reasoning in %s. Turn the winner into a realistic, buildable product plan for "
            "this user.\n\n"
            "- Keep the MVP small. Pick proven technology for the need, not for the trend. Use the user's "
            "skills as a criterion only where the request states them; otherwise label it an assumption.\n"
            "- Prices, costs and margins: back them with the research file or a source you look up (at most 4 "
            "web searches, cite the URL), otherwise label them as hypotheses to test. Give time and cost "
            "ranges, not promises.\n"
            "- Success and kill thresholds must fit this idea; never present them as industry standards.\n"
            "- If something does not apply (a service may need no database), say so in one line instead of "
            "padding.\n\n"
            "Write exactly these sections with these level-2 headings, in this order, using ### for "
            "sub-headings. 1300 words at most: write bullets, not prose, and state each fact once; refer back "
            "to it instead of repeating it in a later section. Every item listed below must still be "
            "covered.\n\n"
            "## %s\n"
            "### Produktdefinition / product definition: working name, precise description, ideal customer "
            "profiles, main problem and concrete benefit, the one unique selling point, positioning against "
            "alternatives.\n"
            "### MVP: must-have features; features for later versions; features deliberately not built.\n\n"
            "## %s\n"
            "Who pays and why; one-off or recurring; price strategy; fixed and variable costs; plausible gross "
            "margin; acquisition channels; risks to profitability and scaling.\n\n"
            "## %s\n"
            "Architecture fitted to the product: frontend, backend, database, authentication and permissions, "
            "external APIs and AI models, hosting and deployment, privacy and security, monitoring, error "
            "handling and maintenance. Then the build order, including the data model and API where needed, "
            "and the tests.\n\n"
            "## %s\n"
            "The cheapest test that checks demand before real development (landing page, interviews, "
            "clickable prototype, concierge MVP, paid pilot or pre-orders where lawful, small ad test): what, "
            "how, cost, duration, measurable success criteria and kill criteria.\n\n"
            "## %s\n"
            "Numbered steps from validation to launch and scaling: validate the problem; research the target "
            "group and competitors; define the MVP scope; build; win the first customers; launch (deployment, "
            "monitoring, support, privacy and legal requirements); optimise and scale. For each step: tasks, "
            "expected result, resources, success criteria, time and cost range.\n\n"
            "## %s\n"
            "What must be answered before any larger investment.\n\n"
            "## %s\n"
            "Exactly three concrete actions the user can start today or this week.\n"
            % (win, name, win, jobs(state, "shortlist")[0]["output"], jobs(state, "verdict")[0]["output"],
               heads["product"], heads["business"], heads["tech"], heads["validation"], heads["roadmap"],
               heads["risks"], heads["next"]))
    raise ValueError(phase)


# ---------- report ----------

def cell(text, limit=220):
    text = re.sub(r"\s+", " ", text or "").replace("|", "/").strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def render(state):
    L = labels(state)
    R = L["report"]
    request = read(_abs(state, "request.md")).strip()
    first, _, interpretation = request.partition("\n")
    verdict = sections(output_text(jobs(state, "verdict")[0]))
    plan = sections(output_text(jobs(state, "plan")[0]))
    result = compute(state)
    win = winner(state)
    pts = votes(state)
    cands = {c["id"]: c for c in shortlist(state)}

    lines = ["# %s: %s" % (R["title"], first.lstrip("# ").strip()), "", "_%s_" % R["disclaimer"], ""]
    lines += ["## 1. %s" % R["s1"], "", find_section(verdict, "Executive Summary") or "", ""]
    lines += ["## 2. %s" % R["s2"], "", interpretation.strip(), ""]

    lines += ["## 3. %s" % R["s3"], ""]
    cols = ["#", R["juror"], R["idea_col"], R["summary_col"]] + ([] if state.get("quick") else [R["points"]])
    lines += ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in ideas(state):
        idea = row["idea"]
        cells = [row["id"], row["juror"]["name"], cell(idea["name"], 80) if idea else R["no_idea"],
                 cell(idea["summary"]) if idea else ""]
        if not state.get("quick"):
            cells.append(str(pts[row["id"]]))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines += ["## 4. %s" % R["s4"], "",
              find_section(sections(output_text(jobs(state, "shortlist")[0])), L["discussion"]) or "", "",
              "**%s:**" % R["shortlist"], ""]
    for c in cands.values():
        lines.append("- **%s %s** (%s): %s" % (c["id"], c["name"], " + ".join(c["sources"]), cell(c["summary"], 400)))
    lines.append("")

    lines += ["## 5. %s" % R["s5"], ""]
    crit = [k for k, _ in CRITERIA]
    cols = [R["rank"], R["candidate"]] + ["%s (%g%%)" % (L["criteria"][k], result["weights"][k]) for k in crit] + \
           [R["score"]] + ([] if state.get("quick") else [R["points"]])
    lines += ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in result["ranking"]:
        name = "%s %s" % (r["id"], cell(r["name"], 60))
        if r["id"] == win:
            name = "**%s**" % name
        score = "%.1f" % r["score"] + (" (%s)" % R["ko"] if r["knocked_out"] else "")
        cells = [str(r["rank"]), name] + ["%g" % r["means"][k] for k in crit] + [score]
        if not state.get("quick"):
            cells.append(str(r["jury_points"]))
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "_%s %d %s._" % (R["formula"], len(result["assessors"]), R["assessors"])]
    if not state.get("quick"):
        lines += ["", "_%s_" % R["vote_note"]]
    lines += ["", "**%s:**" % R["reasons"], ""]
    for r in result["ranking"]:
        for assessor, why in r["why"]:
            lines.append("- %s (%s): %s" % (r["id"], assessor, cell(why, 600)))
        for ko in r["ko"]:
            lines.append("- %s KO: %s" % (r["id"], cell(ko, 400)))
        if r["knocked_out"]:
            lines.append("- %s: %s" % (r["id"], R["knocked"]))
    lines.append("")

    lines += ["## 6. %s" % R["s6"], ""]
    top = next((r["id"] for r in result["ranking"] if not r["knocked_out"]), None)
    if win and top and win != top:
        lines += ["_%s_" % (R["override"] % (win, top, TIE_MARGIN)), ""]
    lines += [find_section(verdict, L["winner"]) or "", ""]

    for n, (key, title) in enumerate(L["plan"]):
        lines += ["## %d. %s" % (n + 7, title), "", find_section(plan, title) or "", ""]

    lines += ["---", "", "_%s_" % (R["full"] % os.path.abspath(state["dir"])), "", CREDIT]
    text = "\n".join(lines) + "\n"
    write(os.path.join(state["dir"], "REPORT.md"), text)
    return text


# ---------- commands ----------

def calls(quick):
    n = len(load_jurors())
    if quick:
        return n, 0, QUICK_SCORERS, n + 1 + QUICK_SCORERS + 2
    return n, n, SCORERS, 2 * n + 1 + SCORERS + 2


def cmd_plan(args):
    n, debate, scorers, total = calls(args.quick)
    print("%d jurors: %d ideas, %s, 1 foreperson, %d assessor(s), 1 judge, 1 product architect = %d sub-agent calls"
          % (n, n, "%d debate statements" % debate if debate else "no debate round (quick)", scorers, total))


def cmd_init(args):
    if not os.path.exists(args.request_file):
        sys.exit("ideacourt: request file not found: %s" % args.request_file)
    request = read(args.request_file).strip()
    if not request:
        sys.exit("ideacourt: the request file is empty")
    research = ""
    if args.research_file:
        if not os.path.exists(args.research_file):
            sys.exit("ideacourt: research file not found: %s" % args.research_file)
        research = read(args.research_file).strip()
    weights = parse_weights(args.weights)
    jurors = load_jurors()
    rd = os.path.join(ROOT, time.strftime("%Y%m%d-%H%M%S"))
    if os.path.exists(rd):
        rd += "-%d" % os.getpid()
    for sub in ["briefs"] + PHASES:
        os.makedirs(os.path.join(rd, sub), exist_ok=True)
    write(os.path.join(rd, "request.md"), request + "\n")
    if research:
        write(os.path.join(rd, "research.md"), research + "\n")
    state = {"dir": rd, "lang": args.lang, "quick": bool(args.quick), "weights": weights,
             "scorers": QUICK_SCORERS if args.quick else SCORERS, "jury": jurors,
             "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save_state(state)
    write(LATEST, rd)
    print("ideacourt: court opened in %s (%d jurors, %s, language %s)"
          % (rd, len(jurors), "quick" if args.quick else "full", args.lang))
    print("next: ideacourt.py prompts ideas")


def cmd_prompts(args):
    state = load_state()
    order = phases(state)
    if args.phase not in order:
        sys.exit("ideacourt: phase %s is not part of this run (phases: %s)" % (args.phase, ", ".join(order)))
    for earlier in order[:order.index(args.phase)]:
        if missing(state, earlier):
            sys.exit("ideacourt: %s is not finished yet. Run: ideacourt.py next" % earlier)
    todo = missing(state, args.phase)
    for j in jobs(state, args.phase):
        write(j["brief"], brief_text(state, args.phase, j))
    if not todo:
        print("ideacourt: %s is complete. Run: ideacourt.py next" % args.phase)
        return
    for w in range(0, len(todo), WAVE):
        print("wave %d:" % (w // WAVE + 1))
        for j in todo[w:w + WAVE]:
            print("  %s  brief=%s" % (j["id"], j["brief"]))
    print("Launch one Agent call per job, one wave at a time. Prompt: "
          "\"Read <brief> and follow it exactly. It is your whole brief.\"")


def cmd_check(args):
    state = load_state()
    bad = [(j, problems(state, args.phase, j)) for j in jobs(state, args.phase)]
    bad = [(j, p) for j, p in bad if p]
    if not bad:
        print("ideacourt: %s complete" % args.phase)
    for j, p in bad:
        print("not accepted: %s -> %s: %s" % (j["id"], j["output"], "; ".join(p)))


def cmd_next(args):
    state = load_state()
    for phase in phases(state):
        if missing(state, phase):
            if phase == "verdict":
                print("ideacourt: weighted ranking\n%s" % ranking_text(state))
            print("next phase: %s. Run: ideacourt.py prompts %s" % (phase, phase))
            return
    print("ideacourt: the court has finished. Run: ideacourt.py render")


def cmd_score(args):
    state = load_state()
    print(ranking_text(state))


def cmd_render(args):
    state = load_state()
    for phase in phases(state):
        if missing(state, phase):
            sys.exit("ideacourt: %s is not finished yet. Run: ideacourt.py next" % phase)
    sys.stdout.write(render(state))


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="ideacourt.py")
    sub = p.add_subparsers(dest="cmd")
    pl = sub.add_parser("plan")
    pl.add_argument("--quick", action="store_true")
    pi = sub.add_parser("init")
    pi.add_argument("--request-file", required=True)
    pi.add_argument("--research-file")
    pi.add_argument("--lang", default="en")
    pi.add_argument("--quick", action="store_true")
    pi.add_argument("--weights")
    for name in ("prompts", "check"):
        sp = sub.add_parser(name)
        sp.add_argument("phase", choices=PHASES)
    for name in ("next", "score", "render"):
        sub.add_parser(name)
    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 1
    {"plan": cmd_plan, "init": cmd_init, "prompts": cmd_prompts, "check": cmd_check,
     "next": cmd_next, "score": cmd_score, "render": cmd_render}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
