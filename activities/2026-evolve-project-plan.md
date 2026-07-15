# Brittamat: AI-assisted yearly planning workflow + structured allergy list + a real safety fix

## Context

Brittamat generates a shopping list for a week of communal cooking aboard a boat, for ~36 people, run once a year for 25+ years. The existing process already works and is not naive:

- `data.py`'s `dishes`, `ingredient_types`, `menu`, `prebought`, `buy_later` are hand-edited each year.
- Variant counts on `MenuItem`s (e.g. `"glutenfri": 3`) are **not** guessed — they come from a deliberate manual process: look at the allergy list, look at the recipe bank, decide which variant(s) each dish needs and how many portions, and occasionally swap a whole dish.
- Mistakes are caught at "compile time": running `main.py` raises on undefined ingredients/missing variants (`alg.find_undefined_ingredients`, the `KeyError`/`ValueError` paths in `alg.py`).

The actual pain point is that this edit → run → fix loop is *tedious*, not that it's unsafe by design. The user wants AI leveraged as a **decision-support conversation** for the three real steps of yearly planning, not a rewrite of the data model:

1. Given an updated allergy list, propose an iteration of the week's menu (dish selection + which variants each dish needs).
2. Validate a draft menu against the allergy list — ask questions on ambiguous cases, propose which variant(s)/counts to set per dish.
3. Given a markdown list of items already bought (bulk pre-buy, or held back for mid-week freshness/availability), update `data.py` and (re)run the pipeline, iterating on any errors until clean.

Two independent, real risks were called out explicitly and must be handled by deterministic Python, not left to LLM judgment:
- **Allergic reactions**: nothing today cross-checks the allergy list against dish variants — that list currently only exists in `docs/Meny 2026.xlsx`, disconnected from `data.py`.
- **Forgetting to buy something** (e.g. the protein for 36 people): reading `alg.py`'s `subtract_from_shopping_list` (lines ~116–132), if `prebought`/`buy_later` contains a quantity larger than what's needed (unit mistake, typo, double-entry), the ingredient's quantity goes to zero or negative and the entry is **silently dropped** from the shopping list — no warning distinguishes "correctly used it all up" from "a data-entry mistake means we won't buy any." This is a latent bug worth fixing regardless of the AI workflow.

## What this plan does NOT do

No migration of `dishes`/`ingredient_types`/`menu`/`prebought`/`buy_later` to YAML. That data model works, is validated by Python running it, and rewriting it was explicitly not the ask — the friction is in the planning conversation around it, not the file format.

## Phase 0 — Persist the plan and reference docs into the repo

- Copy this plan file into the repo (e.g. `docs/planning/2026-evolve-plan.md`) so it's available on any machine, not just this one's local `~/.claude/plans/`.
- `git add` and commit `docs/` (`Meny 2026.xlsx`, `Aktuella Recept.doc.docx`, `Tips för kockar.docx`) — currently untracked and not gitignored — plus the copied plan file, so all reference material travels with the repo.

## Phase 1 — Structured, dual-purpose allergy list

- Add `data/people.md`: a markdown table — name, the existing boolean-ish flags (veg, laktos, nötter, gluten, ägg, skaldjur, äter fisk), free-text notes, and which day(s)/meals they attend. This replaces `docs/Meny 2026.xlsx`'s "kryss-lista" as the source of truth.
- This one file serves two purposes: it's what gets pasted into/read by the AI prompts below, **and** it's the printable A4 reference for the on-duty "allergiansvarig" (allergy-responsible cook) mentioned in `docs/Tips för kockar.docx` — a markdown table prints legibly as-is, no separate export step needed.
- Add a small `Person` dataclass to `classes.py` and a `load_people()` parser in a new `validate.py` (simple markdown-table parsing, no new dependency).

## Phase 2 — Deterministic coverage report (`validate.py`)

- `coverage_report(menu, dishes, people) -> list[CoverageIssue]`: for each `MenuItem`, for each attending `Person`, check whether their structured flags (gluten/lactose/nut/egg/shellfish/veg*) are covered by an existing variant on that dish with a high-enough declared count. Two kinds of issues, both surfaced, never auto-resolved:
  - *Count too low*: variant exists but declared count < attendees needing it.
  - *No variant at all*: a required flag has no corresponding variant key on the dish (the dangerous case — e.g. today's nut-allergy handling is prose-only in the recipe doc, never a formal variant).
- Free-text `notes` (e.g. "Svårt för jättestark mat", "Baljväxter/hon pratar med er") are never auto-interpreted — they're listed per affected day/dish as an explicit manual-review item, matching how the crew already appoints a human allergiansvarig.
- This function is plain, testable Python. It does the arithmetic; the AI conversation (Phase 4) does the judgment calls on top of its output.

## Phase 3 — Fix the silent over-subtraction bug

- In `alg.py`'s `subtract_from_shopping_list`: when the result would be `<= 0`, or the subtracted quantity exceeds the pre-subtraction quantity by more than a small margin, emit an explicit warning (print, or a returned list of `SubtractionWarning`s that `main.py` prints) naming the ingredient and both quantities, instead of silently dropping the row. A correct "used it all up" case and a "typo means we won't buy the protein" case must never look the same in the output.

## Phase 4 — Three portable AI prompt templates (the actual workflow)

Under `docs/prompts/`, one file per step, each referencing `data/people.md`, `docs/Aktuella Recept.doc.docx`, and `data.py` directly so they work from any CLI (Claude Code, plain `claude`, ChatGPT/Codex CLI):

- `propose-menu.md` — input: updated `data/people.md` + the recipe bank + current `data.py` dishes. Output: a proposed day-by-day dish selection and, per dish, which variants are needed and roughly what counts — as a reviewable diff, never applied automatically. Instructed to flag any allergy that no existing or newly-defined variant can safely cover, and to prefer swapping a dish over stretching a variant thin (matching the user's own stated fallback).
- `validate-menu.md` — input: a draft `menu` in `data.py` + `data/people.md`. Instructed to run/reason from `validate.py`'s `coverage_report()` output, ask the user clarifying questions on anything ambiguous (especially free-text notes), and propose the exact variant-count edits to make — again as a diff for human review, not an auto-edit.
- `update-shopping.md` — input: a markdown list of already-bought items (bulk pre-buy or mid-week deferred). Instructed to update `prebought`/`buy_later` in `data.py`, run `uv run python main.py`, read Phase 3's new warnings and any exceptions, and iterate until clean, then summarize the diff for review before commit.

Add thin Claude Code project slash-commands in `.claude/commands/` (`menu-plan.md`, `menu-validate.md`, `shopping-update.md`) that just point at the corresponding `docs/prompts/*.md` file, so the workflow is one command away when working in Claude Code specifically, while the prompt files themselves stay usable from any AI CLI.

## Files touched

- New: `data/people.md`, `validate.py`, `docs/prompts/{propose-menu,validate-menu,update-shopping}.md`, `.claude/commands/{menu-plan,menu-validate,shopping-update}.md`.
- Modified: `classes.py` (add `Person`), `alg.py` (`subtract_from_shopping_list` warnings), `main.py` (print coverage report + subtraction warnings before writing HTML), `README.md` (document the yearly workflow).
- Unchanged: `dishes`/`ingredient_types`/`menu`/`prebought`/`buy_later` in `data.py`, `html5.py`, `wrapped_unit_registry.py`.

## Verification

- `uv run python main.py` still runs end-to-end; output HTML unchanged for the current menu (Phase 3's warnings should be silent/empty on today's data unless it actually finds a real over-subtraction).
- `uv run mypy .` passes.
- Manually run `coverage_report()` against the real `docs/Meny 2026.xlsx` allergy data (transcribed once into `data/people.md`) for the current year's menu and sanity-check the issues it raises against what the user already knows to be true.
- Dry-run each of the three prompts once (propose-menu, validate-menu, update-shopping) against real data and confirm each asks sensible clarifying questions rather than silently guessing on ambiguous allergy notes.
