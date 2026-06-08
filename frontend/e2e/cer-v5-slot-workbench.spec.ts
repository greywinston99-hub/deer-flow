import { expect, test } from "@playwright/test";

const REVIEW_WORKBENCH_PATH = "/workspace/cer/governance/CER_RMF_174/review-workbench";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("cer_dev_role_value", "SENIOR_REVIEWER");
    localStorage.setItem("cer_dev_user_id", "dev-senior");
    localStorage.setItem("cer_dev_user_name", "Dev Senior Reviewer");
  });
});

test("Scenario: Slot-first workbench renders reviewer actions", async ({ page }, testInfo) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (err) => pageErrors.push(err.message));

  const response = await page.goto(REVIEW_WORKBENCH_PATH);
  expect(response?.status()).toBe(200);

  await expect(page.getByText("Source Slot Workbench")).toBeVisible();
  await expect(page.getByTestId("slot-card-IFU")).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Recommendation is not confirmation.")).toBeVisible();

  await page.getByTestId("slot-card-IFU").click();
  await expect(page.getByRole("button", { name: "Stage" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open File Check" })).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath("slot-workbench.png"), fullPage: true });

  const criticalErrors = pageErrors.filter((error) => /TypeError|ReferenceError|Cannot read/i.test(error));
  expect(criticalErrors).toHaveLength(0);
});
