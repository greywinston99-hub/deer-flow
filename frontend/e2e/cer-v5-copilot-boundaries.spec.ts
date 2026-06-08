import { expect, test } from "@playwright/test";

const REVIEW_WORKBENCH_PATH = "/workspace/cer/governance/CER_RMF_174/review-workbench";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("cer_dev_role_value", "SENIOR_REVIEWER");
    localStorage.setItem("cer_dev_user_id", "dev-senior");
    localStorage.setItem("cer_dev_user_name", "Dev Senior Reviewer");
  });
});

test("Scenario: Copilot remains draft-only and human-gated", async ({ page }, testInfo) => {
  await page.goto(REVIEW_WORKBENCH_PATH);
  await page.getByRole("tab", { name: "Review Copilot" }).click();

  await expect(page.getByRole("button", { name: "Draft Next Action" })).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "Draft Next Action" }).click();

  await expect(page.getByTestId("review-copilot-drawer")).toBeVisible();
  await expect(page.getByText("Copilot explains and drafts only. Does not decide.")).toBeVisible();

  const bodyText = await page.locator("body").innerText();
  expect(bodyText).not.toMatch(/auto.confirm|auto.accept|auto.approve|official CEAR|final decision/i);

  await page.screenshot({ path: testInfo.outputPath("copilot-boundaries.png"), fullPage: true });
});
