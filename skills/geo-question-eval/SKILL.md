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

## Website optimization and scan know-how

When using questions to plan SEO/GEO content or evaluate website changes, apply the project's [readability method](../../docs/agent-readable-method.md) and versioned [source-backed policy](../../config/geo-knowhow.json). These are planning guidance; do not pass them or the target brand into independent answering calls.

- Prioritize directly readable HTML facts with matching model/version/market/source, chart data expressed in text, and concise answers to real questions. FAQ presence or schema syntax does not establish answer quality. Do not presuppose unverified R6 components in generated questions.
- Group semantically overlapping questions before creating pages. Distinct selection, alternatives and how-to needs deserve useful content; a generated question does not require its own thin page.
- Markdown and llms.txt are optional Agent affordances, not universal ranking requirements. Generate from one content source and compare actual facts with HTML. Google Search does not use these files to boost visibility; other agents' usage requires evidence.
- Run the Todo readability verification to preserve actual response evidence. Treat extracted text, FAQ headings and numeric differences as diagnostic signals; retain manual/agent factual and relevance review separately. Missing optional files must not lower a GEO score.
- Evaluate public website changes with authorized web-enabled sampling, fixed questions and actual final-answer citation URLs. Keep no-search API brand presence, citation, recommendation fit, factual accuracy, bot requests and human referral visits separate. Resend's observational developer-tool results are not causal evidence for consumer hardware recommendation gains.

Credentials belong in the project-specific OS credential store or server process memory, never prompts, outputs, logs, browser storage or API state. Only send a key to the provider explicitly identified by the user. Stop on authentication/billing failure rather than repeatedly spending or switching providers. No unattended recurring calls.
