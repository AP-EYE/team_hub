from fastapi import FastAPI, Request, HTTPException
from .domain import PROFILES, CONSULTATIONS, actor_from_header, policy_for

app = FastAPI(title="Synthetic business API (not production)")

@app.get('/health')
def health():
    return {"status": "ok", "synthetic": True}

@app.get('/{mode}/{path:path}')
def business_api(mode: str, path: str, request: Request):
    if mode not in ('vulnerable', 'fixed'):
        raise HTTPException(404)
    actor = actor_from_header(request.headers.get('authorization', ''))
    public = path.startswith(('profile/public/', 'profile/leaky/')) or path == 'info/health'
    if not actor and not public:
        raise HTTPException(401, 'synthetic authentication required')
    policy = policy_for(path, actor, {})
    if path.startswith('documents/') and policy['expected'] == 'deny':
        raise HTTPException(403, 'document not shared')
    if mode == 'fixed' and policy['expected'] == 'deny':
        raise HTTPException(403, 'reviewed policy enforced')
    target = path.split('/')[-1]
    if path.startswith(('profile/private/', 'profile/public/', 'profile/leaky/')):
        profile = PROFILES.get(('alpha', target))
        if not profile:
            raise HTTPException(404)
        if path.startswith(('profile/public/', 'profile/leaky/')):
            result = {"tenant_id": "alpha", "member_id": target, "display_name": "가상닉네임", "bio": "공개 소개"}
            if path.startswith('profile/leaky/') and mode == 'vulnerable':
                result['phone'] = profile['phone']
            return result
        return profile
    if path.startswith('tenants/'):
        profile = PROFILES.get((path.split('/')[1], target))
        if not profile:
            raise HTTPException(404)
        return profile
    if path.startswith('consultations/'):
        if target not in CONSULTATIONS:
            raise HTTPException(404)
        return {"tenant_id": "alpha", "customer_no": target, "consult_reason": CONSULTATIONS[target], "appointment_id": "appt-demo-001"}
    if path == 'admin/export':
        return {"records": [v for (t, _), v in PROFILES.items() if t == 'alpha']}
    if path.startswith('documents/'):
        return {"tenant_id": "alpha", "owner_id": "U100", "document_id": path.split('/')[-1], "title": "합성 공유 문서", "content": "민감한 내용 없는 팀 일정"}
    if path.startswith('ambiguous/'):
        return {"tenant_id": "alpha", "member_id": target, "note": "공개 여부가 정해지지 않은 정보"}
    if path.startswith('orders/'):
        return {"tenant_id": "alpha", "customer_no": target, "order_id": "order-001", "mobile_no": "010-0000-0101", "shipping_addr": "가상시 예시구 테스트로 1", "item": "테스트 상품"}
    if path == 'info/health':
        return {"article_id": "info-001", "text": "우울증은 전문가와 상담할 수 있습니다. 이 글은 일반적인 건강 안내이며 개인의 진단 기록이 아닙니다."}
    raise HTTPException(404, 'fixture endpoint not found')
