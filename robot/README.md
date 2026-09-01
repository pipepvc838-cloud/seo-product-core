# Robot Module Boundary

Owner: CHAT-ROBOT-03.

This module contains only the bounded deterministic Product-M01 Robot contract/state-model artifacts authorized by ROBOT-IMPL-001. It does not implement a Robot runtime engine, queue, worker, SaaS orchestration, provider/API client, persistence/database layer, deployment, secrets, or production access.

## Contract surface

- `contracts/execution-model.v1.json` — deterministic task identity, dependency satisfaction, ordering, eligibility/state transitions, idempotency, bounded retry, duplicate prevention, fail-closed rules, recovery/resume, and Backend handoff compatibility.
- `tests/contracts/fixtures.v1.json` — fixed non-secret deterministic fixtures.
- `tests/contracts/validate_contracts.py` — deterministic validator for DAG/cycle rejection, ordering, transitions, retry, idempotency, recovery, and Backend handoff reference consistency.

Backend contract consumption is exclusively through `SRC-CONTRACT-PM01-BE-001`; this Robot module has no `backend/**` repository authority.

Any future executable Robot runtime requires a separate Manager-approved task and capability.
