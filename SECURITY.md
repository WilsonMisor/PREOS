# PREOS Security Policy

PREOS itself governs production assurance and therefore must be treated as security-sensitive governance code.

## Reportable issues

Report defects that could cause PREOS to:

- silently convert UNKNOWN, RED, or HUMAN REVIEW into GREEN;
- accept risk without accountable human authority;
- allow stale evidence to remain current after a relevant change;
- lose tenant, payment, security, privacy, recovery, or production-release controls;
- load or disclose secrets, credentials, personal data, or restricted production data unnecessarily;
- bypass required Blueprint, gstack, Codex, CI, or human gates;
- mutate production state without explicit delegated authority.

## Handling

Do not publish real secrets or sensitive customer data in issues. Use redacted reproduction evidence. Security fixes must include regression tests and change-impact review.
