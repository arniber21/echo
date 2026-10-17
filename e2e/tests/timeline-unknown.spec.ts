import { expect, test } from "@playwright/test";
import type { Case, Event } from "../../frontend/app/types/generated";

for (const width of [1440, 390, 320]) {
  test(`unaligned events retain readable source-clock cards at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const incident: Case = await (
      await page.request.get("/api/cases/demo")
    ).json();
    const video = incident.analysis?.events.find(
      (event) => event.source_type === "video",
    );
    const audio = incident.analysis?.events.find(
      (event) => event.source_type === "audio",
    );
    const photo = incident.analysis?.events.find(
      (event) => event.source_type === "photo",
    );
    if (!incident.analysis || !video || !audio || !photo)
      throw new Error("Fixture needs video, audio and photo events");
    const unknown: Event = {
      ...audio,
      event_id: "unknown-audio",
      title: "Unaligned recorded account",
      case_min: 0,
      case_max: null,
      case_best: 0,
      source_start: 17,
      source_end: 20,
      alignment_basis: "No reliable content match to the primary recording.",
    };
    const other: Event = {
      ...unknown,
      event_id: "other-audio",
      title: "Second unaligned account",
      source_start: 1,
      source_end: 4,
    };
    const unknownPhoto: Event = {
      ...photo,
      event_id: "unknown-photo",
      title: "Photo with unknown placement",
      case_min: 0,
      case_max: null,
      case_best: 0,
      alignment_basis: "Capture time and relative placement are unknown.",
    };
    const boundedPhoto: Event = {
      ...photo,
      event_id: "bounded-photo",
      title: "Photo after supported lower bound",
      case_min: 8,
      case_best: 8,
      case_max: null,
    };
    incident.analysis.events = [
      video,
      unknown,
      other,
      unknownPhoto,
      boundedPhoto,
    ];
    incident.preview = null;
    await page.route("**/api/cases/demo", (route) =>
      route.fulfill({ json: incident }),
    );
    await page.goto("/?case=demo");
    const timeline = page.getByRole("region", {
      name: "Unified timeline",
      exact: true,
    });
    await expect(timeline.locator(".unaligned-event")).toHaveCount(3);
    await expect(timeline.locator(".unified-event")).toHaveCount(2);
    await expect(timeline.locator(".unaligned-event .unified-dot")).toHaveCount(
      0,
    );
    const first = timeline.getByRole("button", {
      name: unknown.title,
      exact: true,
    });
    await expect(first).toContainText("Source 00:17.0 – 00:20.0");
    await expect(first).toContainText("No reliable content match");
    await expect(
      timeline.getByRole("button", { name: unknownPhoto.title, exact: true }),
    ).toContainText("Source time unknown");
    const cards = await timeline
      .locator(".unaligned-event")
      .evaluateAll((elements) =>
        elements.map((element) => ({
          top: element.getBoundingClientRect().top,
          bottom: element.getBoundingClientRect().bottom,
        })),
      );
    for (let index = 1; index < cards.length; index++)
      expect(cards[index]!.top).toBeGreaterThanOrEqual(
        cards[index - 1]!.bottom,
      );
    await expect
      .poll(() =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      )
      .toBeTruthy();
    await first.click();
    await expect
      .poll(() =>
        page
          .locator("audio")
          .evaluate((audio: HTMLAudioElement) => audio.currentTime),
      )
      .toBeCloseTo(17, 1);
    await expect(page.locator(".event-detail")).toContainText(
      "Case time unknown",
    );
    await expect(page.locator(".event-detail")).not.toContainText(
      "Post-incident",
    );
  });
}
