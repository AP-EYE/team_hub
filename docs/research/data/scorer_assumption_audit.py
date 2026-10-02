"""Offline synthetic audit of scoring assumptions. No API calls or real PII.

Run: python scorer_assumption_audit.py
N/G/U/S are mutually exclusive TOY labels, not a legal ordinal scale.
The production annotation scheme must allow overlapping labels and abstention.
All confidence intervals describe this synthetic generator, not field performance.
"""
from collections import Counter
from itertools import combinations
from pathlib import Path
import hashlib
import json
import math
import random
import statistics

SEED = 20260930
COHORTS = 200
PROFILES = {"toy_1_5_10": [0, 1, 5, 10], "equal_special": [0, 1, 5, 5],
            "identifier_heavy": [0, 1, 10, 5]}


def scores(data, weights):
    return [sum(weights[c] for c in fields) for fields in data]


def order(values):
    return sorted(range(len(values)), key=lambda i: (-values[i], i))


def tau_b(x, y):
    c = d = tx = ty = 0
    for i, j in combinations(range(len(x)), 2):
        a, b = x[i] - x[j], y[i] - y[j]
        if a == 0 and b == 0:
            continue
        if a == 0:
            tx += 1
        elif b == 0:
            ty += 1
        elif a * b > 0:
            c += 1
        else:
            d += 1
    denom = math.sqrt((c + d + tx) * (c + d + ty))
    return (c - d) / denom if denom else None


def gamma(x, y):
    signed = [(x[i]-x[j])*(y[i]-y[j]) for i,j in combinations(range(len(x)), 2)]
    c, d = sum(v > 0 for v in signed), sum(v < 0 for v in signed)
    return (c-d)/(c+d) if c+d else None


def metrics(truth, predicted, k=5):
    k = min(k, len(truth))
    best, chosen = order(truth), order(predicted)
    optimum = sum(truth[i] for i in best[:k])
    captured = sum(truth[i] for i in chosen[:k])
    return {"tau_b": tau_b(truth, predicted),
            "top1_is_true_max": int(truth[chosen[0]] == max(truth)),
            "top1_exact_id": int(chosen[0] == best[0]),
            "topk_exact_overlap": len(set(best[:k]) & set(chosen[:k])) / k,
            "relative_regret": (optimum-captured)/optimum if optimum else 0.0,
            "boundary_gap": truth[best[k-1]]-truth[best[k]] if k < len(truth) else None}


def confusion(a, b):
    out = [[0]*4 for _ in range(4)]
    for aa, bb in zip(a, b):
        for x, y in zip(aa, bb):
            out[x][y] += 1
    return out


def macro_f1(cm):
    return statistics.mean(2*cm[i][i]/(sum(cm[i])+sum(row[i] for row in cm))
                           if sum(cm[i])+sum(row[i] for row in cm) else 0 for i in range(4))


def counterexamples():
    truth = [[3,0,0], [2,1,0], [1,1,1], [0,0,1]]
    safe, harmful = [x[:] for x in truth], [x[:] for x in truth]
    safe[0][1] = 3
    harmful[3][0] = 3
    cm1, cm2 = confusion(truth, safe), confusion(truth, harmful)
    assert cm1 == cm2
    w = PROFILES["toy_1_5_10"]
    tr, sa, ha = scores(truth,w), scores(safe,w), scores(harmful,w)
    assert tr == [10,6,3,1] and sa == [20,6,3,1] and ha == [10,6,3,11]
    assert metrics(tr,sa,1)["relative_regret"] == 0
    assert metrics(tr,ha,1)["relative_regret"] == .9
    assert math.isclose(tau_b([1,1,2], [1,2,3]), math.sqrt(2/3))
    assert tau_b([1,1,1], [1,2,3]) is None
    checks = "hand-computed tie and reversal cases"
    try:
        from scipy.stats import kendalltau
        rng = random.Random(SEED)
        for _ in range(100):
            a = [rng.randrange(5) for _ in range(12)]
            b = [rng.randrange(5) for _ in range(12)]
            expected = float(kendalltau(a,b,variant="b").statistic)
            actual = tau_b(a,b)
            assert (actual is None and math.isnan(expected)) or math.isclose(actual,expected,abs_tol=1e-12)
        checks += "; scipy.stats.kendalltau agreement on 100 seeded cases"
    except ImportError:
        pass
    return {"same_confusion_different_rank": {
        "gold_labels":truth,"safe_labels":safe,"harmful_labels":harmful,
        "confusion":cm1,"accuracy":11/12,"macro_f1":macro_f1(cm1),
        "fpr":1/5,"truth_scores":tr,"safe_scores":sa,"harmful_scores":ha,
        "safe_top1":metrics(tr,sa,1),"harmful_top1":metrics(tr,ha,1)},
        "duplicate_example":{"same_subject_same_email_repeated":50,
                             "raw_sum_A_B":[50,10],"set_sum_A_B":[1,10],
                             "assumption":"50 identical observations of one fact; B one sensitive fact"},
        "weight_reversal":{"endpoint_A":[2],"endpoint_B":[3],
                           "scores_by_profile":{p:scores([[2],[3]],v) for p,v in PROFILES.items()}},
        "tie_metric":{"x":[1,1,2],"y":[1,2,3],"old_gamma":gamma([1,1,2],[1,2,3]),
                      "tau_b":tau_b([1,1,2],[1,2,3])},
        "paper_arithmetic":{"formula":"5.25 * 3 * 3 * 1.6", "computed_raw":5.25*3*3*1.6,
                            "computed_normalized":5.25*3*3*1.6/113.4*100,
                            "paper_printed_raw":72,"paper_printed_normalized":63.5},
        "self_checks":checks}


def corrupt(data, mode, rate, placement, seed):
    eligible = [(i,j) for i,fs in enumerate(data) for j,c in enumerate(fs)
                if mode == "MIX" or (mode == "FP" and c == 0) or (mode == "FN" and c != 0)]
    rng = random.Random(seed)
    # Match the entire confusion matrix across placements, not just error counts.
    # Round separately within each true class; report realized denominators.
    endpoints = list(range(len(data)))
    rng.shuffle(endpoints)
    priority = {v:i for i,v in enumerate(endpoints)}
    out = [fs[:] for fs in data]
    m = 0
    for c in range(4):
        candidates = [(i,j) for i,j in eligible if data[i][j] == c]
        rng.shuffle(candidates)
        if placement != "independent":
            candidates.sort(key=lambda pair:priority[pair[0]])
        count = int(rate*len(candidates)+.5)
        m += count
        for idx,(i,j) in enumerate(candidates[:count]):
            rr = random.Random(seed+7919*c+104729*idx)
            out[i][j] = 0 if mode == "FN" else rr.choice([x for x in range(4) if x != c])
    return out, m, len(eligible)


def bootstrap_mean(values, seed):
    values = [v for v in values if v is not None]
    if not values:
        return {"mean":None,"ci95":None,"n":0}
    rng = random.Random(seed)
    samples = sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(600))
    return {"mean":statistics.mean(values),"ci95":[samples[14],samples[584]],"n":len(values)}


def main():
    root = Path(__file__).resolve().parent
    cases = counterexamples()
    cohorts = []
    for c in range(COHORTS):
        rng = random.Random(SEED+c)
        cohorts.append([rng.choices(range(4), weights=[.50,.35,.08,.07], k=rng.randint(3,15))
                        for _ in range(30)])
    rows, summary = [], []
    for mi,mode in enumerate(["FP","FN","MIX"]):
        for ri,rate in enumerate([.05,.10,.20]):
            for placement in ["independent","clustered_endpoint"]:
                noisy = [corrupt(data,mode,rate,placement,SEED+100000*(mi+1)+1000*ri+c)
                         for c,data in enumerate(cohorts)]
                for pi,(profile,w) in enumerate(PROFILES.items()):
                    block=[]
                    for c,(data,(pred,m,n)) in enumerate(zip(cohorts,noisy)):
                        cm=confusion(data,pred)
                        row={"cohort":c,"mode":mode,"target_rate":rate,"placement":placement,
                             "weights":profile,"eligible":n,"changed":m,
                             "eligible_error_rate":m/n if n else 0,
                             "total_error_rate":m/sum(map(len,data)),"confusion":cm,
                             **metrics(scores(data,w),scores(pred,w))}
                        block.append(row)
                    rows.extend(block)
                    summary.append({"mode":mode,"target_rate":rate,"placement":placement,"weights":profile,
                        "n_cohorts":COHORTS,**{key:bootstrap_mean([r[key] for r in block],SEED+pi)
                        for key in ["eligible_error_rate","total_error_rate","tau_b",
                                    "top1_is_true_max","top1_exact_id","topk_exact_overlap","relative_regret"]}})
    paired = []
    lookup = {(r['mode'],r['target_rate'],r['placement'],r['weights'],r['cohort']):r for r in rows}
    for mode in ['FP','FN','MIX']:
        for rate in [.05,.10,.20]:
            differences=[]
            for c in range(COHORTS):
                a=lookup[(mode,rate,'independent','toy_1_5_10',c)]
                b=lookup[(mode,rate,'clustered_endpoint','toy_1_5_10',c)]
                assert a['confusion'] == b['confusion']
                differences.append(b['relative_regret']-a['relative_regret'])
            paired.append({'mode':mode,'target_rate':rate,'confusion_matrices_equal':True,
                           'clustered_minus_independent_regret':bootstrap_mean(differences,SEED)})
    result={"study":"synthetic assumption audit, not real classifier validation", "seed":SEED,
            "design":{"independent_cohorts":COHORTS,"endpoints_per_cohort":30,"fields_per_endpoint":[3,15],
                      "priors":[.50,.35,.08,.07],"weights":PROFILES,"k":5,
                      "ci":"percentile bootstrap over independent cohorts, 600 draws; descriptive synthetic uncertainty",
                      "pairing":"identical cohorts across modes/rates/weights; identical full confusion matrix across error placements; errors fixed across weights",
                      "limitations":["arbitrary generator and weights", "correlated errors only within endpoints",
                                     "not calibrated model errors", "no claim about real Korean/API performance"]},
            "counterexamples":cases,"summary":summary,"paired_placement_differences":paired,
            "original_pilot_sha256":hashlib.sha256((root/'scorer_noise_pilot.py').read_bytes()).hexdigest()}
    (root/'scorer_assumption_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'scorer_assumption_audit_trials.json').write_text(json.dumps({"cohorts":cohorts,"trials":rows},ensure_ascii=False),encoding='utf-8')
    print(json.dumps(cases,ensure_ascii=False,indent=2))
    print('mode rate placement tau_b top1_true_max regret ci95_regret')
    for r in summary:
        if r['weights']=='toy_1_5_10':
            print(r['mode'],r['target_rate'],r['placement'],round(r['tau_b']['mean'],3),
                  round(r['top1_is_true_max']['mean']*100,1),round(r['relative_regret']['mean']*100,2),
                  [round(v*100,2) for v in r['relative_regret']['ci95']])
    print('Saved summary and cohort-level evidence beside this script.')


if __name__ == '__main__':
    main()
