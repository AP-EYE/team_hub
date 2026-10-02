"""개인정보 분류 오류가 엔드포인트 수정 우선순위를 얼마나 바꾸는지 재는 방법 시연.

주의: 합성 데이터와 가정한 가중치로 돌린 **방법 시연**이다. 실제 API 결과가 아니다.
- 엔드포인트 30개, 각 3~15개 필드를 무작위로 만든다.
- 필드 정답 등급: 비식별 / 일반 / 고유식별 / 민감 (ARCHITECTURE 4단계 분류)
- 가중치(가정): 비식별 0, 일반 1, 고유식별 5, 민감 10. 실제 가중치는 처분 사례 수집 후 정한다.
- 엔드포인트 점수 = 노출 필드 가중치 합. 점수 순으로 수정 우선순위를 매긴다.
- 정답 라벨에 오류를 일정 비율로 섞어 순위가 얼마나 바뀌는지 잰다.

오류 종류:
  FP  오탐만: 개인정보가 아닌 필드를 개인정보(일반·고유식별·민감 중 하나)로 잘못 분류
  FN  미탐만: 개인정보 필드를 비식별로 잘못 분류
  MIX 둘 다: 무작위 필드의 등급을 다른 등급으로 바꿈

지표:
  kendall   정답 순위와 오류 순위의 켄달 타우 (1이면 순위 동일, 0이면 무관)
  top5      정답 상위 5개 중 오류 순위 상위 5개에도 든 비율
  top1      1순위 엔드포인트가 그대로인 비율

실행: python scorer_noise_pilot.py   (네트워크 불필요, 고정 시드로 매번 같은 결과)
"""
import random

CLASSES = ["비식별", "일반", "고유식별", "민감"]
WEIGHT = {"비식별": 0, "일반": 1, "고유식별": 5, "민감": 10}
PRIOR = [0.50, 0.35, 0.08, 0.07]
N_ENDPOINTS, TRIALS, SEED = 30, 300, 20260929
RATES = [0.0, 0.05, 0.10, 0.20, 0.30]


def make_endpoints(rng):
    return [[rng.choices(CLASSES, PRIOR)[0] for _ in range(rng.randint(3, 15))]
            for _ in range(N_ENDPOINTS)]


def scores(endpoints):
    return [sum(WEIGHT[c] for c in fields) for fields in endpoints]


def rank_order(sc):
    # 점수 내림차순, 동점은 엔드포인트 번호 순
    return sorted(range(len(sc)), key=lambda i: (-sc[i], i))


def kendall(a, b):
    n = len(a)
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (a[i] - a[j]) * (b[i] - b[j])
            if s > 0:
                conc += 1
            elif s < 0:
                disc += 1
    return (conc - disc) / max(1, conc + disc)


def corrupt(endpoints, rate, mode, rng):
    out = []
    for fields in endpoints:
        new = []
        for c in fields:
            if rng.random() >= rate:
                new.append(c)
                continue
            if mode == "FP":
                new.append(rng.choice(CLASSES[1:]) if c == "비식별" else c)
            elif mode == "FN":
                new.append("비식별" if c != "비식별" else c)
            else:
                new.append(rng.choice([x for x in CLASSES if x != c]))
        out.append(new)
    return out


def main():
    rng = random.Random(SEED)
    print("방법 시연 (합성 데이터, 가정 가중치). 실제 결과 아님.")
    print(f"엔드포인트 {N_ENDPOINTS}개, 반복 {TRIALS}회, 시드 {SEED}\n")
    print(f"{'오류':<4} {'비율':>5} {'kendall':>8} {'top5':>6} {'top1':>6}")
    for mode in ["FP", "FN", "MIX"]:
        for rate in RATES:
            k = t5 = t1 = 0.0
            for _ in range(TRIALS):
                ep = make_endpoints(rng)
                true_sc = scores(ep)
                noisy_sc = scores(corrupt(ep, rate, mode, rng))
                k += kendall(true_sc, noisy_sc)
                tr, nr = rank_order(true_sc), rank_order(noisy_sc)
                t5 += len(set(tr[:5]) & set(nr[:5])) / 5
                t1 += tr[0] == nr[0]
            print(f"{mode:<4} {rate:>5.0%} {k/TRIALS:>8.3f} {t5/TRIALS:>6.1%} {t1/TRIALS:>6.1%}")
        print()


if __name__ == "__main__":
    main()
