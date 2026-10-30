import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader']});
const report={checks:[],errors:[]};
const page=await browser.newPage({viewport:{width:1600,height:1040}});
// Isolate demo acceptance from the user's concurrently edited workspace and uploads.
await page.route('**/api/workspace',r=>r.fulfill({status:200,contentType:'application/json',body:r.request().method()==='GET'?'null':'{"ok":true}'}));
await page.route('**/api/library',async route=>{const response=await route.fetch();const data=await response.json();data.photos=data.photos.filter(p=>p.demo);data.groups=[...new Set(data.photos.map(p=>p.group))];await route.fulfill({response,json:data})});

page.on('pageerror',e=>report.errors.push(e.stack));page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});
const check=(label,pass)=>{report.checks.push({label,pass});if(!pass)throw new Error(label)};
try{
 await page.goto('http://127.0.0.1:5173',{waitUntil:'domcontentloaded'});
 await page.waitForSelector('.scene-node canvas',{timeout:30000});
 await page.waitForFunction(()=>parseFloat(document.querySelector('.heat-summary b')?.textContent)>0);
 await page.waitForTimeout(700);
 check('Five dated photo keyframes',await page.locator('.photo-keyframe').count()===5);
 check('Three live metric tracks',await page.locator('.metric-track').count()===3);
 await page.waitForSelector('.cluster-legend',{timeout:15000});
 check('Real PCA scatterplot loaded',await page.locator('.cluster-summary').innerText().then(t=>t.includes('PCA')));
 const initial=await page.locator('.scene-node canvas').evaluate(c=>c.toDataURL());
 const range=page.getByRole('slider',{name:'Верхний порог',exact:true});
 await range.fill('0.02');await range.dispatchEvent('input');await page.waitForTimeout(400);
 const after=await page.locator('.scene-node canvas').evaluate(c=>c.toDataURL());
 check('Heatmap responds to upper threshold',initial!==after);
 await page.getByRole('switch',{name:'Автоматические пороги',exact:true}).click();
 await page.locator('.photo-keyframe').nth(3).click();
 await page.waitForFunction(()=>document.querySelector('.source-badge')?.textContent?.includes('2021-02-12'));
 check('Photo click selects exact 3D frame',true);
 await page.locator('.photo-keyframe').nth(1).click({modifiers:['Control']});
 check('Ctrl-click multi-selection',await page.locator('.route-selected').count()===2);
 await page.locator('.transition-hit').nth(1).click();
 await page.waitForFunction(()=>document.querySelector('.morph-badge')?.textContent?.includes('50%'));
 check('Pair transition drives 3D morph',true);
 await page.getByRole('slider',{name:'Позиция морфинга',exact:true}).fill('0.7');
 await page.waitForFunction(()=>document.querySelector('.morph-badge')?.textContent?.includes('78%'));
 check('Scrub uses same ease-in-out as 3D scene',true);
 await page.getByRole('button',{name:'Воспроизвести морфинг',exact:true}).click();
 await page.waitForTimeout(350);
 check('Playback advances timeline',await page.getByRole('slider',{name:'Позиция морфинга',exact:true}).inputValue().then(v=>+v>.7));
 await page.getByRole('button',{name:'Воспроизвести морфинг',exact:true}).click();
 await page.locator('.photo-keyframe').nth(2).dblclick();
 await page.waitForSelector('.photo-editor');check('Manual date/angle editor opens',true);
 await page.locator('.photo-editor .icon-btn').first().click();
 await page.getByRole('button',{name:'Ракурсы',exact:true}).first().click();
 await page.waitForSelector('.pose-range-row');check('Five adjustable pose profiles',await page.locator('.pose-range-row').count()===5);
 await page.getByRole('button',{name:'Метрики',exact:true}).first().click();
 await page.waitForSelector('.metric-editor');check('Per-pose config-driven metric editor',await page.locator('.metric-editor').count()>=3);
 // Restore the uncluttered main composition after examining settings.
 await page.evaluate(async()=>{const {useStore,initialNodes,initialEdges}=await import('/src/store.ts');const s=useStore.getState();s.set({nodes:initialNodes,edges:initialEdges,route:s.photos.filter((_,i)=>i%2===0).map(p=>p.id),activeId:s.photos[2].id,mode:'photo',playing:false,playhead:0});s.setHeat({auto:true,vmin:0,view:'front'})});
 await page.getByRole('button',{name:'Показать все ноды',exact:true}).click();
 await page.waitForTimeout(1000);
 // Stress the UI with 90 copies of real demo measurements, only in this test page.
 const original=await page.evaluate(async()=>{const {useStore}=await import('/src/store.ts');const old=useStore.getState().metrics;const base=old.catalog.filter(m=>m.model==='3ddfa_v3');const catalog=Array.from({length:90},(_,i)=>({...base[i%base.length],id:'test_track_'+i,title:'Проверка дорожки '+i}));const rows=old.rows.map(row=>({...row,metrics:Object.fromEntries(catalog.map((m,i)=>[m.id,row.metrics[base[i%base.length].id]]))}));useStore.setState({metrics:{...old,catalog,rows},visibleMetrics:null});return old});
 await page.waitForTimeout(150);check('Virtualized metric rows (90 tracks)',await page.locator('.metric-track').count()<=7);
 await page.locator('.metric-tracks').evaluate(el=>el.scrollTop=3300);await page.waitForTimeout(150);
 check('Scroll renders late metric rows',await page.locator('.metric-track').first().innerText().then(s=>s.includes('Проверка дорожки 67')||s.includes('Проверка дорожки 68')));
 await page.evaluate(async original=>{const {useStore}=await import('/src/store.ts');useStore.setState({metrics:original,visibleMetrics:null})},original);
 await page.locator('.metric-tracks').evaluate(el=>el.scrollTop=0);await page.waitForTimeout(200);
 await page.screenshot({path:'../reports/working-interface.png',fullPage:true});
 report.nodeBounds=await page.locator('.react-flow__node').evaluateAll(ns=>ns.map(n=>({id:n.dataset.id,x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y,w:n.getBoundingClientRect().width,h:n.getBoundingClientRect().height})));
 check('No browser runtime errors',report.errors.length===0);
}catch(e){report.failure=String(e);await page.screenshot({path:'../reports/acceptance-failure.png',fullPage:true});}
finally{await fs.writeFile('../reports/browser-acceptance.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();}
if(report.failure)process.exit(1);
