import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  const networkFails = [];
  page.on('pageerror', err => errors.push(err.message));
  page.on('response', res => {
    if (!res.ok()) {
      networkFails.push(`${res.request().method()} ${res.url()} => ${res.status()}`);
    }
  });
  
  await page.goto('http://localhost:3000/workspace/cer/governance/CER_RMF_174/review-workbench');
  await page.waitForTimeout(5000);
  
  const html = await page.content();
  console.log('Has IFU:', html.includes('IFU'));
  console.log('Has slot-card-IFU:', html.includes('slot-card-IFU'));
  console.log('Has RECOMMENDED:', html.includes('RECOMMENDED'));
  console.log('JS errors:', errors);
  console.log('Network fails:', networkFails);
  
  await browser.close();
})();
