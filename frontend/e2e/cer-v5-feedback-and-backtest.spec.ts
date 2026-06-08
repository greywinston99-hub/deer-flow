import { expect, test } from "@playwright/test";

const REVIEW_WORKBENCH_PATH = "/workspace/cer/governance/CER_RMF_174/review-workbench";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("cer_dev_role_value", "SENIOR_REVIEWER");
    localStorage.setItem("cer_dev_user_id", "dev-senior");
    localStorage.setItem("cer_dev_user_name", "Dev Senior Reviewer");
  });
});

test("Scenario: Shadow backtest stays sandbox-only", async ({ page }, testInfo) => {
  await page.goto(REVIEW_WORKBENCH_PATH);
  await page.getByRole("tab", { name: "Shadow Backtest" }).click();

  await expect(page.getByRole("button", { name: "Run Shadow Backtest" })).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "Run Shadow Backtest" }).click();

  await expect(page.getByText("Sandbox Backtest Summary")).toBeVisible({ timeout: 15000 });
  const bodyText = await page.locator("body").innerText();
  expect(bodyText).toMatch(/sandbox/i);
  expect(bodyText).not.toMatch(/approved|backflow|obsidian|nocodb|active rule/i);

  await page.screenshot({ path: testInfo.outputPath("shadow-backtest.png"), fullPage: true });
});
