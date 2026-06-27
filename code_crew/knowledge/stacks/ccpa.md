---
name: Compliance-CCPA
description: CCPA/CPRA controls checklist — consumer rights, sale/sharing opt-out, sensitive personal information, and privacy notice requirements
metadata:
  type: compliance
  framework: CCPA
  version: CCPA 2018 + CPRA 2023 amendments
  jurisdiction: California (US)
  activate: explicitly — set in CODE_CREW_STACKS or stacks: in .code-crew/config.yaml
---

# Compliance: CCPA / CPRA

CCPA (California Consumer Privacy Act) as amended by CPRA (California Privacy Rights Act) applies to for-profit businesses that:
- Have annual gross revenue over $25M, OR
- Buy, sell, or share personal information of 100,000+ consumers/households per year, OR
- Derive 50%+ of revenue from selling/sharing personal information

**Personal information** under CCPA is broadly defined: identifiers (name, email, IP, cookie ID), commercial records, internet activity, geolocation, biometric, employment, education, inferences drawn from any of the above.

**Sensitive personal information (SPI)** includes: SSN, financial account credentials, precise geolocation, racial/ethnic origin, religious beliefs, health/medical data, sex life, sexual orientation, genetic data, and private communications.

Add `ccpa` to `stacks:` for any project serving California consumers that meets the above thresholds.

---

## Personal Information Inventory

Identify:
- What personal information does this feature collect, use, disclose, sell, or share?
- Is any **sensitive personal information (SPI)** involved?
- With which categories of third parties is PI disclosed?
- Is PI "sold" or "shared" as defined by CCPA? (Sale = exchange for money; Share = for cross-context behavioral advertising)

State: **PI IN SCOPE** (list categories) or **NO PI IN SCOPE**.

---

## Consumer Rights

### Right to Know (§1798.100)
- [ ] Privacy notice accurately describes all categories of PI collected and their purposes
- [ ] If a consumer requests disclosure of PI collected in the past 12 months, the system can fulfill it
- [ ] Disclosure includes: categories of PI, sources, business/commercial purposes, and categories of third parties with whom PI is shared

### Right to Delete (§1798.105)
- [ ] Feature does not create new PI stores without a deletion path
- [ ] Deletion request can be fulfilled within 45 days (automation preferred)
- [ ] Deletion cascades to service providers who received the PI (documented in vendor list)
- [ ] Exceptions documented where deletion is not required (e.g. completing a transaction, security, legal obligation)

### Right to Correct (§1798.106, CPRA)
- [ ] Consumer can request correction of inaccurate PI; correction mechanism exists or is explicitly out of scope

### Right to Opt-Out of Sale/Sharing (§1798.120)
- [ ] If PI is sold or shared, a "Do Not Sell or Share My Personal Information" mechanism exists
- [ ] Opt-out signals (Global Privacy Control) are honored if the feature affects web consumers
- [ ] Opt-out is effective within 15 business days

### Right to Limit Use of SPI (§1798.121, CPRA)
- [ ] If SPI is processed beyond what is necessary for the disclosed purpose, a "Limit the Use of My Sensitive Personal Information" mechanism exists
- [ ] SPI used only for permitted purposes (providing the service, preventing fraud, safety) unless consumer consents to additional use

### Right to Non-Discrimination (§1798.125)
- [ ] No price differential, service degradation, or denial of service for exercising CCPA rights
- [ ] Financial incentive programs (loyalty, discount) have a written policy explaining the basis

---

## Data Handling

- [ ] PI collected only for disclosed business purposes — no secondary use without updating privacy notice
- [ ] Service providers (vendors processing PI on your behalf) have signed a CCPA-compliant service provider contract
- [ ] PI not retained longer than necessary for the disclosed purpose; retention schedule documented
- [ ] SPI receives heightened protection: access limited to what is necessary; not used for advertising
- [ ] Precise geolocation (within 1/4 mile radius) treated as SPI if collected

---

## Privacy Notice Requirements

- [ ] Privacy notice accessible at or before the point of PI collection
- [ ] Notice lists all categories of PI collected and their purposes
- [ ] Notice updated within 12 months of any material change to PI practices
- [ ] Notice written in plain language; available in languages served if reasonably possible

---

## Common Violations (flag as HIGH)

- New PI collection not reflected in privacy notice
- No deletion path for PI created by the feature
- SPI processed beyond permitted purposes without consumer consent
- Opt-out of sale/sharing not honored promptly
- PI shared with a service provider without a CCPA-compliant contract
- GPC signal ignored for web-facing features

---

## Review Output Format

```
CCPA REVIEW
PI categories in scope: [list / NO PI IN SCOPE]
SPI in scope: [YES — list / NO]
Sale or sharing of PI: [YES / NO]

Right to Know:         PASS / FAIL / N/A
Right to Delete:       PASS / FAIL — [detail]
Right to Opt-Out:      PASS / FAIL / N/A
SPI Use Limitation:    PASS / FAIL / N/A
Non-discrimination:    PASS / N/A
Service provider contracts: PASS / FAIL / N/A

CCPA: COMPLIANT or NON-COMPLIANT — [list of blocking findings]
```
