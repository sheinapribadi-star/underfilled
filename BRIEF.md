# Underfilled: research and design brief

## What inspired it

Cal Hacks 12.0 (October 24 to 26, 2025, San Francisco) had a Regeneron prize, and most of its winners went after clinical trials:

- [TrialScope AI](https://devpost.com/software/trialscope-ai), Regeneron Grand Prize. Turns a Phase II or III protocol draft into structured data and benchmarks its design against historical studies from ClinicalTrials.gov.
- [trialmatch.ai](https://devpost.com/software/trial-match-ai), Regeneron Runner-Up. Matches patients to trials, built on the premise that trials fail because they cannot find the right patients fast enough.
- [TrialFlow](https://devpost.com/software/trialflow), Regeneron Runner-Up. Scheduling and a participant burden score to cut dropout.
- [Trialytics](https://devpost.com/software/trialytics), Regeneron Runner-Up. Regulatory paperwork and data standards.

Winner list: [Cal Hacks 12.0 project gallery](https://cal-hacks-12-0.devpost.com/project-gallery).

All four are large builds with an AI layer. None of them shows the plain base rate they are all reacting to. Underfilled is that missing piece: before a team builds a matching agent, how often did designs like theirs run out of patients, and which design choices moved with it?

## User and problem

**User:** a clinical operations lead or study manager at an academic medical center or a small biotech, in the weeks before a protocol is finalized.

**Problem:** feasibility reviews lean on investigator optimism ("we see lots of these patients"). There is rarely a quick, public benchmark that says "academic Phase 2 cancer studies stopped for low accrual at 2.5 times the registry average." The cost of finding out late is a terminated study, wasted patient effort, and no answer.

**Job to be done:** "Before we lock this protocol, tell me if it looks like the ones that ran dry, and what I would change first."

## What it does

1. **Finding.** Counts why terminated trials say they stopped, using the registry's free-text `whyStopped` field.
2. **Pre-flight check.** A short form (phase, sponsor, area, sites, countries, criteria counts, population limits, design) returns a model estimate, its percentile among registered designs, the fields pushing it up or down, a few edits worth testing, the raw rate for trials with the same phase, sponsor, and area, and real low-accrual stops that look like it, with links.
3. **Patterns.** Raw rates by design choice with 95% Wilson intervals.
4. **Model card.** Temporal holdout metrics, calibration, and known limits.

## Data

- [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api), pulled November 11, 2026. No key.
- Cohort: interventional studies, phases 2, 1/2, 2/3, or 3, start date 2010-01-01 to 2019-12-31, overall status COMPLETED or TERMINATED. 38,287 studies (31,930 completed, 6,357 terminated).
- Outcome: terminated and `whyStopped` classified as an enrollment problem. 1,960 studies (5.1% of the cohort, 31% of terminations).
- Condition areas come from the registry's MeSH terms and ancestors, mapped to 15 broad areas. A study can be in more than one.

## Decisions

- **Rules, not an LLM, for the stop reason.** Readable, free, and testable. Rules were tuned on two hand-read samples (220 trials), then frozen and scored on a third sample of 150 that I labeled by hand before looking at the output: precision 0.96, recall 0.91. `python3 scripts/check_classifier.py` reproduces it.
- **COVID-19 is its own bucket.** A pandemic stop says little about protocol design, so it should not count against one.
- **Only fields known before the first patient.** Actual enrollment is excluded because terminated trials report what they reached, not what they planned.
- **Temporal holdout.** Train on starts from 2010 to 2016, test on 2017 to 2019. A random split would flatter the model.
- **Show the raw rate beside the model.** People trust "556 of 4,328 similar trials" more than a coefficient, and it lets them see when the model and the raw data disagree.
- **Edits, not just a score.** A risk number without a next step is trivia. The tool tries a few realistic edits and shows the ones that move the estimate.
- **Look:** a case report form. Numbered fields, hard rules, one dark results panel. Instrument Serif for headlines, Public Sans (the US federal web typeface) for body, DM Mono for data. Vermilion only ever means "stopped for low accrual."

## Results (holdout, trials started 2017 to 2019)

| Metric | Value |
| --- | --- |
| Test trials | 10,516 |
| Base rate | 5.3% |
| AUC | 0.73 |
| Brier score | 0.0483 (0.0498 guessing the base rate) |
| Riskiest tenth | 2.4x the base rate, holding 24% of all low-accrual stops |

The riskiest tenth is overestimated (16.4% predicted, 12.8% observed). The rest tracks closely.

## Success metric

**Product metric:** among protocols a team runs through the check, the share that the tool puts in the riskiest tenth and that then get a documented design change (fewer criteria, more sites, a second country) before the first patient is enrolled. Target for a pilot: half of flagged protocols get at least one change.

**Outcome metric (the one that matters):** low-accrual termination rate for flagged protocols that changed versus flagged protocols that did not, measured on the next registry cohort. Until that exists, the guardrail is the model's own: each new start-year cohort should still show the riskiest tenth at 2x or more the base rate.

## Limits

- Associations, not causes. More sites usually means more money.
- Site counts are the final registered list and may undercount sites a stopped trial never added.
- Withdrawn trials (stopped before the first participant) and unknown-status trials are outside the cohort, so true enrollment failure is higher.
- `whyStopped` is self-reported free text, and 622 terminated trials left it blank.
- Not medical, legal, or regulatory advice.
