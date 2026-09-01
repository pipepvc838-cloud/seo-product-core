# Product-M01 Core Repository Governance

Authority order: Project Constitution/Governance → repository instructions → architecture/policy → ADRs → contracts → Manager-approved task row → approved sources → evidence.

## Repository responsibility
This is a shared Product-M01 implementation repository with two explicit module ownership boundaries only:
- `backend/` — Backend implementation owned by CHAT-BE-04 and constrained by BE-001 plus SEC-001/SEC-002.
- `robot/` — deterministic Robot implementation owned by CHAT-ROBOT-03 and constrained by ROBOT-001 plus accepted Backend contracts.

Shared repository ownership does not merge module ownership, test, deploy, rollback, or change-control authority.

## External responsibility split
`seo-intelligence` retains Intelligence responsibility. `seo-operations` retains Operations/provider governance responsibility. This repository must not redefine or absorb either authority.

## Authority
All implementation or mutation requires an explicit Manager-approved task and task-scoped capability. Repository access does not imply provider/API, secret, database, deployment, or production authority.

## Security
No credentials or secret values may be committed. Provider/API access is deny-by-default and requires separate explicit authority. SEC-001/SEC-002 boundaries remain controlling inputs.

## Bootstrap restriction
BOOT-REPO-002 authorizes governance/bootstrap artifacts only. No Product-M01 feature implementation, application source code, runtime framework, dependencies, services, API endpoints, Robot engine, database/schema artifacts, or deployment configuration are authorized.
