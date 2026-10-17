import {chromium} from 'playwright';
import {writeFile} from 'node:fs/promises';
import path from 'node:path';
const out=path.resolve('../docs/agent/branches/EXP/artifacts');
const browser=await chromium.launch({headless:true,channel:'msedge'});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const report={time:new Date().toISOString(),kind:'UI contract test with mocked API; no provider calls or real credential',checks:[],requests:[],errors:[]};
let scenario='deterministic';let id=0;const results=new Map();
const run={run_id:'contract-fixture',period:'2026-09',status:'pending_review',summary:{mode:'CONTRACT_TEST'},issues:[],outputs:[]};
page.on('pageerror',e=>report.errors.push(e.message));
await page.route('**/api/**',async route=>{
 const request=route.request(),url=new URL(request.url());let data={};let status=200;
 if(url.pathname==='/api/health')data={status:'ok'};
 else if(url.pathname==='/api/runs')data={items:[run]};
 else if(url.pathname.endsWith('/events')||url.pathname.endsWith('/outputs'))data={items:[],next_cursor:null};
 else if(url.pathname==='/api/runs/contract-fixture')data=run;
 else if(url.pathname.endsWith('/investigations')&&request.method()==='POST'){
  const body=request.postDataJSON();report.requests.push({mode:body.mode,hasBearer:!!request.headers().authorization});
  if(scenario==='unauthorized'){status=401;data={error:{code:'UNAUTHORIZED',message:'Mock unauthorized'}};}
  else{
   const iid='mock-inv-'+(++id);data={investigation_id:iid,status:'queued'};
   const result={mode:body.mode,status:body.mode==='llm'?'needs_review':'completed',answer:'Resposta simulada para teste de contrato.',model_called:body.mode==='llm',evidence:[],proposed_changes:[],limitations:['Fixture controlada; não é inferência real.']};
   if(body.mode==='llm')result.model_metrics=[{provider:'openai',model:'contract-model',call_index:1,status:'completed',http_status:200,input_tokens:123,output_tokens:45,total_tokens:168,latency_ms:210,cost_brl:null},{provider:'openai',model:'contract-model',call_index:2,status:'failed',http_status:503,input_tokens:null,output_tokens:null,total_tokens:null,latency_ms:400,cost_brl:null}];
   if(scenario==='unavailable'){result.status='unavailable';result.model_called=false;result.model_metrics=[];result.answer='Modelo indisponível (teste de contrato).';}
   results.set(iid,result);
  }
 }else if(url.pathname.includes('/investigations/'))data={status:'completed',result:results.get(url.pathname.split('/').at(-1))};
 await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
});
async function check(name,fn){try{await fn();report.checks.push({name,pass:true});}catch(e){report.checks.push({name,pass:false,error:e.message});throw e;}}
try{
 await page.goto('http://127.0.0.1:5173');await page.evaluate(()=>{const banner=document.createElement('div');banner.textContent='TESTE DE CONTRATO · respostas simuladas · sem chamada ao modelo';banner.style.cssText='position:fixed;bottom:0;left:0;right:0;z-index:1000;background:#fff1b7;color:#4d3b00;padding:10px;text-align:center;font:13px Arial';document.body.append(banner);});
 await page.getByRole('button',{name:'Modo demonstração',exact:true}).click();await check('published API URL is optional and local default preserved',async()=>{if(await page.getByLabel('Endereço da API').inputValue()!=='')throw Error('local default changed');await page.getByRole('button',{name:'Usar API publicada',exact:true}).click();if(await page.getByLabel('Endereço da API').inputValue()!=='https://api-production-6bfe.up.railway.app')throw Error('wrong published URL');await page.getByLabel('Endereço da API').fill('');});await page.getByRole('button',{name:'Conectar',exact:true}).click();await page.getByRole('button',{name:'Investigação',exact:true}).click();await page.getByLabel('O que você precisa conferir?').fill('Pergunta de contrato sem valor financeiro.');
 await check('default sends deterministic explicitly',async()=>{if(await page.getByLabel('Método da investigação').inputValue()!=='deterministic')throw Error('wrong default');await page.getByRole('button',{name:'Investigar',exact:true}).click();await page.locator('.answer-text').waitFor();if(report.requests.at(-1)?.mode!=='deterministic')throw Error('mode omitted');await page.getByText('Não',{exact:true}).waitFor();});
 await check('LLM without bearer never sends request',async()=>{await page.getByLabel('Método da investigação').selectOption('llm');if(await page.getByRole('button',{name:'Investigar',exact:true}).isEnabled())throw Error('no token enabled');await page.getByText(/Nenhuma chamada será enviada sem token/).waitFor();if(report.requests.length!==1)throw Error('unexpected POST');});
 await page.getByRole('button',{name:'Configurar sessão',exact:true}).click();await page.getByLabel('Token da sessão, se exigido').fill('non-secret-contract-fixture');await page.getByRole('button',{name:'Conectar',exact:true}).click();
 await check('LLM explicit payload bearer and returned metrics preserved',async()=>{await page.getByRole('button',{name:'Investigar',exact:true}).click();await page.getByText('Sim · tentativa registrada',{exact:true}).waitFor();if(report.requests.at(-1)?.mode!=='llm'||!report.requests.at(-1)?.hasBearer)throw Error('transport missing');const metrics=page.getByRole('region',{name:'Execução e métricas da investigação'});await metrics.getByText('123',{exact:true}).waitFor();await metrics.getByText('45',{exact:true}).waitFor();await metrics.getByText('168',{exact:true}).waitFor();if(await metrics.getByText('n/a',{exact:true}).count()<3)throw Error('unknown not n/a');await metrics.getByText('failed / 503',{exact:true}).waitFor();const stored=await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}));if(stored.includes('non-secret-contract-fixture'))throw Error('session persisted');});
 await page.screenshot({path:path.join(out,'investigation-llm-contract-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await check('mobile mode and metrics no document overflow',async()=>{if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('overflow');await page.getByLabel('Método da investigação').waitFor();});await page.screenshot({path:path.join(out,'investigation-llm-contract-mobile.png'),fullPage:true});
 scenario='unauthorized';await check('HTTP401 remains auth error with no fallback',async()=>{await page.getByRole('button',{name:'Investigar',exact:true}).click();await page.getByRole('alert').getByText(/Investigação com IA não autorizada/).waitFor();if(await page.locator('.answer-text').count())throw Error('stale success remains');if(report.requests.at(-1)?.mode!=='llm')throw Error('silent fallback');});
 scenario='unavailable';await check('unavailable and model_called false stay explicit',async()=>{await page.getByRole('button',{name:'Investigar',exact:true}).click();await page.getByText('Modelo indisponível (teste de contrato).',{exact:true}).waitFor();await page.getByRole('region',{name:'Execução e métricas da investigação'}).getByText('Não',{exact:true}).waitFor();});
}finally{await writeFile(path.join(out,'investigation-mode-results.json'),JSON.stringify(report,null,2));await browser.close();}
console.log(JSON.stringify(report,null,2));
if(report.checks.some(check=>!check.pass)||report.errors.length)process.exitCode=1;
