"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const labels = { overview: "분석 개요", findings: "인가 판정", events: "수집 로그", mapping: "CIM · 데이터 결합", model: "로컬 분류 실험", incidents: "사후 로그 분석" };
  const verdictLabels = { confirmed: "취약 확인", allowed: "정상 허용", blocked: "차단 확인", needs_review: "검토 필요" };
  const translation = {status:"상태",model:"모델",model_name:"모델 이름",name:"이름",provider:"제공자",backend:"실행 방식",available:"사용 가능",enabled:"활성화",local:"로컬 실행",model_status:"모델 상태",device:"장치",version:"버전",source:"출처",reason:"근거",error:"오류",latency_ms:"처리 시간 (ms)",duration_ms:"소요 시간 (ms)",accuracy:"정확도",precision:"정밀도",recall:"재현율",f1:"F1",total:"전체",passed:"통과",failed:"실패",cases:"사례",tests:"검증",note:"설명",notes:"설명",scope:"범위",limitations:"한계",license:"라이선스",path:"경로",artifact:"산출물",artifacts:"산출물",results:"결과",checked_at:"확인 시각",evaluated_at:"평가 시각",runtime:"실행 환경",offline:"오프라인",loaded:"모델 로드",rule_based:"규칙 기반",trained:"학습 수행",method:"방식",label:"분류",confidence:"확신도",score:"점수",description:"설명",legal_category:"법적 범주",field_path:"필드 경로",evidence:"근거",threshold:"임곗값",expected:"기대값",actual:"관측값"};
  let state = { meta:{}, summary:{}, findings:[],events:[],mappings:[],links:[],runs:[],model:{},evaluation:{} };
  let selectedFinding = null;
  let selectedEvent = null;
  let busy = false;
  let incidentRuns = [];
  let incidentReport = null;
  let incidentLoaded = false;
  let incidentLoading = false;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g,(ch)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const arr = (value) => Array.isArray(value) ? value : [];
  const number = (value) => Number.isFinite(Number(value)) ? Number(value).toLocaleString("ko-KR") : "—";
  const json = (value) => escapeHtml(JSON.stringify(value ?? {},null,2));
  const object = (value) => value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const printable = (value) => value === null || value === undefined || value === "" ? "—" : typeof value === "boolean" ? (value ? "예" : "아니요") : typeof value === "object" ? JSON.stringify(value) : String(value);
  const valueText = (value) => escapeHtml(printable(value));
  const date = (value) => { if(!value) return "시각 정보 없음"; const d=new Date(value);return Number.isNaN(d.getTime())?String(value):d.toLocaleString("ko-KR",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false}); };
  const modeLabel = (mode) => mode === "vulnerable" ? "취약 상태" : mode === "fixed" ? "수정 상태" : printable(mode);
  const tag = (verdict) => `<span class="tag ${Object.hasOwn(verdictLabels,verdict)?verdict:"plain"}">${escapeHtml(verdictLabels[verdict] || verdict || "미판정")}</span>`;
  const tags = (values) => `<div class="tags">${arr(values).map(v=>`<span class="tag plain">${valueText(v)}</span>`).join("") || '<span class="muted small">기록 없음</span>'}</div>`;
  const empty = (title,message) => `<div class="empty-state"><span class="empty-symbol">◇</span><strong>${escapeHtml(title)}</strong><p>${escapeHtml(message)}</p></div>`;
  const jsonBlock = (value) => `<pre>${json(value)}</pre>`;
  const backendNames = {direct:"선택지 점수 · 0.6B",ollama:"JSON 생성 · Ollama"};
  const backendBody = (id) => Object.hasOwn(backendNames,$(id).value)?{backend:$(id).value}:{};

  function notify(message,type="info") {
    $("notification").className=`notification ${type}`;
    $("notification").textContent=message;
    $("notification").hidden=false;
  }
  function setConnection(online) {
    $("connection").className=`connection ${online?"online":"error"}`;
    $("connection").innerHTML=`<i></i>${online?"로컬 API 연결됨":"API 연결 확인 필요"}`;
  }
  async function request(path,options={}) {
    const response=await fetch(path,{...options,headers:{"Accept":"application/json",...(options.body?{"Content-Type":"application/json"}:{}),...(options.headers||{})}});
    let data;
    const raw=await response.text();
    try { data=JSON.parse(raw); } catch { throw new Error(response.ok?"서버 응답이 JSON 형식이 아닙니다.":`서버 오류 (${response.status})`); }
    if(!response.ok) throw new Error(typeof data.detail==="string"?data.detail:typeof data.error==="string"?data.error:JSON.stringify(data.detail||data.error||data));
    return data;
  }
  async function refresh({quiet=false}={}) {
    $("refresh").disabled=true;
    try {
      const result=await request("/api/state");
      state={...state,...result};
      for(const name of ["findings","events","mappings","links","runs"]) state[name]=arr(result[name]);
      state.meta=object(result.meta);state.summary=object(result.summary);
      setConnection(true);render();
      if(!quiet) { $("notification").hidden=true; }
      return true;
    } catch(error) {
      setConnection(false);notify(`데이터를 불러오지 못했습니다. ${error.message}`,"error");return false;
    } finally { $("refresh").disabled=false; }
  }
  function changeTab(tab) {
    if(!Object.hasOwn(labels,tab)) return;
    for(const panel of document.querySelectorAll(".tab-panel")) panel.classList.toggle("active",panel.id===`tab-${tab}`);
    for(const nav of document.querySelectorAll(".nav-item")) { nav.classList.toggle("active",nav.dataset.tab===tab);nav.setAttribute("aria-current",nav.dataset.tab===tab?"page":"false"); }
    if(matchMedia("(max-width:720px)").matches)document.querySelector(`.nav-item[data-tab="${tab}"]`)?.scrollIntoView({block:"nearest",inline:"nearest"});
    $("breadcrumb-current").textContent=labels[tab];
    document.body.classList.toggle("incident-page",tab==="incidents");
    if(location.hash!==`#${tab}`) history.replaceState(null,"",`#${tab}`);
    if(tab==="incidents"&&!incidentLoaded) loadIncidentRuns({analyze:true});
  }

  function render() {
    const s=state.summary;
    const confirmed=s.confirmed??state.findings.filter(f=>f.verdict==="confirmed").length;
    const review=s.review??state.findings.filter(f=>f.verdict==="needs_review").length;
    const stats=[
      {label:"수집한 요청·응답",value:s.events??state.events.length,icon:"≡",note:"저장된 트래픽 증거",className:""},
      {label:"전체 인가 판정",value:s.findings??state.findings.length,icon:"◇",note:"정상 · 차단 · 취약 · 검토",className:""},
      {label:"확인된 취약 사례",value:confirmed,icon:"!",note:"정책과 응답을 함께 검증",className:"danger"},
      {label:"검토가 필요한 사례",value:review,icon:"?",note:"불확실성을 별도로 관리",className:"warn"},
      {label:"비인가 노출 정보 주체",value:s.subjects??state.links.length,icon:"◎",note:"확인된 응답 내 식별자 수",className:"blue"}
    ];
    $("stats").innerHTML=stats.map(v=>`<div class="stat-card ${v.className}"><div class="stat-top"><span>${v.label}</span><span class="stat-icon">${v.icon}</span></div><div class="stat-value">${number(v.value)}</div><div class="stat-bottom">${v.note}</div></div>`).join("");
    $("nav-count").textContent=number(confirmed);
    const privacyCount=state.events.reduce((total,event)=>total+arr(event.privacy).length,0);
    const steps=[
      ["트래픽 기록",s.events??state.events.length,"건","요청과 응답 보존"],
      ["CIM 정규화",state.mappings.length,"개","필드 의미와 역할 통일"],
      ["개인정보 분류",privacyCount,"항목","저장된 분류 관측 수"],
      ["기록 결합",state.links.length,"건","정보 주체별 연결"],
      ["인가 판정",s.findings??state.findings.length,"건","정책 · 증거 기반 결과"]
    ];
    $("pipeline").innerHTML=steps.map((v,i)=>`<div class="pipeline-step"><div class="pipeline-step-top"><span class="pipeline-number">0${i+1}</span>${v[0]}</div><div class="pipeline-metric">${number(v[1])}<small>${v[2]}</small></div><div class="pipeline-description">${v[3]}</div></div>`).join("");
    renderRecent();renderFindings();renderEvents();renderMappings();renderLinks();renderModel();renderEvaluation();renderRuns();
    $("footer-meta").textContent=`${state.meta.database?`${printable(state.meta.database)} · `:""}${state.meta.version?`v${state.meta.version} · `:""}${new Date().toLocaleTimeString("ko-KR",{hour12:false})} 갱신`;
    if(selectedFinding!==null) showFinding(selectedFinding,false);
    if(selectedEvent!==null) showEvent(selectedEvent,false);
  }
  function renderRecent() {
    const priority={confirmed:0,needs_review:1,blocked:2,allowed:3};
    const selected=state.findings.map((f,i)=>({...f,index:i})).sort((a,b)=>(priority[a.verdict]??4)-(priority[b.verdict]??4)).slice(0,5);
    $("recent-findings").innerHTML=selected.length?selected.map(f=>`<div class="finding-item"><span class="finding-symbol ${Object.hasOwn(verdictLabels,f.verdict)?f.verdict:""}">${f.verdict==="confirmed"?"!":f.verdict==="needs_review"?"?":"✓"}</span><div class="finding-content"><div class="finding-top"><button class="finding-title" data-finding="${f.index}">${valueText(f.title||f.case_id)}</button>${tag(f.verdict)}</div><div class="finding-subtitle"><span class="mono">${valueText(f.endpoint)}</span><br>${valueText(f.category)} <span class="badge-divider">·</span> ${escapeHtml(modeLabel(f.mode))}</div></div></div>`).join(""):empty("아직 분석 결과가 없습니다","취약 시나리오를 실행하면 실제 판정 결과가 이곳에 표시됩니다.");
  }
  function renderFindings() {
    const filter=$("verdict-filter").value;
    const findings=state.findings.map((f,i)=>({...f,index:i})).filter(f=>filter==="all"||f.verdict===filter);
    $("findings-table").innerHTML=findings.length?`<div class="table-scroll"><table><thead><tr><th>시나리오 / 엔드포인트</th><th>판정</th><th>범주</th><th>요청자 → 정보 주체</th><th>수정 우선순위 점수</th><th>환경</th></tr></thead><tbody>${findings.map(f=>`<tr class="clickable-row ${f.index===selectedFinding?"selected":""}" tabindex="0" role="button" data-finding="${f.index}" aria-label="${escapeHtml(f.title||f.case_id)} 상세"><td><div class="cell-title">${valueText(f.title||f.case_id)}</div><div class="cell-subtitle mono">${valueText(f.endpoint)}</div></td><td>${tag(f.verdict)}</td><td><span class="tag plain">${valueText(f.category)}</span></td><td><div>${valueText(f.actor)}</div><div class="cell-subtitle">→ ${valueText(f.subject)}</div></td><td>${f.score===null||f.score===undefined?"—":valueText(f.score)}</td><td class="nowrap small">${escapeHtml(modeLabel(f.mode))}</td></tr>`).join("")}</tbody></table></div>`:empty("표시할 판정이 없습니다",filter==="all"?"시나리오를 실행해 인가 정책과 노출 필드를 확인하세요.":"선택한 판정에 해당하는 결과가 없습니다.");
  }
  function showFinding(index,navigate=true) {
    const f=state.findings[index];if(!f){$("finding-detail").hidden=true;return;}
    selectedFinding=index;
    $("finding-detail").hidden=false;
    $("finding-detail").innerHTML=`<div class="card-heading"><div><div class="section-kicker">FINDING EVIDENCE</div><div class="detail-title"><h2>${valueText(f.title||f.case_id)}</h2>${tag(f.verdict)}</div></div><span class="subtle-badge">${valueText(f.case_id||f.id)}</span></div><div class="detail-grid"><div class="detail-block full"><label>판정 근거</label><p>${valueText(f.reason)}</p></div><div class="detail-block"><label>API / 관측 상태 코드</label><p class="mono">${valueText(f.endpoint)} · ${valueText(f.status_code)}</p></div><div class="detail-block"><label>요청자 / 정보 주체</label><p>${valueText(f.actor)} → ${valueText(f.subject)}</p></div><div class="detail-block full"><label>반환 필드</label>${tags(f.fields)}</div><div class="detail-block full"><label>연결된 증거 로그</label><div class="evidence-links">${evidenceLinks(f.evidence_ids)}</div></div></div>`;
    renderFindings();
    if(navigate){changeTab("findings");$("finding-detail").scrollIntoView({behavior:"smooth",block:"nearest"});}
  }
  function evidenceLinks(ids) {
    return arr(ids).map(id=>{const index=state.events.findIndex(event=>String(event.id)===String(id));return index<0?`<span class="tag plain">#${valueText(id)}</span>`:`<button class="evidence-button" data-event="${index}">로그 #${valueText(id)} ↗</button>`;}).join("") || '<span class="muted small">연결된 증거가 없습니다.</span>';
  }
  function renderEvents() {
    $("event-count").textContent=`${number(state.events.length)}개 로그`;
    const events=state.events.map((e,i)=>({...e,index:i})).reverse();
    $("events-table").innerHTML=events.length?`<div class="table-scroll"><table><thead><tr><th>로그 / 시각</th><th>요청</th><th>요청자</th><th>정보 주체</th><th>응답</th><th>분류 항목</th><th>환경</th></tr></thead><tbody>${events.map(e=>`<tr class="clickable-row ${e.index===selectedEvent?"selected":""}" tabindex="0" role="button" data-event="${e.index}" aria-label="로그 ${escapeHtml(e.id)} 상세"><td><div class="cell-title">#${valueText(e.id)}</div><div class="cell-subtitle">${escapeHtml(date(e.created_at))}</div></td><td><span class="tag blue">${valueText(e.method)}</span><div class="cell-subtitle mono">${valueText(e.path)}</div></td><td>${valueText(e.actor)}</td><td>${valueText(e.subject)}</td><td><span class="tag ${Number(e.status_code)>=400?"plain":"blue"}">${valueText(e.status_code)}</span></td><td>${number(arr(e.privacy).length)}</td><td class="nowrap small">${escapeHtml(modeLabel(e.mode))}</td></tr>`).join("")}</tbody></table></div>`:empty("수집된 로그가 없습니다","데모를 실행하면 게이트웨이를 통과한 요청·응답이 기록됩니다.");
  }
  function showEvent(index,navigate=true) {
    const e=state.events[index];if(!e){$("event-detail").hidden=true;return;}
    selectedEvent=index;$("event-detail").hidden=false;
    $("event-detail").innerHTML=`<div class="card-heading"><div><div class="section-kicker">REQUEST / RESPONSE EVIDENCE</div><h2>로그 #${valueText(e.id)} <span class="tag blue">${valueText(e.method)}</span></h2></div><span class="subtle-badge">${escapeHtml(date(e.created_at))}</span></div><div class="detail-grid"><div class="detail-block full"><label>엔드포인트 / 테넌트 / 처리 시간</label><p class="mono">${valueText(e.path)} · ${valueText(e.tenant)} · ${valueText(e.duration_ms)} ms</p></div><div class="detail-block full"><label>기록 보존 범위</label><p>${valueText(e.response_capture)}</p></div><div class="detail-block"><label>마스킹된 요청</label>${jsonBlock(e.request_redacted)}</div><div class="detail-block"><label>마스킹된 응답</label>${jsonBlock(e.response_redacted)}</div><div class="detail-block"><label>개인정보 분류</label>${jsonBlock(e.privacy||[])}</div><div class="detail-block"><label>인가 정책 / 판정 맥락</label>${jsonBlock(e.policy)}</div><div class="detail-block full"><label>저장 로그 해시 · 내부 무결성 비교</label><p class="mono">${valueText(e.sha256)}<br>${e.integrity_ok===true?"서버의 재계산 해시와 일치":e.integrity_ok===false?"해시 불일치 · 확인 필요":"검증 결과 없음"}</p></div></div>`;
    renderEvents();if(navigate){changeTab("events");$("event-detail").scrollIntoView({behavior:"smooth",block:"nearest"});}
  }
  function renderMappings() {
    $("mappings-table").innerHTML=state.mappings.length?`<div class="table-scroll"><table><thead><tr><th>원본 필드</th><th>공통 의미</th><th>역할</th><th>매핑 출처 / 상태</th><th>근거</th></tr></thead><tbody>${state.mappings.map(m=>`<tr><td class="mono">${valueText(m.source_path)}</td><td class="mono">${valueText(m.canonical)}</td><td>${valueText(m.role)}</td><td><span class="tag plain">${valueText(m.source)}</span><div class="cell-subtitle">${valueText(m.status)}</div></td><td>${valueText(m.reason)}</td></tr>`).join("")}</tbody></table></div>`:empty("등록된 매핑이 없습니다","필드의 의미를 확인한 매핑이 여기에 표시됩니다.");
  }
  function renderLinks() {
    $("links-grid").innerHTML=state.links.length?state.links.map(link=>`<article class="link-card"><div class="link-card-top"><h3>${valueText(link.subject_key)}</h3><span class="tag ${link.attacker_observed?"confirmed":"plain"}">${link.attacker_observed?"공격자 응답에서 관측":"내부 연결 기록"}</span></div><label class="field-label">테넌트 / 식별자</label><p>${valueText(link.tenant)} · ${valueText(link.member_ids)}</p><label class="field-label">연결된 정보</label>${tags(link.fields)}<label class="field-label" style="margin-top:15px">관련 엔드포인트</label>${tags(link.endpoints)}<p>${valueText(link.reason)}</p><div class="evidence-links">${evidenceLinks(link.event_ids)}</div></article>`).join(""):empty("연결된 기록이 없습니다","검증된 식별자로 같은 정보 주체의 기록이 연결되면 표시됩니다.");
  }
  function keyValues(data) {
    if(!data||typeof data!=="object"||Array.isArray(data)) return jsonBlock(data);
    const entries=Object.entries(data);
    if(!entries.length) return '<p class="model-notice">아직 저장된 정보가 없습니다.</p>';
    return `<div class="kv-list">${entries.map(([key,value])=>`<div class="kv-row"><div class="kv-key">${escapeHtml(translation[key]||key)}</div><div class="kv-value">${value&&typeof value==="object"?jsonBlock(value):valueText(value)}</div></div>`).join("")}</div>`;
  }
  function renderModel() {
    const model=object(state.model);
    const {event_results,benchmarks,alternative_benchmarks,...status}=model;
    for(const id of ["classify-backend","mapping-backend"]) {
      $(id).options[0].textContent=`현재 기본값${model.selected_backend?` (${model.backends?.[model.selected_backend]?.model||backendNames[model.selected_backend]||model.selected_backend})`:""}`;
      $(id).querySelector('option[value="ollama"]').textContent=`JSON 생성 · ${model.backends?.ollama?.model||"Ollama"}`;
    }
    renderComparison(model);
    $("model-status").innerHTML=Object.keys(status).length?keyValues(status):`<p class="model-notice">${valueText(state.meta.model_status||"아직 모델의 실행 상태가 제공되지 않았습니다. 분류 성공 여부는 실제 실행 결과로 확인합니다.")}</p>`;
    $("model-pending").textContent=`대기 작업 ${number(model.pending_jobs??0)}건`;
    const records=arr(event_results);
    $("model-event-results").innerHTML=records.length?`<div class="table-scroll"><table><thead><tr><th>증거 로그</th><th>필드 / 엔드포인트</th><th>모델 분류 후보</th><th>출처 / 상태</th><th>실측 지연</th></tr></thead><tbody>${records.map(row=>{const result=object(row.result);return `<tr><td>${evidenceLinks([row.event_id])}</td><td><span class="mono">${valueText(row.field_path)}</span><div class="cell-subtitle mono">${valueText(row.endpoint)}</div></td><td><span class="tag ${result.label?"blue":"plain"}">${valueText(result.label)}</span><div class="cell-subtitle">${valueText(row.decision_role)}</div></td><td>${valueText(result.source||result.model)}<div class="cell-subtitle">${valueText(result.status)}</div></td><td class="nowrap">${result.latency_ms===undefined?"—":`${number(result.latency_ms)} ms`}</td></tr>`;}).join("")}</tbody></table></div><details class="details-toggle"><summary>원본 모델 결과 · 확신도와 한계 확인</summary>${jsonBlock(records)}</details>`:empty("저장된 모델 분류 결과가 없습니다","모델 작업자가 실행 중이면 상담·건강 안내 응답을 비동기로 분류합니다. 완료 후 새로고침으로 확인하세요.");
    $("model-benchmarks").innerHTML=(Object.keys(object(benchmarks)).length?`<details class="details-toggle"><summary>선택지 점수 방식 · 벤치마크 원본</summary>${jsonBlock(benchmarks)}</details>`:"")+(Object.keys(object(alternative_benchmarks)).length?`<details class="details-toggle"><summary>Ollama 방식 · 벤치마크 원본</summary>${jsonBlock(alternative_benchmarks)}</details>`:"")+((Object.keys(object(benchmarks)).length||Object.keys(object(alternative_benchmarks)).length)?'<hr class="section-divider">':"");
  }
  function metricObject(record) {
    for(const candidate of [record?.model,record?.metrics,record?.classification,record]) {
      if(candidate&&typeof candidate==="object"&&typeof candidate.accuracy==="number") return candidate;
    }
    return null;
  }
  function pickBenchmark(records,alias=false) {
    return Object.entries(object(records)).filter(([key,record])=>Boolean(/normaliz|alias/i.test(key))===alias&&metricObject(record)).sort(([keyA,a],[keyB,b])=>{
      const smoke=Number(/smoke/i.test(keyA))-Number(/smoke/i.test(keyB));
      if(smoke)return smoke;
      const ma=metricObject(a),mb=metricObject(b);
      return (mb.n??mb.count??0)-(ma.n??ma.count??0);
    })[0]||null;
  }
  function renderComparison(model) {
    const direct=pickBenchmark(model.benchmarks),alias=pickBenchmark(model.benchmarks,true),alternative=pickBenchmark(model.alternative_benchmarks),alternativeAlias=pickBenchmark(model.alternative_benchmarks,true);
    const baseline=direct&&object(direct[1].baseline);
    const hasBaseline=typeof baseline?.accuracy==="number";
    const percentage=(value)=>typeof value==="number"&&Number.isFinite(value)?`${(value*100).toLocaleString("ko-KR",{maximumFractionDigits:1})}%`:"—";
    const ratio=(m)=>{const total=m.n??m.count;if(total===undefined)return "평가 수 미제공";const correct=m.correct??(Array.isArray(m.errors)?total-m.errors.length:typeof m.accuracy==="number"?Math.round(total*m.accuracy):null);return correct===null?`${number(total)}개 사례`:`${number(correct)} / ${number(total)} 정답`;};
    const cards=[{title:"규칙 기반 기준선",subtitle:"문자열·필드 규칙",entry:hasBaseline?[direct[0],{...direct[1],model:baseline,latency_ms:null}]:null,kind:"baseline"},{title:"선택지 점수 · 0.6B",subtitle:"로컬 CPU · 선택지 토큰 비교",entry:direct,alias,kind:"direct"},{title:"JSON 생성 · Ollama",subtitle:"로컬 생성 모델 · 스키마 출력",entry:alternative,alias:alternativeAlias,kind:"ollama"}];
    $("benchmark-comparison").innerHTML=cards.map(card=>{
      if(!card.entry)return `<article class="benchmark-card"><div class="section-kicker">${escapeHtml(card.subtitle)}</div><h3>${escapeHtml(card.title)}</h3><div class="benchmark-wait">평가 결과 대기</div><p>저장된 실측 결과가 제공되면 표시합니다.</p></article>`;
      const [key,record]=card.entry,m=metricObject(record),latency=object(record.latency_ms),isSmoke=/smoke/i.test(key),belowBaseline=card.kind==="direct"&&hasBaseline&&m.accuracy<baseline.accuracy;
      const status=card.kind==="baseline"?"비교 기준":belowBaseline?"기준선 미달 · 채택 보류":isSmoke?"소규모 스모크 · 검토 필요":"실험 결과 · 추가 검증 필요";
      const median=latency.median??record.median_latency_ms;
      const p95=latency.p95_nearest_rank??record.p95_latency_ms;
      const aliasMetric=card.alias?metricObject(card.alias[1]):null;
      return `<article class="benchmark-card ${belowBaseline?"benchmark-hold":""}"><div class="section-kicker">${escapeHtml(card.subtitle)}</div><h3>${escapeHtml(card.title)}</h3>${card.kind!=="baseline"&&record.model_id?`<p class="benchmark-model">${valueText(record.model_id)}</p>`:""}<div class="benchmark-value">${percentage(m.accuracy)}<span>${ratio(m)}</span></div><span class="tag ${belowBaseline?"confirmed":card.kind==="baseline"?"plain":"needs_review"}">${status}</span><div class="benchmark-details">${typeof m.macro_f1==="number"?`<div><span>Macro F1</span><strong>${m.macro_f1.toFixed(3)}</strong></div>`:""}${median!==undefined?`<div><span>중앙 지연</span><strong>${number(median)} ms</strong></div>`:""}${p95!==undefined?`<div><span>p95 지연</span><strong>${number(p95)} ms</strong></div>`:""}${aliasMetric?`<div><span>별칭 매핑</span><strong>${ratio(aliasMetric)} · ${percentage(aliasMetric.accuracy)}</strong></div>`:""}</div><p class="benchmark-source">${escapeHtml(key)}${isSmoke?" · 스모크 사례만 포함":""}</p></article>`;
    }).join("")+'<p class="benchmark-footnote">작성한 합성 사례에 대한 실측값입니다. 평가 집합이 다르면 수치를 직접 비교할 수 없으며, 실제 서비스 정확도나 법적 판단의 정확도를 의미하지 않습니다.</p>';
  }
  function renderEvaluation() {
    const evaluation=state.evaluation;
    $("model-evaluation").innerHTML=Array.isArray(evaluation)?jsonBlock(evaluation):keyValues(evaluation);
    if(!evaluation||Object.keys(evaluation).length===0){$("evaluation-overview").innerHTML=empty("검증 결과를 기다리고 있습니다","실행 완료 후 서버에서 제공한 평가 결과가 표시됩니다.");return;}
    const scalars=Object.entries(evaluation).filter(([,v])=>v===null||typeof v!=="object").slice(0,8);
    $("evaluation-overview").innerHTML=(scalars.length?`<div class="evaluation-summary">${scalars.map(([k,v])=>`<div class="evaluation-chip">${escapeHtml(translation[k]||k)}<strong>${valueText(v)}</strong></div>`).join("")}</div>`:"")+`<details class="details-toggle"><summary>실제 평가 데이터 확인</summary>${jsonBlock(evaluation)}</details>`;
  }
  function renderRuns() {
    $("run-count").textContent=`최근 실행 ${number(state.runs.length)}건`;
    const recentRuns=state.runs.slice().sort((a,b)=>new Date(b.created_at||b.started_at||0)-new Date(a.created_at||a.started_at||0)).slice(0,6);
    $("run-history").innerHTML=recentRuns.length?`<div class="run-history">${recentRuns.map(run=>`<div class="run-pill"><strong>${escapeHtml(modeLabel(run.mode))}</strong> <span class="badge-divider">·</span> ${valueText(run.status||run.id||run.run_id)}<br>${escapeHtml(date(run.created_at||run.started_at||run.completed_at))}</div>`).join("")}</div>`:"";
  }
  async function runDemo(mode) {
    if(busy)return;busy=true;
    const active=$(mode==="vulnerable"?"run-vulnerable":"run-fixed");const previous=active.innerHTML;
    for(const btn of document.querySelectorAll("[data-run]"))btn.disabled=true;
    active.innerHTML='<span class="loading-spinner"></span> 시나리오 실행 중';
    notify(`${modeLabel(mode)}의 요청을 재현하고 로그·분류·판정 결과를 수집하고 있습니다.`);
    try {
      const result=await request("/api/demo/run",{method:"POST",body:JSON.stringify({mode})});
      const refreshed=await refresh({quiet:true});
      if(refreshed) notify(`${modeLabel(mode)} 시나리오를 실행했습니다. ${typeof result.message==="string"?result.message:"저장된 로그와 판정 결과가 갱신되었습니다."}`,"success");
    }catch(error){notify(`시나리오 실행에 실패했습니다. ${error.message}`,"error");}
    finally{busy=false;active.innerHTML=previous;for(const btn of document.querySelectorAll("[data-run]"))btn.disabled=false;}
  }
  async function classify(event) {
    event.preventDefault();
    const button=$("classify-button");if(button.disabled)return;
    const text=$("sample-text").value.trim();if(!text)return;
    const previous=button.innerHTML;button.disabled=true;button.innerHTML='<span class="loading-spinner"></span> 분류 중';
    $("classification-result").hidden=false;$("classification-result").innerHTML='<p class="model-notice">서버의 실제 분류 결과를 기다리고 있습니다.</p>';
    try{const result=await request("/api/model/classify",{method:"POST",body:JSON.stringify({text,field_path:$("field-path").value.trim(),description:$("field-description").value.trim(),...backendBody("classify-backend")})});$("classification-result").innerHTML='<label class="field-label">모델 분류 후보 · 검토 필요</label><p class="model-notice">모델의 확신도는 법적 판단의 정확도를 보장하지 않습니다. 자동 차단이나 법적 확정에 사용하지 않습니다.</p>'+keyValues(result);}
    catch(error){$("classification-result").innerHTML=`<p class="model-notice">분류를 완료하지 못했습니다. ${escapeHtml(error.message)}</p>`;}
    finally{button.disabled=false;button.innerHTML=previous;}
  }
  async function suggestMapping(event) {
    event.preventDefault();
    const button=$("mapping-button");if(button.disabled)return;
    const field_path=$("mapping-path").value.trim(),description=$("mapping-description").value.trim();
    if(!field_path||!description)return;
    const previous=button.innerHTML;button.disabled=true;button.innerHTML='<span class="loading-spinner"></span> 후보 분석 중';
    $("mapping-result").hidden=false;$("mapping-result").innerHTML='<p class="model-notice">필드 의미를 분석하고 있습니다. 매핑은 자동 승인되지 않습니다.</p>';
    try{const result=await request("/api/mapping/suggest",{method:"POST",body:JSON.stringify({field_path,description,...backendBody("mapping-backend")})});$("mapping-result").innerHTML='<label class="field-label">제안 결과 · 검토 전 후보</label>'+keyValues(result);}
    catch(error){$("mapping-result").innerHTML=`<p class="model-notice">매핑 후보를 생성하지 못했습니다. ${escapeHtml(error.message)}</p>`;}
    finally{button.disabled=false;button.innerHTML=previous;}
  }

  const incidentNumber = (value) => value===null||value===undefined ? "알 수 없음" : number(value);
  function incidentStatus(message,type="info") {
    $("incident-status").className=`incident-status ${type}`;
    $("incident-status").textContent=message;
    $("incident-status").hidden=!message;
  }
  function incidentActorOptions(preferred=$("incident-actor").value) {
    const run=incidentRuns.find(item=>String(item.id)===$("incident-run").value);
    const actors=[...new Set(arr(run?.actors).map(actor=>typeof actor==="object"?actor.actor||actor.name||actor.id:actor).filter(Boolean))];
    $("incident-actor").innerHTML='<option value="all">모든 계정</option>'+actors.map(actor=>`<option value="${escapeHtml(actor)}">${escapeHtml(actor)}</option>`).join("");
    $("incident-actor").value=actors.includes(preferred)||preferred==="all"?preferred:actors.includes("bob")?"bob":"all";
  }
  function incidentParams() {
    return new URLSearchParams({run_id:$("incident-run").value,actor:$("incident-actor").value,capture:$("incident-capture").value});
  }
  function clearIncidentResult() {
    incidentReport=null;$("incident-results").hidden=true;$("incident-evidence").hidden=true;$("incident-empty").hidden=false;
    $("incident-empty").innerHTML=empty("조사 범위를 선택하고 저장 로그를 분석하세요","이미 수집된 기록만 조회합니다. API 요청을 재현하거나 AI 모델을 다시 실행하지 않습니다.");
  }
  async function loadIncidentRuns({preferred,analyze=false}={}) {
    if(incidentLoading)return;
    incidentLoading=true;$("incident-refresh-runs").disabled=true;
    try {
      const result=await request("/api/incidents/runs");
      incidentRuns=arr(result.runs);incidentLoaded=true;
      let saved={};try {saved=JSON.parse(sessionStorage.getItem("guardflow-incident-scope")||"{}");}catch{}
      const previous=preferred||$("incident-run").value||saved.run_id;
      $("incident-run").innerHTML=incidentRuns.length?incidentRuns.map(run=>`<option value="${escapeHtml(run.id)}">${escapeHtml(date(run.created_at))} · ${escapeHtml(modeLabel(run.mode))} · ${number(run.event_count)}건 · ${escapeHtml(run.id)}</option>`).join(""):'<option value="">저장된 조사 기록 없음</option>';
      if(incidentRuns.some(run=>String(run.id)===String(previous)))$("incident-run").value=previous;
      incidentActorOptions(saved.actor||"bob");
      if(["full","metadata_only"].includes(saved.capture))$("incident-capture").value=saved.capture;
      $("incident-analyze").disabled=!incidentRuns.length;
      if(!incidentRuns.length) {clearIncidentResult();$("incident-empty").innerHTML=empty("조사할 저장 로그가 없습니다","아래 ‘합성 조사 로그 준비’로 시연용 요청을 수집한 뒤 분석할 수 있습니다.");}
      incidentStatus("");
    }catch(error){incidentStatus(`저장 목록을 불러오지 못했습니다. ${error.message}`,"error");clearIncidentResult();}
    finally{incidentLoading=false;$("incident-refresh-runs").disabled=false;}
    if(analyze&&incidentRuns.length)await analyzeIncident();
  }
  async function analyzeIncident(event) {
    event?.preventDefault();
    const button=$("incident-analyze");if(button.disabled||!$("incident-run").value)return;
    const original=button.innerHTML,params=incidentParams();
    button.disabled=true;button.innerHTML='<span class="loading-spinner"></span> 저장 로그 조회 중';
    incidentStatus("PostgreSQL에 남아 있는 기록을 조회하고 있습니다. 대상 API를 재호출하지 않습니다.");
    for(const id of ["incident-run","incident-actor","incident-capture","incident-prepare","incident-refresh-runs"])$(id).disabled=true;
    try {
      const report=await request(`/api/incidents/analyze?${params}`);
      incidentReport=report;
      try {sessionStorage.setItem("guardflow-incident-scope",JSON.stringify(Object.fromEntries(params)));}catch{}
      $("incident-report").href=`/api/incidents/report?${params}`;
      renderIncident();
      incidentStatus("저장된 로그의 분석을 완료했습니다. 새 진단 요청 0건 · AI 재실행 없음","success");
    }catch(error){clearIncidentResult();incidentStatus(`저장 로그 분석을 완료하지 못했습니다. ${error.message}`,"error");}
    finally{button.disabled=false;button.innerHTML=original;for(const id of ["incident-run","incident-actor","incident-capture","incident-prepare","incident-refresh-runs"])$(id).disabled=false;}
  }
  async function prepareIncident() {
    const button=$("incident-prepare");if(button.disabled)return;
    const original=button.innerHTML;button.disabled=true;button.innerHTML='<span class="loading-spinner"></span> 합성 로그 수집 중';
    incidentStatus("합성 API에 시연용 요청을 보내 새 조사 기록을 만들고 있습니다. 완료 후 저장된 로그를 분석합니다.");
    try {
      const result=await request("/api/incidents/demo/prepare",{method:"POST"});
      $("incident-capture").value="full";
      try{sessionStorage.setItem("guardflow-incident-scope",JSON.stringify({run_id:result.run_id,actor:"bob",capture:"full"}));}catch{}
      await loadIncidentRuns({preferred:result.run_id,analyze:true});
    }catch(error){incidentStatus(`합성 로그를 준비하지 못했습니다. ${error.message}`,"error");}
    finally{button.disabled=false;button.innerHTML=original;}
  }
  function renderIncident() {
    const report=incidentReport,s=object(report.summary),metadata=report.analysis_mode==="metadata_only_simulation",coverage=object(report.coverage);
    $("incident-results").hidden=false;$("incident-empty").hidden=true;$("incident-evidence").hidden=true;
    $("incident-result-subtitle").textContent=`${report.actor==="all"?"모든 계정":report.actor} · 실행 ${report.run?.id||"미확인"} · ${metadata?"요청 메타데이터만 사용":"저장된 응답 증거 포함"}`;
    const stats=[
      {key:"logged_requests",name:"기록된 호출",note:"선택한 조사 범위의 요청 수",icon:"≡"},
      {key:"api_count",name:"접근 API",note:"일반화한 엔드포인트 수",icon:"↗"},
      {key:"http_success",name:"HTTP 성공 응답",note:"인가의 정상 여부와 별개",icon:"✓"},
      {key:"confirmed_policy_requests",name:"정책 위반 확인 요청",note:metadata?"응답·정책 증거를 사용하지 않음":"저장된 정책 판정과 응답 근거",icon:"!",className:"danger"},
      {key:"returned_subjects",name:"응답 내 정보 주체",note:metadata?"조회 대상과 실제 반환은 다름":"테넌트·식별자별 중복 제거",icon:"◎"},
      {key:"confirmed_exposure_subjects",name:"비인가 노출 정보 주체",note:metadata?"응답 증거가 없어 산정 불가":"위반 확인 응답 내 식별자 수",icon:"◇",className:"blue"}
    ];
    $("incident-stats").innerHTML=stats.map(item=>`<div class="stat-card ${item.className||""}"><div class="stat-top"><span>${item.name}</span><span class="stat-icon">${item.icon}</span></div><div class="stat-value ${s[item.key]===null||s[item.key]===undefined?"unknown-value":""}" data-incident-metric="${item.key}">${incidentNumber(s[item.key])}</div><div class="stat-bottom">${item.note}</div></div>`).join("");
    $("incident-coverage").innerHTML=`<div class="incident-coverage-top"><strong>이 결과는 ‘남아 있는 기록’의 범위입니다</strong><div class="tags"><span class="tag needs_review">로그 완전성 미확인</span><span class="tag ${metadata?"needs_review":"blue"}">${metadata?"응답 증거 사용 안 함":coverage.response_evidence_available?"저장 응답 증거 사용":"응답 증거 없음"}</span></div></div><p>첫 관측 ${escapeHtml(date(report.window?.first_observed))} <span class="badge-divider">→</span> 마지막 관측 ${escapeHtml(date(report.window?.last_observed))}</p><p>${metadata?"호출 이력과 요청 대상은 볼 수 있지만, 실제 반환된 사람·항목·비인가 노출 규모는 알 수 없습니다.":"중복 요청은 호출 수에 각각 포함됩니다. 사람 수는 테넌트와 식별자를 기준으로 중복 제거하며, 전체 피해자 수를 뜻하지 않습니다."}</p>${arr(coverage.notes).length?`<details class="details-toggle"><summary>수집 범위와 증거 상태 확인</summary>${listIncidentNotes(coverage.notes)}</details>`:""}`;
    const calls=arr(report.api_calls);
    $("incident-api-table").innerHTML=calls.length?`<div class="table-scroll"><table><thead><tr><th>접근 API</th><th>호출</th><th>성공 / 거부 / 기타</th><th>정책 위반 요청</th><th>요청한 조회 대상</th><th>저장 근거</th></tr></thead><tbody>${calls.map(call=>`<tr><td><div class="mono cell-title">${escapeHtml(call.method)} ${escapeHtml(call.endpoint)}</div><div class="cell-subtitle">${number(arr(call.paths).length)}개 실제 요청 경로</div></td><td class="incident-count">${incidentNumber(call.requests)}</td><td class="nowrap">${incidentNumber(call.http_success)} / ${incidentNumber(call.denied)} / ${incidentNumber(call.other)}</td><td>${incidentNumber(call.confirmed_policy_requests)}</td><td>${tags(call.requested_targets)}</td><td><div class="evidence-links">${arr(call.evidence_ids).map(id=>`<button class="evidence-button" data-incident-event="${escapeHtml(id)}">#${escapeHtml(id)}</button>`).join("")}</div></td></tr>`).join("")}</tbody></table></div>`:empty("이 범위의 API 접근 기록이 없습니다","선택한 계정과 실행 기록을 확인하세요.");
    const subjects=arr(report.subjects);
    $("incident-subjects").innerHTML=metadata?`<div class="incident-unavailable"><span>?</span><div><strong>응답 증거가 없어 정보 주체를 집계할 수 없습니다</strong><p>URL에서 요청한 ID가 보이더라도, 그 사람의 정보가 실제 반환됐다는 증거는 아닙니다.</p></div></div>`:subjects.length?subjects.map(subject=>`<article class="link-card"><div class="link-card-top"><h3>${escapeHtml(subject.subject_id)}</h3><span class="tag ${arr(subject.confirmed_event_ids).length?"confirmed":"plain"}">${arr(subject.confirmed_event_ids).length?"비인가 반환 근거 있음":"응답에서 관측"}</span></div><p><b>${escapeHtml(subject.tenant)}</b> · ${escapeHtml(subject.namespace)}</p><div class="field-label">선택한 응답 전체에서 관측된 필드</div>${tags(subject.fields)}<div class="incident-confirmed-fields"><div class="field-label">비인가 반환 근거가 있는 필드</div>${tags(subject.confirmed_fields)}</div><p class="mono">${arr(subject.endpoints).map(endpoint=>escapeHtml(endpoint)).join("<br>")}</p><div class="evidence-links">${arr(subject.event_ids).map(id=>`<button class="evidence-button" data-incident-event="${escapeHtml(id)}">#${escapeHtml(id)}</button>`).join("")}</div></article>`).join(""):empty("식별 가능한 정보 주체가 기록되지 않았습니다","필드 누락과 수집 범위 때문에 집계되지 않은 정보가 있을 수 있습니다.");
    const timeline=arr(report.timeline);
    $("incident-timeline").innerHTML=timeline.length?`<div class="table-scroll"><table><thead><tr><th>저장 시각 / 증거</th><th>요청 계정</th><th>요청 경로</th><th>HTTP</th><th>저장된 판정</th><th>증거 체크섬</th></tr></thead><tbody>${timeline.map(event=>`<tr class="clickable-row" role="button" tabindex="0" data-incident-event="${escapeHtml(event.event_id)}" aria-label="저장 증거 ${escapeHtml(event.event_id)} 확인"><td class="nowrap">${escapeHtml(date(event.created_at))}<div class="cell-subtitle">#${escapeHtml(event.event_id)}</div></td><td>${escapeHtml(event.actor)}<div class="cell-subtitle">${escapeHtml(event.actor_tenant)}</div></td><td class="mono">${escapeHtml(event.method)} ${escapeHtml(event.path)}</td><td>${valueText(event.status_code)}</td><td>${metadata?'<span class="tag plain">증거 사용 안 함</span>':tag(event.verdict)}</td><td><span class="tag ${event.integrity_ok===true?"allowed":event.integrity_ok===false?"confirmed":"plain"}">${event.integrity_ok===true?"일치":event.integrity_ok===false?"불일치":"미확인"}</span></td></tr>`).join("")}</tbody></table></div>`:empty("시간순 호출 기록이 없습니다","조회 범위에 해당하는 저장 요청이 없습니다.");
    $("incident-conclusions").innerHTML=listIncidentNotes(report.conclusions);
    $("incident-limitations").innerHTML=listIncidentNotes(report.limitations);
    const candidates=metadata?[]:arr(report.stored_model_candidates);
    $("incident-model-section").hidden=!candidates.length;
    $("incident-model-candidates").innerHTML=candidates.length?`<details class="details-toggle"><summary>저장된 후보 ${number(candidates.length)}건 확인</summary>${jsonBlock(candidates)}</details>`:"";
  }
  function listIncidentNotes(notes) {
    const items=arr(notes);return items.length?`<ul class="incident-note-list">${items.map(note=>`<li>${valueText(note)}</li>`).join("")}</ul>`:'<p class="model-notice">서버에서 제공한 추가 설명이 없습니다.</p>';
  }
  function showIncidentEvidence(id) {
    if(!incidentReport)return;
    const event=arr(incidentReport.timeline).find(item=>String(item.event_id)===String(id));if(!event)return;
    const metadata=incidentReport.analysis_mode==="metadata_only_simulation",panel=$("incident-evidence");
    const metadataFields={event_id:event.event_id,created_at:event.created_at,actor:event.actor,actor_tenant:event.actor_tenant,method:event.method,path:event.path,status_code:event.status_code,integrity_ok:event.integrity_ok};
    panel.hidden=false;panel.innerHTML=`<div class="card-heading"><div><div class="section-kicker">STORED EVIDENCE #${escapeHtml(event.event_id)}</div><h2>조사 근거 상세</h2></div><button class="text-button" id="incident-close-evidence">닫기 ×</button></div><div class="inline-note">분석 대상으로 선택한 실행의 저장 기록입니다. ${metadata?"응답·판정·개인정보 분류는 읽지 않는 모드입니다.":"응답은 마스킹되어 있습니다. 체크섬 일치만으로 로그의 완전성이나 변조 불가능성을 보장하지 않습니다."}</div><div class="detail-grid"><div class="detail-block"><label>요청 메타데이터</label>${jsonBlock(metadataFields)}</div><div class="detail-block"><label>${metadata?"응답 증거 사용 안 함":"저장된 응답 · 분류"}</label>${metadata?'<div class="incident-unavailable"><div><strong>실제 반환 내용은 알 수 없습니다</strong><p>요청한 대상과 반환된 대상의 일치를 확인할 증거가 없습니다.</p></div></div>':jsonBlock({verdict:event.verdict,response_redacted:event.response_redacted,fields:event.fields})}</div></div>`;
    panel.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
  }

  document.addEventListener("click",event=>{
    const incidentEvent=event.target.closest("[data-incident-event]");if(incidentEvent){showIncidentEvidence(incidentEvent.dataset.incidentEvent);return;}
    if(event.target.closest("#incident-close-evidence")){$("incident-evidence").hidden=true;return;}
    const tab=event.target.closest("[data-tab]");if(tab){changeTab(tab.dataset.tab);return;}
    const finding=event.target.closest("[data-finding]");if(finding){showFinding(Number(finding.dataset.finding));return;}
    const evidence=event.target.closest("[data-event]");if(evidence){showEvent(Number(evidence.dataset.event));return;}
    const run=event.target.closest("[data-run]");if(run)runDemo(run.dataset.run);
  });
  document.addEventListener("keydown",event=>{if((event.key==="Enter"||event.key===" ")&&event.target.matches("tr[role=button]")){event.preventDefault();event.target.click();}});
  $("refresh").addEventListener("click",()=>{refresh();if(location.hash==="#incidents")loadIncidentRuns({analyze:true});});
  $("verdict-filter").addEventListener("change",renderFindings);
  $("classify-form").addEventListener("submit",classify);
  $("mapping-form").addEventListener("submit",suggestMapping);
  $("incident-form").addEventListener("submit",analyzeIncident);
  $("incident-prepare").addEventListener("click",prepareIncident);
  $("incident-refresh-runs").addEventListener("click",()=>loadIncidentRuns({analyze:true}));
  $("incident-run").addEventListener("change",()=>{incidentActorOptions();clearIncidentResult();incidentStatus("");});
  $("incident-actor").addEventListener("change",()=>{clearIncidentResult();incidentStatus("");});
  $("incident-capture").addEventListener("change",()=>{clearIncidentResult();incidentStatus("");});
  window.addEventListener("hashchange",()=>changeTab(location.hash.slice(1)));
  clearIncidentResult();render();refresh();changeTab(Object.hasOwn(labels,location.hash.slice(1))?location.hash.slice(1):"overview");
})();
