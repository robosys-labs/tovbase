# Trustgate Adversarial Test Corpus

The corpus is the empirical backbone of the whitepaper. Every algorithm change must report precision/recall against it before merge. Community contributions are the way it grows.

## Format

Each YAML file under `corpus/` holds one or more labeled profile entries.

```yaml
# corpus/known_good.yaml
version: 1
label: known_good           # known_good | known_bad | edge_case
entries:
  - handle: torvalds
    platform: github
    expected_tier: excellent      # excellent | good | fair | poor | untrusted
    expected_min_score: 850
    expected_max_score: 1000
    justification: >
      Linux kernel creator. 30+ years of public Git history,
      verified across multiple platforms. Industry-canonical
      high-trust identity.
    sources:
      - https://github.com/torvalds
      - https://en.wikipedia.org/wiki/Linus_Torvalds
    added_at: 2026-05-10
    added_by: <maintainer>
```

## File layout

| File | Contents | Target size |
|------|----------|-------------|
| `known_good.yaml` | Public figures with documented track record | 1000 |
| `known_bad.yaml` | Disclosed bots, Sybils, deplatformed scammers | 1000 |
| `edge_cases.yaml` | New-but-legitimate, dormant, claim/real-name mismatch | 200 |

v0.2 ships with ~10 seed entries per file as a bootstrapping skeleton. v0.3 targets ≥ 200 per file. v1.0 targets the full ≥ 2200 corpus.

## Running the corpus

```bash
python scripts/run_corpus.py
```

Output (per category):

```
known_good           tier-excellent  precision=0.91   recall=0.94   n=42
known_good           tier-good       precision=0.88   recall=0.85   n=18
known_bad            tier-untrusted  precision=0.97   recall=0.95   n=39
edge_cases           per-entry diff  see report
```

The script reports the delta between actual and expected scores so algorithm changes can be evaluated without re-reading individual entries.

## Contributing entries

Open a PR adding entries to the appropriate file with:

1. **Verifiable evidence** linked under `sources:`. Public profile URLs, archived snapshots, journalism articles. No private databases.
2. **Justification** explaining why the label is correct.
3. **Range, not point.** `expected_min_score` / `expected_max_score` should leave room for natural score evolution. Excellent profiles drift between 850 and 950 over a year.
4. **Maintainer review.** Corpus entries follow the same governance as seed-list changes (see GOVERNANCE.md), with a 7-day public comment window.

For `known_bad` entries, the justification must reference a public source confirming the bad behavior — a journalistic exposé, a platform's transparency report, or a public disclosure. We do not accept "looks like a bot to me."

## Removing entries

Entries can be removed if:
- The platform deletes the account (we update the corpus to reflect reality).
- New evidence overturns the label (e.g. an account flagged as a bot turns out to be a real but unusual person — happens).
- The subject explicitly requests removal *and* removal does not materially affect benchmark integrity.

Removals follow the same governance + comment-window process as additions.
