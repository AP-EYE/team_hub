"""Deterministic baseline and reviewed semantic mappings. AI suggestions are separate."""
import re

MAPPINGS = [
    {"source_path": "member_id", "canonical": "data_subject.id", "role": "data_subject", "reason": "합성 회원 서비스 계약에 등록된 회원번호"},
    {"source_path": "customer_no", "canonical": "data_subject.id", "role": "data_subject", "reason": "회원 서비스와 동일한 alpha 회원번호 체계"},
    {"source_path": "owner_id", "canonical": "resource.owner.id", "role": "resource_owner", "reason": "문서 소유자, 요청자와 구별"},
    {"source_path": "phone", "canonical": "person.phone", "role": "attribute", "reason": "회원 연락처"},
    {"source_path": "mobile_no", "canonical": "person.phone", "role": "attribute", "reason": "주문 배송 연락처 별칭"},
    {"source_path": "address", "canonical": "person.address", "role": "attribute", "reason": "회원 주소"},
    {"source_path": "shipping_addr", "canonical": "person.address", "role": "attribute", "reason": "배송 주소 별칭"},
    {"source_path": "name", "canonical": "person.name", "role": "attribute", "reason": "회원 이름"},
    {"source_path": "email", "canonical": "person.email", "role": "attribute", "reason": "회원 이메일"},
    {"source_path": "consult_reason", "canonical": "consultation.reason", "role": "attribute", "reason": "개인 상담 입력 내용"},
    {"source_path": "order_id", "canonical": "resource.order.id", "role": "resource", "reason": "주문 식별자, 법정 고유식별정보 아님"},
    {"source_path": "appointment_id", "canonical": "resource.appointment.id", "role": "resource", "reason": "예약 식별자, 법정 고유식별정보 아님"},
]
for mapping in MAPPINGS:
    mapping.update(source="approved_registry", status="approved", namespace="synthetic-member-v1")
BY_FIELD = {m['source_path']: m for m in MAPPINGS}
SECRET_KEYS = {"authorization", "cookie", "set-cookie", "password", "access_token", "refresh_token", "api_key", "secret"}


def classify_field(key, value, path=""):
    result = {"path": path or key, "label": "OTHER", "legal_category": "분류 대상 아님", "source": "rules-v1", "confidence": None}
    if key in {'member_id', 'customer_no', 'owner_id'}:
        result.update(label="SERVICE_ID", legal_category="서비스 식별자 / 맥락상 개인정보")
    elif key in {'phone', 'tel', 'mobile_no'} or (isinstance(value, str) and re.fullmatch(r'010-\d{4}-\d{4}', value)):
        result.update(label="PHONE", legal_category="일반 개인정보")
    elif key in {'address', 'shipping_addr'}:
        result.update(label="ADDRESS", legal_category="일반 개인정보")
    elif key == 'name':
        result.update(label="NAME", legal_category="일반 개인정보")
    elif key == 'email':
        result.update(label="EMAIL", legal_category="일반 개인정보")
    elif key == 'consult_reason':
        if any(term in str(value) for term in ['진단을 받고', '약을 복용', '치료 중', '신앙은', '종교는']):
            result.update(label="SENSITIVE_CANDIDATE", legal_category="제23조 민감정보 후보 / 문맥 검토 필요")
        else:
            result.update(label="PERSONAL_CONTEXT", legal_category="일반 상담 맥락 / 민감성 미확정")
    elif key in SECRET_KEYS:
        result.update(label="SECRET", legal_category="인증 비밀 / 개인정보 법정 분류와 별개")
    mapping = BY_FIELD.get(key)
    if mapping:
        result['canonical'] = mapping['canonical']
    return result


def inspect_payload(payload, prefix=''):
    privacy = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f'{prefix}.{key}' if prefix else key
            if isinstance(value, (dict, list)):
                privacy.extend(inspect_payload(value, path))
            else:
                item = classify_field(key.lower(), value, path)
                if item['label'] != 'OTHER':
                    privacy.append(item)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            privacy.extend(inspect_payload(value, f'{prefix}[{index}]'))
    return privacy


def redact(payload):
    if isinstance(payload, list):
        return [redact(v) for v in payload]
    if isinstance(payload, dict):
        result = {}
        for key, value in payload.items():
            if key.lower() in SECRET_KEYS:
                result[key] = '[REMOVED]'
            elif isinstance(value, (dict, list)):
                result[key] = redact(value)
            elif classify_field(key.lower(), value)['label'] in {'PHONE', 'ADDRESS', 'NAME', 'EMAIL', 'SENSITIVE_CANDIDATE', 'PERSONAL_CONTEXT'}:
                result[key] = '[REDACTED:' + classify_field(key.lower(), value)['label'] + ']'
            else:
                result[key] = value
        return result
    return payload


def records(payload):
    """Only explicit fixture records; no fuzzy name join or arbitrary recursive ID inference."""
    if not isinstance(payload, dict):
        return []
    candidates = payload.get('records', [payload])
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict) and item.get('tenant_id') and (item.get('member_id') or item.get('customer_no') or item.get('owner_id'))]


def observations(payload):
    result = []
    for record in records(payload):
        subject = record.get('member_id') or record.get('customer_no') or record.get('owner_id')
        for item in inspect_payload(record):
            if item.get('canonical'):
                result.append({"tenant": record['tenant_id'], "namespace": "synthetic-member-v1", "subject_id": subject, "canonical": item['canonical'], "label": item['label']})
    return result


def decide(policy, status_code, body):
    if policy['state'] == 'unknown':
        return 'needs_review', 'UNKNOWN', policy['reason'], []
    successful = 200 <= status_code < 300
    if not successful:
        if status_code in (401, 403) and policy['expected'] == 'deny':
            return 'blocked', policy['category'], '정책상 거부 대상이 실제 401/403으로 차단됨', []
        return 'needs_review', policy['category'], '예상 동작과 다른 오류 응답 또는 서비스 실패', []
    if policy['expected'] == 'deny':
        if not records(body):
            return 'needs_review', policy['category'], '성공 상태코드이나 대상 데이터 증거가 없어 비인가 노출 확정 보류', []
        return 'confirmed', policy['category'], '검토된 정책의 거부 조건인데 대상 데이터가 성공 응답에 포함됨', list(body) if isinstance(body, dict) else []
    if policy['expected'] == 'allow_fields':
        if not isinstance(body, dict) or not body.get('member_id'):
            return 'needs_review', 'BOPLA', '예상한 공개 프로필 응답 형식이 아니므로 검토 필요', []
        extra = sorted(set(body) - set(policy['public_fields'])) if isinstance(body, dict) else []
        if extra:
            return 'confirmed', 'BOPLA', '공개 허용 목록에 없는 필드가 응답에 포함됨', extra
        return 'allowed', 'NONE', '승인된 공개 필드만 반환됨; 타인 신원이라는 이유로 경보하지 않음', []
    return 'allowed', 'NONE', policy['reason'], []
