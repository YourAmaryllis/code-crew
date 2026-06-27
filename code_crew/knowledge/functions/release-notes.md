---
name: SDLC-ReleaseEngineer-ReleaseNotes
description: Release notes and changelog conventions — format, audience, per-story contributions, and what to include
metadata:
  type: process
  role: release-engineer
  phase: "20"
---

# Release Notes

## Two Documents, Two Audiences

| Document | Audience | Format | Where |
|----------|---------|--------|-------|
| CHANGELOG.md | Developers, internal | Keep a Changelog format | Repo root |
| GitHub Release | End users, partners | Plain English summary | GitHub Releases |

CHANGELOG.md is the technical record. The GitHub Release is the customer-facing announcement.
They cover the same changes but at different levels of detail.

---

## CHANGELOG.md Format

Follow [Keep a Changelog](https://keepachangelog.com/) conventions:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.6.0] — 2026-06-21

### Added
- Data dictionary upload is now mandatory for dataset registration (PROJ-NNN)
- New validation endpoint `POST /datasets/validate-dictionary` for pre-upload checks

### Changed
- Registration step 2 now enforces data dictionary before allowing Step 3 (PROJ-NNN)
- File upload size limit increased from 5 MB to 10 MB (PROJ-NNN)

### Fixed
- Data dictionary upload state was not cleared on wizard cancel (PROJ-NNN)

### Security
- Added XSS prevention for filename display in error review log (PROJ-NNN)

## [0.5.3] — 2026-05-14
...
```

Sections (use only those with entries):
- **Added** — new feature or capability
- **Changed** — change to existing behavior (backward compatible)
- **Deprecated** — soon-to-be removed feature
- **Removed** — removed feature (breaking — requires MAJOR bump for stable APIs)
- **Fixed** — bug fix
- **Security** — security vulnerability fix (always include CVE if applicable)

---

## Per-Story Release Note Contribution

Each story contributes one or more changelog lines. Format:

```
<Section>: <plain English description of the user-visible change> (<JIRA-KEY>)
```

Rules:
- Write what changed from the user's perspective, not what code changed
- One line per user-visible change (a story may have multiple)
- Include the Jira key in parentheses
- Past tense: "Added...", "Fixed...", "Changed..."
- No technical jargon in the Added/Changed/Fixed/Security lines unless unavoidable
- If a story has no user-visible change (e.g. internal refactor), it goes in Changed with "Internal: ..."

Examples:
```markdown
### Added
- Sellers must now upload a data dictionary before completing dataset registration (PROJ-NNN)

### Fixed  
- Upload area now correctly resets when a rejected file is removed (PROJ-NNN)

### Security
- File name display in the Error Review Log now escapes HTML to prevent XSS (PROJ-NNN)
```

---

## GitHub Release Notes

GitHub Release is the customer-facing document. Written for the Release Manager to review:

```markdown
## Release 0.6.0 — Data Dictionary Enforcement

This release makes the data dictionary upload mandatory in the dataset registration wizard.
Sellers cannot proceed to Step 3 without a valid data dictionary file.

### What's New
- **Mandatory data dictionary**: Dataset registration now requires a data dictionary
  upload in Step 2. Files must be CSV or Excel format, up to 10 MB.
- **Clearer error messages**: The wizard now shows specific guidance when a file is
  rejected, including the exact validation failure reason.

### Bug Fixes
- Fixed: Upload area did not reset correctly after removing a rejected file.

### Security
- Fixed potential XSS in the file name display in the Error Review Log.

### Migration Notes
None required — new validation only affects new registrations.

### Known Issues
None.

---
Full changelog: [CHANGELOG.md](./CHANGELOG.md)
QA sign-off: [link to staging acceptance comment]
Smoke tests: [GitHub Actions run link]
```

---

## What NOT to Include

- Commit SHAs or branch names
- Internal refactoring with no user impact (goes in CHANGELOG under "Changed: Internal..." but not in GitHub Release)
- Draft/speculative changes
- Changes not yet tested in staging

---

## Release Notes for Hotfixes

Hotfix releases get abbreviated notes:

```markdown
## [0.5.1] — 2026-06-21

### Fixed
- Critical: Data dictionary bypass allowed sellers to skip mandatory upload when
  navigating back to Step 2 after completing Step 3 (PROJ-NNN)
```

GitHub Release title: `Hotfix 0.5.1 — <one-line description>`
