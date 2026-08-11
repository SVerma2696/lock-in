# Security Policy

Lock In is a personal desktop app (Pomodoro timer + app blocker). It
runs entirely on your own machine — the only optional network call is
the Claude fallback (off by default), which sends a single window
title string and nothing else. See the README's "Claude fallback"
section for the full data-handling details.

## Supported versions

Only the **latest released version** is supported. This is a small
solo project, not something with a long-term support branch — if a
security issue is found, the fix goes into the next release, not a
backport.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a security problem.

Instead, use GitHub's private vulnerability reporting:

1. Go to the **Security** tab on this repository.
2. Click **Report a vulnerability**.
3. Describe the issue — what it is, how to reproduce it, and what it
   affects.

This opens a private conversation that only you and the maintainer can
see, so the issue isn't public until there's a fix.

## What counts as a security issue here

Realistic examples for this project: something that lets a window
title or config value execute unintended code, a way to escalate the
app's blocking/minimize permissions beyond what's documented, or a way
to leak more than the single window-title string the README says the
Claude fallback sends.

General bugs, feature requests, and "the classifier misjudged my
window" are regular GitHub issues, not security reports.
