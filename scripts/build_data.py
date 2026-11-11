"""Build data/bundle.json for Underfilled from data/raw/studies.jsonl.

Outcome: a study counts as "stopped for low accrual" when it is TERMINATED and
its whyStopped text is classified as an enrollment problem (scripts/reasons.py).
Everything else in the cohort (completed, or terminated for another reason)
is the comparison group.
"""
import json, math, os, re, sys
from collections import Counter, defaultdict
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
from reasons import classify  # noqa: E402

RAW = os.path.join(HERE, "..", "data", "raw", "studies.jsonl")
OUT = os.path.join(HERE, "..", "data", "bundle.json")

AREAS = [  # (key, label, MeSH terms)
    ("cancer", "Cancer", ["Neoplasms"]),
    ("heart", "Heart and blood vessels", ["Cardiovascular Diseases"]),
    ("neuro", "Brain and nerves", ["Nervous System Diseases"]),
    ("mental", "Mental health", ["Mental Disorders"]),
    ("infection", "Infections", ["Infections"]),
    ("lung", "Lungs and airways", ["Respiratory Tract Diseases"]),
    ("digestive", "Digestive system", ["Digestive System Diseases"]),
    ("metabolic", "Metabolic and endocrine", ["Nutritional and Metabolic Diseases", "Endocrine System Diseases"]),
    ("immune", "Immune system", ["Immune System Diseases"]),
    ("skin", "Skin and connective tissue", ["Skin and Connective Tissue Diseases"]),
    ("blood", "Blood and lymph", ["Hemic and Lymphatic Diseases"]),
    ("urogenital", "Urinary and reproductive", ["Urogenital Diseases", "Female Urogenital Diseases and Pregnancy Complications"]),
    ("musculo", "Bones, joints, muscles", ["Musculoskeletal Diseases"]),
    ("eye", "Eye", ["Eye Diseases"]),
    ("congenital", "Inherited and congenital", ["Congenital, Hereditary, and Neonatal Diseases and Abnormalities"]),
]
ITYPES = ["DRUG", "BIOLOGICAL", "DEVICE", "PROCEDURE", "BEHAVIORAL", "RADIATION", "DIETARY_SUPPLEMENT"]
BULLET = re.compile(r"^\s*(\*|-|•|·|‣|\u2022|\d{1,2}[.)]|[a-zA-Z][.)]|\(\w{1,3}\))\s+")


def years(s):
    if not s:
        return None
    m = re.match(r"([\d.]+)\s*(Year|Month|Week|Day|Hour|Minute)", s)
    if not m:
        return None
    v = float(m.group(1)); u = m.group(2)
    return v * {"Year": 1, "Month": 1 / 12, "Week": 1 / 52, "Day": 1 / 365, "Hour": 1 / 8760, "Minute": 1 / 525600}[u]


def count_criteria(block):
    lines = [l for l in block.split("\n") if l.strip()]
    b = sum(1 for l in lines if BULLET.match(l))
    if b == 0:
        b = sum(1 for l in lines if not re.search(r"criteria\s*:?\s*$", l, re.I))
    return b


def parse_elig(text):
    if not text:
        return 0, 0, 0
    parts = re.split(r"exclusion criteria\s*:?", text, maxsplit=1, flags=re.I)
    inc = re.sub(r"^\s*inclusion criteria\s*:?", "", parts[0], flags=re.I)
    exc = parts[1] if len(parts) > 1 else ""
    return count_criteria(inc), count_criteria(exc), len(text.split())


def sponsor(c):
    if c == "INDUSTRY":
        return "industry"
    if c in ("NIH", "FED", "OTHER_GOV"):
        return "government"
    return "academic"  # OTHER, NETWORK, INDIV, UNKNOWN: universities, hospitals, cooperative groups


def phase(ps):
    ps = tuple(ps or [])
    return {("PHASE2",): "2", ("PHASE3",): "3", ("PHASE1", "PHASE2"): "1/2", ("PHASE2", "PHASE3"): "2/3"}.get(ps, "2")


def site_bucket(n):
    if n <= 1:
        return "1"   # 0 listed is treated as a single unnamed site
    if n <= 5:
        return "2-5"
    if n <= 20:
        return "6-20"
    if n <= 100:
        return "21-100"
    return "100+"


def load():
    out = []
    for line in open(RAW):
        d = json.loads(line)
        p = d["protocolSection"]
        st = p["statusModule"]
        why = st.get("whyStopped")
        status = st["overallStatus"]
        reason = classify(why) if status == "TERMINATED" else "completed"
        de = p.get("designModule", {})
        el = p.get("eligibilityModule", {})
        locs = p.get("contactsLocationsModule", {}).get("locations", []) or []
        countries = {l.get("country") for l in locs if l.get("country")}
        cb = d.get("derivedSection", {}).get("conditionBrowseModule", {})
        terms = {x["term"] for x in cb.get("meshes", []) + cb.get("ancestors", [])}
        areas = [k for k, _, ts in AREAS if any(t in terms for t in ts)]
        ai = p.get("armsInterventionsModule", {})
        itypes = sorted({i.get("type") for i in ai.get("interventions", []) or []})
        n_inc, n_exc, words = parse_elig(el.get("eligibilityCriteria", ""))
        maxy = years(el.get("maximumAge"))
        miny = years(el.get("minimumAge"))
        oc = p.get("outcomesModule", {})
        masking = (de.get("designInfo", {}).get("maskingInfo", {}) or {}).get("masking") or "NONE"
        out.append({
            "nct": p["identificationModule"]["nctId"],
            "title": p["identificationModule"].get("briefTitle", ""),
            "status": status, "why": why or "", "reason": reason,
            "y": 1 if reason == "low accrual" else 0,
            "start": int((st.get("startDateStruct", {}) or {}).get("date", "2010")[:4]),
            "phase": phase(de.get("phases")),
            "sponsor": sponsor(p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("class")),
            "n_inc": n_inc, "n_exc": n_exc, "words": words,
            "sites": len(locs), "countries": len(countries),
            "healthy": bool(el.get("healthyVolunteers")),
            "upper_age": maxy is not None and maxy < 90,
            "kids_only": maxy is not None and maxy < 18.5,
            "older_only": miny is not None and miny >= 60,
            "one_sex": el.get("sex") in ("FEMALE", "MALE"),
            "open_label": masking == "NONE",
            "randomized": (de.get("designInfo", {}) or {}).get("allocation") == "RANDOMIZED",
            "arms": len(ai.get("armGroups", []) or []),
            "n_primary": len(oc.get("primaryOutcomes", []) or []),
            "n_secondary": len(oc.get("secondaryOutcomes", []) or []),
            "areas": areas, "itypes": itypes,
        })
    return out


# ---------- model ----------
def featurize(r):
    f = {
        "phase 1/2": r["phase"] == "1/2", "phase 2/3": r["phase"] == "2/3", "phase 3": r["phase"] == "3",
        "industry sponsor": r["sponsor"] == "industry", "government sponsor": r["sponsor"] == "government",
        "log inclusion criteria": math.log1p(min(r["n_inc"], 60)),
        "log exclusion criteria": math.log1p(min(r["n_exc"], 80)),
        "sites 2-5": site_bucket(r["sites"]) == "2-5", "sites 6-20": site_bucket(r["sites"]) == "6-20",
        "sites 21-100": site_bucket(r["sites"]) == "21-100", "sites 100+": site_bucket(r["sites"]) == "100+",
        "multinational": r["countries"] > 1,
        "healthy volunteers": r["healthy"], "upper age limit": r["upper_age"], "children only": r["kids_only"],
        "older adults only": r["older_only"], "one sex only": r["one_sex"],
        "open label": r["open_label"], "randomized": r["randomized"],
        "3+ arms": r["arms"] >= 3,
        "log primary outcomes": math.log1p(min(r["n_primary"], 20)),
    }
    for k, _, _ in AREAS:
        f["area: " + k] = k in r["areas"]
    for t in ITYPES:
        f["uses " + t.lower().replace("_", " ")] = t in r["itypes"]
    return f


def fit_logreg(X, y, lam=1.0, iters=50):
    n, k = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    w = np.zeros(k + 1)
    reg = np.full(k + 1, lam); reg[0] = 0
    for _ in range(iters):
        z = Xb @ w
        p = 1 / (1 + np.exp(-z))
        g = Xb.T @ (p - y) + reg * w
        H = (Xb * (p * (1 - p))[:, None]).T @ Xb + np.diag(reg)
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    cov = np.linalg.inv(H)
    return w, cov


def predict(w, X):
    return 1 / (1 + np.exp(-(w[0] + X @ w[1:])))


def auc(y, s):
    order = np.argsort(s)
    ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s) + 1)
    # average ties
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, ranks); ranks = (sums / cnt)[inv]
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def wilson(k, n, z=1.96):
    if n == 0:
        return [0, 0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 4), round(min(1, c + h), 4)]


def rate_table(rows, keyfn, order=None):
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        for k in (keyfn(r) if isinstance(keyfn(r), list) else [keyfn(r)]):
            agg[k][0] += r["y"]; agg[k][1] += 1
    keys = order or sorted(agg)
    return [{"k": k, "stops": agg[k][0], "n": agg[k][1], "rate": round(agg[k][0] / agg[k][1], 4) if agg[k][1] else 0,
             "ci": wilson(agg[k][0], agg[k][1])} for k in keys if agg[k][1]]


def bucket(v, edges, labels):
    for e, l in zip(edges, labels):
        if v <= e:
            return l
    return labels[-1]


def main():
    rows = load()
    y = np.array([r["y"] for r in rows], float)
    feats = [featurize(r) for r in rows]
    names = list(feats[0].keys())
    X = np.array([[float(f[n]) for n in names] for f in feats])
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd

    start = np.array([r["start"] for r in rows])
    tr, te = start <= 2016, start >= 2017
    # Holdout: scale with training-year statistics only, so nothing from 2017-2019 leaks in.
    mu_tr, sd_tr = X[tr].mean(0), X[tr].std(0) + 1e-9
    Z_ho = (X - mu_tr) / sd_tr
    w_tr, _ = fit_logreg(Z_ho[tr], y[tr])
    p_te = predict(w_tr, Z_ho[te])
    # Robustness: site and country counts come from the final registry record, so
    # refit without them to show how much the score leans on those fields.
    keep = [i for i, n in enumerate(names) if not n.startswith("sites") and n != "multinational"]
    Xk = X[:, keep]
    mk, sk = Xk[tr].mean(0), Xk[tr].std(0) + 1e-9
    w_k, _ = fit_logreg(((Xk - mk) / sk)[tr], y[tr])
    auc_no_sites = auc(y[te], predict(w_k, ((Xk - mk) / sk)[te]))
    test_auc = auc(y[te], p_te)
    brier = float(np.mean((p_te - y[te]) ** 2))
    base_te = float(y[te].mean())
    brier_base = float(np.mean((base_te - y[te]) ** 2))
    # calibration by decile and top-decile lift
    q = np.quantile(p_te, np.linspace(0, 1, 11))
    calib = []
    for i in range(10):
        m = (p_te >= q[i]) & (p_te <= q[i + 1]) if i == 9 else (p_te >= q[i]) & (p_te < q[i + 1])
        calib.append({"decile": i + 1, "pred": round(float(p_te[m].mean()), 4), "obs": round(float(y[te][m].mean()), 4), "n": int(m.sum())})
    top = p_te >= q[9]
    lift = float(y[te][top].mean() / base_te)
    share_caught = float(y[te][top].sum() / y[te].sum())

    w_all, cov = fit_logreg(Z, y)
    se = np.sqrt(np.diag(cov))
    coefs = []
    for i, n in enumerate(names):
        b, s = w_all[i + 1], se[i + 1]
        # odds ratio per unit of the raw feature (one flag flip, or one log step)
        coefs.append({"name": n, "beta_std": round(float(b), 4), "or": round(float(math.exp(b / sd[i])), 3),
                      "lo": round(float(math.exp((b - 1.96 * s) / sd[i])), 3), "hi": round(float(math.exp((b + 1.96 * s) / sd[i])), 3)})

    # descriptive tables
    term = [r for r in rows if r["status"] == "TERMINATED"]
    reasons = Counter(r["reason"] for r in term)
    by_year = rate_table(rows, lambda r: r["start"])
    tables = {
        "phase": rate_table(rows, lambda r: r["phase"], ["1/2", "2", "2/3", "3"]),
        "sponsor": rate_table(rows, lambda r: r["sponsor"], ["industry", "academic", "government"]),
        "sites": rate_table(rows, lambda r: site_bucket(r["sites"]), ["1", "2-5", "6-20", "21-100", "100+"]),
        "exclusion": rate_table(rows, lambda r: bucket(r["n_exc"], [5, 10, 15, 20, 30], ["0-5", "6-10", "11-15", "16-20", "21-30", "31+"]),
                                ["0-5", "6-10", "11-15", "16-20", "21-30", "31+"]),
        "inclusion": rate_table(rows, lambda r: bucket(r["n_inc"], [3, 6, 10, 15], ["0-3", "4-6", "7-10", "11-15", "16+"]),
                                ["0-3", "4-6", "7-10", "11-15", "16+"]),
        "area": sorted(rate_table(rows, lambda r: r["areas"] or ["unmapped"]), key=lambda d: -d["rate"]),
        "masking": rate_table(rows, lambda r: "open label" if r["open_label"] else "blinded", ["open label", "blinded"]),
    }
    # phase x sponsor x area cube for the "trials like yours" panel
    cube = defaultdict(lambda: [0, 0])
    for r in rows:
        for a in (r["areas"] or ["unmapped"]):
            cube[f"{r['phase']}|{r['sponsor']}|{a}"][0] += r["y"]
            cube[f"{r['phase']}|{r['sponsor']}|{a}"][1] += 1
    # real examples of low-accrual stops, for quotes and the similar-trials list
    examples = [{"nct": r["nct"], "t": r["title"][:110], "ph": r["phase"], "sp": r["sponsor"], "a": r["areas"],
                 "why": r["why"][:180], "s": r["start"], "sites": r["sites"], "exc": r["n_exc"]}
                for r in rows if r["y"] == 1]
    p_all = predict(w_all, Z)
    pctl = [round(float(v), 5) for v in np.quantile(p_all, np.linspace(0, 1, 101))]

    bundle = {
        "generated": "2026-11-11",
        "cohort": {"n": len(rows), "completed": int(sum(r["status"] == "COMPLETED" for r in rows)),
                   "terminated": len(term), "low_accrual": int(y.sum()),
                   "start_range": [2010, 2019], "phases": "Phase 2, Phase 1/2, Phase 2/3, Phase 3", "type": "interventional"},
        "reasons": [{"k": k, "n": v} for k, v in reasons.most_common()],
        "by_year": by_year,
        "tables": tables,
        "model": {"names": names, "mu": [round(float(v), 6) for v in mu], "sd": [round(float(v), 6) for v in sd],
                  "w": [round(float(v), 6) for v in w_all],
                  "holdout": {"train": "start 2010-2016", "test": "start 2017-2019", "n_train": int(tr.sum()), "n_test": int(te.sum()),
                              "auc": round(test_auc, 3), "auc_no_sites": round(auc_no_sites, 3), "brier": round(brier, 4), "brier_base": round(brier_base, 4),
                              "base_rate": round(base_te, 4), "top_decile_lift": round(lift, 2),
                              "top_decile_share": round(share_caught, 3), "calibration": calib},
                  "coefs": coefs, "pctl": pctl},
        "areas": [{"k": k, "label": l} for k, l, _ in AREAS],
        "cube": {k: v for k, v in cube.items()},
        "examples": examples,
        "medians": {"n_inc": int(np.median([r["n_inc"] for r in rows])), "n_exc": int(np.median([r["n_exc"] for r in rows]))},
    }
    with open(OUT, "w") as f:
        json.dump(bundle, f, separators=(",", ":"))
    print(json.dumps({k: bundle[k] for k in ("cohort", "reasons")}, indent=1))
    print(json.dumps(bundle["model"]["holdout"], indent=1))
    for c in sorted(coefs, key=lambda c: -abs(math.log(c["or"]))):
        print(f"{c['name']:28s} OR {c['or']:.2f} [{c['lo']:.2f}, {c['hi']:.2f}]")
    for k, t in tables.items():
        print(k, [(d["k"], d["n"], round(d["rate"] * 100, 1)) for d in t])
    print("size", os.path.getsize(OUT))


if __name__ == "__main__":
    main()
