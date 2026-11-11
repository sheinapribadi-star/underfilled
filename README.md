# Underfilled

A pre-flight check for one dull but deadly trial risk: not enough people sign up.

**Live demo:** https://sheinapribadi-star.github.io/underfilled/

## The idea in plain English

About 1 in 20 Phase 2 and 3 trials that started in the 2010s ended because they could not enroll enough people. That is 1,960 studies, and 31% of every terminated trial in the cohort, more than safety and efficacy stops combined.

Underfilled reads those trials from ClinicalTrials.gov and turns them into a quick check. Describe a protocol (phase, sponsor, condition area, number of sites, how many inclusion and exclusion criteria, and so on). You get an estimate of the chance it ends as a low-accrual stop, how that compares with the registry, which fields push it up or down, a few edits worth testing, and real stopped trials that looked like yours.

It is meant to start a feasibility conversation, not end one.

## Where it came from

At [Cal Hacks 12.0](https://cal-hacks-12-0.devpost.com/project-gallery) (October 2025), most of the projects that won Regeneron's prizes went after clinical trials:

- [TrialScope AI](https://devpost.com/software/trialscope-ai) (Regeneron Grand Prize) structures protocol drafts and benchmarks them against historical studies.
- [trialmatch.ai](https://devpost.com/software/trial-match-ai) (Runner-Up) matches patients to trials.
- [TrialFlow](https://devpost.com/software/trialflow) (Runner-Up) tackles scheduling and dropout.

Each is a big AI build. Underfilled is the small, checkable layer underneath them: the base rates. The full brief is in [BRIEF.md](BRIEF.md).

## Data sources

| Source | Used for |
| --- | --- |
| [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api) | 38,287 interventional Phase 2, 1/2, 2/3, and 3 studies that started 2010 to 2019 and are now completed or terminated. Pulled November 11, 2026. |
| `whyStopped` free text | Reason each terminated trial stopped, sorted by [scripts/reasons.py](scripts/reasons.py) |
| Registry MeSH condition terms | 15 broad condition areas |

Every number on the site comes from that pull. The three example designs on the form are made up and labeled as examples. The trials listed under "Trials like yours" are real registry records, linked to their pages.

## Method

- **Stop reasons:** readable regex rules. Tuned on two hand-read samples, then frozen and scored on 150 more terminated trials I labeled by hand: precision 0.96, recall 0.91 for the low-accrual bucket. COVID-19 stops are kept separate.
- **Model:** L2-regularized logistic regression on 43 fields known before the first patient (phase, sponsor type, criteria counts, site and country counts, population limits, masking, randomization, arms, primary outcomes, condition area, intervention type).
- **Honest test:** trained on trials that started 2010 to 2016, scored on 2017 to 2019. AUC 0.73. The riskiest tenth had 2.4x the base rate and held 24% of all low-accrual stops. The top tenth is somewhat overestimated (16.4% predicted vs 12.8% observed). The live tool uses a refit on all years.
- **Raw rates** in the charts use 95% Wilson intervals.

## Design decisions

- **A case report form, not a dashboard.** Clinical teams fill in forms all day. Numbered fields and hard rules read as a working document.
- **One color means one thing.** Vermilion is only ever "stopped for low accrual." Slate blue is everything else.
- **Raw rate next to the model.** "556 of 4,328 similar trials" is easier to trust and to argue with than a coefficient.
- **Edits, not just a score.** The tool tries realistic changes (fewer exclusions, more sites, a second country) and shows the ones that move the estimate.
- **Only pre-launch fields.** Actual enrollment is left out because stopped trials report what they reached, not what they planned.
- **Static and keyless.** One JSON bundle, plain JavaScript, no tracking, served by GitHub Pages.

## The metric that would show it works

Among protocols flagged in the riskiest tenth, the share that get a documented design change before the first patient, and then the low-accrual termination rate of flagged protocols that changed versus those that did not on the next registry cohort. Until that exists, the guardrail is that each new start-year cohort still shows the riskiest tenth at 2x or more the base rate.

## Limits

Associations, not causes. Site counts are the final registered list. Withdrawn and unknown-status trials are outside the cohort, so true enrollment failure is higher than shown. `whyStopped` is self-reported. Not medical, legal, or regulatory advice.

## Rebuild

```
python3 scripts/fetch_trials.py        # about a minute, writes data/raw/studies.jsonl (gitignored)
python3 scripts/build_data.py          # writes data/bundle.json and prints the model card
python3 scripts/check_classifier.py    # scores the stop-reason rules on the hand-labeled sample
python3 -m http.server                 # then open http://localhost:8000
```

Needs Python 3 with NumPy.

## Credit

Built by [Sheina Pribadi](https://sheinapribadi-star.github.io/). Trial data from ClinicalTrials.gov, a service of the U.S. National Library of Medicine. Inspired by the Cal Hacks 12.0 teams credited above. MIT licensed.
