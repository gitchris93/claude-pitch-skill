---
name: pitch
description: >-
  Turn an open goal ("How do I make money with AI videos?", "Which app should I build?") into one
  chosen business idea and a buildable product plan. Twelve juror Claudes with different business
  lenses each invent their own idea, debate them, a foreperson builds a shortlist, independent
  assessors score it on seven weighted criteria, a judge picks the winner and a product architect
  writes the MVP, business model, tech plan, validation test and roadmap. Use when the user asks
  what business, product, app, SaaS or side project to build, how to make money with something,
  or says "idea court" or types /pitch. Not for writing pitch decks, sales pitches or pitch texts.
  For judging an idea the user already has, use court.
argument-hint: "[--quick] [--lang CODE] [--weights market=20,...] <your goal, wish or problem>"
license: MIT
metadata:
  author: "GitChris93"
  based-on: "court by Alex Chen (https://github.com/alexyc9381/court-skill), MIT"
  version: "1.0.0"
---

# pitch

The user brings a goal, not an idea. Twelve jurors each invent a different answer, argue about them,
and the court ends with one recommended idea, the scores behind the choice, and a plan to build and
test it. You are the clerk: you prepare the file, drive the phases and present the report. You never
invent an idea, never score, never vote and never soften the result.

The jurors, assessors and judge are roles played by sub-agents of the same model. Say so if asked;
never call them independent experts.

What the user typed after `/pitch`: `$ARGUMENTS`

If that is blank, or still reads like a placeholder, take the goal from the conversation: what the
user most recently wanted to build, earn or solve.

## The tool

Every piece of bookkeeping goes through `ideacourt.py` in this skill's folder. Find a working Python
3 once, in this order, and keep using it: `python3`, `python`, `py -3` (on Windows `python3` is often
only a Microsoft Store placeholder that prints an error). Then:

```bash
<python> "${CLAUDE_SKILL_DIR}/ideacourt.py" <command>
```

Below, `IC` means exactly that command. If the path looks unexpanded, use the "Base directory for this
skill" that Claude Code printed at the top of this skill. The state lives in `.ideacourt/<run>/` in
the current directory, and every command after `init` finds it through `.ideacourt/LATEST`.

## Step 1: size it

| flag | meaning |
| --- | --- |
| `--quick` | Skip the separate debate round (the foreperson runs it) and use 1 assessor instead of 3. |
| `--lang CODE` | Always pass the ISO code of the language the user wrote in (`de`, `en`, `fr`, ...). Every agent writes in it; report headings exist in `de` and `en`, other languages get English headings. |
| `--weights k=v,...` | Only when the user asks to weight the criteria differently. All seven keys, summing to 100: `market, revenue, reach, feasibility, edge, cost, risk`. |

Run `IC plan` (with `--quick` if given) and tell the user in one line how big the run is, for example
"12 jurors, 30 sub-agent calls", then start. If this skill fired on its own (the user did not type
the command or ask for the court), ask once first and offer `--quick`.

Sub-agents write into `.ideacourt/` in the current directory. In the default permission mode that is
one approval per file; suggest accept-edits mode (Shift+Tab) for the run. Do not change the user's
settings yourself.

## Step 2: understand the request (phase 1)

**Sub-agents cannot see this conversation.** Everything they know comes from
`.ideacourt/request.md`, so write it to stand on its own:

```markdown
# <the request, verbatim>

**Goal:** what the user actually wants to achieve (income, independence, a product to sell, ...)
**Underlying need:** the problem behind the request
**Proposed path vs. goal:** the solution the user named ("AI videos", "an app") is one path to the
goal, not the goal itself; say how far the court may move away from it
**Desired outcome:** what a good result looks like for the user
**Likely customers:** who could pay, if the request suggests it; otherwise "open"
**Constraints:** budget, time, skills, team size, location, language, as far as the user stated them
**Success criteria:** what the user would count as success
**Assumptions:** every gap you filled, each marked "Assumption:"
**Reality check:** only if the request expects something no one can promise (see below)
```

Use the language of the request. Rules:

- Write only what the user said or what follows directly from it. Do not invent facts about the person
  (skills, money, location, job). A gap that matters becomes an explicit assumption, chosen cautiously
  (for example "Assumption: solo, part-time, no investor money, basic technical skills").
- **Too vague to work with** (for example "I want to be successful": no domain, no hint that it is
  about a business or product): ask ONE targeted question with the AskUserQuestion tool before
  anything else, offering 2 to 4 concrete directions plus their key constraint (budget/time), and wait.
  Only if the user declines, continue with clearly labelled assumptions and say in the request file
  that the direction was assumed.
- **Ambiguous but workable**: do not ask; state the assumptions and continue.
- **Unrealistic or guaranteed outcomes** (for example "an app that guarantees 10,000 EUR profit a month
  within 30 days"): do not repeat the promise as the goal. Write under **Reality check** that no idea
  can guarantee income or a timeline, that the court will look for the most promising testable
  hypothesis, and turn the number into a success criterion to test, not a promise.
- **Hard limits** the user named (for example "at most 500 euros", "alone") go under Constraints with
  the word "hard": the assessors knock out candidates that break them.

## Step 3: research, only when it changes the decision

If the request depends on current market facts (prices of existing tools, whether a market is
crowded, platform rules), run 3 to 6 targeted web searches and write `.ideacourt/research.md`:
one bullet per fact, with the source URL and the date you read it. Prefer official product and
pricing pages, documentation and reputable reports; mark community anecdotes as such. No opinions,
no recommendations. Skip this step when nothing you could look up would change which idea wins, or
when no web tool is available; the briefs then tell every agent that market numbers are estimates.

## Step 4: open the court

```bash
IC init --request-file .ideacourt/request.md [--research-file .ideacourt/research.md] --lang <code> [--quick] [--weights ...]
```

## Step 5: the run

Always drive it with `IC next`. It reads the files on disk and names the next phase. The phases run
in this order: `ideas` (12 independent ideas), `debate` (12 critiques, skipped with `--quick`),
`shortlist` (foreperson), `scoring` (independent assessors), `verdict` (judge), `plan` (product
architect).

Every phase works the same way:

1. `IC prompts <phase>` writes one brief per job and lists the jobs still to run, in waves.
2. Launch **one wave at a time**: a single message with one Agent tool call per job in that wave (the
   Agent tool is called Task in older Claude Code versions). Each call is:
   - `subagent_type`: `general-purpose`
   - `description`: `ideacourt <phase> <job id>`
   - `prompt`: `Read <brief path> and follow it exactly. It is your whole brief.`

   Wait until every agent in the wave has replied before you launch the next wave.
3. After the last wave, run `IC next`. If an output is missing or malformed it sends you back to the
   same phase; `IC check <phase>` says what is wrong, and `prompts` lists only those jobs. Re-run
   them once. If a juror or assessor fails twice, write the single line `SKIPPED` into its file and
   move on. If the foreperson, judge or architect fails twice, stop and tell the user which file is
   wrong. Never write an idea, a critique, a score, a verdict or a plan yourself.

Before the `verdict` phase, `IC next` prints the weighted ranking. The script computes it: the mean of
the assessors' 0-10 ratings per criterion, then score = sum of (rating / 10 x weight), with the default
weights market need 20, revenue 20, reachability 15, feasibility 15, differentiation 10, startup cost
10, risk 10. A candidate knocked out by most assessors cannot win. The judge must choose the top
candidate or one within 3 points of it.

## Step 6: the report

When `IC next` says the court has finished:

```bash
IC render
```

It writes `REPORT.md` into the run folder and prints it, in this order: executive summary,
interpretation of the request, the twelve ideas, the debate result and shortlist, the scoring table,
the winner, product concept, business model, technical plan, validation strategy, roadmap, risks and
open questions, and the three next actions. Show the user the report exactly as written. Then add at
most two lines of your own: the single first action you would start with, and the path to the full run.

Rules for you, the clerk:

- Never change, re-rank or re-calculate the scores, and never swap the winner.
- Never add praise, certainty or income promises the report does not contain. A score is a decision
  aid, not a forecast.
- If the user disagrees with the result, offer a new run with their corrections written into a new
  request file (for example a stated budget, skills or a direction to exclude). Do not argue for an
  idea yourself.
- To stress-test the winning idea afterwards, the user can put it on trial with `/court`.
