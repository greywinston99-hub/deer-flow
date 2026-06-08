import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));
  
  await page.goto('http://localhost:3000/workspace/cer/governance/CER_RMF_174/review-workbench');
  await page.waitForTimeout(5000);
  
  const html = await page.content();
  console.log('Has disclaimer:', html.includes('Recommendation is not confirmation'));
  console.log('Has Reviewer workload:', html.includes('Reviewer workload should focus'));
  console.log('Has summary cards:', html.includes('Blocking Gaps'));
  console.log('Has IFU:', html.includes('IFU'));
  console.log('Has slot-card-IFU:', html.includes('slot-card-IFU'));
  console.log('Has RECOMMENDED:', html.includes('RECOMMENDED'));
  console.log('JS errors:', errors);
  
  await browser.close();
})();
