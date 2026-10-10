// The contract has no patient-list route. These ids match backend/seed/seed.py.
export const DEMO_PATIENTS = [
  { id: "11111111-1111-4111-8111-111111111111", displayName: "Jane Doe" },
  { id: "22222222-2222-4222-8222-222222222222", displayName: "John Roe" },
  { id: "33333333-3333-4333-8333-333333333333", displayName: "Amy Lee" },
] as const;

export type DemoPatient = (typeof DEMO_PATIENTS)[number];
