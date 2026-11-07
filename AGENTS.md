# Project instructions

## Layout exception requested by the user

For this project, `/Users/richardzhu/dev/no_escape` is the working root. The user explicitly removed the `workspace/` requirement on November 7, 2026. Keep `PLAN.md` at the root and application material under `clearway/`. Do not recreate a workspace wrapper or move project files outside this root.

The existing `ECC/` and `ECC-codex-reviewed/` folders are local tool material, not Clearway application source. They are excluded from this repository's tracked files. Do not run their setup scripts as part of the Clearway build.

## Protected data

Any designated `holdout/` remains protected. Only the main agent may deliberately access it for an evaluation, after stating that step to the user. Worker agents must not list, read, copy, or reference holdout. A root-layout change does not revoke these protections. Do not create or reorganize a holdout without a concrete need and authorization.

## Previews and testing

Use Codex's visible built-in browser (`iab`) for web previews and browser testing. Use `open_in_codex` in the right panel for artifacts when available. Run development servers and automated checks through terminal tools. Do not use personal browser windows, native computer control, AppleScript, or OS commands that launch external browsers. If the built-in browser is unavailable, report the limitation and continue terminal checks.

## Build handoff

Read `PLAN.md` and `clearway/docs/DECISIONS.md` before implementation. A planning request or a quoted overnight prompt does not itself start an unattended build. When a build is authorized, use the selected scope and documented fallbacks, preserve honest fixture/replay/inference labels, and honor provider caps. Do not log or commit secrets or downloaded source media.
