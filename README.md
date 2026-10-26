# /pitch

**Don't know what to build? Let twelve Claudes pitch you their best idea, then fight over it.**

`/pitch` is a free Claude Code skill. It turns an open goal like *"How do I make money with AI videos?"*
into **one recommended business idea and a plan to build and test it**.

Normally, asking Claude for business ideas gives you one polite list. `/pitch` runs it as a court
instead: twelve jurors with different business lenses each invent their own idea without seeing the
others. Then they tear each other's ideas apart, independent assessors score the shortlist, and a
judge picks the winner. A product architect turns the winner into an MVP, a business model, a tech
plan, a validation test and a roadmap.

```
/pitch How do I make money with AI videos?
/pitch Which mobile app could I build to run a profitable business?
/pitch I want to build a digital product alone with at most 500 euros.
/pitch --quick What software could I sell as a solo developer?
```

> Already have an idea and want it stress-tested? Use [`/court`](https://github.com/alexyc9381/court-skill),
> the skill this project is built on. `/pitch` finds the idea; `/court` puts it on trial.

## How it works

| # | Phase | Who | What happens |
|---|---|---|---|
| 1 | Understand | Claude (the clerk) | Separates your real goal from the solution you named, and writes down constraints (budget, time, skills) and every assumption. If the request is too vague, Claude asks you one targeted question. If it expects guaranteed income, Claude turns that into a testable hypothesis instead. |
| 2 | Research | Claude | One shared round of searches for the whole jury: existing offers and their prices, how crowded the space is, platform rules. Each fact with its source. |
| 3 | Ideas | 12 jurors, all at once and independently | Each juror pitches one concrete idea: problem, customer, solution, business model, pricing, edge, build effort, startup cost, risks, demand test and assumptions. |
| 4 | Debate | 12 jurors | Every juror reads all twelve ideas and names a top 3, the strongest objection, one improvement, a possible combination and one idea to drop. |
| 5 | Shortlist | Foreperson | Drops weak ideas, merges and improves the strong ones, and builds a shortlist of 3 to 5 candidates. |
| 6 | Scoring | 3 assessors, independently | Rate every candidate from 0 to 10 on seven criteria, and can knock out anything that breaks a hard limit you set, such as your budget. |
| 7 | Verdict | Judge | Picks the winner and explains why the alternatives lost. |
| 8 | Plan | Product architect | Writes the product concept, MVP scope, business model, technical architecture, validation test with kill criteria, step-by-step roadmap, open risks and three things to do this week. |

### The jury

The Market Strategist · The Revenue Architect · The Customer Advocate · The AI Innovator ·
The Product Builder · The Growth Hacker · The SaaS Expert · The Solo-Founder Advisor ·
The Financial Analyst · The Competitor Analyst · The Risk Analyst · The Contrarian

### Scoring is done by code, not by vibes

The script `ideacourt.py` calculates the ranking from the assessors' ratings, so the model cannot
"feel" its way to a winner:

| Criterion | Weight |
|---|---:|
| Market need and customer problem | 20% |
| Revenue and profit potential | 20% |
| Reachability of the target group | 15% |
| Technical and operational feasibility | 15% |
| Competitive edge and differentiation | 10% |
| Startup cost and capital need (higher = cheaper) | 10% |
| Risk and regulation (higher = safer) | 10% |

`score = Σ (mean rating / 10 × weight)`, from 0 to 100.

- A candidate that most assessors knock out cannot win.
- The judge must pick the top score, or a candidate within 3 points of it when the result is a near tie.
- The jurors' debate votes are shown for transparency, but they don't decide. The most popular idea
  is not automatically the best one.
- You can change the weights with `--weights` (see below).

## What you get

A `REPORT.md` in `.ideacourt/<run>/` with 13 sections:

1. Executive summary
2. What you actually want (the interpretation of your request)
3. The twelve ideas
4. What the jury debate decided
5. Scoring table
6. Winner, and why the others lost
7. Product concept and MVP
8. Business model
9. Technical plan
10. Validation strategy
11. Step-by-step roadmap
12. Risks and open questions
13. Your next three actions

Every idea, debate statement, score sheet and brief is saved next to it, so you can check how the
decision was reached. `/pitch` only writes into `.ideacourt/` and never touches your other files.
The report is written in the language you asked in (headings in English or German).

## Install

**Ask Claude.** In Claude Code, say:

```
Install the pitch skill from https://github.com/GitChris93/claude-pitch-skill
```

**Or by hand** (needs Python 3, no other dependencies):

```bash
git clone https://github.com/GitChris93/claude-pitch-skill
cd claude-pitch-skill
python3 build.py --install      # Windows: py -3 build.py --install
```

This copies the `pitch/` folder to `~/.claude/skills/pitch/`. Restart Claude Code and type `/pitch`.

**claude.ai / Claude Desktop:** Download `pitch-skill.zip` from the
[latest release](https://github.com/GitChris93/claude-pitch-skill/releases/latest) (or build it
yourself with `python3 build.py`, which writes `dist/pitch-skill.zip`) and upload it under
*Settings → Capabilities → Skills*. Uploaded skills sync to Claude Code too, so use only one of the
install ways, or the skill shows up twice.

## Usage

```
/pitch [--quick] [--lang CODE] [--weights k=v,...] <your goal, wish or problem>
```

| Flag | Meaning |
|---|---|
| `--quick` | Skips the separate debate round (the foreperson runs it) and uses 1 assessor instead of 3. |
| `--lang CODE` | Report language. Claude sets this from the language you write in. |
| `--weights k=v,...` | Custom weights: all of `market, revenue, reach, feasibility, edge, cost, risk`, summing to 100. Example: `--weights market=30,revenue=20,reach=10,feasibility=15,edge=5,cost=15,risk=5` |

**Usage cost:** A full run makes **30 sub-agent calls** (12 ideas, 12 debate statements,
1 foreperson, 3 assessors, 1 judge, 1 architect). `--quick` makes **16**. Every call counts toward
your plan's usage, so start with `--quick` if you are near your limit.

Tip: switch to accept-edits mode (Shift+Tab) during a run. Each sub-agent writes one file, and
otherwise you approve each one.

## Tests

```bash
python3 -m unittest discover -s tests -v      # Windows: py -3 -m unittest discover -s tests -v
```

The tests cover:

- the phase order and how malformed agent output is rejected
- the score formula and the averaging of the assessors' ratings
- budget knock-outs and near-tie rules
- `--quick` mode and languages
- all 13 report sections, and the rules every agent is briefed with

The sub-agents are replaced by fixture files, so the tests check the bookkeeping, not how good the
ideas of a live run are. `tests/test_court_regression.py` additionally runs the original `/court`
end to end when you point `COURT_SKILL_ZIP` at its `court-skill.zip` (or put the zip in the repo root). Otherwise that test is skipped.

## Uninstall

Delete `~/.claude/skills/pitch`, and the `.ideacourt/` folder in any project where you ran it.

## Honest limits

- The jurors, assessors and judge are **roles played by the same model**, not independent experts.
  Separate briefs, independent idea generation and averaged scores reduce agreeable answers, but
  they don't remove them.
- A high score is a **structured decision aid, not a prediction of success**, and never a promise of
  income. Market numbers without a source are marked as estimates or hypotheses to test.
- Treat the report as a well-argued starting point, not as financial, legal or business advice.

## Special thanks

This project would not exist without **[court](https://github.com/alexyc9381/court-skill)** by
**Alex Chen** ([@nocodealex](https://instagram.com/nocodealex), [chen.media](https://chen.media)).

`/court` came up with the idea of making Claude stop agreeing with you, by putting an idea on trial
in front of a jury of Claudes who never see each other. `/pitch` reuses its architecture:

- a Python script that keeps the state, writes one brief per sub-agent and checks every output
- jurors that work independently in waves
- a clerk that never argues and never softens the result

`/pitch` points that machinery at a different question: not *"is this idea good?"* but *"what
should I build?"*. Thank you, Alex, for publishing it under the MIT license. If you like `/pitch`,
go star [court-skill](https://github.com/alexyc9381/court-skill) too.

## License

MIT. See [`LICENSE`](LICENSE). Includes the copyright notice of
[court](https://github.com/alexyc9381/court-skill) © 2026 Alex Chen, MIT.
