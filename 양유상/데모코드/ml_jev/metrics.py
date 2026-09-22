"""Metrics for a frozen single-label development set, including abstention."""
from collections import Counter
import math
import statistics

LABELS = ('HEALTH', 'RELIGION', 'CONTACT', 'GOVERNMENT_ID', 'PERSON_NAME', 'ACCOUNT_ID', 'OTHER', 'UNKNOWN')
PERSON_RELATED = frozenset(LABELS[:6])
SENSITIVE_TECHNICAL = frozenset(('HEALTH', 'RELIGION', 'GOVERNMENT_ID'))


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def ratio(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def method_metrics(rows, method, dataset_count):
    observed = [(row, row['methods'][method]) for row in rows if method in row.get('methods', {})]
    count = len(observed)
    matrix = {gold: {pred: 0 for pred in (*LABELS, 'ERROR')} for gold in LABELS}
    slices = {}
    latency = []
    errors = 0
    for row, result in observed:
        pred = result.get('label') if result.get('label') in LABELS else 'ERROR'
        matrix[row['expected']][pred] += 1
        correct = pred == row['expected']
        bucket = slices.setdefault(row['slice'], {'slice': row['slice'], 'count': 0, 'correct': 0})
        bucket['count'] += 1
        bucket['correct'] += int(correct)
        errors += int(pred == 'ERROR')
        value = result.get('latency_ms')
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
            latency.append(value)
    per_label = []
    for label in LABELS:
        support = sum(matrix[label].values())
        predicted = sum(matrix[gold][label] for gold in LABELS)
        true_positive = matrix[label][label]
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label.append({'label': label, 'support': support, 'predicted': predicted,
                          'precision': round(precision, 6) if count else None,
                          'recall': round(recall, 6) if count else None,
                          'f1': round(f1, 6) if count else None})
    correct = sum(matrix[label][label] for label in LABELS)
    health_false_alarms = [row['id'] for row, result in observed if row['expected'] not in ('HEALTH', 'UNKNOWN') and result.get('label') == 'HEALTH']
    health_misses = [row['id'] for row, result in observed if row['expected'] == 'HEALTH' and result.get('label') != 'HEALTH']
    sensitive_misses = [row['id'] for row, result in observed if row['expected'] in SENSITIVE_TECHNICAL and result.get('label') != row['expected']]
    sensitive_underflags = [row['id'] for row, result in observed if row['expected'] in SENSITIVE_TECHNICAL and result.get('label') in ('OTHER', 'UNKNOWN', None)]
    personal_false_alarms = [row['id'] for row, result in observed if row['expected'] == 'OTHER' and result.get('label') in PERSON_RELATED]
    unsupported_assertions = [row['id'] for row, result in observed if row['expected'] == 'UNKNOWN' and result.get('label') in LABELS and result.get('label') != 'UNKNOWN']
    complete_pairs = []
    pairs = {}
    for row, result in observed:
        if row.get('pair_id'):
            pairs.setdefault(row['pair_id'], []).append((row, result))
    for pair_id, values in pairs.items():
        if len(values) == 2:
            complete_pairs.append({'pair_id': pair_id, 'case_ids': [row['id'] for row, _ in values],
                                   'both_correct': all(result.get('label') == row['expected'] for row, result in values)})
    high_confidence_errors = []
    thresholds = []
    if method == 'semif':
        for row, result in observed:
            score = result.get('score')
            if isinstance(score, (int, float)) and math.isfinite(score) and score >= .9 and result.get('label') != row['expected']:
                high_confidence_errors.append(row['id'])
        for threshold in (.6, .8, .9):
            accepted = [(row, result) for row, result in observed
                        if result.get('label') in LABELS and result.get('label') != 'UNKNOWN'
                        and isinstance(result.get('score'), (int, float))
                        and math.isfinite(result['score']) and result['score'] >= threshold]
            accepted_correct = sum(row['expected'] == result['label'] for row, result in accepted)
            thresholds.append({'threshold': threshold, 'coverage': ratio(len(accepted), count),
                               'selective_accuracy': ratio(accepted_correct, len(accepted)),
                               'accepted': len(accepted), 'correct': accepted_correct,
                               'review': count - len(accepted)})
    return {'status': 'completed' if count == dataset_count else ('partial' if count else 'not_run'),
            'count': count, 'correct': correct, 'accuracy': ratio(correct, count),
            'macro_f1': round(sum(x['f1'] for x in per_label) / len(LABELS), 6) if count else None,
            'macro_f1_scope': 'All eight labels; zero division is zero. Partial runs may have unobserved label supports.',
            'failed': errors, 'confusion_matrix': matrix, 'per_label': per_label,
            'latency_ms': {'count': len(latency), 'median': round(statistics.median(latency), 3) if latency else None,
                           'p95': round(percentile(latency, .95), 3) if latency else None,
                           'p95_method': 'linear interpolation at (n - 1) * 0.95'},
            'slices': [{**x, 'accuracy': ratio(x['correct'], x['count'])} for x in sorted(slices.values(), key=lambda x: x['slice'])],
            'high_confidence_errors': high_confidence_errors, 'high_confidence_error_threshold': .9 if method == 'semif' else None,
            'thresholds': thresholds,
            'review_definition': 'Predicted UNKNOWN, failed output, or SemIf score below the chosen threshold. UNKNOWN remains a real gold category in raw accuracy.',
            'diagnostics': {'health_false_alarms': health_false_alarms, 'health_misses': health_misses,
                            'sensitive_type_misses': sensitive_misses, 'sensitive_underflags': sensitive_underflags,
                            'personal_type_false_alarms_on_other': personal_false_alarms,
                            'unsupported_assertions_on_unknown': unsupported_assertions,
                            'sensitive_definition': 'Technical HEALTH, RELIGION, GOVERNMENT_ID categories; not a legal sensitivity determination.',
                            'health_false_alarm_definition': 'Predicted HEALTH on known non-HEALTH gold; excludes UNKNOWN gold, which is counted as unsupported assertion.',
                            'sensitive_type_miss_definition': 'Any incorrect type on a technical sensitive gold, including confusion between two sensitive types.',
                            'sensitive_underflag_definition': 'Technical sensitive gold predicted OTHER or UNKNOWN, or failed output.'},
            'contrast_pairs': {'evaluated_pairs': len(complete_pairs),
                               'both_correct': sum(x['both_correct'] for x in complete_pairs), 'pairs': complete_pairs}}
