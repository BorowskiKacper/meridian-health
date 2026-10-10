import type { Finding, Patient, Specialty, TabKind } from "./types";

export const NOW_MINUTE = 100;

const nora: Patient = {
  id: "nora",
  name: "Nora Ellison",
  age: 47,
  sex: "F",
  mrn: "SYN-204817",
  summary:
    "Handlebar fall onto the left side today. The older chart has a lipid result and a father with colon cancer at 50, which moves screening earlier.",
  family: ["Father: colorectal cancer at 50"],
  specialties: ["trauma", "cardiology", "gi", "primary"],
  smsOptIn: true,
  notes: [],
  reminders: [
    {
      id: "colon",
      title: "Colorectal screening",
      detail: "Average-risk start at 45. Not yet adjusted for family history.",
      status: "scheduled",
    },
  ],
  findings: [
    {
      id: "ldl",
      structureId: "cardiovascular.heart",
      title: "LDL",
      condition: "Elevated LDL cholesterol",
      note: "Lipid panel from 18 months ago.",
      severity: "watch",
      kind: "lab",
      minute: 30,
      specialties: ["cardiology", "primary"],
      meds: ["No statin"],
      observations: [{ label: "LDL", value: "142 mg/dL" }],
      outward: [0.35, 0.55, 0.85],
      view: "anterior",
    },
    {
      id: "rib",
      structureId: "skeletal.sixth_rib_l",
      title: "Sixth left rib",
      condition: "Left sixth rib fracture",
      note: "Cortical break under the impact, with crepitus. Treat as the unstable chest wall.",
      severity: "critical",
      kind: "injury",
      minute: 74,
      specialties: ["trauma"],
      meds: ["Analgesia not charted yet"],
      observations: [
        { label: "Chest", value: "Tender, crepitus" },
        { label: "SpO₂", value: "94% on air" },
      ],
      outward: [0.55, 0.2, 1],
      view: "left",
      impact: true,
    },
    {
      id: "lung",
      structureId: "visceral.left_lung",
      title: "Left lung",
      condition: "Pulmonary contusion",
      note: "Contusion behind the broken rib. No large pneumothorax on the first film.",
      severity: "watch",
      kind: "injury",
      minute: 78,
      specialties: ["trauma"],
      meds: ["Oxygen not started"],
      observations: [{ label: "Film", value: "No large pneumothorax" }],
      outward: [1, 0.15, 0.55],
      view: "left",
    },
    {
      id: "ventricle",
      structureId: "cardiovascular.left_ventricle",
      title: "Left ventricle",
      condition: "Possible cardiac injury",
      note: "Troponin rising after the chest impact. Wall motion not yet reviewed.",
      severity: "watch",
      kind: "injury",
      minute: 82,
      specialties: ["trauma", "cardiology"],
      meds: ["No cardiac medication charted"],
      observations: [{ label: "Troponin", value: "Rising" }],
      outward: [0.85, 0.25, 0.7],
      view: "anterior",
    },
    {
      id: "liver",
      structureId: "visceral.liver",
      title: "Liver",
      condition: "Possible capsular laceration",
      note: "Do not clear the abdomen on the plain film.",
      severity: "watch",
      kind: "injury",
      minute: 86,
      specialties: ["trauma", "gi"],
      meds: ["No abdominal medication charted"],
      observations: [{ label: "CT", value: "Pending" }],
      outward: [-0.65, 0.25, 1],
      view: "anterior",
    },
    {
      id: "tibia",
      structureId: "skeletal.tibia_l",
      title: "Left tibia",
      condition: "Transverse tibial shaft fracture",
      note: "Transverse shaft fracture from the kerb. Distal pulses present.",
      severity: "critical",
      kind: "injury",
      minute: 90,
      specialties: ["trauma"],
      meds: ["Splint ordered, not recorded as placed"],
      observations: [{ label: "Pulses", value: "Present" }],
      outward: [0.35, 0.1, 1],
      view: "left",
      impact: true,
    },
    {
      id: "spleen",
      structureId: "lymphoid.spleen",
      title: "Spleen",
      condition: "No splenic injury on first look",
      note: "Reviewed. No free fluid and no blush.",
      severity: "clear",
      kind: "injury",
      minute: 96,
      specialties: ["trauma", "gi"],
      meds: [],
      observations: [{ label: "Ultrasound", value: "No free fluid" }],
      outward: [1, 0.2, 0.15],
      view: "left",
    },
  ],
};

const marcus: Patient = {
  id: "marcus",
  name: "Marcus Hale",
  age: 62,
  sex: "M",
  mrn: "SYN-118342",
  summary:
    "Type 2 diabetes for eleven years with early kidney disease. Here for a quarterly review; last A1c was above target.",
  family: ["Mother: type 2 diabetes", "Brother: myocardial infarction at 58"],
  specialties: ["primary", "nephrology", "cardiology"],
  smsOptIn: true,
  notes: [],
  reminders: [
    {
      id: "eye",
      title: "Diabetic eye exam",
      detail: "Annual retinal exam. Last done 14 months ago.",
      status: "due",
    },
    {
      id: "a1c",
      title: "A1c recheck",
      detail: "Every three months while above target.",
      status: "scheduled",
    },
  ],
  findings: [
    {
      id: "a1c",
      structureId: "visceral.pancreas",
      title: "A1c",
      condition: "Type 2 diabetes, above target",
      note: "Rising over the last two checks.",
      severity: "watch",
      kind: "lab",
      minute: 60,
      specialties: ["primary"],
      meds: ["Metformin 1000 mg twice daily"],
      observations: [
        { label: "A1c", value: "8.4%" },
        { label: "Prior", value: "7.9%" },
      ],
      outward: [0.2, 0.3, 1],
      view: "anterior",
    },
    {
      id: "kidney",
      structureId: "visceral.kidney_l",
      title: "Kidneys",
      condition: "Chronic kidney disease, stage 3a",
      note: "eGFR stable for a year. Albuminuria present.",
      severity: "watch",
      kind: "disease",
      minute: 40,
      specialties: ["nephrology", "primary"],
      meds: ["Lisinopril 20 mg daily"],
      observations: [
        { label: "eGFR", value: "52 mL/min" },
        { label: "UACR", value: "64 mg/g" },
      ],
      outward: [1, 0.1, -0.4],
      view: "posterior",
    },
    {
      id: "heart",
      structureId: "cardiovascular.heart",
      title: "Heart",
      condition: "Hypertension, controlled",
      note: "Home readings in range.",
      severity: "clear",
      kind: "disease",
      minute: 20,
      specialties: ["cardiology", "primary"],
      meds: ["Lisinopril 20 mg daily"],
      observations: [{ label: "BP", value: "128/78" }],
      outward: [0.35, 0.55, 0.85],
      view: "anterior",
    },
  ],
};

export const seedPatients: Patient[] = [nora, marcus];

/** Anatomy loaded around the findings so the marks sit on a recognisable torso and leg. */
export const bodyContext = [
  "skeletal.ribs",
  "skeletal.sternum",
  "skeletal.clavicle_l",
  "skeletal.clavicle_r",
  "visceral.lungs",
  "cardiovascular.heart",
  "visceral.liver",
  "visceral.stomach",
  "visceral.pancreas",
  "visceral.kidney_l",
  "visceral.colon",
  "lymphoid.spleen",
  "skeletal.femur_l",
  "skeletal.patella_l",
  "skeletal.tibia_l",
  "skeletal.fibula_l",
];

export const tabLabel: Record<TabKind, string> = {
  body: "Body",
  region: "Region",
  timeline: "Timeline",
  queue: "Approvals",
  research: "Research",
  lab: "Lab document",
  reminders: "Reminders",
  chat: "Conversation",
};

export const openableTabs: TabKind[] = ["body", "timeline", "queue", "lab", "reminders"];

export const specialtyLabel: Record<Specialty, string> = {
  all: "All findings",
  trauma: "Trauma",
  cardiology: "Cardiology",
  gi: "GI",
  primary: "Primary care",
  nephrology: "Nephrology",
};

export const severityLabel = { critical: "Critical", watch: "Watch", clear: "Clear" } as const;
export const kindLabel = { injury: "Injury", disease: "Disease", lab: "Lab" } as const;

export function whenLabel(minute: number): string {
  if (minute < 25) return "2 years ago";
  if (minute < 50) return "18 months ago";
  if (minute < 72) return "Earlier this year";
  if (minute < 100) return "This visit";
  return "Now";
}

export function findingVisible(finding: Finding, minute: number, specialty: Specialty): boolean {
  if (finding.minute > minute) return false;
  return specialty === "all" || finding.specialties.includes(specialty);
}

export const ldl190: Finding = {
  id: "ldl-190",
  structureId: "cardiovascular.heart",
  title: "LDL today",
  condition: "LDL at the statin threshold",
  note: "Dictated this visit.",
  severity: "critical",
  kind: "lab",
  minute: 100,
  specialties: ["cardiology", "primary"],
  meds: [],
  observations: [{ label: "LDL", value: "190 mg/dL" }],
  outward: [0.15, 0.7, 0.7],
  view: "anterior",
};

export const fibula: Finding = {
  id: "fibula",
  structureId: "skeletal.fibula_l",
  title: "Left fibula",
  condition: "Possible fibular fracture",
  note: "Tender over the lateral leg after the kerb strike.",
  severity: "watch",
  kind: "injury",
  minute: 100,
  specialties: ["trauma"],
  meds: [],
  observations: [{ label: "Exam", value: "Lateral tenderness" }],
  outward: [-0.15, 0.05, 1],
  view: "left",
};

export const colonScreen: Finding = {
  id: "colon",
  structureId: "visceral.colon",
  title: "Colon",
  condition: "Colorectal screening overdue",
  note: "Father diagnosed at 50, so screening starts at 40. She is 47 and has not had one.",
  severity: "watch",
  kind: "disease",
  minute: 100,
  specialties: ["gi", "primary"],
  meds: [],
  observations: [{ label: "Family", value: "Father, colorectal cancer at 50" }],
  outward: [0.25, -0.35, 0.95],
  view: "anterior",
};

export const labPanel = {
  title: "Comprehensive metabolic panel",
  lab: "Riverside Clinical Labs",
  collected: "Collected this morning",
  rows: [
    { test: "ALT", value: "88", unit: "U/L", range: "7–56", flag: "High" },
    { test: "AST", value: "41", unit: "U/L", range: "10–40", flag: "High" },
    { test: "Creatinine", value: "1.3", unit: "mg/dL", range: "0.6–1.1", flag: "High" },
    { test: "Sodium", value: "139", unit: "mmol/L", range: "135–145", flag: "" },
    { test: "Potassium", value: "4.1", unit: "mmol/L", range: "3.5–5.1", flag: "" },
    { test: "Glucose", value: "104", unit: "mg/dL", range: "70–99", flag: "High" },
  ],
};

export const altLab: Finding = {
  id: "alt",
  structureId: "visceral.liver",
  title: "ALT",
  condition: "Elevated ALT",
  note: "From the photographed paper panel.",
  severity: "watch",
  kind: "lab",
  minute: 100,
  specialties: ["gi", "primary"],
  meds: [],
  observations: [{ label: "ALT", value: "88 U/L, high" }],
  outward: [-0.2, 0.55, 0.9],
  view: "anterior",
};

export const creatinineLab: Finding = {
  id: "creatinine",
  structureId: "visceral.kidney_l",
  title: "Creatinine",
  condition: "Creatinine above range",
  note: "From the photographed paper panel.",
  severity: "watch",
  kind: "lab",
  minute: 100,
  specialties: ["primary"],
  meds: [],
  observations: [{ label: "Creatinine", value: "1.3 mg/dL, high" }],
  outward: [1, 0.05, 0.35],
  view: "left",
};
