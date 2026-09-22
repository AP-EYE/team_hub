"""Explicit synthetic identities and reviewed policy oracle; never inferred by AI."""
TOKENS = {
    "demo-alice": {"id": "U100", "name": "alice", "tenant": "alpha", "role": "member"},
    "demo-bob": {"id": "U200", "name": "bob", "tenant": "alpha", "role": "member"},
    "demo-admin": {"id": "A001", "name": "admin", "tenant": "alpha", "role": "admin"},
    "demo-mallory": {"id": "U100", "name": "mallory", "tenant": "beta", "role": "member"},
}
PROFILES = {
    ("alpha", "U100"): {"tenant_id": "alpha", "member_id": "U100", "name": "가상회원 가", "phone": "010-0000-0101", "address": "가상시 예시구 테스트로 1", "email": "alice@example.invalid"},
    ("alpha", "U200"): {"tenant_id": "alpha", "member_id": "U200", "name": "가상회원 나", "phone": "010-0000-0202", "address": "가상시 예시구 테스트로 2", "email": "bob@example.invalid"},
    ("beta", "U100"): {"tenant_id": "beta", "member_id": "U100", "name": "가상회원 다", "phone": "010-0000-0303", "address": "가상시 검증구 테스트로 3", "email": "mallory@example.invalid"},
}
CONSULTATIONS = {"U100": "지난달 우울증 진단을 받고 약을 복용 중이며 치료 상담을 원합니다.", "U200": "상담실 운영 시간과 주차 가능 여부가 궁금합니다."}


def actor_from_header(header):
    token = header.removeprefix("Bearer ") if header else ""
    return TOKENS.get(token)


def policy_for(path, actor, response):
    """Target ownership comes from fixture contract/path, not returned identity alone."""
    actor = actor or {"id": "anonymous", "tenant": "none", "role": "anonymous"}
    parts = path.strip("/").split("/")
    target = parts[-1] if parts else ""
    tenant = "alpha"
    policy = {"version": "reviewed-fixture-policy-v1", "state": "approved", "expected": "deny", "category": "BOLA", "public_fields": []}
    if path.startswith("ambiguous/"):
        return {**policy, "state": "unknown", "expected": "review", "category": "UNKNOWN", "reason": "업무 권한 정책이 제공되지 않아 응답만으로 인가 위반 확정 불가"}
    if path.startswith("profile/public/") or path.startswith("profile/leaky/"):
        return {**policy, "expected": "allow_fields", "category": "BOPLA", "public_fields": ["tenant_id", "member_id", "display_name", "bio"], "reason": "공개 프로필: 별명·소개·서비스 식별자만 공개 허용"}
    if path == "info/health":
        return {**policy, "expected": "allow", "category": "NONE", "reason": "개인의 진료 기록이 아닌 공개 안내문"}
    if path == "admin/export":
        permitted = actor["role"] == "admin" and actor["tenant"] == "alpha"
        return {**policy, "expected": "allow" if permitted else "deny", "category": "BFLA", "reason": "alpha 테넌트 관리자 전용 내보내기"}
    if path.startswith("documents/"):
        permitted = actor["tenant"] == "alpha" and (actor["id"] == "U100" or (target == "shared" and actor["id"] == "U200"))
        return {**policy, "expected": "allow" if permitted else "deny", "reason": "객체 소유자 또는 명시된 공유 대상만 조회 허용"}
    if path.startswith("tenants/"):
        tenant, target = parts[1], parts[-1]
    permitted = actor["tenant"] == tenant and (actor["id"] == target or actor["role"] == "admin")
    return {**policy, "expected": "allow" if permitted else "deny", "reason": "동일 테넌트의 소유자 또는 관리자만 조회 허용"}


SCENARIOS = [
    {"id": "owner", "title": "소유자의 비공개 프로필 조회", "actor": "alice", "path": "profile/private/U100"},
    {"id": "bola_profile", "title": "타인의 비공개 프로필 조회", "actor": "bob", "path": "profile/private/U100"},
    {"id": "bola_consult", "title": "타인의 상담 내용 조회", "actor": "bob", "path": "consultations/U100"},
    {"id": "public", "title": "타인의 공개 프로필 정상 조회", "actor": "bob", "path": "profile/public/U100"},
    {"id": "bopla", "title": "공개 프로필의 비공개 필드 과다 반환", "actor": "bob", "path": "profile/leaky/U100"},
    {"id": "bfla", "title": "일반 회원의 관리자 기능 호출", "actor": "bob", "path": "admin/export"},
    {"id": "admin", "title": "관리자의 허용된 내보내기", "actor": "admin", "path": "admin/export"},
    {"id": "shared", "title": "명시적으로 공유된 문서 조회", "actor": "bob", "path": "documents/shared"},
    {"id": "unshared", "title": "공유되지 않은 문서 차단", "actor": "bob", "path": "documents/private"},
    {"id": "unknown", "title": "정책 없는 엔드포인트 검토 보류", "actor": "bob", "path": "ambiguous/U100"},
    {"id": "tenant", "title": "다른 테넌트의 동일 회원번호 조회", "actor": "bob", "path": "tenants/beta/profile/U100"},
    {"id": "beta_owner", "title": "beta 소유자의 동일 번호 정상 조회", "actor": "mallory", "path": "tenants/beta/profile/U100"},
    {"id": "anonymous", "title": "인증 없는 비공개 조회 차단", "actor": "anonymous", "path": "profile/private/U100"},
    {"id": "general_info", "title": "건강 키워드가 있는 일반 안내문", "actor": "bob", "path": "info/health"},
    {"id": "order", "title": "소유자의 주문·별칭 필드 조회", "actor": "alice", "path": "orders/U100"},
    {"id": "general_consult", "title": "건강정보가 아닌 본인 상담 조회", "actor": "bob", "path": "consultations/U200"},
]
