# Phase 2: Data Contracts and Shared Helpers - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 02-data-contracts-and-shared-helpers
**Areas discussed:** Contract format, Helper extraction scope, Contract enforcement

---

## Contract Format

| Option | Description | Selected |
|--------|-------------|----------|
| TypedDict (Recommended) | Python stdlib TypedDict classes at top of fetcher section. Greppable, IDE-friendly, Claude can read cold. | ✓ |
| Docstring spec | Structured docstring listing keys, types, required/optional. Less formal, zero import overhead. | |
| Separate markdown doc | data_contracts.md in repo. Readable but risks going stale. | |

**User's choice:** TypedDict (Recommended)
**Notes:** Previewed the TypedDict class structure with `ClientData` and `CampaignData`. User confirmed.

---

## Helper Extraction Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Extract the obvious (Recommended) | Extract rate_calc and return-struct builder. Leave 7-day averages and campaign iteration platform-specific. | ✓ |
| Extract everything possible | Also unify 7-day average and campaign iteration into shared helpers. More DRY but adds abstraction. | |
| Minimal — document only | Don't extract helpers. Just add TypedDict contracts and docstrings. | |

**User's choice:** Extract the obvious (Recommended)
**Notes:** Previewed `_calc_rates()` and `_build_client_data()` signatures. User confirmed pragmatic approach.

---

## Contract Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Documentation only (Recommended) | TypedDict is the spec. Tests verify shape. No runtime checks in production. | ✓ |
| Debug-mode validation | Optional --strict flag validates in dev/test only. Zero prod overhead. | |
| Always validate | Assert required keys after every fetch in production. Defensive but adds overhead. | |

**User's choice:** Documentation only (Recommended)
**Notes:** Previewed test pattern using `ClientData.__required_keys__`. User confirmed tests-only approach.

---

## Claude's Discretion

- Exact TypedDict field structure (Required/NotRequired pattern)
- Helper placement within server.py sections
- `_build_client_data` signature design
- Test fixture design for contract verification tests

## Deferred Ideas

None — discussion stayed within phase scope
