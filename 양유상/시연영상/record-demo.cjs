const fs = require('node:fs');
const path = require('node:path');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (error) {
  const modulePath = process.env.DEMO_PLAYWRIGHT_MODULE;
  if (!modulePath) throw error;
  ({ chromium } = require(modulePath));
}

const root = __dirname;
const base = process.env.DEMO_BASE_URL || 'http://127.0.0.1:8810';
const browserCandidates = [
  process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES, 'Google', 'Chrome', 'Application', 'chrome.exe'),
  process.env['PROGRAMFILES(X86)'] && path.join(process.env['PROGRAMFILES(X86)'], 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  process.env.PROGRAMFILES && path.join(process.env.PROGRAMFILES, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
].filter(Boolean);
const browserExecutable = process.env.DEMO_BROWSER_EXECUTABLE || browserCandidates.find(candidate => fs.existsSync(candidate));
const timelinePath = path.join(root, 'rendered', 'audio', 'timeline.json');
const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
const outputDir = path.join(root, 'rendered', 'video');
fs.mkdirSync(outputDir, { recursive: true });
for (const file of fs.readdirSync(outputDir).filter(name => /^page@.*\.webm$/i.test(name))) {
  fs.rmSync(path.join(outputDir, file));
}
const sceneStarts = [];
let recordingOrigin;

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function subtitle(page, text, scene) {
  await page.evaluate(({ text, scene }) => {
    document.getElementById('codex-demo-caption')?.remove();
    const outer = document.createElement('div');
    outer.id = 'codex-demo-caption';
    outer.innerHTML = `<div class="demo-caption-kicker">${scene}</div><div class="demo-caption-text"></div>`;
    outer.querySelector('.demo-caption-text').textContent = text;
    Object.assign(outer.style, {
      position: 'fixed', zIndex: '2147483647', left: '6%', right: '6%', bottom: '20px',
      padding: '15px 24px 17px', borderRadius: '12px', color: '#fff',
      background: 'rgba(8, 20, 40, .94)', boxShadow: '0 6px 26px rgba(0,0,0,.28)',
      fontFamily: 'Malgun Gothic, Arial, sans-serif', textAlign: 'center',
      pointerEvents: 'none', lineHeight: '1.55', border: '1px solid rgba(173,203,255,.24)'
    });
    Object.assign(outer.querySelector('.demo-caption-kicker').style, {
      color: '#92bcff', fontSize: '13px', letterSpacing: '.08em', marginBottom: '4px', fontWeight: '700'
    });
    Object.assign(outer.querySelector('.demo-caption-text').style, {
      fontSize: '22px', fontWeight: '600'
    });
    document.body.appendChild(outer);
  }, { text, scene });
}

async function scene(page, entry, action) {
  await action();
  await subtitle(page, entry.caption, entry.id.replace(/^\d+-/, '').replaceAll('-', ' ').toUpperCase());
  const now = Date.now();
  recordingOrigin ??= now;
  sceneStarts.push({ id: entry.id, start_seconds: Number(((now - recordingOrigin) / 1000).toFixed(3)) });
  await delay(Math.ceil(entry.speech_seconds * 1000));
}

async function assertHealth() {
  for (const route of ['/', '/api/state', '/api/incidents/runs', '/api/jev/state']) {
    const response = await fetch(base + route);
    if (!response.ok) throw new Error(`${route} returned HTTP ${response.status}`);
  }
}

async function main() {
  await assertHealth();
  const browser = await chromium.launch({
    headless: true,
    ...(browserExecutable ? { executablePath: browserExecutable } : {}),
  });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    deviceScaleFactor: 1,
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
    recordVideo: { dir: outputDir, size: { width: 1600, height: 900 } },
  });
  const page = await context.newPage();
  const videoHandle = page.video();
  page.setDefaultTimeout(20_000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let screen = 0;

  try {
    const items = timeline.scenes;
    const entry = id => items.find(item => item.id.startsWith(id));
    const e1 = entry('01-title');
    await page.setContent(`<!doctype html><html lang="ko"><meta charset="utf-8"><body style="margin:0;background:linear-gradient(135deg,#0b1730,#123b63 60%,#1e6790);color:#fff;font-family:'Malgun Gothic',Arial,sans-serif"><main style="height:100vh;display:flex;align-items:center;justify-content:center;text-align:left"><section style="width:68%"><div style="color:#a6c8ff;letter-spacing:.18em;font-size:18px">AP-EYE · KICKOFF DEMO</div><h1 style="font-size:58px;line-height:1.25;margin:22px 0">API 보안 게이트웨이<br>기본 데모 + AI 실험실</h1><p style="font-size:26px;color:#d4e6ff">인가 제어 · 사후 로그 조사 · 한국어 개인정보 분류</p><div style="margin-top:42px;padding:14px 20px;border:1px solid #6595c8;border-radius:12px;display:inline-block;color:#d9eaff;font-size:18px">로컬 실행 · 합성 데이터 · 결과는 검토 후보</div></section></main></body></html>`);
    await scene(page, e1, async () => {});
    screen++;

    await page.goto(base + '/', { waitUntil: 'networkidle' });
    await page.waitForSelector('#tab-overview.active');
    await page.screenshot({ path: path.join(outputDir, '01-overview.png') });
    await scene(page, entry('02-overview'), async () => {});
    screen++;

    await page.locator('button.nav-item[data-tab="findings"]').click();
    await page.waitForSelector('#tab-findings.active');
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(outputDir, '02-findings.png'), fullPage: false });
    await scene(page, entry('03-findings'), async () => {});
    screen++;

    await page.locator('button.nav-item[data-tab="events"]').click();
    await page.waitForSelector('#tab-events.active');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outputDir, '03-events.png') });
    await scene(page, entry('04-events'), async () => {});
    screen++;

    await page.locator('button.nav-item[data-tab="mapping"]').click();
    await page.waitForSelector('#tab-mapping.active');
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(outputDir, '04-mapping.png') });
    await scene(page, entry('05-mapping'), async () => {});
    screen++;

    await page.locator('button.nav-item[data-tab="incidents"]').click();
    await page.waitForSelector('#tab-incidents.active');
    await page.waitForFunction(() => [...document.querySelectorAll('#incident-run option')].some(o => o.textContent.includes('incident-4bf3904446c9')));
    const runValue = await page.locator('#incident-run option').evaluateAll(options => options.find(o => o.textContent.includes('incident-4bf3904446c9'))?.value);
    if (!runValue) throw new Error('Saved synthetic incident run was not found');
    await page.locator('#incident-run').selectOption(runValue);
    const actors = await page.locator('#incident-actor option').evaluateAll(options => options.map(o => o.value));
    if (actors.includes('bob')) await page.locator('#incident-actor').selectOption('bob');
    await page.locator('#incident-capture').selectOption('full');
    await page.locator('#incident-analyze').click();
    await page.waitForFunction(() => document.querySelector('#incident-results')?.hidden === false);
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outputDir, '05-incident-full.png') });
    await scene(page, entry('06-incident-full'), async () => {});
    screen++;

    await page.locator('#incident-capture').selectOption('metadata_only');
    await page.locator('#incident-analyze').click();
    await page.waitForFunction(() => document.querySelector('#incident-results')?.hidden === false && document.querySelector('[data-incident-metric="returned_subjects"]')?.textContent.includes('알 수 없음'));
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(outputDir, '06-incident-metadata.png') });
    await scene(page, entry('07-incident-metadata'), async () => {});
    screen++;

    await page.goto(base + '/privacy-lab#experiment', { waitUntil: 'networkidle' });
    await page.waitForSelector('#case-search');
    await page.waitForFunction(() => document.querySelectorAll('#case-list [data-case]').length > 0);
    await page.locator('#case-search').fill('ko96-h01');
    await page.locator('#case-list [data-case="ko96-h01"]').click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outputDir, '07-ai-case-health.png') });
    await scene(page, entry('08-ai-example'), async () => {});
    screen++;

    await page.locator('#case-search').fill('ko96-o01');
    await page.locator('#case-list [data-case="ko96-o01"]').click();
    await page.waitForTimeout(400);
    await page.locator('a[data-tab="evaluation"]').click();
    await page.waitForSelector('#method-cards .method-card');
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(outputDir, '08-ai-evaluation.png') });
    await scene(page, entry('09-ai-results'), async () => {});
    screen++;

    await page.locator('a[data-tab="experiment"]').click();
    await page.waitForSelector('#panel-experiment.active');
    await page.locator('#case-search').fill('');
    await page.locator('#errors-only').check();
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(outputDir, '09-ai-errors.png') });
    await scene(page, entry('10-limits'), async () => {});
    screen++;

    if (errors.length) throw new Error(`Browser page errors: ${errors.join(' | ')}`);
  } finally {
    await context.close();
    await browser.close();
  }

  const source = await videoHandle.path();
  if (!fs.existsSync(source)) throw new Error('Playwright did not produce a video file');
  const final = path.join(outputDir, 'AP-EYE-kickoff-demo.webm');
  if (path.resolve(source) !== path.resolve(final)) {
    fs.copyFileSync(source, final);
    fs.rmSync(source);
  }
  const lastScene = sceneStarts[sceneStarts.length - 1];
  const lastEntry = timeline.scenes.find(item => item.id === lastScene.id);
  const durationSeconds = Number((lastScene.start_seconds + lastEntry.speech_seconds).toFixed(3));
  fs.writeFileSync(path.join(outputDir, 'recording-manifest.json'), JSON.stringify({
    source: base,
    viewport: '1600x900',
    recorded_scenes: screen,
    duration_seconds: durationSeconds,
    scene_starts: sceneStarts,
    browser_page_errors: errors,
    recording: path.basename(final),
    created_at: new Date().toISOString(),
  }, null, 2));
  console.log(JSON.stringify({ video: final, bytes: fs.statSync(final).size, duration_seconds: durationSeconds, scenes: screen, errors }, null, 2));
}

main().catch(error => { console.error(error); process.exitCode = 1; });
