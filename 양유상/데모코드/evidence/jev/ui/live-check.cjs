/* One real browser form submission. Run only after the batch evaluation ends. */
function loadPlaywright() {
  try { return require('playwright'); }
  catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND' || !error.message.includes("'playwright'")) throw error;
    if (process.env.DEMO_PLAYWRIGHT_MODULE) return require(process.env.DEMO_PLAYWRIGHT_MODULE);
    throw new Error('UI checks require Playwright. Use an installed playwright package or set DEMO_PLAYWRIGHT_MODULE to a prepared Playwright module path.', {cause:error});
  }
}
const { chromium } = loadPlaywright();
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const BASE = 'http://127.0.0.1:8810';
const CASE_ID = 'ko96-h01';
const OUT = __dirname;
const TIMEOUT_MS = 300000;
const LABELS = ['HEALTH','RELIGION','CONTACT','GOVERNMENT_ID','PERSON_NAME','ACCOUNT_ID','OTHER','UNKNOWN'];
const report = {
  status:'RUNNING', started_at:new Date().toISOString(),
  source:'One actual same-origin browser form POST; no mock, retry or fallback',
  fixed_case_id:CASE_ID, method:'semif', input_mode:'full',
  correctness_is_ui_pass_condition:false,
  checks:[], page_errors:[], console_errors:[], failed_requests:[],
  post_requests:[], screenshots:[]
};
let browser;
let page;
const check = (name,passed,detail='') => report.checks.push({name,passed,detail});
const duration = value => Number(value)<1000 ? `${Number(value).toFixed(0)} ms` : `${(Number(value)/1000).toFixed(2)}초`;
const percentage = (value,digits=1) => `${(Number(value)*100).toFixed(digits)}%`;
const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');

async function main() {
  browser=await chromium.launch({headless:true,channel:'chrome'});
  page=await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
  page.setDefaultTimeout(30000);
  report.browser=await browser.version();
  page.on('pageerror',error=>report.page_errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')report.console_errors.push(message.text());});
  page.on('requestfailed',request=>report.failed_requests.push({url:request.url(),error:request.failure()}));
  page.on('request',request=>{
    if(request.method()==='POST') report.post_requests.push({url:request.url(),method:request.method(),body:request.postData(),at:new Date().toISOString()});
  });

  const navigation=await page.goto(`${BASE}/privacy-lab`,{waitUntil:'networkidle',timeout:60000});
  check('lab_http_200',navigation.status()===200,navigation.status());
  await page.locator('#case-list [data-case]').first().waitFor();
  const stateResponse=await page.request.get(`${BASE}/api/jev/state`,{timeout:30000});
  if(!stateResponse.ok())throw new Error(`State request failed: HTTP ${stateResponse.status()}`);
  const snapshot=await stateResponse.json();
  report.runtime=snapshot.runtime;
  report.batch_status_at_start=snapshot.evaluation?.status||null;
  if(snapshot.evaluation?.status==='running') throw new Error('Batch evaluation is still running. No classification POST was submitted.');
  if(snapshot.runtime?.busy) throw new Error('The local worker is busy. No classification POST was submitted.');
  const selected=snapshot.cases.find(item=>item.id===CASE_ID);
  if(!selected)throw new Error(`Fixed synthetic case ${CASE_ID} was not present; no alternative was chosen.`);
  report.expected_label=selected.expected;
  report.expected_label_source='Demo-authored evaluation criterion; not a browser functionality requirement';

  await page.locator(`#case-list [data-case="${CASE_ID}"]`).click();
  await page.locator('#input-mode').selectOption('full');
  await page.locator('#method').selectOption('semif');
  check('fixed_case_selected',await page.locator('#selected-case').innerText()===CASE_ID);
  check('original_text_selected',await page.locator('#input-text').inputValue()===(selected.text||''));
  check('full_mode_selected',await page.locator('#input-mode').inputValue()==='full');
  check('semif_method_selected',await page.locator('#method').inputValue()==='semif');

  // Register the response listener before the single click. Never click again.
  const responsePromise=page.waitForResponse(response=>{
    return new URL(response.url()).pathname==='/api/jev/classify' && response.request().method()==='POST';
  },{timeout:TIMEOUT_MS});
  const requestStarted=performance.now();
  report.submitted_at=new Date().toISOString();
  await page.locator('#classify-button').click();
  check('button_disabled_during_inference',await page.locator('#classify-button').isDisabled());
  const response=await responsePromise;
  const rawBody=await response.body();
  report.response_received_at=new Date().toISOString();
  report.browser_submission_to_body_ms=Number((performance.now()-requestStarted).toFixed(2));
  report.http_status=response.status();
  report.response_file='live-classification-response.json';
  report.response_sha256=sha256(rawBody);
  fs.writeFileSync(path.join(OUT,report.response_file),rawBody);
  const result=JSON.parse(rawBody.toString('utf8'));
  report.response_headers=response.headers();
  report.response_summary={
    label:result.label, score:result.score, allowed_token_mass:result.allowed_token_mass,
    model_latency_ms:result.latency_ms, model:result.model, source:result.source,
    status:result.status, input_mode:result.input_mode, semif_commit:result.semif_commit,
    generated_tokens:result.generated_tokens, external_inference:result.external_inference
  };
  // Classification quality is recorded separately; disagreement is not a UI failure.
  report.matches_expected=typeof result.label==='string' ? result.label===selected.expected : null;
  report.expected_and_observed={expected:selected.expected,observed:result.label||null};
  check('classification_http_200',response.status()===200,response.status());
  if(!response.ok())throw new Error(`The single classification request returned HTTP ${response.status()}. Raw response was saved; no retry or fallback occurred.`);

  await page.waitForFunction(()=>!document.getElementById('classify-button').disabled,{},{timeout:TIMEOUT_MS});
  await page.locator('#live-result .result-label').waitFor();
  const expectedName=snapshot.labels[result.label]?.name||result.label;
  const displayedLabel=await page.locator('#live-result .result-label').innerText();
  const displayedLatency=await page.locator('#live-result .result-meta').innerText();
  const displayedChosenScore=await page.locator('#live-result .score-row.chosen .score-value').innerText();
  check('displayed_label_matches_response',displayedLabel.includes(expectedName)&&displayedLabel.includes(result.label),{displayed:displayedLabel,response:result.label});
  check('displayed_selected_score_matches_response',displayedChosenScore===percentage(result.score),{displayed:displayedChosenScore,response:result.score});
  check('displayed_latency_matches_response',displayedLatency.includes(duration(result.latency_ms)),{displayed:displayedLatency,response_ms:result.latency_ms});
  check('eight_option_score_rows',await page.locator('#live-result .score-row').count()===8);
  for(let index=0;index<LABELS.length;index++){
    const label=LABELS[index];
    const actual=await page.locator('#live-result .score-row').nth(index).locator('.score-value').innerText();
    check(`score_${label}_matches_response`,actual===percentage(result.probabilities[label]),{displayed:actual,response:result.probabilities[label]});
  }
  const explanation=await page.locator('#live-result .score-explanation').first().innerText();
  check('allowed_token_mass_matches_response',explanation.includes(percentage(result.allowed_token_mass,3)),{displayed:explanation,response:result.allowed_token_mass});
  check('uncalibrated_score_explanation_visible',explanation.includes('보정된 신뢰도나 법적 판단이 아닙니다'));
  check('review_status_visible',await page.locator('.result-card .card-heading').innerText().then(text=>text.includes('검토 후보')));
  check('button_reenabled_after_response',await page.locator('#classify-button').isEnabled());
  check('no_live_error_displayed',await page.locator('#live-result .live-error').count()===0);
  check('exactly_one_post_request',report.post_requests.length===1,report.post_requests);
  const posted=report.post_requests[0];
  const requestBody=posted?.body?JSON.parse(posted.body):null;
  const expectedRequest={text:selected.text||'',field_path:selected.field_path||'',description:selected.description||'',input_mode:'full',method:'semif'};
  check('post_payload_matches_original_case',requestBody&&Object.entries(expectedRequest).every(([key,value])=>requestBody[key]===value),requestBody);
  check('post_is_same_origin_classify_route',posted?.url===`${BASE}/api/jev/classify`,posted?.url);
  check('desktop_no_page_overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:path.join(OUT,'desktop-live-experiment.png'),fullPage:true});report.screenshots.push('desktop-live-experiment.png');
  await page.locator('.result-card').screenshot({path:path.join(OUT,'desktop-live-result.png')});report.screenshots.push('desktop-live-result.png');
  report.displayed_latency=displayedLatency;
  report.latency_interpretation='model_latency_ms is the server-provided measured inference duration. browser_submission_to_body_ms includes the form submission and HTTP response body receipt. This is one sample, not a latency benchmark.';
  check('no_javascript_errors',report.page_errors.length===0,report.page_errors);
  check('no_console_errors',report.console_errors.length===0,report.console_errors);
  check('no_failed_requests',report.failed_requests.length===0,report.failed_requests);
}

main().catch(async error=>{
  report.failure=String(error.stack||error);
  report.status='ERROR';
  if(page){
    try{await page.screenshot({path:path.join(OUT,'live-failure.png'),fullPage:true,timeout:15000});report.screenshots.push('live-failure.png');}catch(screenshotError){report.failure_screenshot_error=String(screenshotError);}
  }
}).finally(async()=>{
  if(browser)await browser.close();
  report.finished_at=new Date().toISOString();
  report.passed=report.checks.filter(item=>item.passed).length;
  report.total=report.checks.length;
  if(report.status!=='ERROR')report.status=report.passed===report.total?'PASS':'FAIL';
  fs.writeFileSync(path.join(OUT,'live-validation.json'),JSON.stringify(report,null,2),'utf8');
  console.log(JSON.stringify({status:report.status,passed:report.passed,total:report.total,model_latency_ms:report.response_summary?.model_latency_ms,browser_submission_to_body_ms:report.browser_submission_to_body_ms,matches_expected:report.matches_expected,post_count:report.post_requests.length,failed:report.checks.filter(item=>!item.passed),failure:report.failure,screenshots:report.screenshots}));
  if(report.status!=='PASS')process.exitCode=1;
});
