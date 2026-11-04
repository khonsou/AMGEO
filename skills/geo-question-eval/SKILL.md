---
name: geo-question-eval
description: Generate consumer questions for a product across discovery, alternatives, how-to and factual intents; run isolated API answers and evaluate Angry Miao brand or product presence. Use for this project's question-testing workflow, not for claiming consumer UI rankings or factual accuracy.
---

# Product questions and brand presence

Use the product description and four intents to build a small bilingual panel. The implementation and run evidence live in `src/am_seo/question_lab.py` and `outputs/runtime/console/question-lab/`.

1. Generate consumer questions covering find/select, alternatives, how-to, and facts, in Chinese and English. Keep each question specific to a plausible need, not a string of SEO keywords. State that generated questions are hypotheses, not measured search volume.
2. Identify brand-seeded questions before testing. A question naming Angry Miao, 怒喵, AM Infinity Mouse or CYBERBOARD is a branded question; report it separately from neutral discovery. Do not increase discovery scores by embedding brand names in questions.
3. Freeze the exact question panel and fingerprint before sampling. Reuse the frozen panel for a retest; creating a new panel cannot prove a score improvement.
4. Answer every question in a separate stateless API request. Do not provide the product description, brand context, generated panel history, score or target brand to the answering call. A basic chat completion has no verified web retrieval; label it API/no-search and preserve that scope.
5. Match brand and known product aliases in the actual answer. Preserve exact matching text, raw answer, model, mode, time, errors and available usage. No-answer counts zero among completed tests; provider/network errors and unattempted questions are separate.
6. Report each language and neutral/branded group independently. Local presence matching measures mention, not endorsement, answer accuracy, verified citations or consumer-interface visibility. Keep earlier Agent/web-search observations separate.
7. Use misses to create or update concrete content tasks. Never treat a generated draft, a manual checkbox, or a passed JSON parser as proof of publication or brand lift.

Credentials belong in the project-specific OS credential store or server process memory, never prompts, outputs, logs, browser storage or API state. Only send a key to the provider explicitly identified by the user. Stop on authentication/billing failure rather than repeatedly spending or switching providers. No unattended recurring calls.
