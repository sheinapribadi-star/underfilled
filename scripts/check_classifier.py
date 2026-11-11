"""Score scripts/reasons.py against the hand-labeled validation sample."""
import json, os, sys
HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
from reasons import classify

sample = json.load(open(os.path.join(HERE, "validation_sample_ids.json")))
gold = set(json.load(open(os.path.join(HERE, "validation_labels.json")))["low_accrual_indices"])
tp = fp = fn = tn = 0
for i, (nct, why) in enumerate(sample):
    pred, g = classify(why) == "low accrual", i in gold
    tp += pred and g; fp += pred and not g; fn += g and not pred; tn += not pred and not g
print(f"n={len(sample)} tp={tp} fp={fp} fn={fn} tn={tn}")
print(f"precision={tp/(tp+fp):.3f} recall={tp/(tp+fn):.3f} accuracy={(tp+tn)/len(sample):.3f}")
