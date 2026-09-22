"use strict";

const LABELS = ["HEALTH", "RELIGION", "CONTACT", "GOVERNMENT_ID", "PERSON_NAME", "ACCOUNT_ID", "OTHER", "UNKNOWN"];
const NAMES = {HEALTH:"건강 정보", RELIGION:"종교 정보", CONTACT:"연락처", GOVERNMENT_ID:"공적 식별자", PERSON_NAME:"이름", ACCOUNT_ID:"계정 식별자", OTHER:"해당 없음", UNKNOWN:"판단 보류", ERROR:"실행 오류"};
const METHODS = {semif:"SemIf · 선택지 점수", json:"Ollama · JSON 생성", rules:"고정 규칙"};
const SLICE_NAMES = {direct:"명확한 개인정보", explicit:"명확한 개인정보", context:"문맥 구분", contextual:"문맥 구분", ambiguous:"모호한 입력", ambiguity:"모호한 입력", negative:"일반 정보", public:"일반 정보", schema:"필드 의미", alias:"필드 별칭", injection:"프롬프트 공격", prompt_injection:"프롬프트 공격", negation:"부정·일반 문장", contrast:"대조 예시", synthetic:"합성 예시"};
Object.assign(SLICE_NAMES,{ambiguous_alias:"모호한 별칭",clinical_result:"검사 결과",context_contrast:"문맥 대조",explicit_schema:"명확한 스키마",field_only:"필드 정보만 있음",field_semantics:"필드 의미",home_address:"거주지 주소",hypothetical:"가정한 상황",identifier_semantics:"식별자의 역할",insufficient_schema:"스키마 정보 부족",medication:"복약 정보",mixed_value:"여러 의미가 섞인 값",name_component:"이름의 일부",noisy_korean:"오타·구어체 한국어",opaque_alias:"의미가 불명확한 별칭",ordinary_public:"일반 공개 정보",third_party:"제삼자에 관한 언급"});
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const num = value => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) ? Number(value) : null;
const pct = (value, digits = 1) => num(value) === null ? "미측정" : `${(Number(value) * 100).toFixed(digits)}%`;
const duration = value => num(value) === null ? "미측정" : Number(value) < 1000 ? `${Number(value).toFixed(0)} ms` : `${(Number(value) / 1000).toFixed(2)}초`;
const labelName = value => state?.labels?.[value]?.name || NAMES[value] || value || "결과 없음";
const sliceName = value => SLICE_NAMES[value] || value || "기타";
const scopeText = value => !value || String(value).includes("Authored development set") ? "직접 작성한 개발 평가셋 · 독립 검증셋 및 전문가 검수 없음" : value;
let state = null;
let selectedId = null;
let isClassifying = false;
let isRefreshing = false;
let liveSnapshot = null;

function showNotice(message, error = false) { $("notice").textContent = message; $("notice").classList.toggle("error", error); $("notice").hidden = !message; }
function currentCase() { return (state?.cases || []).find(item => item.id === selectedId); }
function evalRows() { return Array.isArray(state?.evaluation?.rows) ? state.evaluation.rows : []; }
function currentRow() { return evalRows().find(item => item.id === selectedId); }
function methodResult(row, method) { return row?.methods?.[method] || null; }
function inputs() { return {text:$("input-text").value, field_path:$("field-path").value, description:$("field-description").value, input_mode:$("input-mode").value, method:$("method").value}; }
function sameOriginal(input = inputs()) { const item = currentCase(); return !!item && input.input_mode === "full" && input.text === String(item.text ?? "") && input.field_path === String(item.field_path ?? "") && input.description === String(item.description ?? ""); }
function correctResult(result, expected) { return result && typeof result.label === "string" && result.label === expected; }
function statusResult(result) { return result && result.label && !["error", "failed", "unavailable"].includes(result.status); }
function resultScore(result) { return num(result?.score); }
function pill(text, style = "neutral") { return `<span class="pill ${esc(style)}">${esc(text)}</span>`; }
function empty(message) { return `<div class="empty">${esc(message)}</div>`; }

async function fetchJSON(url, options) {
  const response = await fetch(url, options);
  let payload;
  try { payload = await response.json(); } catch { throw new Error(`응답을 읽을 수 없습니다. HTTP ${response.status}`); }
  if (!response.ok) { const detail = payload.detail || payload.error || payload.message; throw new Error(typeof detail === "string" ? detail : `요청 실패 · HTTP ${response.status}`); }
  return payload;
}

async function refreshState(silent = false) {
  if (isRefreshing) return;
  isRefreshing = true;
  $("refresh").disabled = true;
  try {
    state = await fetchJSON("/api/jev/state");
    renderRuntime(); renderFilterOptions(); renderCases(); renderComparison(); renderEvaluation(); renderGuide();
    if (!selectedId && state.cases?.length) selectCase(state.cases[0].id, false);
    else renderExpectation();
    if (!silent) showNotice("");
  } catch (error) {
    $("runtime-status").textContent = "데이터 연결 실패";
    $("runtime-status").className = "runtime-status error";
    if (!silent || !state) showNotice(`실험 데이터를 불러오지 못했습니다. ${error.message}`, true);
    if (!state) $("case-list").innerHTML = empty("예시를 가져오지 못했습니다. 새로고침으로 다시 연결할 수 있습니다.");
  } finally { isRefreshing = false; $("refresh").disabled = false; }
}

function renderRuntime() {
  const runtime = state?.runtime || {};
  const ready = ["ready", "ok", "healthy", "running"].includes(runtime.status);
  $("runtime-status").textContent = ready ? runtime.busy ? "로컬 모델 사용 중" : "로컬 모델 준비됨" : runtime.status === "loading" ? "로컬 모델 로딩 중" : "로컬 상태 확인 필요";
  $("runtime-status").className = `runtime-status ${ready ? "ready" : ""}`;
  $("runtime-detail").textContent = `${runtime.model || "모델 정보 미수신"} · ${runtime.backend === "actual_semif_llamacpp" ? "실제 SemIf · 로컬 CPU" : runtime.backend || "실행 환경 미수신"} · ${runtime.external_inference === false ? "외부 추론 없음" : "외부 추론 여부 미확인"}`;
  const count = state?.cases?.length || 0;
  $("footer-status").textContent = `합성 예시 ${count}개 · 마지막 조회 ${new Date().toLocaleTimeString("ko-KR", {hour:"2-digit", minute:"2-digit", second:"2-digit"})}`;
}

function renderFilterOptions() {
  const label = $("case-label").value;
  const slice = $("case-slice").value;
  $("case-label").innerHTML = `<option value="all">모든 분류</option>` + LABELS.map(key => `<option value="${esc(key)}">${esc(labelName(key))}</option>`).join("");
  const slices = [...new Set((state?.cases || []).map(item => item.slice).filter(Boolean))];
  $("case-slice").innerHTML = `<option value="all">모든 유형</option>` + slices.map(key => `<option value="${esc(key)}">${esc(sliceName(key))}</option>`).join("");
  $("case-label").value = LABELS.includes(label) ? label : "all";
  $("case-slice").value = slices.includes(slice) ? slice : "all";
}

function renderCases() {
  const query = $("case-search").value.trim().toLowerCase();
  const label = $("case-label").value;
  const slice = $("case-slice").value;
  const errorsOnly = $("errors-only").checked;
  const cases = (state?.cases || []).filter(item => {
    const result = methodResult(evalRows().find(row => row.id === item.id), "semif");
    return (label === "all" || item.expected === label) && (slice === "all" || item.slice === slice) && (!errorsOnly || (statusResult(result) && !correctResult(result, item.expected))) && (!query || [item.id, item.field_path, item.description, item.text].some(value => String(value || "").toLowerCase().includes(query)));
  });
  $("case-count").textContent = `${cases.length} / ${state?.cases?.length || 0}`;
  $("case-list").innerHTML = cases.length ? cases.map(item => {
    const result = methodResult(evalRows().find(row => row.id === item.id), "semif");
    const wrong = statusResult(result) && !correctResult(result, item.expected);
    return `<button type="button" class="case-item ${selectedId === item.id ? "selected" : ""}" data-case="${esc(item.id)}" aria-pressed="${selectedId === item.id}"><span class="case-top"><span class="case-id">${esc(item.id)}</span>${pill(labelName(item.expected))}</span><span class="case-preview">${esc(item.text || item.description || item.field_path || "빈 값 예시")}</span><span class="case-bottom"><span>${esc(sliceName(item.slice))}</span>${wrong ? `<span class="case-error">SemIf 오분류</span>` : item.pair_id ? `<span>대조 예시 있음</span>` : ""}</span></button>`;
  }).join("") : empty(errorsOnly ? "현재 조건에서 기록된 오분류가 없습니다." : "검색 조건에 맞는 예시가 없습니다.");
}

function selectCase(id, scroll = false) {
  const item = (state?.cases || []).find(entry => entry.id === id);
  if (!item) return;
  selectedId = id;
  $("field-path").value = item.field_path || "";
  $("field-description").value = item.description || "";
  $("input-text").value = item.text || "";
  $("input-mode").value = "full";
  $("selected-case").textContent = id;
  resetLiveResult(); renderCases(); renderExpectation(); renderComparison(); renderInputMode();
  if (scroll) { changeTab("experiment"); document.querySelector(".editor").scrollIntoView({behavior:"smooth", block:"start"}); }
}

function renderExpectation() {
  const item = currentCase();
  $("case-expectation").hidden = !item;
  if (!item) return;
  const original = sameOriginal();
  $("case-expectation").className = `expectation${original ? "" : " changed"}`;
  $("case-expectation").innerHTML = original ? `데모 기준의 기대 분류 <strong>${esc(labelName(item.expected))}</strong><p>${esc(item.reason || "해당 필드의 의미와 문맥을 기준으로 작성한 합성 평가 예시입니다.")}</p>` : `입력이 달라져 기존 정답과의 자동 비교를 중지했습니다.<p>원본 예시의 기대 분류는 ${esc(labelName(item.expected))}입니다. 예시를 다시 선택하면 원본으로 돌아갑니다.</p>`;
}

function renderInputMode() {
  const mode = $("input-mode").value;
  $("input-mode-note").textContent = mode === "schema_only" ? "필드와 설명만 전달합니다. 값은 추론 입력에서 제외됩니다." : mode === "value_only" ? "값만 전달합니다. 필드명과 설명은 추론 입력에서 제외됩니다." : "필드·설명·값을 로컬 모델로 전달합니다.";
  renderExpectation();
}

function resetLiveResult() {
  if (isClassifying) return;
  liveSnapshot = null;
  $("live-result").innerHTML = `<div class="result-placeholder"><span>✧</span><strong>분류 결과를 기다리고 있습니다</strong><p>실행하면 선택한 방식의 실제 결과가 여기에 표시됩니다. 아래는 원본 예시의 저장된 평가입니다.</p></div>`;
}

function renderComparison() {
  const row = currentRow();
  if (!selectedId) { $("selected-comparison").innerHTML = empty("예시를 선택하면 같은 입력에 대한 세 방식의 결과가 표시됩니다."); return; }
  if (!row) { $("selected-comparison").innerHTML = empty("이 예시의 저장된 평가 결과가 아직 없습니다. 위에서 실시간 분류를 실행할 수 있습니다."); return; }
  $("selected-comparison").className = "";
  $("selected-comparison").innerHTML = `<div class="saved-grid">${Object.entries(METHODS).map(([method, title]) => {
    const result = methodResult(row, method);
    return `<div class="saved-method"><h3>${esc(title)}</h3><div class="saved-label">${esc(result?.label ? labelName(result.label) : "실행 기록 없음")}</div><p>${result?.latency_ms !== undefined ? esc(duration(result.latency_ms)) : "지연 시간 미측정"}${method === "semif" && num(result?.score) !== null ? `<br>선택지 점수 ${esc(pct(result.score))}` : ""}</p>${statusResult(result) ? pill(correctResult(result, row.expected) ? "기대와 일치" : "기대와 불일치", correctResult(result, row.expected) ? "green" : "red") : pill("미확인")}</div>`;
  }).join("")}</div>${renderSavedScores(methodResult(row,"semif"))}<p class="score-explanation">원본 예시 <strong>${esc(selectedId)}</strong>의 저장된 결과입니다. 편집한 입력의 결과는 위 실시간 실행 영역에 따로 표시됩니다.</p>`;
}

function renderSavedScores(result) {
  if (!result?.probabilities || !LABELS.some(label => num(result.probabilities[label]) !== null)) return "";
  return `<details class="saved-scores"><summary>저장된 SemIf 선택지 점수 펼치기</summary><div class="scores">${LABELS.map(label => { const score = num(result.probabilities[label]); return `<div class="score-row ${result.label === label ? "chosen" : ""}"><span>${esc(labelName(label))}</span><div class="score-track"><div class="score-fill" style="width:${score === null ? 0 : Math.max(0,Math.min(100,score*100))}%"></div></div><span class="score-value">${score === null ? "—" : esc(pct(score))}</span></div>`; }).join("")}</div><p class="score-explanation">허용 토큰 질량 ${num(result.allowed_token_mass) === null ? "미제공" : esc(pct(result.allowed_token_mass,3))} · 선택지 내부 점수는 보정된 신뢰도가 아닙니다.</p></details>`;
}

async function classify(event) {
  event.preventDefault();
  if (isClassifying) return;
  const input = inputs();
  const expected = sameOriginal(input) ? currentCase().expected : null;
  const snapshot = {input:{...input}, expected, case_id:selectedId};
  isClassifying = true;
  $("classify-button").disabled = true;
  $("classify-button").textContent = "로컬 모델 실행 중…";
  showNotice("");
  $("live-result").innerHTML = `<div class="result-placeholder"><span class="spinner"></span><strong>${esc(METHODS[input.method])} 실행 중</strong><p>실제 CPU 추론이 끝나면 표시합니다. 모델을 처음 읽을 때는 더 오래 걸릴 수 있습니다.</p></div>`;
  try {
    const result = await fetchJSON("/api/jev/classify", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(input)});
    liveSnapshot = {...snapshot, result}; renderLiveResult();
  } catch (error) { $("live-result").innerHTML = `<div class="live-error">분류를 완료하지 못했습니다.<br>${esc(error.message)}<br>다른 방식의 결과로 대체하지 않았습니다.</div>`; }
  finally { isClassifying = false; $("classify-button").disabled = false; $("classify-button").textContent = "로컬 분류 실행 ↗"; }
}

function renderLiveResult() {
  if (!liveSnapshot) return;
  const {result, input, expected, case_id:caseId} = liveSnapshot;
  const canCompare = expected !== null;
  const correct = canCompare && correctResult(result, expected);
  const header = `<div class="result-top"><div><div class="result-label">${esc(labelName(result.label))}<small>${esc(result.label || "")}</small></div>${canCompare ? `<div class="result-check ${correct ? "" : "wrong"}">${correct ? "✓ 데모 기대 분류와 일치" : `↳ 데모 기대 분류는 ${esc(labelName(expected))}`}</div>` : `<div class="result-check">입력이 변경되어 정답 비교 없음</div>`}</div><div class="result-meta">${esc(duration(result.latency_ms))}<br>${esc(METHODS[input.method])}<br>${esc({full:"필드 + 설명 + 값",schema_only:"필드와 설명만",value_only:"값만"}[input.input_mode])}</div></div>`;
  let body;
  if (input.method === "semif") {
    body = `<div class="scores">${LABELS.map(label => { const score = num(result.probabilities?.[label]); return `<div class="score-row ${result.label === label ? "chosen" : ""}"><span>${esc(labelName(label))}</span><div class="score-track"><div class="score-fill" style="width:${score === null ? 0 : Math.max(0, Math.min(100, score * 100))}%"></div></div><span class="score-value">${score === null ? "—" : esc(pct(score))}</span></div>`; }).join("")}</div><div class="score-explanation">선택지 내부 점수 <strong>${esc(pct(result.score))}</strong> · 허용 토큰 질량 <strong>${num(result.allowed_token_mass) === null ? "미제공" : esc(pct(result.allowed_token_mass, 3))}</strong><br>위 점수는 정해진 8개 선택지 안의 상대값이며, 보정된 신뢰도나 법적 판단이 아닙니다.</div>`;
  } else {
    body = `<div class="json-result">${esc(JSON.stringify({label:result.label, status:result.status, model:result.model}, null, 2))}</div><div class="score-explanation">JSON 생성 방식은 선택지 점수 분포를 제공하지 않습니다. 생성한 분류 코드와 실제 응답 시간만 비교합니다.</div>`;
  }
  const stale = JSON.stringify(inputs()) !== JSON.stringify(input);
  $("live-result").innerHTML = header + body + `<p class="score-explanation">${stale ? "현재 입력과 다른 실행 결과입니다. " : ""}실행 입력: ${esc(caseId || "직접 입력")} · ${esc(result.source || input.method)}${result.semif_commit ? ` · 커밋 ${esc(result.semif_commit.slice(0, 10))}` : ""}<br>개인정보 분류 후보이며 자동 승인하지 않습니다.</p>`;
}

function renderEvaluation() {
  const evaluation = state?.evaluation;
  const count = evaluation?.dataset?.count ?? state?.cases?.length ?? 0;
  const status = evaluation?.status;
  const complete = ["complete", "completed", "done"].includes(status);
  $("evaluation-status").textContent = complete ? "실행 기록 확인" : status === "running" ? "평가 진행 중" : evaluation ? "저장된 부분 결과" : "평가 기록 대기";
  $("evaluation-status").className = `pill ${complete ? "green" : "neutral"}`;
  $("evaluation-scope").textContent = `${count}개 합성 예시 · ${scopeText(evaluation?.dataset?.scope)}${!complete ? " · 완료된 결과만 표시하며 미실행 항목은 추정하지 않습니다." : ""}`;
  $("method-cards").innerHTML = Object.entries(METHODS).map(([key, title]) => {
    const metrics = evaluation?.methods?.[key];
    const accuracy = metrics?.count ? metrics.correct / metrics.count : null;
    return `<article class="method-card ${key === "semif" ? "featured" : ""}"><div class="kicker">${key === "semif" ? "LOCAL SEMIF" : key === "json" ? "LOCAL GENERATIVE JSON" : "FROZEN RULE BASELINE"}</div><h3>${esc(title)}</h3><div class="method-value">${num(accuracy) === null ? "미측정" : esc(pct(accuracy))}${num(accuracy) === null ? "" : `<small>정확도</small>`}</div><p>${metrics?.count ? `${esc(metrics.correct)} / ${esc(metrics.count)}개 기대 분류와 일치` : "실행된 평가 결과를 기다리고 있습니다."}</p><div class="method-details"><div><span>매크로 F1</span><strong>${num(metrics?.macro_f1) === null ? "미측정" : Number(metrics.macro_f1).toFixed(3)}</strong></div><div><span>중앙 응답 시간</span><strong>${esc(duration(metrics?.latency_ms?.median))}</strong></div><div><span>p95 응답 시간</span><strong>${esc(duration(metrics?.latency_ms?.p95))}</strong></div></div></article>`;
  }).join("");
  renderMatrix(); renderSlices(); renderHighErrors(); renderThreshold();
}

function renderMatrix() {
  const method = $("matrix-method").value;
  const metrics = state?.evaluation?.methods?.[method];
  if (!metrics?.count || !metrics?.confusion_matrix) { $("confusion-matrix").innerHTML = empty("아직 혼동 행렬을 만들 실행 결과가 없습니다."); $("per-label").innerHTML = empty("분류별 지표가 아직 없습니다."); return; }
  const matrix = metrics.confusion_matrix;
  const columns = [...LABELS, ...new Set(Object.values(matrix).flatMap(row => Object.keys(row).filter(label => !LABELS.includes(label) && Number(row[label]) > 0)))];
  const max = Math.max(1, ...LABELS.flatMap(gold => columns.map(pred => Number(matrix[gold]?.[pred] || 0))));
  $("confusion-matrix").innerHTML = `<table class="matrix"><caption class="sr-only">${esc(METHODS[method])} 혼동 행렬, 행은 기대 분류, 열은 예측 분류</caption><thead><tr><th>기대 ↓ / 예측 →</th>${columns.map(label => `<th scope="col">${esc(labelName(label))}</th>`).join("")}</tr></thead><tbody>${LABELS.map(gold => `<tr><th scope="row">${esc(labelName(gold))}<code>${esc(gold)}</code></th>${columns.map(pred => { const value = Number(matrix[gold]?.[pred] || 0); const alpha = value ? .12 + value / max * .6 : 0; return `<td class="${value === 0 ? "zero" : gold === pred ? "" : "off-error"}" style="background:${value === 0 ? "#fafcff" : gold === pred ? `rgba(177,202,239,${alpha})` : `rgba(245,205,216,${alpha})`}" title="기대 ${esc(labelName(gold))} · 예측 ${esc(labelName(pred))}: ${value}개">${value}</td>`; }).join("")}</tr>`).join("")}</tbody></table>`;
  const perLabel = metrics.per_label;
  const rows = Array.isArray(perLabel) ? perLabel : Object.entries(perLabel || {}).map(([label, entry]) => ({label,...entry}));
  $("per-label").innerHTML = rows.length ? `<table><thead><tr><th>분류</th><th>예시 수</th><th>정밀도</th><th>재현율</th><th>F1</th></tr></thead><tbody>${rows.map(item => `<tr><td>${esc(labelName(item.label))}<code>${esc(item.label)}</code></td><td>${esc(item.support)}</td><td>${esc(pct(item.precision))}</td><td>${esc(pct(item.recall))}</td><td>${num(item.f1) === null ? "미측정" : Number(item.f1).toFixed(3)}</td></tr>`).join("")}</tbody></table>` : empty("분류별 지표가 아직 없습니다.");
}

function renderSlices() {
  const values = state?.evaluation?.methods?.semif?.slices;
  const rows = Array.isArray(values) ? values : Object.entries(values || {}).map(([slice, entry]) => ({slice,...entry}));
  $("slice-results").innerHTML = rows.length ? rows.map(item => {
    const accuracy = item.count ? item.correct / item.count : 0;
    return `<div class="slice-row"><div>${esc(sliceName(item.slice))}<small>${esc(item.correct)} / ${esc(item.count)}개 일치</small></div><div class="slice-track"><div style="width:${Math.max(0,Math.min(100,accuracy*100))}%"></div></div><div class="slice-percent">${esc(pct(accuracy))}</div></div>`;
  }).join("") : empty("SemIf의 유형별 결과가 아직 없습니다.");
}

function renderHighErrors() {
  const rows = evalRows().filter(row => { const result = methodResult(row,"semif"); return statusResult(result) && !correctResult(result,row.expected) && (resultScore(result) ?? 0) >= .9; });
  $("high-errors").innerHTML = rows.length ? rows.map(row => { const result = methodResult(row,"semif"); const item = state.cases?.find(entry => entry.id === row.id); return `<button class="error-item" type="button" data-case-jump="${esc(row.id)}"><strong>${esc(row.id)} · ${esc(pct(result.score))}</strong><p>${esc(item?.text || item?.description || "평가 예시")}</p><span>기대 ${esc(labelName(row.expected))} → 예측 ${esc(labelName(result.label))} ↗</span></button>`; }).join("") : empty(evalRows().length ? "현재 기록에 점수 90% 이상인 오분류가 없습니다. 공격 내성이 입증되었다는 의미는 아닙니다." : "평가 기록이 생기면 높은 점수의 오분류를 표시합니다.");
}

function renderThreshold() {
  const threshold = Number($("threshold").value) / 100;
  $("threshold-value").textContent = pct(threshold,0);
  const rows = evalRows().filter(row => methodResult(row,"semif"));
  if (!rows.length) { $("threshold-stats").innerHTML = empty("선별 기준을 계산할 평가 기록이 없습니다."); return; }
  const accepted = rows.filter(row => { const result = methodResult(row,"semif"); return statusResult(result) && result.label !== "UNKNOWN" && resultScore(result) !== null && resultScore(result) >= threshold; });
  const correct = accepted.filter(row => correctResult(methodResult(row,"semif"),row.expected)).length;
  const coverage = accepted.length / rows.length;
  $("threshold-stats").innerHTML = `<div class="threshold-stat"><span>기준을 넘는 후보</span><strong>${accepted.length}<small>/ ${rows.length}개</small></strong><small>포함률 ${esc(pct(coverage))}</small></div><div class="threshold-stat"><span>후보 안의 정확도</span><strong>${accepted.length ? pct(correct/accepted.length,0) : "—"}</strong><small>${correct}개 일치 / ${accepted.length}개</small></div><div class="threshold-stat"><span>보류할 예시</span><strong>${rows.length-accepted.length}</strong><small>낮은 점수·UNKNOWN·오류</small></div>`;
}

function renderGuide() {
  $("label-guide").innerHTML = LABELS.map(label => `<article class="guide-card"><h3>${esc(labelName(label))}</h3><code>${esc(label)}</code><p>${esc(state?.labels?.[label]?.description || "해당 항목의 평가 기준 설명이 아직 제공되지 않았습니다.")}</p></article>`).join("");
  const runtime = state?.runtime || {};
  const dataset = state?.evaluation?.dataset || {};
  const entries = [["실제 모델",runtime.model || "미확인"],["실행 백엔드",runtime.backend || "미확인"],["SemIf 커밋",runtime.semif_commit || "미확인"],["외부 추론",runtime.external_inference === false ? "없음 · 로컬 모델로만 추론" : "미확인"],["평가 입력 수",dataset.count ?? state?.cases?.length ?? "미확인"],["평가셋 SHA-256",dataset.sha256 || "미확인"],["평가 범위",scopeText(dataset.scope)]];
  $("runtime-facts").innerHTML = entries.map(([key,value]) => `<div class="fact"><span>${esc(key)}</span><strong>${esc(value)}</strong></div>`).join("");
}

function changeTab(tab, updateHash = true) {
  if (!["experiment","evaluation","guide"].includes(tab)) tab = "experiment";
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.toggle("active", panel.id === `panel-${tab}`));
  document.querySelectorAll("[data-tab]").forEach(button => button.classList.toggle("active",button.dataset.tab===tab));
  if (updateHash && location.hash !== `#${tab}`) history.replaceState(null,"",`#${tab}`);
}

document.addEventListener("click", event => {
  const tab = event.target.closest("[data-tab]"); if (tab) { event.preventDefault(); changeTab(tab.dataset.tab); return; }
  const jump = event.target.closest("[data-case-jump]"); if (jump) { selectCase(jump.dataset.caseJump,true); return; }
  const selected = event.target.closest("[data-case]"); if (selected) selectCase(selected.dataset.case);
});
$("refresh").addEventListener("click",() => refreshState());
$("classify-form").addEventListener("submit",classify);
["case-search","case-label","case-slice","errors-only"].forEach(id => $(id).addEventListener(id === "case-search" ? "input" : "change",renderCases));
["field-path","field-description","input-text"].forEach(id => $(id).addEventListener("input",() => { renderExpectation(); if (liveSnapshot) renderLiveResult(); }));
$("input-mode").addEventListener("change",() => { renderInputMode(); if (liveSnapshot) renderLiveResult(); });
$("method").addEventListener("change",() => { if (liveSnapshot) renderLiveResult(); });
$("matrix-method").addEventListener("change",renderMatrix);
$("threshold").addEventListener("input",renderThreshold);
window.addEventListener("hashchange",() => changeTab(location.hash.slice(1),false));
changeTab(location.hash.slice(1),false);
refreshState();
setInterval(() => { if (document.visibilityState === "visible" && state?.evaluation?.status === "running") refreshState(true); },15000);
