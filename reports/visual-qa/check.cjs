// Local browser verification; no server, user profile, or network resources.
const { chromium } = require('C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const { pathToFileURL } = require('node:url');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const results = [];
  try {
    for (const width of [1280, 390]) {
      const page = await browser.newPage({viewport:{width,height:900},deviceScaleFactor:1});
      const requests = [];
      await page.route(/^https?:/, route => { requests.push(route.request().url()); return route.abort(); });
      for (const name of ['synthetic-report','fixture-empty','fixture-single','fixture-flat','fixture-tiny','fixture-negative']) {
        await page.goto(pathToFileURL(path.join(__dirname,`${name}.html`)).href);
        await page.evaluate(() => document.fonts.ready);
        const metrics = await page.evaluate(() => ({
          viewport:innerWidth, scrollWidth:document.documentElement.scrollWidth,
          clippedText:[...document.querySelectorAll('svg text')].filter(el => {
            const box=el.getBBox(), vb=el.ownerSVGElement.viewBox.baseVal;
            return box.x<0 || box.y<0 || box.x+box.width>vb.width || box.y+box.height>vb.height;
          }).map(el=>el.textContent),
          tableScroll:[...document.querySelectorAll('.table-container')].map(el=>({client:el.clientWidth,scroll:el.scrollWidth})),
        }));
        results.push({name,width,...metrics,requests:[...requests]});
        if (name==='synthetic-report') {
          await page.screenshot({path:path.join(__dirname,`${name}-${width}.png`),fullPage:true});
          await page.locator('.card-grid').nth(2).screenshot({path:path.join(__dirname,`position-${width}.png`)});
          if (width===390) {
            const scrolled = await page.locator('.table-container').evaluateAll(elements=>elements.map(el=>{
              el.scrollLeft=el.scrollWidth;
              return el.scrollLeft>0;
            }));
            if (!scrolled.every(Boolean)) throw Error('Narrow tables do not scroll');
            await page.locator('.table-container').first().screenshot({path:path.join(__dirname,'trades-scroll-end-390.png')});
          }
        }
        await page.locator('.chart-container').screenshot({path:path.join(__dirname,`${name}-chart-${width}.png`)});
      }
      await page.close();
    }
    fs.writeFileSync(path.join(__dirname,'browser-check.json'),JSON.stringify(results,null,2));
    console.log(JSON.stringify(results));
    if (results.some(r=>r.scrollWidth>r.viewport || r.clippedText.length || r.requests.length))
      throw Error('Visual geometry or offline resource check failed');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
