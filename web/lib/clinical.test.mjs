import assert from "node:assert/strict";
import test from "node:test";
import { allergySummary, bloodPressure, recordedPoints, sourceLabel, weightTrend } from "./clinical.ts";

test("missing allergy data differs from an explicit active NKDA record", () => {
  assert.equal(allergySummary([]), "Status not recorded");
  assert.equal(allergySummary([{ category: "nkda", status: "active" }]), "No known drug allergies");
  assert.equal(allergySummary([{ category: "nkda", status: "inactive" }]), "Status not recorded");
  assert.equal(allergySummary([{ category: "drug", status: "active", substance: "Penicillin" }]), "Penicillin");
});

test("measurements are validated, sorted, and retain source metadata", () => {
  const points = [
    { at: "2025-03-01", value: 66, source: "demo_vitals", documentId: "doc-1" },
    { at: "2024-01-01", value: 64 },
    { at: "2025-01-01", value: NaN },
    { at: "invalid", value: 70 },
  ];
  const output = recordedPoints({ points });
  assert.deepEqual(output.map((p) => p.value), [64, 66]);
  assert.equal(output[1].source, "demo_vitals");
  assert.equal(output[1].documentId, "doc-1");
  assert.equal(points[0].value, 66);
});

test("BP grouping does not invent missing components or combine incompatible units", () => {
  const systolic = { name: "Systolic blood pressure", unit: "mmHg", points: [] };
  const diastolic = { name: "Diastolic blood pressure", unit: "mmHg", points: [] };
  const incompatible = { name: "Systolic blood pressure", unit: "kPa", points: [] };
  assert.deepEqual(bloodPressure([systolic]), [systolic]);
  assert.deepEqual(bloodPressure([diastolic, incompatible, systolic]), [systolic, diastolic]);
  assert.equal(weightTrend([systolic]), undefined);
});

test("synthetic and missing provenance remain explicit", () => {
  assert.equal(sourceLabel("demo_vitals"), "Synthetic demo vitals");
  assert.equal(sourceLabel(), "Source not recorded");
});
