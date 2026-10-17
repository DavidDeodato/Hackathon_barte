import {chromium} from 'playwright';
import {writeFile} from 'node:fs/promises';
import path from 'node:path';
const out=path.resolve('../docs/agent/branches/EXP/artifacts');
const browser=await chromium.launch({headless:true,channel:'msedge'});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const result={time:new Date().toISOString(),checks:[],errors:[]};
page.on('pageerror',e=>result.errors.push(e.message));
async function check(name,fn){try{await fn();result.checks.push({name,pass:true});}catch(e){result.checks.push({name,pass:false,error:e.message});throw e;}}
try{
 await page.goto('http://127.0.0.1:5173');await page.getByRole('button',{name:'Modo demonstração',exact:true}).click();await page.getByRole('button',{name:'Conectar',exact:true}).click();
 await page.getByRole('region',{name:'Indicadores da execução'}).getByText('R$ 207.039,73',{exact:true}).waitFor();
 await check('primary button creates real run and awaits result',async()=>{const before=await page.getByRole('combobox',{name:'Execução',exact:true}).inputValue();await page.getByRole('button',{name:'Processar fechamento',exact:true}).click();await page.waitForFunction(id=>document.querySelector('.runbar select')?.value!==id,before);await page.getByRole('region',{name:'Indicadores da execução'}).getByText('R$ 207.039,73',{exact:true}).waitFor({timeout:60000});await page.getByText('Revisão pendente',{exact:true}).first().waitFor();result.real_run_id=await page.getByRole('combobox',{name:'Execução',exact:true}).inputValue();});
 await check('run switch closes stale original record',async()=>{await page.getByRole('tab',{name:/Saídas/}).click();await page.locator('.output-list').getByRole('button',{name:/comissoes_por_lojista.csv/}).click();await page.getByRole('button',{name:'Ver registro'}).first().click();await page.getByRole('complementary',{name:'Detalhe do registro'}).waitFor();const selector=page.getByRole('combobox',{name:'Execução',exact:true});const options=await selector.locator('option').evaluateAll(nodes=>nodes.map(n=>n.value).filter(Boolean));await selector.selectOption(options.find(id=>id!==result.real_run_id));if(await page.getByRole('complementary',{name:'Detalhe do registro'}).isVisible())throw Error('stale record remains');});
 const errorsPage=await browser.newPage();
 await errorsPage.route('**/api/health',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:'ok'})}));
 await errorsPage.route('**/api/runs',route=>route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({error:{code:'UNAUTHORIZED',message:'Sessão não autorizada (cenário de teste).'}})}));
 await check('HTTP401 stays explicit error and never financial success',async()=>{await errorsPage.goto('http://127.0.0.1:5173');await errorsPage.getByRole('button',{name:'Modo demonstração',exact:true}).click();await errorsPage.getByRole('button',{name:'Conectar',exact:true}).click();await errorsPage.getByRole('alert').getByText('Sessão não autorizada (cenário de teste).').waitFor();if(await errorsPage.getByRole('region',{name:'Indicadores da execução'}).getByText('R$ 207.039,73',{exact:true}).count())throw Error('invented result after401');await errorsPage.screenshot({path:path.join(out,'error401-test.png')});});
 await errorsPage.close();
}finally{await writeFile(path.join(out,'primary-results.json'),JSON.stringify(result,null,2));await browser.close();}
console.log(JSON.stringify(result,null,2));
if(result.checks.some(check=>!check.pass)||result.errors.length)process.exitCode=1;
