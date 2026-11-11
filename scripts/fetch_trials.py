"""Pull the Underfilled cohort from the ClinicalTrials.gov API v2 (public, no key).

Cohort: interventional Phase 2 or Phase 3 studies that started 2010-2019 and are
now COMPLETED or TERMINATED. Writes data/raw/studies.jsonl (gitignored).
"""
import json, os, time, urllib.parse, urllib.request

API = "https://clinicaltrials.gov/api/v2/studies"
QUERY = ("AREA[StudyType]INTERVENTIONAL AND AREA[StartDate]RANGE[2010-01-01,2019-12-31] "
         "AND (AREA[Phase]PHASE2 OR AREA[Phase]PHASE3)")
FIELDS = ",".join([
    "NCTId", "BriefTitle", "OverallStatus", "WhyStopped", "Phase", "StartDate",
    "PrimaryCompletionDate", "LeadSponsorClass", "EligibilityCriteria", "MinimumAge",
    "MaximumAge", "HealthyVolunteers", "Sex", "LocationCountry", "EnrollmentCount",
    "EnrollmentType", "ConditionMeshTerm", "ConditionAncestorTerm", "Condition", "DesignAllocation", "DesignMasking",
    "ArmGroupLabel", "InterventionType", "PrimaryOutcomeMeasure", "SecondaryOutcomeMeasure",
])
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "studies.jsonl")


def page(token=None):
    params = {"query.term": QUERY, "filter.overallStatus": "COMPLETED,TERMINATED",
              "fields": FIELDS, "pageSize": 1000, "format": "json"}
    if token:
        params["pageToken"] = token
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "underfilled-research/1.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:  # retry politely
            print("retry", attempt, e)
            time.sleep(3 * (attempt + 1))
    raise SystemExit("API failed")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    n, token = 0, None
    with open(OUT, "w") as f:
        while True:
            d = page(token)
            for s in d.get("studies", []):
                f.write(json.dumps(s) + "\n")
                n += 1
            token = d.get("nextPageToken")
            print("studies", n)
            if not token:
                break
            time.sleep(0.4)


if __name__ == "__main__":
    main()
