// Independent Carbon integration QA. Existing run; deterministic reviews only.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..');
const {chromium}=require(path.join(root,'web/node_modules/playwright'));
const out=path.join(root,'docs/agent/branches/QA/artifacts/carbon_r011');fs.mkdirSync(out,{recursive:true});
const run='3c0bd187-5f20-4223-9399-d1ab32aa55a1';
const files=['App.tsx','CarbonOverview.tsx','CaseWorkspace.tsx','carbon.css','case-workspace.css'];
const hashes=()=>Object.fromEntries(files.map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'web/src',f))).digest('hex')]));
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'}),page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(10000);const report={started:new Date().toISOString(),run,hashesBefore:hashes(),checks:{},observations:{},errors:[],console:[],failedRequests:[],requests:[],responses:[],limits:['Real localhost API and existing run; only deterministic review POSTs. No new close, bearer, provider, publication or payment.','Known case regression; not a financial model quality or innovation benchmark.']};
const check=(name,value)=>(report.checks[name]=!!value,console.log(name+': '+!!value));
page.on('pageerror',e=>report.errors.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))report.console.push({type:m.type(),text:m.text()})});
page.on('requestfailed',r=>report.failedRequests.push({url:r.url(),error:r.failure()?.errorText}));
page.on('request',r=>{if(r.url().includes('/api/'))report.requests.push({path:new URL(r.url()).pathname,method:r.method(),...(r.method()==='POST'?{body:r.postDataJSON()}:{} )})});
page.on('response',r=>{if(r.url().includes('/api/'))report.responses.push({path:new URL(r.url()).pathname,status:r.status()})});
const shot=async name=>page.screenshot({path:path.join(out,name+'.png'),fullPage:false});
const noOverflow=()=>page.evaluate(()=>({ok:document.documentElement.scrollWidth<=innerWidth,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.right>innerWidth+1&&getComputedStyle(e).position!=='fixed'}).slice(0,12).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right}))}));
try{
await page.goto('http://127.0.0.1:5173',{waitUntil:'domcontentloaded'});
await page.getByLabel('Execução',{exact:true}).selectOption(run);await page.getByText('R$ 207.039,73',{exact:true}).first().waitFor();await page.locator('.file-tile').first().waitFor();
let body=await page.locator('body').innerText();check('actualSummaryAmounts',body.includes('R$ 207.039,73')&&body.includes('R$ 39.543,45'));
check('partialAndHumanReviewVisible',body.includes('ajustes tardios ausentes')&&body.includes('Helena'));
check('noReferenceFabrications',!['EST992347','tr_','2.850,20','961,43','4.320,17'].some(t=>body.includes(t)));
check('csvPreviewsLabeled',body.includes('CSV')&&body.includes('Prévia tabular'));
await shot('overview-desktop');
await page.getByRole('button',{name:'Abrir mesa de revisão',exact:true}).click();
let cw=page.locator('.case-layer:not([hidden]) .case-workspace');await cw.locator('.cw-dossier').waitFor();
for(const key of ['casa','atlas','mundo']){
if(key!=='casa')await page.locator('.case-entry-tabs').getByRole('button',{name:key.charAt(0).toUpperCase()+key.slice(1),exact:true}).click();
cw=page.locator('.case-layer:not([hidden]) .case-workspace');await cw.locator('.cw-dossier').waitFor();
const response=await page.request.get(`http://127.0.0.1:8000/api/runs/${run}/cases/${key}`),{packet}=await response.json();
report.observations[key]={packetAmount:packet.amount,recipient:packet.recipient,owner:packet.owner,screen:await cw.innerText()};
check(key+'CanonicalDestination',await cw.locator('.cw-parties').innerText().then(t=>t.includes(packet.recipient)&&t.includes(packet.owner)));
check(key+'CanonicalAmount',await cw.locator('.cw-amount strong').innerText().then(t=>key==='atlas'?t==='Não determinado':t===({casa:'R$ 15.397,42',mundo:'R$ 1.418,85'})[key]));
check(key+'ClosureIsRequired',report.observations[key].screen.includes('O que falta para encerrar')&&report.observations[key].screen.includes('Preparação não equivale a aprovação ou envio'));
await cw.locator('.cw-review-controls select').selectOption('llm');check(key+'NoBearerBlocksLLM',await cw.getByRole('button',{name:'Iniciar investigação',exact:true}).isDisabled());
await cw.locator('.cw-review-controls select').selectOption('deterministic');
await cw.getByRole('button',{name:'Conferir pacote',exact:true}).click();await cw.getByText('Pacote determinístico · papéis não executados',{exact:true}).waitFor({timeout:25000});
check(key+'DeterministicRoles',await cw.innerText().then(t=>t.includes('Modelo acionado: não')&&t.includes('Aprovação não demonstrada')));
await cw.locator('.cw-job summary').click();const jobText=await cw.locator('.cw-job').innerText();report.observations[key].job=jobText;
check(key+'ActualJob',jobText.includes('pending review'));
await cw.locator('.mcr-operational > summary').click();check(key+'ActualEvents',await cw.locator('.mcr-operational > summary').innerText().then(t=>!/· 0 eventos/.test(t)));
await shot(key+'-desktop');
await page.getByRole('button',{name:'Fechamento',exact:true}).click();await page.getByRole('button',{name:'Investigação',exact:true}).click();
check(key+'SurvivesNavigation',await page.locator('.case-layer:not([hidden]) .cw-job').innerText().then(t=>t===jobText));
await page.setViewportSize({width:390,height:844});report.observations[key].mobile=await noOverflow();check(key+'MobileNoOverflow',report.observations[key].mobile.ok);await shot(key+'-mobile');await page.setViewportSize({width:1440,height:1000});
}
await page.getByRole('button',{name:'Fechamento',exact:true}).click();await page.setViewportSize({width:390,height:844});report.observations.overviewMobile=await noOverflow();check('overviewMobileNoOverflow',report.observations.overviewMobile.ok);await shot('overview-mobile');
await page.getByRole('button',{name:'Fontes',exact:true}).click();await page.locator('.file-selector').getByRole('button',{name:'comissoes_por_lojista.csv',exact:true}).click();await page.getByRole('button',{name:'Ver registro'}).first().click();await page.getByRole('button',{name:'Conferir rastro desta saída'}).click();await page.locator('.trace-record').first().waitFor();
check('realTraceStillAccessible',await page.locator('.trace-record').count()>0);report.observations.traceMobile=await noOverflow();check('traceMobileNoOverflow',report.observations.traceMobile.ok);await shot('trace-mobile');await page.getByRole('button',{name:'Fechar detalhe'}).click();
check('noFinancialCloseOrLLM',!report.requests.some(r=>r.method==='POST'&&(r.body?.mode==='llm'||r.path==='/api/runs')));
check('noPageErrors',report.errors.length===0);check('noConsoleErrors',report.console.filter(e=>e.type==='error').length===0);
}catch(e){report.failure=String(e.stack);await page.screenshot({path:path.join(out,'failure.png'),fullPage:false});report.failureScreen=await page.locator('body').innerText();process.exitCode=1;}
report.hashesAfter=hashes();report.codeChanged=JSON.stringify(report.hashesBefore)!==JSON.stringify(report.hashesAfter);report.finished=new Date().toISOString();fs.writeFileSync(path.join(out,'probe_004.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({checks:report.checks,failure:report.failure,codeChanged:report.codeChanged,errors:report.errors,console:report.console,failedRequests:report.failedRequests},null,2));await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1});



