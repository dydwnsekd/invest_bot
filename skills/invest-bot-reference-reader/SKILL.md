---
name: invest-bot-reference-reader
description: Use this skill when implementing invest_bot features by analyzing reference/open-trading-api first, especially for domestic stock authentication, market data, account queries, and order workflows.
---

# invest-bot-reference-reader

Use this skill when working on `invest_bot` features that depend on `reference/open-trading-api`.

## When to use

- 국내주식 API 연동 기능을 구현할 때
- 인증, 시세 조회, 잔고 조회, 주문 기능을 추가할 때
- reference 예제를 현재 프로젝트 구조에 맞게 재구성할 때
- 기능 구현 전에 어떤 reference 파일을 먼저 봐야 할지 정리할 때

## Read first

Always read these files before making changes:

- `C:/Users/user/PycharmProjects/invest_bot/agent.md`
- `C:/Users/user/PycharmProjects/invest_bot/README.md`
- `C:/Users/user/PycharmProjects/invest_bot/reference/open-trading-api/README.md`

Then inspect the relevant folders:

- `reference/open-trading-api/docs/`
- `reference/open-trading-api/examples_llm/`
- `reference/open-trading-api/examples_user/`
- `reference/open-trading-api/strategy_builder/`
- `reference/open-trading-api/backtester/`

## Workflow

1. Confirm the task stays within the current project scope: domestic stocks, Python 3.13, `pip`, `pytest`.
2. Find the smallest relevant example in `reference/open-trading-api`.
3. Extract the API behavior, required parameters, and response shape from the reference.
4. Rebuild the feature inside the project structure instead of copying the example verbatim.
5. Keep trading logic, strategy logic, and data collection logic separated.
6. Add at least one verification artifact such as a test, runnable script, or usage example.
7. Update `README.md` if the behavior, structure, or setup changed.

## Rules

- Prioritize domestic stock flows only.
- Treat `reference/` as source material, not production-ready project code.
- Use `reference/` heavily in the early build phase, but keep the project independently maintainable.
- Separate mock trading and live trading paths clearly.
- Do not hardcode secrets, account numbers, or tokens.
- Do not expand order execution logic without a validation path.
- Prefer reusable wrappers and modules over one-off scripts.
- Add dependencies based on current project needs, not by copying all reference dependencies.

## Expected outputs

For most implementation tasks, leave at least one of the following:

- `pytest` test
- executable script
- example usage
- source reference note in code comments or docs when helpful

## Read next if needed

- `./references/project-rules.md`
