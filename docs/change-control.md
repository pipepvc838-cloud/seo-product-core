# Change Control and Rollback

- `main` is the canonical branch.
- BOOT-REPO-002 does not authorize Product-M01 implementation or production deployment.
- Any later implementation change requires a Manager-approved task, explicit module scope, accepted dependencies, approved SourceRefs/CapabilityRefs, tests, and evidence.
- Backend and Robot changes must remain separately attributable in review, tests, deployment decisions, and rollback.
- Until narrower implementation contracts exist, rollback is commit/revert based to the last accepted repository state; module-specific changes should be reverted without forcing unrelated module rollback.
- Provider/API, secret, database/schema, deployment, and GitHub settings/protection changes require separate explicit authority.
- Cross-module coupling, unrelated refactors, and authority expansion are prohibited unless explicitly accepted later.
