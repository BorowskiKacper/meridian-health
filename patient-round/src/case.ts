import type { StandardView } from '@authorod/svitylo-3d-anatomy-atlas/core';

export type Severity = 'critical' | 'watch' | 'clear';
export type BodyRegion = 'chest' | 'abdomen' | 'limb';
export type Specialty = 'trauma' | 'chest' | 'abdomen' | 'ortho';

export interface Observation {
  label: string;
  value: string;
}

export interface Finding {
  id: string;
  structureId: string;
  title: string;
  note: string;
  severity: Severity;
  /** Preferred outward direction in patient space: +X is the patient's left, +Y up, +Z anterior. */
  outward: [number, number, number];
  view: StandardView;
  /** Minutes after arrival. The timeline hides anything later than the slider. */
  minute: number;
  region: BodyRegion;
  impact?: boolean;
  condition: string;
  meds: string[];
  observations: Observation[];
}

export const NOW_MINUTE = 40;

export const patient = {
  name: 'Nora Ellison',
  meta: '47 · cyclist · arrived 40 min ago',
  story:
    'Went over the handlebars onto her left side. The left shin struck the kerb. She is awake and talking. Oxygen is 94% on air, the left chest is tender with crepitus, and the left leg is swollen with pulses present.',
};

export const findings: Finding[] = [
  {
    id: 'rib',
    structureId: 'skeletal.sixth_rib_l',
    title: 'Sixth left rib',
    note: 'Cortical break under the impact, with crepitus. Treat this as the unstable chest wall.',
    severity: 'critical',
    outward: [0.55, 0.2, 1],
    view: 'left',
    minute: 8,
    region: 'chest',
    impact: true,
    condition: 'Left sixth rib fracture',
    meds: ['Analgesia not charted yet'],
    observations: [
      { label: 'Chest', value: 'Tender, crepitus' },
      { label: 'SpO₂', value: '94% on air' },
    ],
  },
  {
    id: 'lung',
    structureId: 'visceral.left_lung',
    title: 'Left lung',
    note: 'Contusion behind the broken rib. No large pneumothorax on the first film. Recheck if breathing gets harder.',
    severity: 'watch',
    outward: [1, 0.15, 0.55],
    view: 'left',
    minute: 12,
    region: 'chest',
    condition: 'Pulmonary contusion',
    meds: ['Oxygen not started'],
    observations: [
      { label: 'Film', value: 'No large pneumothorax' },
      { label: 'SpO₂', value: '94% on air' },
    ],
  },
  {
    id: 'ventricle',
    structureId: 'cardiovascular.left_ventricle',
    title: 'Left ventricle',
    note: 'Troponin is rising. Wall motion has not been reviewed. Keep her monitored while the chest is the priority.',
    severity: 'watch',
    outward: [0.85, 0.25, 0.7],
    view: 'anterior',
    minute: 18,
    region: 'chest',
    condition: 'Possible cardiac injury',
    meds: ['No cardiac medication charted'],
    observations: [{ label: 'Troponin', value: 'Rising' }],
  },
  {
    id: 'liver',
    structureId: 'visceral.liver',
    title: 'Liver',
    note: 'Possible capsular laceration. The CT is still open. Do not clear the abdomen on the plain film.',
    severity: 'watch',
    outward: [-0.65, 0.25, 1],
    view: 'anterior',
    minute: 22,
    region: 'abdomen',
    condition: 'Possible capsular laceration',
    meds: ['No abdominal medication charted'],
    observations: [{ label: 'CT', value: 'Still open' }],
  },
  {
    id: 'tibia',
    structureId: 'skeletal.tibia_l',
    title: 'Left tibia',
    note: 'Transverse shaft fracture from the kerb. Pulses are present. Splint before she leaves the bay.',
    severity: 'critical',
    outward: [0.35, 0.1, 1],
    view: 'left',
    minute: 28,
    region: 'limb',
    impact: true,
    condition: 'Transverse tibial shaft fracture',
    meds: ['Splint ordered, not recorded as placed'],
    observations: [{ label: 'Pulses', value: 'Present' }],
  },
  {
    id: 'spleen',
    structureId: 'lymphoid.spleen',
    title: 'Spleen',
    note: 'Reviewed. No free fluid and no blush. Leave it on the list so the clear call stays visible.',
    severity: 'clear',
    outward: [1, 0.2, 0.15],
    view: 'left',
    minute: 36,
    region: 'abdomen',
    condition: 'No splenic injury on the first look',
    meds: ['None for the spleen'],
    observations: [{ label: 'Ultrasound', value: 'No free fluid, no blush' }],
  },
];

/** A chart proposal the queue can approve onto the body. Not on the chart until then. */
export const fibulaProposal: Finding = {
  id: 'fibula',
  structureId: 'skeletal.fibula_l',
  title: 'Left fibula',
  note: 'Tender over the lateral leg after the kerb strike. Watch for a second fracture.',
  severity: 'watch',
  outward: [-0.15, 0.05, 1],
  view: 'left',
  minute: 40,
  region: 'limb',
  condition: 'Possible fibular fracture',
  meds: ['None yet'],
  observations: [{ label: 'Exam', value: 'Lateral tenderness' }],
};

/** Groups placed on the scene so the marks sit in a body, not in empty space. */
export const contextIds = [
  'skeletal.ribs',
  'skeletal.sternum',
  'skeletal.clavicle_l',
  'skeletal.clavicle_r',
  'visceral.lungs',
  'cardiovascular.heart',
  'visceral.liver',
  'lymphoid.spleen',
  'skeletal.femur_l',
  'skeletal.patella_l',
  'skeletal.tibia_l',
  'skeletal.fibula_l',
];

export const severityLabel: Record<Severity, string> = {
  critical: 'Critical',
  watch: 'Watch',
  clear: 'Clear',
};

export const severityColor: Record<Severity, string> = {
  critical: '#e15a4a',
  watch: '#e2a53a',
  clear: '#3e9a6d',
};

const specialtyRegion: Record<Exclude<Specialty, 'trauma'>, BodyRegion> = {
  chest: 'chest',
  abdomen: 'abdomen',
  ortho: 'limb',
};

export function findingVisible(finding: Finding, minute: number, specialty: Specialty): boolean {
  if (finding.minute > minute) return false;
  if (specialty === 'trauma') return true;
  return finding.region === specialtyRegion[specialty];
}
