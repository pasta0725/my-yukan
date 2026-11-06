const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1080,height:1920}});
for(const id of process.argv.slice(2)){ await p.goto('file://'+__dirname+'/thumb.html#'+id); await p.reload(); await p.waitForFunction(()=>document.title==='done'); await p.waitForTimeout(400);
 await p.screenshot({path:__dirname+`/out/v3_${id}.png`});}
await b.close()})();
