// New R006 comparison UI gate only; does not repeat financial baseline or use LLM.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const {chromium}=require(path.join(root,'web/node_modules/playwright'));
const out=path.join(root,'docs/agent/branches/QA/artifacts');
(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const report={checks:{},console:[],pageErrors:[],api:[],viteMessages:[],responses:[]};
  let result;
  page.on('pageerror',e=>report.pageErrors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')report.console.push(m.text());if(m.text().includes('[vite]'))report.viteMessages.push(m.text());});
  page.on('response',async r=>{if(r.url().includes('/api/comparisons')){report.api.push({path:new URL(r.url()).pathname,status:r.status()});try{const data=await r.json();report.responses.push(data);if(data.result)result=data;}catch{}}});
  try{
    await page.goto('http://127.0.0.1:5173');
    await page.getByRole('button',{name:/^Conectar API/}).click();
    await page.getByLabel('Endereço da API').fill('');
    await page.getByRole('button',{name:'Conectar',exact:true}).click();
    await page.getByLabel('Execução anterior',{exact:true}).waitFor();
    const options=await page.getByLabel('Execução anterior',{exact:true}).locator('option').evaluateAll(nodes=>nodes.map(n=>({value:n.value,label:n.textContent})).filter(x=>x.value));
    if(options.length<2)throw new Error('Need two actual available runs; no invented delta');
    const before=options.find(x=>x.value==='5d9cd7ef-9f3c-47e7-8dcc-81045bfab964')||options[0];
    const after=options.find(x=>x.value==='cc2a76c3-0623-4774-b65b-6c7d620350c5')||options.find(x=>x.value!==before.value);
    report.runs={before,after};
    await page.getByLabel('Execução anterior',{exact:true}).selectOption(before.value);
    await page.getByLabel('Execução seguinte',{exact:true}).selectOption(after.value);
    await page.getByRole('button',{name:'Comparar',exact:true}).click();
    await page.locator('.comparison-status').waitFor({timeout:30000});
    report.checks.actualResult=result?.status==='completed'&&result.result?.status==='completed';
    report.checks.identicalRunsZeroDelta=Array.isArray(result?.result?.outputs)&&result.result.outputs.every(o=>!o.added.length&&!o.removed.length&&!o.changed.length);
    report.checks.originalRefsInResult=Array.isArray(result?.result?.outputs)&&result.result.outputs.length===6;
    report.checks.noFinancialApproval=(await page.locator('.comparison-panel').innerText()).includes('Não equivale a aprovação financeira');
    report.checks.noAggregateTotal=(await page.locator('.comparison-panel').innerText()).includes('Não existe total agregado');
    report.body=await page.locator('.comparison-panel').innerText();
    await page.locator('.comparison-panel details').first().locator('summary').click();
    report.checks.detailExpands=await page.getByText('Sem diferenças neste arquivo.',{exact:true}).first().isVisible();
    await page.screenshot({path:path.join(out,'comparison-ui-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    report.checks.mobileNoDocumentOverflow=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);
    await page.locator('.comparison-panel').screenshot({path:path.join(out,'comparison-ui-mobile.png')});
    report.checks.noConsoleOrPageErrors=!report.pageErrors.length&&!report.console.length;
    report.result=result;
  }catch(e){report.failure=String(e.stack);report.failureBody=await page.locator('body').innerText().catch(()=>null);await page.screenshot({path:path.join(out,'comparison-ui-failure.png'),fullPage:false}).catch(()=>{});process.exitCode=1;}
  fs.writeFileSync(path.join(out,'ui_compare_002.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({checks:report.checks,runs:report.runs,failure:report.failure,console:report.console,pageErrors:report.pageErrors,api:report.api},null,2));
  await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
