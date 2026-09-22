let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (error) {
  const modulePath = process.env.DEMO_PLAYWRIGHT_MODULE;
  if (!modulePath) throw error;
  ({ chromium } = require(modulePath));
}
const fs = require('node:fs');
const path = require('node:path');
const out = __dirname;
const base = 'http://127.0.0.1:8810';

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 });
  const errors = [], consoleErrors = [], failedRequests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if(message.type()==='error') consoleErrors.push(message.text()); });
  page.on('requestfailed', request => failedRequests.push({url:request.url(),error:request.failure()}));
  const response = await page.goto(base, { waitUntil: 'networkidle' });
  await page.locator('#connection.online').waitFor();
  const snapshot = await page.request.get(base+'/api/state').then(r=>r.json());
  const report = {status:'RUNNING',at:new Date().toISOString(),browser:await browser.version(),source:'Live localhost API; no demo runs initiated by this check',http_status:response.status(),observed_run_id:snapshot.runs?.[0]?.id,observed_summary:snapshot.summary,selected_backend:snapshot.model?.selected_backend,selected_model:snapshot.model?.model,checks:[],screenshots:[]};
  const check = (name,passed,detail='') => report.checks.push({name,passed,detail});
  check('overview_loaded',await page.locator('#tab-overview').isVisible());
  check('five_actual_counters',await page.locator('.stat-card').count()===5);
  check('desktop_no_page_overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'desktop-overview.png'),fullPage:true});report.screenshots.push('desktop-overview.png');
  for(const tab of ['findings','events','mapping','model']) {
    await page.locator('.nav-item[data-tab="'+tab+'"]').click();
    check(tab+'_tab_visible',await page.locator('#tab-'+tab).isVisible());
    check(tab+'_no_page_overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(out,'desktop-'+tab+'.png'),fullPage:true});report.screenshots.push('desktop-'+tab+'.png');
    if(tab==='model') { await page.locator('#benchmark-comparison').screenshot({path:path.join(out,'desktop-model-comparison.png')});report.screenshots.push('desktop-model-comparison.png'); }
  }
  check('three_benchmark_cards',await page.locator('#benchmark-comparison .benchmark-card').count()===3);
  check('direct_below_baseline_visible',await page.locator('#benchmark-comparison .benchmark-hold').innerText().then(t=>t.includes('채택 보류')));
  const alternativeModel=snapshot.model?.alternative_benchmarks?.['evaluation-summary']?.model_id;
  check('alternative_model_identity_visible',Boolean(alternativeModel)&&await page.locator('#benchmark-comparison').innerText().then(t=>t.includes(alternativeModel)),alternativeModel);
  const alternativeMetrics=snapshot.model?.alternative_benchmarks?.['evaluation-summary'];
  check('alternative_actual_correct_count',await page.locator('#benchmark-comparison').innerText().then(t=>t.includes(`${alternativeMetrics.correct} / ${alternativeMetrics.count} 정답`)));
  for(const id of ['classify-backend','mapping-backend']) {
    await page.locator('.nav-item[data-tab="'+(id==='classify-backend'?'model':'mapping')+'"]').click();
    check(id+'_three_options',await page.locator('#'+id+' option').count()===3);
    await page.locator('#'+id).selectOption('direct');check(id+'_direct_selectable',await page.locator('#'+id).inputValue()==='direct');
    await page.locator('#'+id).selectOption('ollama');check(id+'_ollama_selectable',await page.locator('#'+id).inputValue()==='ollama');
    await page.locator('#'+id).selectOption('');check(id+'_default_omits_override',await page.locator('#'+id).inputValue()==='');
  }
  await page.locator('.nav-item[data-tab="findings"]').click();
  if(await page.locator('#findings-table tbody tr').count()) {
    await page.locator('#findings-table tbody tr').first().click();
    check('finding_detail_opens',await page.locator('#finding-detail').isVisible());
    if(await page.locator('#finding-detail [data-event]').count()) {
      await page.locator('#finding-detail [data-event]').first().click();
      check('finding_links_to_event',await page.locator('#event-detail').isVisible()&&await page.locator('#tab-events').isVisible());
      await page.screenshot({path:path.join(out,'desktop-evidence.png'),fullPage:true});report.screenshots.push('desktop-evidence.png');
    }
  } else check('live_empty_findings_visible',await page.locator('#findings-table .empty-state').isVisible());
  await page.setViewportSize({width:390,height:844});
  for(const tab of ['overview','findings','events','mapping','model']) {
    await page.locator('.nav-item[data-tab="'+tab+'"]').click();
    await page.evaluate(()=>scrollTo(0,0));
    check('mobile_'+tab+'_no_page_overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(out,'mobile-'+tab+'.png'),fullPage:tab==='overview'});report.screenshots.push('mobile-'+tab+'.png');
    if(tab==='model') { await page.locator('#benchmark-comparison').screenshot({path:path.join(out,'mobile-model-comparison.png')});report.screenshots.push('mobile-model-comparison.png'); }
  }
  // Isolated empty-state contract check; never modifies the server or stored evidence.
  await page.route('**/api/state', route=>route.fulfill({json:{meta:snapshot.meta,summary:{events:0,findings:0,confirmed:0,review:0,subjects:0},runs:[],events:[],findings:[],mappings:[],links:[],model:{status:'NOT_RUN'},evaluation:{status:'NOT_RUN'}}}));
  await page.reload({waitUntil:'networkidle'});
  const finalSnapshot=await page.request.get(base+'/api/state').then(r=>r.json());
  report.final_run_id=finalSnapshot.runs?.[0]?.id;
  check('representative_run_unchanged',report.observed_run_id===report.final_run_id);
  check('stored_event_count_unchanged',snapshot.summary?.total_events===finalSnapshot.summary?.total_events);
  check('empty_contract_zero_count',(await page.locator('.stat-value').allTextContents()).every(x=>x==='0'));
  check('empty_contract_explains_next_action',await page.locator('#recent-findings .empty-state').isVisible());
  await page.unroute('**/api/state');
  await page.reload({waitUntil:'networkidle'});
  check('no_uncaught_javascript_errors',errors.length===0,errors);
  check('no_browser_console_errors',consoleErrors.length===0,consoleErrors);
  check('no_failed_network_requests',failedRequests.length===0,failedRequests);
  report.console_errors=consoleErrors;report.failed_requests=failedRequests;report.page_errors=errors;
  report.status=report.checks.every(c=>c.passed)?'PASS':'FAIL';
  fs.writeFileSync(path.join(out,'ui-validation.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({status:report.status,checks:report.checks.length,failed:report.checks.filter(x=>!x.passed),errors,consoleErrors,output:out},null,2));
  await browser.close();
  if(report.status!=='PASS')process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1});
