import { expect, test } from "@playwright/test";

test("all analysis tabs remain visible and operable at 320 pixels", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto("/?case=demo");
  const tabs = page.locator(".insights-panel").getByRole("tablist");
  await tabs.scrollIntoViewIfNeeded();
  for (const name of ["Case summary", "Missing evidence", "Contradictions"]) {
    await expect(tabs.getByRole("tab", { name, exact: false })).toBeInViewport({
      ratio: 1,
    });
  }
  await tabs.getByRole("tab", { name: "Contradictions", exact: false }).click();
  await expect(
    page.getByRole("heading", { name: "Contradictions", exact: true }),
  ).toBeVisible();
});
