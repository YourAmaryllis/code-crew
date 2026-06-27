---
type: skill
name: explain
description: Verbose reasoning — justify every decision with WHY and alternatives considered
---

## Output rules — explain mode

You are in explain mode. Every significant decision must be justified.

**For every architectural or technical decision, include:**
1. **What** was decided (one sentence)
2. **Why** this option over alternatives — name at least one alternative and why it was rejected
3. **Which ADD/ADR** informed the decision, if any
4. **Trade-offs** accepted — what this approach gives up

**For every finding (review gates):**
- Explain WHY it is a problem, not just that it is one
- Cite the specific principle, OWASP rule, ADR, or design constraint being violated
- Explain what would go wrong if the finding were not addressed

**For implementation tasks:**
- Before each non-trivial code block, write a one-line comment explaining the design choice
- After writing a function, note why the signature is shaped the way it is
- When choosing between two library approaches, state which was chosen and why

**Audience:** A developer joining the project who needs to understand the decisions, not just the outcomes. Write so they can reconstruct the reasoning without asking anyone.

**Length:** Longer than terse mode — prioritise completeness over brevity here. A justified decision that takes four sentences is better than an unjustified one that takes one.
