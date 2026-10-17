import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
const out=path.resolve('../docs/agent/branches/EXP/artifacts');
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1080},reducedMotion:'reduce'});
const errors=[],failures=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
page.on('requestfailed',r=>{if(r.failure()?.errorText!=='net::ERR_ABORTED')failures.push({url:r.url(),error:r.failure()?.errorText});});
const results=[];
async function check(name,fn){try{await fn();results.push({name,pass:true});}catch(e){results.push({name,pass:false,error:e.message});await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}}
async function shot(name){await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});}
try{
 await page.goto('http://127.0.0.1:5173/');
 await check('identity + explicit demonstration',async()=>{await page.getByRole('heading',{name:'Fechamento mensal'}).waitFor();await page.getByText('Demonstração de interface. Nenhum valor financeiro foi calculado.').waitFor();if(!(await page.title()).includes('Lastro'))throw Error('wrong title');});
 await shot('desktop-demo');
 await check('demo investigation never fabricates answer',async()=>{await page.getByRole('button',{name:'Investigação',exact:true}).click();await page.getByText('Conecte a API para executar uma investigação.').waitFor({state:'visible'}).catch(async()=>{await page.getByText(/Conecte a API para executar/).waitFor();});if(await page.getByRole('button',{name:'Investigar',exact:true}).isEnabled())throw Error('demo enabled');});
 await check('API connection and real baseline',async()=>{await page.getByRole('button',{name:'Modo demonstração',exact:true}).click();await page.getByRole('button',{name:'Conectar',exact:true}).click();await page.getByRole('button',{name:'Fechamento',exact:true}).click();await page.getByRole('region',{name:'Indicadores da execução'}).getByText('R$ 207.039,73',{exact:true}).waitFor();await page.getByRole('region',{name:'Indicadores da execução'}).getByText('R$ 39.543,45',{exact:true}).waitFor();await page.getByText(/Baseline sem ajustes tardios/).waitFor();await page.getByText('Revisão pendente',{exact:true}).first().waitFor();});
 await shot('desktop-real');
 await check('output preview and full trace by output ID',async()=>{await page.getByRole('tab',{name:/Saídas/}).click();await page.locator('.output-list').getByRole('button',{name:/comissoes_por_lojista.csv/}).click();await page.getByRole('region',{name:/Prévia de comissoes/}).waitFor();await page.getByRole('button',{name:'Ver registro'}).first().click();await page.getByRole('complementary',{name:'Detalhe do registro'}).waitFor();await page.getByRole('button',{name:'Conferir rastro desta saída'}).click();await page.getByRole('heading',{name:/componentes de origem/}).waitFor();if(await page.locator('.trace-record').count()===0)throw Error('no trace components');await shot('trace-real');await page.getByRole('button',{name:'Fechar detalhe'}).click();});
 await shot('outputs-real');
 await check('download real CSV',async()=>{const download=page.waitForEvent('download');await page.getByRole('button',{name:'Baixar CSV'}).click();const file=await download;if(!file.suggestedFilename().endsWith('.csv'))throw Error('not csv');});
 await check('pending review and filter',async()=>{await page.getByRole('button',{name:/^Pendências/}).click();await page.getByRole('textbox',{name:'Filtrar pendências'}).fill('Casa');await page.getByText('DEVOLUCAO_CASA',{exact:true}).waitFor();await page.getByRole('button',{name:'Ver registro'}).first().click();await page.getByRole('complementary',{name:'Detalhe do registro'}).getByText('Helena + comercial',{exact:true}).waitFor();await page.getByRole('button',{name:'Fechar detalhe'}).click();});
 await shot('pending-real');
 await check('real deterministic investigation',async()=>{await page.getByRole('button',{name:'Investigação',exact:true}).click();await page.getByRole('button',{name:/Por que a devolução da Casa/}).click();await page.getByRole('button',{name:'Investigar',exact:true}).click();await page.locator('.answer-text').waitFor({timeout:45000});await page.getByText('Evidências localizadas',{exact:true}).waitFor();await page.waitForTimeout(1800);if(!await page.locator('.answer-text').isVisible())throw Error('answer lost after refresh');});
 await shot('investigation-real');
 await check('mission control uses real events',async()=>{await page.getByRole('button',{name:'Central de agentes',exact:true}).click();await page.locator('.mc').waitFor();});
 await shot('agents-real');
 await page.getByRole('button',{name:'Fechamento',exact:true}).click();
 await page.getByRole('tab',{name:'Resumo',exact:true}).click();
 await check('real comparison of two recorded runs',async()=>{const before=page.getByRole('combobox',{name:'Execução anterior'}),after=page.getByRole('combobox',{name:'Execução seguinte'});await before.waitFor();const ids=await before.locator('option').evaluateAll(options=>options.map(option=>option.value).filter(Boolean));if(ids.length<2)throw Error('need two real runs');await before.selectOption(ids[0]);await after.selectOption(ids[1]);await page.getByRole('button',{name:'Comparar',exact:true}).click();await page.getByText(/Comparação registrada/).waitFor({timeout:45000});});
 await shot('comparison-real');
 await check('displayed period follows selected run',async()=>{await page.getByLabel('Competência',{exact:true}).fill('2026-10');const footer=await page.locator('.page-footer').innerText();if(!footer.includes('2026-09'))throw Error('footer follows creation selector');await page.getByLabel('Competência',{exact:true}).fill('2026-09');});
 await shot('desktop-real');
 for(const [name,width,height,zoom] of [['laptop',1100,900,1],['laptop-125',1280,900,1.25],['mobile',390,844,1]]){
  await page.setViewportSize({width,height});await page.evaluate(z=>{document.body.style.zoom=z;},zoom);await shot(name);
  await check(name+' no document overflow',async()=>{const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);if(overflow)throw Error('document overflow');});
 }
 await page.evaluate(()=>{document.body.style.zoom='1';});
 await check('mobile navigation',async()=>{await page.getByRole('button',{name:'Fontes',exact:true}).click();await page.getByRole('heading',{name:'Arquivos da apuração'}).waitFor();});
 await shot('mobile-sources');
 await check('keyboard escape and focus confinement',async()=>{await page.getByRole('button',{name:'Conexão da API'}).click();await page.getByRole('button',{name:'Conectar',exact:true}).focus();await page.keyboard.press('Tab');if(await page.locator('.close-dialog').evaluate(el=>el!==document.activeElement))throw Error('focus left dialog');await page.keyboard.press('Escape');if(await page.getByRole('dialog').isVisible())throw Error('Escape did not close');});
 const external=failures.filter(r=>!r.url.startsWith('http://127.0.0.1'));
 results.push({name:'runtime console/page errors',pass:errors.length===0,errors});
 results.push({name:'unexpected failed network',pass:failures.length===0,failures,external});
} finally {
 await writeFile(path.join(out,'ui-results.json'),JSON.stringify({time:new Date().toISOString(),browser:'Edge via Playwright; Browser plugin not available',results,errors,failures},null,2));
 await browser.close();
}
if(results.some(r=>!r.pass))process.exitCode=1;
console.log(JSON.stringify(results,null,2));
