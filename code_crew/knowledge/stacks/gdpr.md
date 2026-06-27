---
name: Compliance-GDPR
description: GDPR controls checklist — lawful basis, data subject rights, privacy by design, retention, breach notification for code and infrastructure review
metadata:
  type: compliance
  framework: GDPR
  jurisdiction: EU / EEA (and adequacy countries)
  activate: explicitly — set in CODE_CREW_STACKS or stacks: in .code-crew/config.yaml
---

# Compliance: GDPR

GDPR applies to any system that processes **personal data** of individuals in the EU/EEA, regardless of where the system is hosted. Personal data is any information that identifies or can identify a natural person: name, email, IP address, cookie ID, location data, health data, financial data, device identifiers.

**Special category data** (health, biometric, racial/ethnic origin, religion, political opinion, sexual orientation, criminal records) requires explicit consent and higher protection controls.

Add `gdpr` to `stacks:` for any project that processes EU/EEA personal data.

---

## Personal Data Inventory

Before reviewing, identify:
- What personal data does this feature create, read, update, or delete?
- Is any special category data involved?
- What is the lawful basis for processing? (consent / contract / legal obligation / vital interests / public task / legitimate interests)
- Is personal data transferred outside the EU/EEA? If so, to which country and under what transfer mechanism (adequacy decision / SCCs / BCRs)?

State: **PD IN SCOPE** (list data types + lawful basis) or **NO PD IN SCOPE**.

---

## Article 5 — Data Processing Principles

- [ ] **Lawfulness, fairness, transparency**: data collected only for stated purpose; user informed at point of collection
- [ ] **Purpose limitation**: data used only for the purpose for which it was collected; no secondary use without consent
- [ ] **Data minimisation**: feature collects only the minimum data required — no opportunistic collection
- [ ] **Accuracy**: mechanism exists to correct inaccurate personal data if required by the use case
- [ ] **Storage limitation**: retention period defined; data deleted or anonymised after retention window
- [ ] **Integrity and confidentiality**: personal data encrypted in transit and at rest; access controlled

## Article 17 — Right to Erasure ("Right to be Forgotten")

- [ ] Feature does not create new personal data stores without a deletion path
- [ ] If feature creates a new store: a documented deletion procedure exists (ideally automated via soft-delete + purge job)
- [ ] Deletion cascades to all related stores (caches, backups, search indexes, analytics)
- [ ] Anonymisation used where deletion is not possible (e.g. aggregate analytics)

## Article 20 — Right to Data Portability

- [ ] If feature stores personal data provided by the user, a machine-readable export path exists (JSON or CSV)
- [ ] Export does not require manual intervention (automation required at scale)

## Article 25 — Privacy by Design and Default

- [ ] Personal data not collected or retained by default unless the user explicitly opts in
- [ ] Most privacy-protective option is the default (no pre-ticked consent boxes)
- [ ] New data flows documented in the data processing registry (or flagged for DPO update)
- [ ] Data shared with sub-processors only under GDPR-compliant data processing agreements

## Article 32 — Security of Processing

- [ ] Personal data encrypted at rest (column-level or storage-layer)
- [ ] Personal data encrypted in transit (TLS 1.2+)
- [ ] Access to personal data logged (who accessed what, when)
- [ ] Pseudonymisation applied where direct identification is not required (e.g. analytics)
- [ ] No personal data in error messages, logs, or debug output
- [ ] No personal data in URL query strings (use POST body or headers)

## Article 33/34 — Breach Notification

- [ ] Data flows are documented sufficiently to support 72-hour breach notification (GDPR Art. 33)
- [ ] Access logs support "which records did this user/system access between T1 and T2" queries
- [ ] Incident response process covers personal data breaches

## Cross-Border Transfers (Chapter V)

- [ ] No personal data transferred to a non-adequate country without SCCs or BCRs in place
- [ ] Cloud provider regions checked: personal data only in EU/EEA regions or adequate-country regions
- [ ] Third-party SDKs that transmit personal data (analytics, crash reporting) are whitelisted and covered by DPA

## Consent (Article 7, if lawful basis is consent)

- [ ] Consent is specific, informed, freely given, and unambiguous (no bundled consent)
- [ ] Consent can be withdrawn as easily as it was given
- [ ] Consent records are timestamped and auditable
- [ ] Feature does not use consent as the lawful basis where another basis (contract, legitimate interest) is more appropriate

---

## Common Violations (flag as HIGH or CRITICAL)

- Personal data stored in logs (even temporarily)
- No retention policy on a new personal data store
- No deletion path for personal data created by the feature
- Personal data transferred to a third-party service without a DPA
- Personal data sent to a non-EU region without adequacy or SCCs
- Pre-ticked consent checkbox
- Feature collects more data than needed for its stated purpose

---

## Review Output Format

```
GDPR REVIEW
Personal data in scope: [list types / NO PD IN SCOPE]
Lawful basis: [consent / contract / legitimate interest / etc.]
Special category data: [YES — list / NO]
Cross-border transfers: [YES — list countries + mechanism / NO]

Art. 5 Principles:        PASS / FAIL — [detail]
Art. 17 Erasure:          PASS / FAIL / N/A
Art. 25 Privacy by Design: PASS / FAIL — [detail]
Art. 32 Security:         PASS / FAIL — [detail]
Cross-border transfers:   PASS / FAIL / N/A

GDPR: COMPLIANT or NON-COMPLIANT — [list of blocking findings]
```
