# Architecture Boundaries

## Repository topology
This repository is shared only to reduce repository-management cost. Module ownership remains strict:
- `backend/` → CHAT-BE-04, governed by BE-001 and SEC-001/SEC-002.
- `robot/` → CHAT-ROBOT-03, governed by ROBOT-001 and accepted Backend contracts.

## Boundary rules
Backend must not absorb Robot state-machine/execution ownership. Robot must not invent or own Backend interfaces beyond BE-001-validated assumptions. Neither module owns WordPress plugin lifecycle, Intelligence authority, or Operations/provider governance.

## Deployment boundary
Backend and Robot are independently deployable units even though they share a repository. Repository bootstrap does not authorize deployment.

## Test/CI boundary
Baseline CI may validate shared governance and boundary integrity. Future implementation tests must remain module-scoped, with Backend and Robot test gates independently attributable.

## Rollback boundary
Backend and Robot changes must be independently revertible by commit/change scope. Shared repository history must not require coupled rollback unless a later accepted task explicitly proves a coupled contract.
