# AM SEO

This entire repository is the Angry Miao SEO/GEO project. Continue the current chat's work here.

## Objective
- Use agents to execute and verify SEO/GEO tasks for Chinese and English markets.
- Finish available tasks, write concrete outputs and continue independent work when a dependency is missing.
- Do not replace execution with a list of tasks for a developer, editor or operator.

## Project map
- `src/am_seo/`: the local CLI and project integration code.
- `config/upstreams.lock.json`: official upstream URLs, exact commits and licenses.
- `vendor/`: ignored upstream Git checkouts; do not silently edit their code or run install hooks.
- `scripts/`: reproducible setup and integration commands.
- `tests/`: meaningful offline tests; synthetic fixtures stay in temporary directories.
- `outputs/`: user-facing deliverables, evidence, task graph and execution kit.
- `work/`: ignored research material and scratch work.

## Execute
- Read `outputs/agent-kit/RUN-AGENT.md` and `outputs/agent-kit/tasks.json` before continuing task execution.
- The human-facing entry is the local browser console; keep its workflow usable without CLI or JSON editing.
- Check recorded console requests and feedback under `outputs/runtime/console/` when continuing work; a recorded request is not an executed optimization or new access authority.
- Start with `./am-seo status`, `./am-seo doctor`, and `./am-seo deps verify`.
- Run `python3 -m unittest discover -s tests -v` and `./am-seo run --offline` after integration changes.
- For actual source-site edits, inspect the connected site's real repository and serving configuration first.
- A public HTML edit is not a website-source patch or a Shopify mutation.
- Preserve exact evidence and rollback information; validate before marking tasks completed.

## Product facts and measurement
- Every numerical/product/policy claim requires a matching model, version, market and source.
- Quarantine conflicting fields; omit unsupported optional claims and continue supported content.
- Never choose the AM Infinity .97 wired weight of 37g/39g by model confidence.
- Brand source claims are not independently measured hardware performance.
- Never invent search volume, traffic, citations, benchmarks, delivery dates or future revenue.
- Keep consumer UI, API answers and search-only retrieval measurements separate.
- No-AI-answer tests count as zero in the completed-test denominator; errors are reported separately.
- Source timestamps and new execution timestamps must remain distinct.

## Connections and external effects
- Keep secrets, cookies and full customer/transaction data out of the repository and outputs.
- No live provider calls, account changes, production writes or outbound messages without the relevant access and authorized scope.
- Existing authorization persists: execute within it without repeated routine confirmation.
- Missing connections block only the dependent action; do not claim the organization lacks the account.
- Preserve earlier deliverables and use `outputs/` for new deliverables.
