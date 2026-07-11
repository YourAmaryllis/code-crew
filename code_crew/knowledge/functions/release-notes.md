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

## [0.6.0] — YYYY-MM-DD

### Added
- <new feature visible to users> (<issue-key>)
- New validation endpoint `POST /<resource>/validate` for pre-upload checks

### Changed
- <behavioral change> (<issue-key>)
- File upload size limit increased from X MB to Y MB (<issue-key>)

### Fixed
- <bug fix description> (<issue-key>)

### Security
- <security fix description> (<issue-key>)

## [0.5.3] — YYYY-MM-DD
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
<Section>: <plain English description of the user-visible change> (<issue-key>)
```

Rules:
- Write what changed from the user's perspective, not what code changed
- One line per user-visible change (a story may have multiple)
- Include the issue key in parentheses
- Past tense: "Added...", "Fixed...", "Changed..."
- No technical jargon in the Added/Changed/Fixed/Security lines unless unavoidable
- If a story has no user-visible change (e.g. internal refactor), it goes in Changed with "Internal: ..."

Examples:
```markdown
### Added
- Users must now complete <validation step> before proceeding to the next step (<issue-key>)

### Fixed  
- <Upload/form area> now correctly resets when an invalid input is removed (<issue-key>)

### Security
- <Field> display now escapes HTML to prevent XSS (<issue-key>)
```

---

## GitHub Release Notes

GitHub Release is the customer-facing document. Written for the Release Manager to review:

```markdown
## Release 0.6.0 — <Feature Name>

This release <one-sentence description of the user-visible impact>.

### What's New
- **<Feature>**: <What the user can now do or is now required to do>.
- **Clearer error messages**: The <UI area> now shows specific guidance when <condition>,
  including <detail>.

### Bug Fixes
- Fixed: <UI component> did not reset correctly after <user action>.

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
- Critical: <Security bypass description> (<issue-key>)
```

GitHub Release title: `Hotfix 0.5.1 — <one-line description>`
