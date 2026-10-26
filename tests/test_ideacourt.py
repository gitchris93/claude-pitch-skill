"""Tests for pitch/ideacourt.py: the pipeline, validation, scoring and report.

The sub-agents are replaced by fixture files, so these tests check the bookkeeping the skill relies
on, not the quality of the ideas a live run produces.

    py -3 -m unittest discover -s tests -v
"""
import contextlib
import importlib.util
import io
import os
import re
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(os.path.dirname(HERE), "pitch")

spec = importlib.util.spec_from_file_location("ideacourt", os.path.join(SKILL, "ideacourt.py"))
ic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ic)

REQUEST_DE = """# Wie kann ich mit KI-Videos Geld verdienen?

**Ziel:** Ein Einkommen mit KI-Videos aufbauen.
**Einschränkungen:** hart: maximal 500 Euro Budget, Einzelperson.
**Annahmen:** Annahme: Teilzeit, grundlegende technische Kenntnisse.
"""


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ic.main(list(argv))
    return out.getvalue()


def idea_text(state, name, summary="Kurz und konkret."):
    lines = ["## %s: %s" % (ic.labels(state)["idea"], name)]
    for key, label in ic.labels(state)["fields"]:
        lines.append("**%s:** %s" % (label, summary if key == "summary" else "Inhalt für %s (Schätzung)" % key))
    return "\n".join(lines) + "\n"


def shortlist_text(state, n=3):
    fields = "\n".join("**%s:** Text %s" % (label, key) for key, label in ic.labels(state)["fields"])
    parts = ["## %s\n- J04 und J07 sind am stärksten.\n- J09: verworfen, zu teuer." % ic.labels(state)["discussion"]]
    for i in range(1, n + 1):
        parts.append("## S%d: Kandidat %d\nSOURCE: J%02d + J%02d\n%s" % (i, i, i, i + 3, fields))
    return "\n\n".join(parts) + "\n"


def score_line(sid, vals, why="Gründe.", ko=None):
    keys = [k for k, _ in ic.CRITERIA]
    text = "SCORE %s: %s\nWHY %s: %s\n" % (sid, ", ".join("%s=%s" % (k, v) for k, v in zip(keys, vals)), sid, why)
    if ko:
        text += "KO %s: %s\n" % (sid, ko)
    return text


def plan_text(state):
    return "\n\n".join("## %s\nInhalt %s.\n### Unterpunkt\nmehr." % (title, key)
                       for key, title in ic.labels(state)["plan"]) + "\n"


class Court(unittest.TestCase):
    lang = "de"
    quick = False

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        os.makedirs(".ideacourt")
        ic.write(".ideacourt/request.md", REQUEST_DE)
        args = ["init", "--request-file", ".ideacourt/request.md", "--lang", self.lang]
        if self.quick:
            args.append("--quick")
        run(*args)
        self.state = ic.load_state()

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, phase, job_id, text):
        ic.write(ic._abs(self.state, phase, "%s.md" % job_id), text)

    def fill_ideas(self):
        for i in range(12):
            self.put("ideas", "juror-%02d" % (i + 1), idea_text(self.state, "Idee %d" % (i + 1)))

    def fill_debate(self, top="J04, J07, J01"):
        for i in range(12):
            self.put("debate", "juror-%02d" % (i + 1),
                     "TOP 3: %s\nWHY: x\nOBJECTION: J04: y\nIMPROVE: J07: z\nCOMBINE: none\nDROP: J09: teuer\n" % top)

    def fill_scores(self, sheets):
        for i, text in enumerate(sheets):
            self.put("scoring", "assessor-%d" % (i + 1), text)

    def default_sheets(self):
        s = score_line("S1", [8, 7, 8, 7, 6, 8, 7]) + score_line("S2", [6, 6, 6, 6, 6, 6, 6]) + \
            score_line("S3", [5, 5, 5, 5, 5, 5, 5])
        return [s] * self.state["scorers"]

    def until_verdict(self):
        self.fill_ideas()
        if not self.quick:
            self.fill_debate()
        self.put("shortlist", "foreperson", shortlist_text(self.state))
        self.fill_scores(self.default_sheets())


class FullRun(Court):
    def test_plan_counts_all_calls(self):
        self.assertIn("= 30 sub-agent calls", run("plan"))
        self.assertIn("= 16 sub-agent calls", run("plan", "--quick"))

    def test_all_twelve_jurors_sit(self):
        self.assertEqual(len(self.state["jury"]), 12)
        self.assertEqual(len({j["name"] for j in self.state["jury"]}), 12)
        out = run("prompts", "ideas")
        self.assertIn("wave 1:", out)
        self.assertIn("wave 2:", out)
        self.assertEqual(out.count("brief="), 12)

    def test_phases_in_order(self):
        self.assertIn("next phase: ideas", run("next"))
        with self.assertRaises(SystemExit):
            run("prompts", "scoring")
        self.fill_ideas()
        self.assertIn("next phase: debate", run("next"))
        self.fill_debate()
        self.assertIn("next phase: shortlist", run("next"))
        self.put("shortlist", "foreperson", shortlist_text(self.state))
        self.assertIn("next phase: scoring", run("next"))
        self.fill_scores(self.default_sheets())
        out = run("next")
        self.assertIn("next phase: verdict", out)
        self.assertIn("1. S1 Kandidat 1: 73.5 / 100", out)
        self.put("verdict", "judge", "WINNER: S1\n## Executive Summary\nKurz.\n## Gewinner\nWeil.\n")
        self.assertIn("next phase: plan", run("next"))
        self.put("plan", "architect", plan_text(self.state))
        self.assertIn("the court has finished", run("next"))

    def test_malformed_idea_is_sent_back(self):
        self.fill_ideas()
        self.put("ideas", "juror-03", "## IDEE: Halb\n**Kurzbeschreibung:** nur das\n")
        self.assertIn("next phase: ideas", run("next"))
        check = run("check", "ideas")
        self.assertIn("juror-03", check)
        self.assertIn("Zielgruppe", check)
        self.assertNotIn("juror-04", check)
        self.assertEqual(run("prompts", "ideas").count("brief="), 1)

    def test_skipped_juror_is_accepted(self):
        self.fill_ideas()
        self.put("ideas", "juror-05", "SKIPPED\n")
        self.assertIn("next phase: debate", run("next"))

    def test_weighted_score_formula(self):
        means = {"market": 8, "revenue": 7, "reach": 8, "feasibility": 7, "edge": 6, "cost": 8, "risk": 7}
        # 16 + 14 + 12 + 10.5 + 6 + 8 + 7
        self.assertEqual(ic.weighted(means, dict(ic.CRITERIA)), 73.5)
        self.assertEqual(ic.weighted({k: 10 for k, _ in ic.CRITERIA}, dict(ic.CRITERIA)), 100)
        self.assertEqual(sum(w for _, w in ic.CRITERIA), 100)

    def test_scores_are_averaged_across_assessors(self):
        self.until_verdict()
        a = score_line("S1", [10, 10, 10, 10, 10, 10, 10]) + score_line("S2", [5] * 7) + score_line("S3", [1] * 7)
        b = score_line("S1", [6, 6, 6, 6, 6, 6, 6]) + score_line("S2", [5] * 7) + score_line("S3", [1] * 7)
        c = score_line("S1", [8, 8, 8, 8, 8, 8, 8]) + score_line("S2", [5] * 7) + score_line("S3", [1] * 7)
        self.fill_scores([a, b, c])
        top = ic.compute(self.state)["ranking"][0]
        self.assertEqual(top["id"], "S1")
        self.assertEqual(top["score"], 80.0)
        self.assertEqual(top["means"]["market"], 8.0)

    def test_score_outside_range_is_rejected(self):
        self.until_verdict()
        bad = score_line("S1", [11, 7, 8, 7, 6, 8, 7]) + score_line("S2", [6] * 7) + score_line("S3", [5] * 7)
        self.put("scoring", "assessor-2", bad)
        self.assertIn("outside 0..10", run("check", "scoring"))
        self.assertIn("next phase: scoring", run("next"))

    def test_budget_knockout_cannot_win(self):
        # Test C: the best-scoring candidate breaks the 500 EUR hard limit for 2 of 3 assessors
        self.until_verdict()
        s1 = [10, 10, 10, 10, 10, 1, 8]
        ko = "braucht mehr als 500 Euro"
        sheets = [score_line("S1", s1, ko=ko) + score_line("S2", [6] * 7) + score_line("S3", [5] * 7),
                  score_line("S1", s1, ko=ko) + score_line("S2", [6] * 7) + score_line("S3", [5] * 7),
                  score_line("S1", s1) + score_line("S2", [6] * 7) + score_line("S3", [5] * 7)]
        self.fill_scores(sheets)
        ranking = ic.compute(self.state)["ranking"]
        self.assertEqual(ranking[-1]["id"], "S1")
        self.assertTrue(ranking[-1]["knocked_out"])
        self.assertEqual(ic.allowed_winners(self.state), ["S2"])
        self.put("verdict", "judge", "WINNER: S1\n## Executive Summary\nx\n## Gewinner\ny\n")
        self.assertIn("not allowed", run("check", "verdict"))
        self.assertEqual(ic.winner(self.state), "S2")

    def test_single_ko_does_not_knock_out(self):
        self.until_verdict()
        sheets = self.default_sheets()
        sheets[0] = sheets[0] + "KO S1: ein Gutachter ist dagegen\n"
        self.fill_scores(sheets)
        self.assertFalse(ic.compute(self.state)["ranking"][0]["knocked_out"])

    def test_near_tie_lets_judge_choose(self):
        self.until_verdict()
        sheet = score_line("S1", [7] * 7) + score_line("S2", [7, 7, 7, 7, 7, 7, 5]) + score_line("S3", [3] * 7)
        self.fill_scores([sheet] * 3)
        self.assertEqual(ic.allowed_winners(self.state), ["S1", "S2"])  # 70 vs 68
        self.put("verdict", "judge", "WINNER: S2\n## Executive Summary\nx\n## Gewinner\ny\n")
        self.assertEqual(run("check", "verdict").strip(), "ideacourt: verdict complete")
        self.assertEqual(ic.winner(self.state), "S2")
        self.assertIn("near tie", ic.brief_text(self.state, "verdict", ic.jobs(self.state, "verdict")[0]))

    def test_judge_cannot_pick_a_clear_loser(self):
        self.until_verdict()
        self.put("verdict", "judge", "WINNER: S3\n## Executive Summary\nx\n## Gewinner\ny\n")
        self.assertIn("next phase: verdict", run("next"))
        self.assertEqual(ic.winner(self.state), "S1")

    def test_debate_votes_are_counted_but_do_not_decide(self):
        self.until_verdict()
        pts = ic.votes(self.state)
        self.assertEqual((pts["J04"], pts["J07"], pts["J01"]), (36, 24, 12))
        ranking = ic.compute(self.state)["ranking"]
        # S1 = J01 + J04 (48 points), S3 = J03 + J06 (0 points): ranking follows the score
        self.assertEqual([r["id"] for r in ranking], ["S1", "S2", "S3"])
        self.assertEqual(ranking[0]["jury_points"], 48)

    def test_shortlist_needs_sources_and_discussion(self):
        self.fill_ideas()
        self.fill_debate()
        self.put("shortlist", "foreperson", "## S1: Nur eine\n**Kurzbeschreibung:** x\n")
        check = run("check", "shortlist")
        self.assertIn("Diskussion", check)
        self.assertIn("2 to 5 candidates", check)
        self.assertIn("SOURCE", check)

    def test_plan_needs_every_section(self):
        self.until_verdict()
        self.put("verdict", "judge", "WINNER: S1\n## Executive Summary\nx\n## Gewinner\ny\n")
        self.put("plan", "architect", "## Produktkonzept\nnur das\n")
        check = run("check", "plan")
        for title in ("Geschäftsmodell", "Validierungsstrategie", "Sofortmaßnahmen"):
            self.assertIn(title, check)

    def test_render_refuses_unfinished_run(self):
        with self.assertRaises(SystemExit):
            run("render")

    def test_report_has_all_thirteen_sections_in_order(self):
        self.until_verdict()
        self.put("verdict", "judge", "WINNER: S1\n## Executive Summary\nDie Empfehlung.\n## Gewinner\nDie Begründung.\n")
        self.put("plan", "architect", plan_text(self.state))
        report = run("render")
        heads = re.findall(r"^## (\d+)\. (.+)$", report, re.M)
        self.assertEqual([int(n) for n, _ in heads], list(range(1, 14)))
        self.assertEqual(heads[2][1], "Die zwölf Ideen")
        self.assertEqual(heads[12][1], "Sofortmaßnahmen")
        self.assertIn("Die Empfehlung.", report)
        self.assertIn("Annahme: Teilzeit", report)
        self.assertIn("**S1 Kandidat 1**", report)
        self.assertIn("| 1 | **S1 Kandidat 1** | 8 | 7 | 8 | 7 | 6 | 8 | 7 | 73.5 | 48 |", report)
        self.assertIn("keine Garantie", report)
        self.assertIn("Inhalt tech.", report)
        for i in range(1, 13):
            self.assertIn("| J%02d |" % i, report)
        self.assertTrue(os.path.exists(ic._abs(self.state, "REPORT.md")))
        self.assertIn("Die Empfehlung.", ic.read(ic._abs(self.state, "REPORT.md")))


class QuickRun(Court):
    quick = True

    def test_quick_skips_debate_and_uses_one_assessor(self):
        self.assertEqual(self.state["scorers"], 1)
        self.fill_ideas()
        self.assertIn("next phase: shortlist", run("next"))
        with self.assertRaises(SystemExit):
            run("prompts", "debate")
        brief = ic.brief_text(self.state, "shortlist", ic.jobs(self.state, "shortlist")[0])
        self.assertIn("quick mode", brief)
        self.assertIn("The Contrarian", brief)

    def test_quick_report_renders(self):
        self.until_verdict()
        self.put("verdict", "judge", "WINNER: S1\n## Executive Summary\nx\n## Gewinner\ny\n")
        self.put("plan", "architect", plan_text(self.state))
        report = run("render")
        self.assertNotIn("Jury-Punkte", report)
        self.assertEqual(len(re.findall(r"^## \d+\. ", report, re.M)), 13)


class English(Court):
    lang = "en"

    def test_english_labels(self):
        self.until_verdict()
        self.put("verdict", "judge", "WINNER: S1\n## Executive Summary\nx\n## Winner\ny\n")
        self.put("plan", "architect", plan_text(self.state))
        report = run("render")
        self.assertIn("## 3. The twelve ideas", report)
        self.assertIn("## 13. Next actions", report)


class OtherLanguage(Court):
    lang = "fr"

    def test_unknown_language_falls_back_to_english_headings(self):
        brief = ic.brief_text(self.state, "ideas", ic.jobs(self.state, "ideas")[0])
        self.assertIn("ISO code 'fr'", brief)
        self.assertIn("## IDEA:", brief)


class Briefs(Court):
    """What every live agent is told: the rules behind test scenarios A to E."""

    def brief(self, phase, i=0):
        return ic.brief_text(self.state, phase, ic.jobs(self.state, phase)[i])

    def test_every_brief_forbids_guarantees_and_invented_facts(self):
        self.until_verdict()
        self.put("verdict", "judge", "WINNER: S1\n## Executive Summary\nx\n## Gewinner\ny\n")
        for phase in ic.PHASES:
            text = self.brief(phase)
            self.assertIn("Never promise or imply guaranteed income", text, phase)
            self.assertIn("Never invent facts", text, phase)
            self.assertIn("not a panel of independent experts", text, phase)
            self.assertIn("German", text, phase)
            self.assertIn(ic._abs(self.state, "request.md"), text, phase)

    def test_each_juror_gets_a_distinct_lens(self):
        lenses = {self.brief("ideas", i).split("You are JUROR")[1].split("\n")[0] for i in range(12)}
        self.assertEqual(len(lenses), 12)

    def test_idea_brief_asks_for_every_required_field(self):
        text = self.brief("ideas")
        for _, label in ic.labels(self.state)["fields"]:
            self.assertIn("**%s:**" % label, text)
        self.assertIn("never see the other jurors' ideas", text)
        self.assertIn("unrealistic", text)

    def test_scoring_brief_applies_budget_and_avoids_double_counting(self):
        self.until_verdict()
        text = self.brief("scoring")
        self.assertIn("cannot reach a first test within it scores 3 or less", text)
        self.assertIn("Count each weakness once", text)
        self.assertIn("HIGHER = CHEAPER", text)
        self.assertIn("Do not reward an idea for being clever", text)

    def test_research_file_is_passed_on(self):
        ic.write(".ideacourt/research.md", "- Fakt (https://example.com, 2026-10-26)\n")
        run("init", "--request-file", ".ideacourt/request.md", "--research-file", ".ideacourt/research.md",
            "--lang", "de")
        state = ic.load_state()
        self.assertIn("research.md", ic.brief_text(state, "ideas", ic.jobs(state, "ideas")[0]))
        self.assertIn("There is no research file", self.brief("ideas"))

    def test_custom_weights(self):
        w = ic.parse_weights("market=30,revenue=20,reach=10,feasibility=15,edge=5,cost=15,risk=5")
        self.assertEqual(w["market"], 30)
        for bad in ("market=30", "market=50,revenue=20,reach=10,feasibility=15,edge=5,cost=15,risk=5",
                    "magic=100"):
            with self.assertRaises(SystemExit):
                ic.parse_weights(bad)


class SkillFile(unittest.TestCase):
    """The orchestration rules for scenarios D, E and F live in SKILL.md."""

    @classmethod
    def setUpClass(cls):
        cls.raw = ic.read(os.path.join(SKILL, "SKILL.md"))
        cls.text = re.sub(r"\s+", " ", cls.raw)  # line wrapping does not matter

    def test_frontmatter_registers_the_command(self):
        m = re.match(r"^---\n(.*?)\n---\n", self.raw, re.S)
        self.assertTrue(m)
        self.assertRegex(m.group(1), r"(?m)^name: pitch$")
        self.assertRegex(m.group(1), r"(?m)^description: ")
        self.assertIn("Not for writing pitch decks", self.text)
        self.assertIn("$ARGUMENTS", self.text)
        self.assertIn("${CLAUDE_SKILL_DIR}/ideacourt.py", self.text)

    def test_vague_request_gets_one_question(self):  # scenario D
        self.assertIn("Too vague to work with", self.text)
        self.assertIn("ask ONE targeted question", self.text)
        self.assertIn("Do not invent facts about the person", self.text)

    def test_unrealistic_expectations(self):  # scenario E
        self.assertIn("Reality check", self.text)
        self.assertIn("no idea can guarantee income", self.text)

    def test_points_to_court_for_existing_ideas(self):  # scenario F: the two skills do not compete
        self.assertIn("use court", self.text)
        self.assertIn("`/court`", self.text)

    def test_windows_python_fallback(self):
        self.assertIn("`py -3`", self.text)


if __name__ == "__main__":
    unittest.main()
