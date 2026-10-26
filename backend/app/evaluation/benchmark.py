"""
LOCALYN Baseline Evaluation & Benchmarking Suite

Implements comparative evaluation across:
1. Baseline 1: Same Date + Same Ward
2. Baseline 2: Same Date + Same Ward + Naive Category String Match
3. LOCALYN Proposed Engine: Crosswalk Taxonomy + Spatial Point-in-Polygon + Multi-Feature Scorer

Computes Precision, Recall, and F1-Score against the Stratified Gold Set.
"""

from typing import List, Dict, Any, Tuple, Optional
from backend.app.fusion.gold_set import get_gold_set
from backend.app.fusion.matcher import CandidateGenerator, CandidatePair, score_temporal_compatibility
from backend.app.geo.wards import normalize_ward_name, resolve_point_to_ward, LEGACY_198_TO_225_MAP


def evaluate_predictions(
    y_true: List[str],
    y_pred: List[bool]
) -> Dict[str, Any]:
    """
    Computes confusion matrix and evaluation metrics.
    Only evaluates over definitive positive / negative pairs (skips uncertain).
    """
    tp = 0
    fp = 0
    fn = 0
    tn = 0

    for true_label, pred in zip(y_true, y_pred):
        if true_label == "uncertain":
            continue
        if true_label == "positive":
            if pred:
                tp += 1
            else:
                fn += 1
        elif true_label == "negative":
            if pred:
                fp += 1
            else:
                tn += 1

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round((2 * precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }


def _is_ward_compatible(w1: str, w2_raw: str, resolved: Optional[Dict[str, Any]]) -> bool:
    """Evaluates naive ward match between BBMP ward and BTP observation."""
    if not w1:
        return False
    if w2_raw and (w1 in w2_raw or w2_raw in w1):
        return True
    if resolved:
        w2_res = normalize_ward_name(resolved.get("ward_name"))
        if w2_res and (w1 in w2_res or w2_res in w1):
            return True
        if resolved.get("ward_id") in LEGACY_198_TO_225_MAP.get(w1, []):
            return True
        if w1 in (resolved.get("assembly_constituency") or "").lower():
            return True
    return False


def run_baseline_1_date_ward(pairs: List[Dict[str, Any]]) -> List[bool]:
    """
    Baseline 1: Matches if same calendar date and same ward name.
    Ignores category, taxonomy, and textual evidence.
    """
    preds = []
    for p in pairs:
        bbmp = p["bbmp"]
        btp = p["btp"]

        d1 = str(bbmp.get("grievance_date", ""))[:10]
        d2 = str(btp.get("timestamp", ""))[:10]
        same_date = bool(d1 and d2 and d1 == d2)

        w1 = normalize_ward_name(bbmp.get("ward_name"))
        w2_raw = normalize_ward_name(btp.get("location_name") or btp.get("location"))
        resolved = None
        if btp.get("latitude") and btp.get("longitude"):
            resolved = resolve_point_to_ward(btp["latitude"], btp["longitude"])

        same_ward = _is_ward_compatible(w1, w2_raw, resolved)
        preds.append(same_date and same_ward)
    return preds


def run_baseline_2_date_ward_category(pairs: List[Dict[str, Any]]) -> List[bool]:
    """
    Baseline 2: Same Date + Same Ward + Naive Category string match.
    Fails to capture administrative vocabulary mismatches without the crosswalk.
    """
    preds = []
    for p in pairs:
        bbmp = p["bbmp"]
        btp = p["btp"]

        d1 = str(bbmp.get("grievance_date", ""))[:10]
        d2 = str(btp.get("timestamp", ""))[:10]
        same_date = bool(d1 and d2 and d1 == d2)

        w1 = normalize_ward_name(bbmp.get("ward_name"))
        w2_raw = normalize_ward_name(btp.get("location_name") or btp.get("location"))
        resolved = None
        if btp.get("latitude") and btp.get("longitude"):
            resolved = resolve_point_to_ward(btp["latitude"], btp["longitude"])
        same_ward = _is_ward_compatible(w1, w2_raw, resolved)

        # Naive category match: exact string equality on raw category
        cat1 = str(bbmp.get("category", "")).lower()
        cat2 = str(btp.get("cause", "")).lower()
        subcat1 = str(bbmp.get("sub_category", "")).lower()

        # Naive matches without crosswalk taxonomy
        naive_cat_match = (cat1 in cat2 or cat2 in cat1 or subcat1 in cat2 or cat2 in subcat1)
        preds.append(same_date and same_ward and naive_cat_match)
    return preds


def run_localyn_model(pairs: List[Dict[str, Any]]) -> Tuple[List[bool], List[Dict[str, Any]]]:
    """
    LOCALYN Proposed Model:
    1. Candidate generator constraints
    2. Crosswalk taxonomy
    3. Point-in-polygon ward containment
    4. Multi-feature scoring (temporal + spatial + semantic + text)
    """
    generator = CandidateGenerator()
    preds = []
    detailed_pairs = []

    for p in pairs:
        bbmp = p["bbmp"]
        btp = p["btp"]

        is_cand, _ = generator.is_candidate(bbmp, btp)
        if not is_cand:
            preds.append(False)
            detailed_pairs.append({
                "pair_id": p.get("id"),
                "is_candidate": False,
                "is_match": False,
                "score": 0.0
            })
        else:
            pair = CandidatePair(bbmp, btp)
            preds.append(pair.is_match)
            detailed_pairs.append({
                "pair_id": p.get("id"),
                "is_candidate": True,
                "is_match": pair.is_match,
                "score": pair.match_score,
                "features": pair.features,
                "explanations": pair.explanations
            })

    return preds, detailed_pairs


def run_full_benchmark() -> Dict[str, Any]:
    """Runs all 3 baselines against the Gold Set and compiles the benchmark comparison."""
    gold_set = get_gold_set()
    y_true = [p["ground_truth"] for p in gold_set]

    # Baseline 1
    p1 = run_baseline_1_date_ward(gold_set)
    res_b1 = evaluate_predictions(y_true, p1)

    # Baseline 2
    p2 = run_baseline_2_date_ward_category(gold_set)
    res_b2 = evaluate_predictions(y_true, p2)

    # Baseline 3: LOCALYN
    p3, detailed = run_localyn_model(gold_set)
    res_localyn = evaluate_predictions(y_true, p3)

    return {
        "gold_set_size": len(gold_set),
        "evaluated_pairs": len([y for y in y_true if y != "uncertain"]),
        "results": {
            "baseline_1_date_ward": {
                "name": "Baseline 1: Same Date + Same Ward",
                "description": "Naive spatio-temporal co-occurrence; ignores civic category and text.",
                **res_b1
            },
            "baseline_2_date_ward_category": {
                "name": "Baseline 2: Same Date + Same Ward + Naive Category",
                "description": "Requires matching date, ward, and raw category string without crosswalk.",
                **res_b2
            },
            "localyn_proposed": {
                "name": "LOCALYN: Crosswalk + Point-in-Polygon + Multi-Feature Scorer",
                "description": "Candidate gating, 161-entry crosswalk, polygon resolution & decoupled features.",
                **res_localyn
            }
        },
        "detailed_predictions": detailed
    }


def generate_benchmark_markdown_table(benchmark_data: Dict[str, Any]) -> str:
    """Formats benchmark results into a clean markdown table suitable for research papers."""
    results = benchmark_data["results"]
    b1 = results["baseline_1_date_ward"]
    b2 = results["baseline_2_date_ward_category"]
    loc = results["localyn_proposed"]

    table = [
        "| Approach | TP | FP | FN | Precision | Recall | F1-Score |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        f"| **Baseline 1 (Date + Ward)** | {b1['tp']} | {b1['fp']} | {b1['fn']} | {b1['precision']:.3f} | {b1['recall']:.3f} | **{b1['f1']:.3f}** |",
        f"| **Baseline 2 (Date + Ward + Naive Cat)** | {b2['tp']} | {b2['fp']} | {b2['fn']} | {b2['precision']:.3f} | {b2['recall']:.3f} | **{b2['f1']:.3f}** |",
        f"| **LOCALYN (Ours: Crosswalk + PIP + Scorer)** | {loc['tp']} | {loc['fp']} | {loc['fn']} | **{loc['precision']:.3f}** | **{loc['recall']:.3f}** | **{loc['f1']:.3f}** |"
    ]
    return "\n".join(table)
