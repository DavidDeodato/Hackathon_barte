// Real UI + separate QA API; only test-origin banner is injected, no values/results mocked.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const {chromium}=require(path.join(root,'web/node_modules/playwright'));
const out=path.join(root,'docs/agent/branches/QA/artifacts/nonzero_001');
const proof=JSON.parse(fs.readFileSync(path.join(out,'proof.json'),'utf8'));
(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const report={dataset_kind:'synthetic_test',checks:{},console:[],pageErrors:[],requests:[],screenshot_label:'QA harness injects only a synthetic-origin banner; no product ability to detect synthetic inputs is claimed.'};
  let response;
  page.on('console',m=>{if(m.type()==='error')report.console.push(m.text())});
  page.on('pageerror',e=>report.pageErrors.push(e.message));
  page.on('response',async r=>{if(r.url().includes('8002/api/comparisons')){report.requests.push({path:new URL(r.url()).pathname,status:r.status()});try{const body=await r.json();if(body.result)response=body;}catch{}}});
  try{
    await page.goto('http://127.0.0.1:5173');
    await page.getByRole('button',{name:/^Conectar API/}).click();
    await page.getByLabel('Endereço da API').fill('http://127.0.0.1:8002');
    await page.getByRole('button',{name:'Conectar',exact:true}).click();
    await page.getByLabel('Execução anterior',{exact:true}).selectOption(proof.before_run_id);
    await page.getByLabel('Execução seguinte',{exact:true}).selectOption(proof.after_run_id);
    await page.getByRole('button',{name:'Comparar',exact:true}).click();
    await page.locator('.comparison-status').waitFor({timeout:30000});
    const row=page.locator('.comparison-panel tbody tr').filter({has:page.locator('td:first-child').filter({hasText:/^divergencias_taxa\.csv$/})});
    await row.locator('summary').click();
    const detail=await row.innerText();
    const actual=response?.result?.outputs?.find(x=>x.name==='divergencias_taxa.csv');
    report.checks.realComparisonCompleted=response?.status==='completed';
    report.checks.correctChangedLine=actual?.changed?.length===1&&actual.changed[0].after.ref_origem===proof.fixture.source_ref;
    report.checks.expectedNonzeroDelta=actual?.changed?.[0]?.monetary_delta===proof.fixture.expected_delta_brl;
    report.checks.detailShowsDeltaAndSource=detail.includes('64.49')&&detail.includes(proof.fixture.source_ref);
    report.checks.noFinancialApproval=(await page.locator('.comparison-panel').innerText()).includes('Não equivale a aprovação financeira');
    report.checks.noCrossNatureTotal=(await page.locator('.comparison-panel').innerText()).includes('Não existe total agregado');
    await page.evaluate(()=>{const panel=document.querySelector('.comparison-panel');const p=document.createElement('p');p.setAttribute('data-qa-fixture-label','true');p.style.cssText='padding:14px;background:#fff2d1;border:2px solid #9a6300;color:#4f3400;font-weight:bold';p.textContent='QA · CENÁRIO SINTÉTICO: uma cobrança Orbe alterada em cópia isolada. Não é ajuste recebido nem regra aprovada. Aviso inserido pelo teste; números abaixo vieram da API QA real.';panel.prepend(p);});
    await page.locator('.comparison-panel').screenshot({path:path.join(out,'nonzero-comparison-desktop.png')});
    await page.setViewportSize({width:390,height:844});
    report.checks.mobileNoDocumentOverflow=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);
    await page.locator('.comparison-panel').screenshot({path:path.join(out,'nonzero-comparison-mobile.png')});
    report.checks.noConsoleOrPageErrors=!report.console.length&&!report.pageErrors.length;
    report.response=response;
  }catch(e){report.failure=String(e.stack);report.body=await page.locator('body').innerText();process.exitCode=1;}
  fs.writeFileSync(path.join(out,'ui_proof.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({checks:report.checks,failure:report.failure,console:report.console,pageErrors:report.pageErrors,requests:report.requests},null,2));
  await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
