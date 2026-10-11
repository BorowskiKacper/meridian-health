import assert from "node:assert/strict";
import { test } from "node:test";

import { diffLines, isOpenableLocator, reviewSummary, routeLabel } from "./format";

test("route labels match the doctor request routes", () => {
  assert.equal(routeLabel("chart_update"), "Chart update");
  assert.equal(routeLabel("clinical_question"), "Clinical question");
  assert.equal(routeLabel("check_screenings"), "Screening review");
});

test("diffs show allowlisted before and after values", () => {
  assert.deepEqual(
    diffLines({ status: "active", name: "Hypertension" }, { status: "controlled", name: "Hypertension" }),
    ["status: active → controlled", "name: Hypertension"],
  );
});

test("only http locators open, chart locators stay text", () => {
  assert.equal(
    isOpenableLocator("https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/colorectal-cancer-screening"),
    true,
  );
  assert.equal(isOpenableLocator("note:11111111-1111-4111-8111-111111111111"), false);
  assert.equal(isOpenableLocator("Northwind preventive policy"), false);
});

test("reminder review keeps the answer and counts new suggestions", () => {
  assert.equal(reviewSummary("Screenings are up to date.", 0), "Screenings are up to date.");
  assert.equal(reviewSummary(null, 1), "1 reminder change is waiting.");
  assert.equal(reviewSummary("Reviewed.", 2), "Reviewed. 2 reminder changes are waiting.");
});
