# Pilot guide: testing Blueprint School with real learners

Five people, one 30-minute session each, finds most usability problems. Pick a mix: two beginners, two with some
experience, one experienced engineer.

## Before you start
1. Run the app (`docker compose up`) and share the link (`ngrok http 8000`).
2. Ask each tester to create an account. Notes they send are linked to it.
3. Tell them: *"We are testing the product, not you. If something confuses you, that is the product's fault. Please think out loud."*

## Tasks (read them out one at a time, then stay quiet and watch)
| # | Task | What you are checking |
|---|------|----------------------|
| 1 | "Find where you would start learning." | Is **Start here** obvious? |
| 2 | "Open the Load balancer lesson and complete the lab." | Can they act in the lab without help? |
| 3 | "In your own words, what did the lab teach you?" | Did they understand it, or just click? |
| 4 | "Try the Cache lesson, then explain why the hit rate changed." | Transfer to a second concept |
| 5 | "Open Challenge and try one scenario." | Is an unknown problem too hard or unclear? |
| 6 | "Open Mastery. What does it tell you?" | Is the score understood? |

Do not hint. Note where they hesitate, re-read, or say "hm". Ask afterwards: *"What was the most confusing moment?"*

## What the tester does while using it
The **Feedback** button (bottom right of every page) records which page they were on. Ask them to press it
whenever something is unclear, broken, or good.

## Reading the results
```bash
cd backend && python -m tools.pilot_report
```
It lists pages by share of "not clear" answers, plus every bug, confusing note and idea.

## Success measures for round one
- At least 4 of 5 testers finish tasks 1 and 2 without help.
- At least 4 of 5 can explain a lab result in their own words (task 3).
- No page where most feedback is "not clear".

Fix the top three problems, then run a second round with new testers before building anything big.
