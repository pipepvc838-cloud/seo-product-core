# Baseline Tests

This directory is a bootstrap test boundary only. It contains no Product-M01 implementation tests yet.

Baseline validation must prove:
- required bootstrap governance files exist;
- `backend/` and `robot/` boundaries both exist and remain distinct;
- no prohibited feature/source scaffolding is present;
- no committed secrets or credentials are introduced;
- change-control and rollback documentation remain present;
- shared repository usage does not collapse module ownership.

Future Backend and Robot implementation tests must remain independently attributable and require later Manager-approved authority.
