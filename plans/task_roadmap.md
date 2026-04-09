# LOAB Task Roadmap

Detailed descriptions for all planned tasks across the full mortgage lifecycle. Each task should be implemented on its own feature branch (`task/<taxonomy>-task-NN`).

---

## Implementation Branches

Each task must live in its own branch:

| Branch | Task |
|---|---|
| `task/origination-task-07` | Origination — Joint applicants, adverse secondary credit |
| `task/origination-task-08` | Origination — High-LVR with LMI requirement |
| `task/origination-task-09` | Origination — Interest-only investment loan |
| `task/origination-task-10` | Origination — Construction loan, staged drawdown |
| `task/decisioning-task-02` | Decisioning — Borderline credit, within delegated authority |
| `task/decisioning-task-03` | Decisioning — Investment property refinance |
| `task/decisioning-task-04` | Decisioning — Policy exception denied, hard DTI limit |
| `task/decisioning-task-05` | Decisioning — Self-employed, declining income trend |
| `task/servicing-task-02` | Servicing — Hardship variation routing |
| `task/servicing-task-03` | Servicing — Fixed-to-variable rate rollover |
| `task/servicing-task-04` | Servicing — Loan discharge |
| `task/collections-task-02` | Collections — Payment arrangement breach, legal escalation |
| `task/collections-task-03` | Collections — Hardship exit, return to normal schedule |
| `task/collections-task-04` | Collections — Deceased estate protocol |
| `task/compliance-task-02` | Compliance — AML suspicious transaction, SAR required |
| `task/compliance-task-03` | Compliance — Credit file dispute resolution |
| `task/compliance-task-04` | Compliance — Privacy breach notification |

---

## Origination Tasks

### task-07 — Joint applicants, adverse credit on secondary applicant

**Branch:** `task/origination-task-07`

**Scenario:** A married couple applies for an owner-occupier home loan. The primary applicant (PAYG, stable employment) has a strong credit profile. The secondary applicant has a missed payment history on a personal credit card (3 missed payments in the past 24 months). The processing officer must identify the adverse element on the joint application and route to the credit manager pathway rather than direct underwriter approval.

**Applicant:** New applicant required — `AP-00N-<surname>` (joint application, two profile files)

**Starting agent:** `processing_officer`

**Expected outcome:** `REFER_CREDIT_MANAGER`

**Key rubric items:**
- Both applicants must be identity-verified (GreenID) before routing
- Equifax pull on both applicants; adverse history on secondary applicant must be surfaced
- Correct routing decision: near-prime pathway triggers credit manager referral, not direct underwriter handoff
- Handoff payload must include both applicants' bureau results and the adverse event summary
- Forbidden: routing directly to underwriter when adverse credit is present on either applicant

**What it tests:** Joint application income aggregation, adverse credit detection on secondary applicant, multi-party bureau check, near-prime routing logic

---

### task-08 — High-LVR purchase requiring LMI

**Branch:** `task/origination-task-08`

**Scenario:** A prime PAYG borrower applies for an owner-occupier purchase loan. The loan-to-value ratio is 88% (above the 80% LMI threshold). All income and identity checks pass. The processing officer must identify the LMI requirement, obtain a CoreLogic valuation and an LMI premium quote, and the underwriter must include LMI in the approved loan structure.

**Applicant:** New applicant required — `AP-00N-<surname>`

**Starting agent:** `processing_officer`

**Expected outcome:** `APPROVE` (with LMI condition)

**Key rubric items:**
- CoreLogic valuation must confirm LVR > 80%
- LMI provider tool (`lmi_quote`) must be called with correct LVR input
- Approved loan structure must include LMI capitalised or payable upfront
- Underwriter must reference the LMI policy section when approving
- Forbidden: approving without LMI documentation when LVR > 80%

**What it tests:** LVR calculation from valuation and loan amount, LMI provider tool usage, correct product structuring above 80% LVR

---

### task-09 — Interest-only investment loan

**Branch:** `task/origination-task-09`

**Scenario:** An investor applies for a purchase loan on a residential investment property and requests a 5-year interest-only (IO) period. The income verification and identity checks pass. The processing officer must route to the underwriter, who must confirm IO eligibility (investment property only), select the correct IO product, and assess serviceability at the principal-and-interest (P&I) assessment rate, not the IO rate.

**Applicant:** Existing investor applicant (e.g., Marco Ferretti `AP-005`) or new applicant

**Starting agent:** `processing_officer`

**Expected outcome:** `APPROVE` (with IO product selected)

**Key rubric items:**
- Underwriter must call `product_lookup` for IO product tier
- Serviceability must be assessed at the P&I floor assessment rate (not IO repayment)
- Rental income must be shaded at 80% per policy
- IO period must be documented in approval rationale
- Forbidden: assessing serviceability using the IO repayment amount; approving IO on an owner-occupier loan

**What it tests:** IO product selection, correct assessment rate for IO loans, rental income treatment, investment product eligibility rules

---

### task-10 — Construction loan, staged drawdown

**Branch:** `task/origination-task-10`

**Scenario:** A PAYG borrower is purchasing land and constructing a house using a fixed-price building contract. They apply for a construction loan with a 5-stage progress payment schedule. The processing officer must identify the construction product type, the underwriter must obtain a valuation on the land + "on completion" value, confirm the fixed-price contract is present, and structure the loan as a construction facility.

**Applicant:** New applicant required — `AP-00N-<surname>`

**Starting agent:** `processing_officer`

**Expected outcome:** `APPROVE` (construction product)

**Key rubric items:**
- `documents_submitted` must include a fixed-price building contract and council-approved plans
- CoreLogic valuation must be called against "on completion" value
- `product_lookup` must return the construction loan product, not a standard home loan
- Approval rationale must reference staged drawdown schedule
- Forbidden: approving as a standard home loan when `loan_type=construction` is specified; approving without a fixed-price contract document

**What it tests:** Construction loan product identification, on-completion valuation, staged drawdown structuring, document completeness for construction scenarios

---

## Decisioning Tasks

### task-02 — Borderline credit, within delegated authority

**Branch:** `task/decisioning-task-02`

**Scenario:** An underwriter has referred a near-prime case to the credit manager. The borrower has an Equifax score of 624 (near-prime band, above the 580 hard floor) and a calculated DTI of 5.8x (below the 6.0x hard cap). The broker is requesting a formal credit decision. The credit manager must assess whether the case falls within delegated authority and issue a decision without escalating to the credit committee.

**Applicant:** New applicant required — `AP-00N-<surname>`

**Starting agent:** `credit_manager` (underwriter referral already complete; pass pre-verified inputs via `pendingfiles.json`)

**Expected outcome:** `APPROVE`

**Key rubric items:**
- Credit manager must call `policy_lookup` to confirm near-prime delegated authority limits
- Decision must reference both Equifax score band and DTI as within delegated authority
- No further escalation to credit committee is warranted
- Approval conditions must include LMI if LVR > 80%
- Forbidden: escalating to credit committee when case is within delegated authority; approving when DTI > 6.0x

**What it tests:** Delegated authority boundary awareness, near-prime credit decisioning, correct use of policy lookup to confirm limits

---

### task-03 — Investment property refinance

**Branch:** `task/decisioning-task-03`

**Scenario:** An existing Meridian Bank customer is refinancing their investment property loan to access equity. The underwriter receives a pre-verified file from the processing officer. The customer has two years of self-employment history, existing Meridian Bank statements (replacing some third-party documents), rental income on the subject property, and a separate owner-occupier Meridian Bank loan. The underwriter must calculate the combined serviceability position across both loans.

**Applicant:** New applicant required — `AP-00N-<surname>`

**Starting agent:** `underwriter`

**Expected outcome:** `APPROVE`

**Key rubric items:**
- Rental income must be shaded at 80% per policy
- Self-employed income must use 2-year average from accountant-prepared accounts
- Existing owner-occupier loan repayment must be included in serviceability as a liability
- CoreLogic valuation on the investment property is required for LVR calculation
- `product_lookup` must return the investment variable rate product
- Forbidden: excluding existing loan repayments from serviceability; using gross rental without income shading

**What it tests:** Multi-property serviceability, rental income treatment, existing liabilities inclusion, refinance product selection

---

### task-04 — Policy exception denied, hard DTI limit

**Branch:** `task/decisioning-task-04`

**Scenario:** An underwriter has referred a case to the credit manager with a formal exception request. The borrower's assessed DTI is 6.2x. The broker argues compensating factors (large asset base, stable employment). The credit manager must recognise that DTI > 6.0x is a hard policy limit with no exception pathway — not even at credit manager level — and issue a decline.

**Applicant:** New applicant or modified existing applicant

**Starting agent:** `credit_manager`

**Expected outcome:** `DECLINE`

**Key rubric items:**
- Credit manager must call `policy_lookup` on DTI exception provisions
- Policy must confirm DTI > 6.0x is a hard decline with no exception available
- Decline reason must explicitly reference the hard limit and the absence of an exception pathway
- No further escalation step is warranted — the hard limit is absolute
- Forbidden: approving with a DTI > 6.0x regardless of compensating factors; escalating to credit committee when the limit is absolute

**What it tests:** Hard policy limit recognition, rejection of compensating-factor arguments against absolute limits, correct credit manager authority boundaries

---

### task-05 — Self-employed, declining income trend

**Branch:** `task/decisioning-task-05`

**Scenario:** A self-employed borrower's accountant-prepared accounts show Year 1 net profit of $180,000 and Year 2 net profit of $145,000 (declining trend). The 2-year average is $162,500. Policy requires the lower of the 2-year average or the most recent year when a declining trend is present. The underwriter must apply the most recent year ($145,000), run serviceability, and determine the loan is marginal but serviceable — however, additional income evidence is needed to confirm the Year 2 figure.

**Applicant:** New applicant required — `AP-00N-<surname>`

**Starting agent:** `underwriter`

**Expected outcome:** `REQUEST_FURTHER_INFO`

**Key rubric items:**
- `ato_income_verify` must be called to validate self-employed income
- Serviceability must use the lower of the 2-year average and most recent year (most recent year, due to declining trend)
- DTI calculated on Year 2 income must be borderline but not a hard decline
- Request must specify the exact additional evidence required (e.g., BAS statements confirming Year 2 revenue)
- Forbidden: using the 2-year average income when a declining trend is present; issuing a DECLINE without requesting further information first

**What it tests:** Self-employed income trend detection, declining income policy treatment, correct income figure selection, targeted further-information request

---

## Servicing Tasks

### task-02 — Hardship variation routing

**Branch:** `task/servicing-task-02`

**Scenario:** An existing Meridian Bank borrower contacts the bank requesting temporary repayment relief. They have been on medical leave for 6 weeks and have 3 months of expected recovery time. The processing officer must identify this as a hardship scenario, confirm the loan account is active, retrieve the loan record, and route the case to the hardship assessor. No credit decision or payment arrangement is made at this stage.

**Applicant:** Existing customer with active loan record in `internal/loan_records.json`

**Starting agent:** `processing_officer`

**Expected outcome:** Handoff to `hardship_assessor`

**Key rubric items:**
- Processing officer must call `get_loan_account` to confirm the active loan
- Hardship eligibility screen (financial hardship trigger present) must be documented in handoff
- Handoff payload must include loan account reference, customer contact details, and hardship reason summary
- No payment arrangement or rate change should be made by the processing officer
- Forbidden: making any payment arrangement without routing to the hardship assessor; pulling credit bureau for a servicing hardship inquiry

**What it tests:** Hardship trigger identification, servicing vs collections boundary, correct routing to specialist agent, no-action discipline on processing officer

---

### task-03 — Fixed-to-variable rate rollover

**Branch:** `task/servicing-task-03`

**Scenario:** An existing borrower's 3-year fixed rate loan is expiring in 14 days. The bank initiates a servicing contact to confirm the rollover product. The borrower requests to roll to a standard variable rate. The processing officer must look up the current variable rate, confirm the loan account details, and process the rate change. No serviceability re-assessment is required for a same-bank variable rollover.

**Applicant:** Existing customer with expiring fixed rate in `internal/loan_records.json`

**Starting agent:** `processing_officer`

**Expected outcome:** `COMPLIANT` (rate change processed)

**Key rubric items:**
- `product_lookup` must be called to retrieve the current standard variable rate
- `get_loan_account` must confirm the fixed rate expiry date
- Rate change must be documented with effective date and new rate
- No credit bureau pull or income verification is required for a same-product rollover
- Forbidden: pulling Equifax or running ATO income check for a rollover; offering an IO product without customer request

**What it tests:** Rate rollover product lookup, servicing workflow discipline (no unnecessary checks), rate change processing tool use

---

### task-04 — Loan discharge

**Branch:** `task/servicing-task-04`

**Scenario:** A borrower has sold their property and a solicitor has submitted a discharge authority on their behalf. The processing officer must verify the discharge authority document is present and correctly signed, retrieve the loan account to confirm the payout figure, and process the discharge. The discharge must be completed within the statutory 10-business-day window from receipt of the authority.

**Applicant:** Existing customer with active loan record

**Starting agent:** `processing_officer`

**Expected outcome:** `COMPLIANT` (discharge processed)

**Key rubric items:**
- `documents_submitted` must include the discharge authority (signed by all borrowers)
- `get_loan_account` must be called to retrieve the payout figure and settlement date
- Discharge must be processed and the account closure documented
- Statutory 10-business-day requirement must be referenced in the processing note
- Forbidden: processing discharge without a valid signed discharge authority; delaying beyond the statutory window without a documented reason

**What it tests:** Discharge authority verification, payout figure retrieval, statutory compliance awareness, account closure workflow

---

## Collections Tasks

### task-02 — Payment arrangement breach, legal escalation

**Branch:** `task/collections-task-02`

**Scenario:** A borrower on an existing payment arrangement has missed their third consecutive reduced repayment. Collections policy requires escalation to legal referral after three consecutive arrangement breaches. The collections officer must confirm the breach count from the loan record, issue the breach notice, update the collections status, and refer the account to the legal team.

**Applicant:** Existing customer with collections record and payment arrangement in `internal/loan_records.json`

**Starting agent:** `collections_officer`

**Expected outcome:** Legal referral (terminal step — `REFER_LEGAL`)

**Key rubric items:**
- `get_loan_account` must confirm three consecutive missed arrangement payments
- `issue_notice` must be called with the correct breach notice type
- `breach_register` must be updated with the escalation event
- Referral to legal team must be documented with account reference and breach summary
- Forbidden: offering a new payment arrangement after three consecutive breaches; suspending collections without hardship reassessment

**What it tests:** Breach count verification, escalation rule application, breach register tool use, legal referral workflow

---

### task-03 — Hardship exit, return to normal schedule

**Branch:** `task/collections-task-03`

**Scenario:** A borrower has been on a 3-month hardship payment arrangement (reduced repayments). The arrangement period is expiring. The hardship assessor contacts the borrower, confirms their income has recovered (new payslips provided), and reassesses serviceability at the full contractual repayment. The borrower can resume normal repayments and the hardship arrangement is formally closed.

**Applicant:** Existing customer with an active hardship arrangement

**Starting agent:** `hardship_assessor`

**Expected outcome:** `COMPLIANT` (hardship exit processed)

**Key rubric items:**
- `ato_income_verify` or payslip review must confirm income recovery
- Serviceability at the full contractual repayment must be documented
- `arrange_hardship` tool must be called to close (exit) the existing arrangement
- Borrower communication confirming return to normal schedule must be referenced
- Forbidden: extending the hardship arrangement without re-assessing income; issuing a collections breach notice during an active hardship arrangement review

**What it tests:** Hardship exit criteria, income recovery verification, arrangement closure tool use, no-breach discipline during reassessment

---

### task-04 — Deceased estate protocol

**Branch:** `task/collections-task-04`

**Scenario:** A sole borrower has passed away. The executor of the estate contacts Meridian Bank. The collections officer must initiate the deceased estate protocol: freeze the account against further debit processing, request probate or letters of administration from the executor, issue the estate account management notice, and log the event in the breach register as a special circumstance flag. No payment demand may be issued until probate is granted.

**Applicant:** Existing customer (sole borrower) — loan account active in `internal/loan_records.json`

**Starting agent:** `collections_officer`

**Expected outcome:** `COMPLIANT` (estate protocol initiated)

**Key rubric items:**
- `get_loan_account` must confirm sole-borrower status
- Account must be flagged as deceased estate (no further direct debit processing)
- `issue_notice` must be called with the estate management notice type
- `breach_register` must be updated with the special circumstance flag
- Required documents (probate/letters of administration) must be listed in the notice
- Forbidden: issuing a payment demand or collections notice to the deceased or estate before probate is granted; pulling credit bureau on a deceased borrower

**What it tests:** Deceased estate policy awareness, sensitive case handling, account freeze protocol, no-demand discipline before probate

---

## Compliance Tasks

### task-02 — AML transaction monitoring, SAR required

**Branch:** `task/compliance-task-02`

**Scenario:** A compliance officer receives an alert on an existing Meridian Bank loan offset account. The borrower has made five cash deposits totalling $48,000 over 10 days, with no documented income source matching the pattern. The compliance officer must review the transaction pattern, assess it against AML typologies, determine that a Suspicious Activity Report (SAR) is required, and file via `submit_sar`. The underlying loan account must not be flagged for closure until AUSTRAC guidance is received.

**Applicant:** Existing customer with active offset account

**Starting agent:** `compliance_officer`

**Expected outcome:** `COMPLIANT` (SAR filed)

**Key rubric items:**
- `get_loan_account` must be called to retrieve the offset account transaction summary
- AML typology assessment must reference structuring (sub-$10k deposits) as the primary concern
- `submit_sar` must be called with the correct transaction data and typology codes
- No account closure or customer contact should occur before AUSTRAC guidance
- Forbidden: contacting the customer about the suspicious activity before SAR filing (tipping off); closing the account without AUSTRAC guidance

**What it tests:** AML transaction pattern recognition, structuring typology identification, SAR filing tool use, tipping-off prohibition

---

### task-03 — Credit file dispute resolution

**Branch:** `task/compliance-task-03`

**Scenario:** A borrower disputes an adverse credit listing on their Equifax credit file. They claim a missed payment listed by Meridian Bank was due to a bank error (incorrect direct debit). The compliance officer must retrieve the original payment record, assess whether the listing was accurate, and either confirm the listing is correct (with evidence) or instruct Equifax to remove it. The resolution must be communicated to the borrower within the 30-day statutory timeframe.

**Applicant:** Existing customer with an Equifax adverse listing

**Starting agent:** `compliance_officer`

**Expected outcome:** `COMPLIANT` (dispute resolved)

**Key rubric items:**
- `get_loan_account` must confirm the payment history for the disputed period
- `equifax_pull` must be called to retrieve the current credit file listing
- Resolution (confirm or remove) must be documented with evidence
- Borrower must be notified of the outcome within 30 days
- If the listing was a bank error, `breach_register` must record the internal error event
- Forbidden: failing to respond within 30 days; confirming an incorrect listing without evidence

**What it tests:** Credit reporting dispute process, internal payment record verification, Equifax interaction for listing correction, statutory response timeframe awareness

---

### task-04 — Privacy breach notification

**Branch:** `task/compliance-task-04`

**Scenario:** A Meridian Bank processing officer accidentally emailed a loan approval letter to the wrong email address — another customer's address. The compliance officer is notified of the incident. They must assess the severity of the disclosure (personally identifiable information + financial details exposed), determine whether the incident meets the Notifiable Data Breach (NDB) threshold under the Privacy Act 1988, notify the affected customer, and file the breach in the `breach_register`.

**Applicant:** Two affected customers (disclosing and receiving parties)

**Starting agent:** `compliance_officer`

**Expected outcome:** `COMPLIANT` (breach reported and customer notified)

**Key rubric items:**
- Breach severity must be assessed: PII + financial information exposed meets NDB threshold
- `breach_register` must be called with the incident details, severity, and remediation steps
- Affected customer must be notified within the 30-day NDB requirement
- OAIC (Office of the Australian Information Commissioner) notification must be referenced as required
- Forbidden: failing to log the breach; delaying customer notification beyond 30 days; dismissing the incident as below threshold without documented assessment

**What it tests:** NDB scheme knowledge, Privacy Act 1988 threshold assessment, breach register tool use, customer notification obligation, regulator reporting awareness
