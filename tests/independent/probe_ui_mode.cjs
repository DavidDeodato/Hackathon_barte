// QA control/render probe with fully intercepted API. Zero model/provider requests.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
const {chromium}=require(path.join(root,'web/node_modules/playwright'));
const out=path.join(root,'docs/agent/branches/QA/artifacts');
(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const report={kind:'QA independent UI control probe; API mocked, no LLM quality or provider call certified',checks:{},posts:[],externalRequests:[],pageErrors:[]};
  let scenario='normal',sequence=0;
  const investigations=new Map();
  const run={run_id:'QA-MODE-FIXTURE',period:'2026-09',status:'pending_review',summary:{mode:'QA_MOCK'},issues:[],outputs:[]};
  page.on('pageerror',e=>report.pageErrors.push(e.message));
  await page.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url());
    if(!['127.0.0.1','localhost'].includes(url.hostname)){report.externalRequests.push(url.origin);await route.abort();return;}
    if(!url.pathname.startsWith('/api/')){await route.continue();return;}
    let status=200,body={};
    if(url.pathname==='/api/health')body={status:'ok'};
    else if(url.pathname==='/api/runs')body={items:[run],next_cursor:null};
    else if(url.pathname.endsWith('/events')||url.pathname.endsWith('/outputs'))body={items:[],next_cursor:null};
    else if(url.pathname==='/api/runs/QA-MODE-FIXTURE')body=run;
    else if(request.method()==='POST'&&url.pathname.endsWith('/investigations')){
      const input=request.postDataJSON();report.posts.push({mode:input.mode,bearerPresent:!!request.headers().authorization});
      if(scenario==='forbidden'){status=403;body={error:{code:'FORBIDDEN',message:'QA mocked 403'}};}
      else{
        const iid='QA-I-'+(++sequence);body={investigation_id:iid,status:'queued'};
        investigations.set(iid,{status:'pending_review',result:{status:'needs_review',mode:input.mode,model_called:input.mode==='llm',answer:'QA MOCK: control/render result only.',evidence:[],proposed_changes:[],limitations:['QA API fixture; no provider invocation.'],model_metrics:input.mode==='llm'?[{model:'QA-UNMEASURED',call_index:1,status:'failed',http_status:503,input_tokens:null,output_tokens:null,total_tokens:null,latency_ms:null,cost_brl:null}]:[]}});
      }
    }else if(url.pathname.includes('/investigations/'))body=investigations.get(url.pathname.split('/').at(-1));
    else{status=404;body={error:{code:'QA_NOT_FOUND',message:'Unmocked endpoint'}};}
    await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  });
  try{
    await page.goto('http://127.0.0.1:5173');
    await page.getByRole('button',{name:'Modo demonstração',exact:true}).click();
    report.checks.localDefaultPreserved=await page.getByLabel('Endereço da API').inputValue()==='';
    await page.getByRole('button',{name:'Conectar',exact:true}).click();
    await page.getByRole('button',{name:'Investigação',exact:true}).click();
    await page.getByLabel('O que você precisa conferir?').fill('QA control fixture, no financial calculation');
    report.checks.deterministicDefault=await page.getByLabel('Método da investigação').inputValue()==='deterministic';
    await page.getByRole('button',{name:'Investigar',exact:true}).click();
    await page.locator('.answer-text').waitFor();
    report.checks.explicitDeterministicPayload=report.posts.length===1&&report.posts[0].mode==='deterministic';
    await page.getByLabel('Método da investigação').selectOption('llm');
    report.checks.noBearerBlocksLLM=await page.getByRole('button',{name:'Investigar',exact:true}).isDisabled()&&report.posts.length===1;
    await page.getByRole('button',{name:'Configurar sessão',exact:true}).click();
    await page.getByLabel('Token da sessão, se exigido').fill('QA-PUBLIC-NON-CREDENTIAL');
    await page.getByRole('button',{name:'Conectar',exact:true}).click();
    await page.getByRole('button',{name:'Investigar',exact:true}).click();
    const metrics=page.getByRole('region',{name:'Execução e métricas da investigação'});
    await metrics.getByText('failed / 503',{exact:true}).waitFor();
    report.checks.explicitLLMAndBearer=report.posts.at(-1).mode==='llm'&&report.posts.at(-1).bearerPresent;
    report.checks.attemptNotSuccess=(await metrics.innerText()).includes('Sim · tentativa registrada')&&(await metrics.innerText()).includes('failed / 503');
    report.checks.unknownMetricsNotZero=await metrics.getByRole('cell',{name:'n/a',exact:true}).count()===5;
    report.checks.noTokenPersisted=!(await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}))).includes('QA-PUBLIC-NON-CREDENTIAL');
    await page.evaluate(()=>{const label=document.createElement('p');label.textContent='QA · API INTEGRALMENTE SIMULADA · nenhum modelo ou provedor chamado';label.style.cssText='padding:12px;background:#fff2d1;border:2px solid #9a6300;font-weight:bold';document.querySelector('.answer-panel').prepend(label);});
    await page.locator('.answer-panel').screenshot({path:path.join(out,'investigation-mode-mocked-desktop.png')});
    await page.setViewportSize({width:390,height:844});
    report.checks.mobileNoOverflow=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);
    await page.locator('.answer-panel').screenshot({path:path.join(out,'investigation-mode-mocked-mobile.png')});
    scenario='forbidden';
    const postsBefore=report.posts.length;
    await page.getByRole('button',{name:'Investigar',exact:true}).click();
    await page.getByRole('alert').getByText(/Investigação com IA não autorizada/).waitFor();
    report.checks.forbiddenNoFallback=report.posts.length===postsBefore+1&&report.posts.at(-1).mode==='llm';
    report.checks.forbiddenClearsStaleAnswer=await page.locator('.answer-text').count()===0;
    report.checks.noExternalRequests=report.externalRequests.length===0;
    report.checks.noPageErrors=report.pageErrors.length===0;
  }catch(e){report.failure=String(e.stack);process.exitCode=1;}
  fs.writeFileSync(path.join(out,'investigation_mode_probe_001.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
  await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
