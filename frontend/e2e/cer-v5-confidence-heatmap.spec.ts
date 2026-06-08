import { expect, test } from "@playwright/test";

const REVIEW_WORKBENCH_PATH = "/workspace/cer/governance/CER_RMF_174/review-workbench";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("cer_dev_role_value", "SENIOR_REVIEWER");
    localStorage.setItem("cer_dev_user_id", "dev-senior");
    localStorage.setItem("cer_dev_user_name", "Dev Senior Reviewer");
  });
});

test("Scenario: Confidence heatmap highlights reviewer attention bands", async ({ page }, testInfo) => {
  await page.goto(REVIEW_WORKBENCH_PATH);
  await page.getByRole("tab", { name: "Confidence Heatmap" }).click();

  await expect(page.getByTestId("confidence-heatmap")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("High-confidence items may be staged, but never auto-approved.")).toBeVisible();
  await expect(page.getByText(/Integrity:/).first()).toBeVisible();
  await expect(page.getByText(/Readability:/).first()).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath("confidence-heatmap.png"), fullPage: true });
});
