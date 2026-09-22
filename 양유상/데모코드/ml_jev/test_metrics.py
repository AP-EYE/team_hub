"""Small arithmetic checks with constructed outputs, no model execution."""
from ml_jev.metrics import method_metrics, percentile


def test_metrics_distinguish_error_unknown_and_sensitive_false_alarm():
    examples = [
        ('h-ok', 'HEALTH', 'HEALTH', .95),
        ('h-other', 'HEALTH', 'OTHER', .92),
        ('r-health', 'RELIGION', 'HEALTH', .91),
        ('other-health', 'OTHER', 'HEALTH', .97),
        ('unknown-ok', 'UNKNOWN', 'UNKNOWN', .99),
        ('unknown-forced', 'UNKNOWN', 'CONTACT', .85),
        ('government-error', 'GOVERNMENT_ID', None, None),
    ]
    rows = [{'id': case_id, 'expected': gold, 'slice': 'arithmetic', 'methods': {'semif': {
        'label': pred, 'score': score, 'latency_ms': latency}}}
        for latency, (case_id, gold, pred, score) in enumerate(examples, 1)]
    result = method_metrics(rows, 'semif', 96)
    assert result['status'] == 'partial' and result['count'] == 7
    assert result['correct'] == 2 and result['accuracy'] == round(2 / 7, 6)
    assert result['failed'] == 1
    assert result['confusion_matrix']['GOVERNMENT_ID']['ERROR'] == 1
    assert result['confusion_matrix']['UNKNOWN']['UNKNOWN'] == 1
    assert result['diagnostics']['health_false_alarms'] == ['r-health', 'other-health']
    assert result['diagnostics']['sensitive_type_misses'] == ['h-other', 'r-health', 'government-error']
    assert result['diagnostics']['sensitive_underflags'] == ['h-other', 'government-error']
    assert result['diagnostics']['personal_type_false_alarms_on_other'] == ['other-health']
    assert result['diagnostics']['unsupported_assertions_on_unknown'] == ['unknown-forced']
    assert result['high_confidence_errors'] == ['h-other', 'r-health', 'other-health']
    threshold = result['thresholds'][2]
    assert threshold['accepted'] == 4 and threshold['correct'] == 1
    assert threshold['coverage'] == round(4 / 7, 6) and threshold['selective_accuracy'] == .25
    assert result['latency_ms']['median'] == 4 and result['latency_ms']['p95'] == 6.7
    health = next(x for x in result['per_label'] if x['label'] == 'HEALTH')
    assert health['support'] == 2 and health['precision'] == round(1 / 3, 6)
    assert health['recall'] == .5 and health['f1'] == .4
    # UNKNOWN F1 = 2/3; HEALTH F1 = .4; six other classes F1 = 0.
    assert abs(result['macro_f1'] - ((.4 + 2 / 3) / 8)) < .000001


def test_unrun_and_zero_accepted_have_null_accuracy_not_false_zero():
    empty = method_metrics([], 'semif', 96)
    assert empty['count'] == 0 and empty['status'] == 'not_run'
    assert empty['accuracy'] is None and empty['macro_f1'] is None
    assert all(row['selective_accuracy'] is None for row in empty['thresholds'])
    rows = [{'id': 'u', 'expected': 'UNKNOWN', 'slice': 'unknown',
             'methods': {'semif': {'label': 'UNKNOWN', 'score': .99, 'latency_ms': 5}}}]
    observed = method_metrics(rows, 'semif', 1)
    assert observed['accuracy'] == 1 and observed['status'] == 'completed'
    assert all(row['coverage'] == 0 and row['accepted'] == 0 and row['selective_accuracy'] is None for row in observed['thresholds'])
    assert percentile([9], .95) == 9
