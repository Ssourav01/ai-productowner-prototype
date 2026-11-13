# AI Prototype for Product Owners

Thesis project: literature analysis of AI-based requirements engineering and development of an AI prototype that supports selected work packages of product owners (POs). Practice partner: ONE Business & Technology GmbH, Berlin.

## Goal

1. Analyze the literature on AI-based requirements engineering and map **which type of AI** (generative, agentic, classical ML/NLP, ...) can support **which step** of the PO process.
2. Use interview results from ONE to prioritize PO work packages (value, effort, obligatory tasks).
3. Build a prototype for the selected work package(s).
4. Demo it to ONE practitioners and evaluate it.

## Candidate idea (hypothesis, to be validated)

Change impact analysis: when a business requirement changes, identify affected tickets, their dependencies and software components. This is only built if the literature review and interviews support it as a high-value work package.

## Module

| Name | Focus (initial) |
|------|-----------------|
| _M 1_ | Create demo JIRA backlog |
| _M 2_ | Read-only integration + baseline |
| _M 3_ | AI Analysis + validation |

Everyone contributes to all parts. Focus areas are only for ownership of tasks.

## Repository structure

```
docs/          meeting notes, slides, research questions
literature/    reading list, search log, screening sheets, mapping matrix
prototype/     code (created once the work package is chosen)
evaluation/    test scenarios, results, questionnaires
data/          LOCAL ONLY, never committed (see .gitignore)
```

## Working agreements

- `main` is always stable. Work on short-lived branches (e.g. `lit-matrix`, `ui-prototype`) and merge through pull requests with one review.
- Tasks live in GitHub Issues and the Projects board.
- **Never commit** interview transcripts, ONE data, API keys or personal data. Use `data/` locally and `.env` for secrets.
- Meeting notes go in `docs/meetings/YYYY-MM-DD.md`.

## Status

- [ ] First meeting with professor
- [ ] 1st Module development
- [ ] 
- [ ] 
- [ ] 
- [ ] 
- [ ] 

