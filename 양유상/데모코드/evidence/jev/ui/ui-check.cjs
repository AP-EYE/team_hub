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
const base = 'http://127.0.0.1:8810';
const out = __dirname;
const report = {status:'RUNNING', at:new Date().toISOString(),source:'Live same-origin lab APIs; no inference or evaluation POST requests',checks:[],screenshots:[],errors:[],console_errors:[],failed_requests:[],write_requests:[]};
const check = (name,passed,detail='') => report.checks.push({name,passed,detail});
const has = (text,value) => text.includes(String(value));
(async()=>{
  const browser = await chromium.launch({headless:true,channel:'chrome'});
  const page = await browser.newPage({viewport:{width:1440,height:1100},deviceScaleFactor:1});
  report.browser=await browser.version();
  page.on('pageerror',error=>report.errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')report.console_errors.push(message.text());});
  page.on('requestfailed',request=>report.failed_requests.push({url:request.url(),error:request.failure()}));
  page.on('request',request=>{if(!['GET','HEAD'].includes(request.method()))report.write_requests.push({method:request.method(),url:request.url()});});
  const response=await page.goto(base+'/privacy-lab',{waitUntil:'networkidle',timeout:60000});
  check('http_200',response.status()===200,response.status());
  await page.locator('#case-list [data-case]').first().waitFor({timeout:30000});
  const snapshot=await page.request.get(base+'/api/jev/state').then(r=>r.json());
  report.runtime=snapshot.runtime;
  report.evaluation_status=snapshot.evaluation?.status;
  report.evaluated_counts=Object.fromEntries(Object.entries(snapshot.evaluation?.methods||{}).map(([name,m])=>[name,m.count]));
  report.dataset=snapshot.evaluation?.dataset;
  const original=snapshot.cases[0];
  check('actual_case_count',await page.locator('#case-list [data-case]').count()===snapshot.cases.length,snapshot.cases.length);
  check('first_case_input',await page.locator('#input-text').inputValue()===(original.text||''));
  check('first_case_expected_visible',await page.locator('#case-expectation').innerText().then(t=>has(t,snapshot.labels[original.expected].name)));
  check('three_input_modes',await page.locator('#input-mode option').count()===3);
  check('two_live_methods',await page.locator('#method option').count()===2);
  check('official_jev_identity_distinction',await page.locator('.identity-note').innerText().then(t=>t.includes('공식 TypeSafe Jev와 별개')));
  check('original_name_openjev_visible',await page.locator('.identity-strip').innerText().then(t=>t.includes('OpenJev')));
  check('desktop_experiment_no_overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#input-text').fill((original.text||'')+' 편집');
  check('edited_input_comparison_disabled',await page.locator('#case-expectation').innerText().then(t=>t.includes('자동 비교를 중지')));
  await page.locator('#case-list [data-case]').first().click();
  await page.locator('#input-mode').selectOption('schema_only');
  check('schema_only_expected_disabled',await page.locator('#case-expectation').innerText().then(t=>t.includes('자동 비교를 중지')));
  check('schema_only_exclusion_explained',await page.locator('#input-mode-note').innerText().then(t=>t.includes('값은 추론 입력에서 제외')));
  await page.locator('#input-mode').selectOption('value_only');
  check('value_only_exclusion_explained',await page.locator('#input-mode-note').innerText().then(t=>t.includes('필드명과 설명은 추론 입력에서 제외')));
  await page.locator('#case-list [data-case]').first().click();
  await page.locator('#case-label').selectOption('RELIGION');
  check('label_filter_count',await page.locator('#case-list [data-case]').count()===snapshot.cases.filter(c=>c.expected==='RELIGION').length);
  await page.locator('#case-label').selectOption('all');
  const slice=snapshot.cases.find(c=>c.slice==='prompt_injection')?.slice||snapshot.cases[0].slice;
  await page.locator('#case-slice').selectOption(slice);
  check('slice_filter_count',await page.locator('#case-list [data-case]').count()===snapshot.cases.filter(c=>c.slice===slice).length);
  await page.locator('#case-slice').selectOption('all');
  await page.locator('#case-search').fill('no-such-case-7a9c4');
  check('case_search_empty_visible',await page.locator('#case-list .empty').isVisible());
  await page.locator('#case-search').fill('');
  const classified=(snapshot.evaluation?.rows||[]).find(row=>row.methods?.semif?.probabilities);
  if(classified){
    await page.locator(`[data-case="${classified.id}"]`).click();
    check('saved_three_methods',await page.locator('.saved-method').count()===3);
    await page.locator('.saved-scores summary').click();
    check('saved_eight_score_bars',await page.locator('.saved-scores .score-row').count()===8);
    const chosen=classified.methods.semif;
    check('saved_actual_label',await page.locator('.saved-method').first().innerText().then(t=>t.includes(snapshot.labels[chosen.label]?.name||chosen.label)));
    check('saved_score_not_confidence',await page.locator('.saved-scores').innerText().then(t=>t.includes('보정된 신뢰도가 아닙니다')));
  }
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:path.join(out,'desktop-experiment.png'),fullPage:true});report.screenshots.push('desktop-experiment.png');
  await page.locator('aside [data-tab="evaluation"]').click();
  check('evaluation_tab_visible',await page.locator('#panel-evaluation').isVisible());
  check('three_method_cards',await page.locator('.method-card').count()===3);
  for(const method of ['semif','json','rules']){
    await page.locator('#matrix-method').selectOption(method);
    const metrics=await page.evaluate(key=>state?.evaluation?.methods?.[key],method);
    if(metrics?.count){
      check(method+'_matrix_eight_rows',await page.locator('#confusion-matrix tbody tr').count()===8);
      const total=await page.locator('#confusion-matrix tbody td').allTextContents().then(vals=>vals.reduce((sum,value)=>sum+Number(value),0));
      const expected=Object.values(metrics.confusion_matrix||{}).reduce((sum,row)=>sum+Object.values(row).reduce((s,v)=>s+Number(v),0),0);
      check(method+'_matrix_preserves_all_counts',total===expected,{observed:total,expected});
      check(method+'_per_label_eight_rows',await page.locator('#per-label tbody tr').count()===8);
    }else check(method+'_unmeasured_visible',await page.locator('#confusion-matrix .empty').isVisible());
  }
  await page.locator('#matrix-method').selectOption('semif');
  for(const threshold of [0,80,100]){
    await page.locator('#threshold').fill(String(threshold));
    const rows=await page.evaluate(()=>(state?.evaluation?.rows||[]).filter(row=>row.methods?.semif));
    const accepted=rows.filter(row=>{const r=row.methods.semif;return r.label&&r.label!=='UNKNOWN'&&!['error','failed','unavailable'].includes(r.status)&&r.score!=null&&Number(r.score)>=threshold/100;});
    if(rows.length){const count=await page.locator('.threshold-stat strong').first().evaluate(e=>e.childNodes[0].textContent.trim());check('threshold_'+threshold+'_actual_accepted',Number(count)===accepted.length,{observed:Number(count),expected:accepted.length});}
  }
  await page.locator('#threshold').fill('80');
  check('threshold_unknown_review_visible',await page.locator('.threshold-layout').innerText().then(t=>t.includes('UNKNOWN')&&t.includes('검토')));
  check('desktop_evaluation_no_overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  check('authored_set_limit_visible',await page.locator('.scope-note').innerText().then(t=>t.includes('실제 서비스 정확도를 뜻하지')));
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:path.join(out,'desktop-evaluation.png'),fullPage:true});report.screenshots.push('desktop-evaluation.png');
  await page.locator('#confusion-matrix').screenshot({path:path.join(out,'desktop-confusion-matrix.png')});report.screenshots.push('desktop-confusion-matrix.png');
  await page.locator('aside [data-tab="guide"]').click();
  check('eight_label_guide_cards',await page.locator('.guide-card').count()===8);
  check('actual_commit_visible',await page.locator('#runtime-facts').innerText().then(t=>t.includes(snapshot.runtime.semif_commit)));
  check('actual_dataset_sha_visible',await page.locator('#runtime-facts').innerText().then(t=>t.includes(snapshot.evaluation?.dataset?.sha256||'미확인')));
  check('calibration_limit_visible',await page.locator('.guide-notes').innerText().then(t=>t.includes('실제 정답률이 90%라는 뜻은 아닙니다')));
  check('desktop_guide_no_overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:path.join(out,'desktop-guide.png'),fullPage:true});report.screenshots.push('desktop-guide.png');
  await page.setViewportSize({width:390,height:844});
  for(const tab of ['experiment','evaluation','guide']){
    await page.locator(`.mobile-tabs [data-tab="${tab}"]`).click();
    await page.evaluate(()=>scrollTo(0,0));
    check('mobile_'+tab+'_visible',await page.locator('#panel-'+tab).isVisible());
    check('mobile_'+tab+'_no_overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(out,'mobile-'+tab+'.png'),fullPage:tab!=='evaluation'});report.screenshots.push('mobile-'+tab+'.png');
  }
  await page.locator('.mobile-tabs [data-tab="evaluation"]').click();
  check('mobile_matrix_scrolls_inside_container',await page.locator('#confusion-matrix').evaluate(e=>e.scrollWidth>e.clientWidth&&e.clientWidth<390));
  await page.locator('.mobile-tabs [data-tab="experiment"]').click();
  const reportResponse=await page.request.get(base+'/api/jev/report');
  check('markdown_report_available_or_explicitly_pending',[200,409].includes(reportResponse.status()),reportResponse.status());
  if(reportResponse.status()===200)check('report_is_markdown',(reportResponse.headers()['content-type']||'').includes('text/markdown'));
  await page.goto(base,{waitUntil:'networkidle'});
  check('existing_dashboard_lab_link',await page.locator('a[href="/privacy-lab"]').count()===1);
  check('no_javascript_errors',report.errors.length===0,report.errors);
  check('no_console_errors',report.console_errors.length===0,report.console_errors);
  check('no_failed_requests',report.failed_requests.length===0,report.failed_requests);
  check('no_inference_or_mutation_requests',report.write_requests.length===0,report.write_requests);
  await browser.close();
  report.passed=report.checks.filter(item=>item.passed).length;report.total=report.checks.length;report.status=report.passed===report.total?'PASS':'FAIL';
  fs.writeFileSync(path.join(out,'ui-validation.json'),JSON.stringify(report,null,2),'utf8');
  console.log(JSON.stringify({status:report.status,passed:report.passed,total:report.total,failed:report.checks.filter(c=>!c.passed),screenshots:report.screenshots}));
  if(report.status!=='PASS')process.exitCode=1;
})().catch(error=>{report.status='ERROR';report.failure=String(error.stack||error);fs.writeFileSync(path.join(out,'ui-validation.json'),JSON.stringify(report,null,2),'utf8');console.error(error);process.exitCode=1;});
