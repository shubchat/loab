# Origination Single-Applicant Suite (Initial Batch)

## Goal
Create an initial origination-focused benchmark suite using single-applicant files only, with dynamic orchestration (decision-contract routing) and rubric-based scoring.

## Implemented Tasks
- `task-01-origination` (existing): clean PAYG prime approval (PO -> UW -> APPROVE)
- `task-06-origination-missing-docs-rfi`: PO-only missing mandatory docs -> `REQUEST_FURTHER_INFO`
- `task-07-origination-payg-near-prime-hard-decline`: PAYG near-prime + DTI > 6.0x -> PO -> CM -> `DECLINE`
- `task-08-origination-payg-subprime-hard-decline`: PAYG sub-prime (<580) -> PO -> CM -> `DECLINE`
- `task-09-origination-self-employed-dti-hard-decline`: self-employed DTI hard decline (cloned from task-02 scenario under origination naming)
- `task-10-origination-fraud-thinfile-halt`: DVS mismatch + thin file fraud hold (cloned from task-05 scenario under origination naming)

## New Customer Profiles
- `AP-006` PAYG owner-occupier with missing mandatory document (privacy consent omitted)
- `AP-007` PAYG near-prime with high DTI
- `AP-008` PAYG sub-prime hard decline case

## Mock API Data Added
Providers updated to support AP-006/AP-007/AP-008:
- `greenid`
- `equifax`
- `ato`
- `asic` (employer ABNs for PAYG accidental-call resilience)
- `corelogic`

## Notes / Next Steps
- Add remaining origination single-applicant cases (e.g. self-employed strong approve, thin-file clean manual assessment).
- Add co-borrower support in runner (`pendingfiles.applicants` all profiles) before co-borrower origination tasks.
- Run and tune rubrics for tasks 06-10 using current model(s).
