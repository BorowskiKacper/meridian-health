import {
  Group,
  Mesh,
  MeshBasicMaterial,
  Plane,
  Raycaster,
  Vector2,
  Vector3,
  type PerspectiveCamera,
} from 'three';
import type { AtlasViewer } from '@authorod/svitylo-3d-anatomy-atlas/core';
import { severityColor, severityLabel, type CutAxis, type SceneFinding as Finding, type Tool } from './types';
import {
  liveRenderer,
  meshVisible,
  nameOfMesh,
  protectedIds,
  structureCenters,
  surfaceAnchor,
} from './bridge';
import { alignUp, makeCursor, makeCutPlane, makeImpact, makePin, makeSegment } from './markers';

export type { CutAxis, Tool };

export interface MeasureRecord {
  id: string;
  cm: number;
  from: string;
  to: string;
}

export interface NoteRecord {
  id: string;
  text: string;
  where: string;
}

interface PinRecord {
  id: string;
  title: string;
  kicker: string;
  color: string;
  point: Vector3;
  normal: Vector3;
  group: Group;
  label: HTMLButtonElement;
  impact?: Group;
}

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export class SceneOverlay {
  readonly root = new Group();
  tool: Tool = 'orbit';
  impacts = true;
  cutaway = false;
  cutAxis: CutAxis = 'y';
  activeId = '';
  private chartFindings: Finding[] = [];
  measures: MeasureRecord[] = [];
  notes: NoteRecord[] = [];

  private readonly pins: PinRecord[] = [];
  private readonly lookups: PinRecord[] = [];
  private readonly measureGroups: Group[] = [];
  private readonly notePins: PinRecord[] = [];
  private readonly cursor: ReturnType<typeof makeCursor>;
  private planeGroup: Group | null = null;
  private centers = new Map<string, Vector3>();
  private kept = new Set<string>();
  private cut = 1;
  private span = 1;
  private readonly min = new Vector3();
  private readonly max = new Vector3();
  private dragging = false;
  private down: { x: number; y: number; id: number } | null = null;
  private pending: { point: Vector3; name: string } | null = null;
  private raf = 0;
  private readonly raycaster = new Raycaster();
  private readonly ndc = new Vector2();
  private readonly dragPlane = new Plane();
  private readonly hitPoint = new Vector3();
  private readonly labels: HTMLElement;
  private onChange: () => void;

  constructor(
    private readonly viewer: AtlasViewer,
    labels: HTMLElement,
    private readonly listeners: { change: () => void; probe: (text: string | null) => void },
  ) {
    this.labels = labels;
    this.onChange = listeners.change;
    this.cursor = makeCursor();
    this.root.add(this.cursor);
    const bounds = viewer.catalog.manifest.bounds;
    this.min.set(bounds.min[0], bounds.min[1], bounds.min[2]);
    this.max.set(bounds.max[0], bounds.max[1], bounds.max[2]);
    this.span = Math.max(this.max.x - this.min.x, this.max.y - this.min.y, this.max.z - this.min.z) * 1.2;
    this.attach();
    const canvas = liveRenderer(viewer)?.canvas;
    canvas?.addEventListener('pointerdown', this.onPointerDown, true);
    canvas?.addEventListener('pointermove', this.onPointerMove);
    canvas?.addEventListener('pointerup', this.onPointerUp);
    canvas?.addEventListener('pointerleave', this.onPointerLeave);
    this.raf = requestAnimationFrame(this.frame);
  }

  setFindings(next: Finding[]): void {
    this.chartFindings = next;
    if (!next.some((item) => item.id === this.activeId)) this.activeId = next[0]?.id ?? '';
  }

  rebuild(): void {
    this.clearPins(this.pins);
    this.refreshKept();
    this.centers = structureCenters(this.viewer);
    for (const finding of this.chartFindings) {
      const outward = new Vector3(...finding.outward);
      const anchor = surfaceAnchor(this.viewer, finding.structureId, outward);
      if (!anchor) continue;
      const pin = this.addPin({
        id: finding.id,
        title: finding.title,
        kicker: severityLabel[finding.severity],
        color: severityColor[finding.severity],
        point: anchor.point,
        normal: anchor.normal,
        className: `tag ${finding.severity}`,
      });
      if (finding.impact) {
        const impact = makeImpact(severityColor[finding.severity]);
        impact.visible = this.impacts;
        pin.group.add(impact);
        pin.impact = impact;
      }
      this.pins.push(pin);
    }
    this.syncActive();
    this.onChange();
  }

  setActive(id: string): void {
    this.activeId = id;
    this.syncActive();
  }

  setTool(tool: Tool): void {
    this.tool = tool;
    this.pending = null;
    if (tool !== 'probe') this.cursor.visible = false;
    this.onChange();
  }

  setImpacts(on: boolean): void {
    this.impacts = on;
    for (const pin of this.pins) if (pin.impact) pin.impact.visible = on;
    this.onChange();
  }

  setCutaway(on: boolean): void {
    this.cutaway = on;
    if (!on) {
      this.planeGroup?.removeFromParent();
      this.planeGroup = null;
      this.viewer.showHidden();
      this.onChange();
      return;
    }
    if (!this.centers.size) this.centers = structureCenters(this.viewer);
    const anchor = this.pins.find((pin) => pin.id === this.activeId);
    const component = this.axisIndex();
    this.cut = anchor ? anchor.point.getComponent(component) : (this.min.getComponent(component) + this.max.getComponent(component)) / 2;
    this.ensurePlane();
    this.applyCut();
    this.onChange();
  }

  setCutAxis(axis: CutAxis): void {
    this.cutAxis = axis;
    if (!this.cutaway) return;
    const component = this.axisIndex();
    const anchor = this.pins.find((pin) => pin.id === this.activeId);
    this.cut = anchor ? anchor.point.getComponent(component) : (this.min.getComponent(component) + this.max.getComponent(component)) / 2;
    this.placePlane();
    this.applyCut();
    this.onChange();
  }

  /** 0 keeps the low side of the axis, 1 removes almost everything. */
  setCutT(t: number): void {
    const component = this.axisIndex();
    const low = this.min.getComponent(component);
    const high = this.max.getComponent(component);
    this.cut = low + (high - low) * Math.min(1, Math.max(0, t));
    if (this.cutaway) {
      this.placePlane();
      this.applyCut();
      this.onChange();
    }
  }

  cutT(): number {
    const component = this.axisIndex();
    const low = this.min.getComponent(component);
    const high = this.max.getComponent(component);
    if (high - low < 1e-6) return 0.5;
    return (this.cut - low) / (high - low);
  }

  cutCaption(): string {
    const cm = Math.round(this.cut * 1000) / 10;
    if (this.cutAxis === 'y') return `Keeping tissue below ${cm} cm`;
    if (this.cutAxis === 'x') return cm >= 0 ? `Open to the patient's right of ${cm} cm` : `Open to the patient's left of ${Math.abs(cm)} cm`;
    return cm >= 0 ? `Open behind ${cm} cm anterior` : `Open behind ${Math.abs(cm)} cm posterior`;
  }

  focusFinding(finding: Finding): void {
    const previous = this.viewer.getState()?.selected ?? this.chartFindings.map((item) => item.structureId);
    this.viewer.select([finding.structureId], 'replace');
    this.viewer.setView(finding.view);
    this.viewer.select(previous.length ? previous : this.chartFindings.map((item) => item.structureId), 'replace');
  }

  addLookup(structureId: string, title: string): void {
    const anchor = surfaceAnchor(this.viewer, structureId, new Vector3(0, 0.2, 1));
    if (!anchor) return;
    const existing = this.lookups.find((pin) => pin.id === structureId);
    existing?.group.removeFromParent();
    existing?.label.remove();
    const next = this.lookups.filter((pin) => pin.id !== structureId);
    this.lookups.length = 0;
    this.lookups.push(...next);
    this.lookups.push(
      this.addPin({
        id: structureId,
        title,
        kicker: 'Lookup',
        color: '#9aabbf',
        point: anchor.point,
        normal: anchor.normal,
        className: 'tag lookup',
      }),
    );
    this.centers.set(structureId, anchor.point.clone());
    this.refreshKept();
    if (this.cutaway) this.applyCut();
    this.onChange();
  }

  clearLookups(): void {
    this.clearPins(this.lookups);
    this.refreshKept();
    if (this.cutaway) this.applyCut();
    this.onChange();
  }

  clearMeasures(): void {
    this.pending = null;
    this.measures = [];
    for (const group of this.measureGroups) group.removeFromParent();
    this.measureGroups.length = 0;
    this.labels.querySelectorAll('.measure-tag').forEach((node) => node.remove());
    this.onChange();
  }

  clearNotes(): void {
    this.clearPins(this.notePins);
    this.notes = [];
    this.onChange();
  }

  private refreshKept(): void {
    this.kept = protectedIds(this.viewer, [
      ...this.chartFindings.map((finding) => finding.structureId),
      ...this.lookups.map((pin) => pin.id),
    ]);
  }

  private addPin(options: {
    id: string;
    title: string;
    kicker: string;
    color: string;
    point: Vector3;
    normal: Vector3;
    className: string;
  }): PinRecord {
    const group = makePin(options.color);
    group.position.copy(options.point);
    alignUp(group, options.normal);
    this.root.add(group);
    const label = document.createElement('button');
    label.type = 'button';
    label.className = options.className;
    label.innerHTML = `<span>${options.kicker}</span><strong></strong>`;
    label.querySelector('strong')!.textContent = options.title;
    label.addEventListener('click', () => {
      const finding = this.chartFindings.find((item) => item.id === options.id);
      if (finding) {
        this.activeId = finding.id;
        this.syncActive();
        this.focusFinding(finding);
        this.onChange();
      }
    });
    this.labels.append(label);
    return { ...options, group, label };
  }

  private clearPins(list: PinRecord[]): void {
    for (const pin of list) {
      pin.group.removeFromParent();
      pin.label.remove();
    }
    list.length = 0;
  }

  private syncActive(): void {
    for (const pin of this.pins) pin.label.classList.toggle('is-active', pin.id === this.activeId);
  }

  private attach(): void {
    const renderer = liveRenderer(this.viewer);
    if (!renderer || this.root.parent === renderer.scene) return;
    renderer.scene.add(this.root);
  }

  private ensurePlane(): void {
    if (!this.planeGroup) {
      this.planeGroup = makeCutPlane(this.span);
      this.root.add(this.planeGroup);
    }
    this.placePlane();
  }

  private axisIndex(): 0 | 1 | 2 {
    return this.cutAxis === 'x' ? 0 : this.cutAxis === 'y' ? 1 : 2;
  }

  private placePlane(): void {
    const plane = this.planeGroup;
    if (!plane) return;
    const center = this.min.clone().add(this.max).multiplyScalar(0.5);
    center.setComponent(this.axisIndex(), this.cut);
    plane.position.copy(center);
    plane.rotation.set(0, 0, 0);
    if (this.cutAxis === 'y') plane.rotation.x = -Math.PI / 2;
    else if (this.cutAxis === 'x') plane.rotation.y = Math.PI / 2;
  }

  private applyCut(): void {
    const component = this.axisIndex();
    const hide: string[] = [];
    for (const [id, center] of this.centers) {
      if (this.kept.has(id)) continue;
      if (center.getComponent(component) > this.cut + 0.004) hide.push(id);
    }
    this.viewer.showHidden();
    if (hide.length) this.viewer.hide(hide);
  }

  private camera(): PerspectiveCamera | null {
    return liveRenderer(this.viewer)?.rig.camera ?? null;
  }

  private pick(event: PointerEvent): { point: Vector3; name: string } | null {
    const renderer = liveRenderer(this.viewer);
    if (!renderer) return null;
    const hit = renderer.pick(event.clientX, event.clientY, (mesh) => meshVisible(this.viewer, mesh));
    if (!hit) return null;
    return { point: hit.point.clone(), name: nameOfMesh(this.viewer, hit.mesh) ?? 'Surface' };
  }

  private raycastHandle(event: PointerEvent): boolean {
    const renderer = liveRenderer(this.viewer);
    const handle = this.planeGroup?.getObjectByName('handle');
    if (!renderer || !handle) return false;
    const rect = renderer.canvas.getBoundingClientRect();
    this.ndc.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(this.ndc, renderer.rig.camera);
    return this.raycaster.intersectObject(handle, false).length > 0;
  }

  private readonly onPointerDown = (event: PointerEvent) => {
    if (event.button !== 0) return;
    this.down = { x: event.clientX, y: event.clientY, id: event.pointerId };
    if (!this.cutaway || !this.raycastHandle(event)) return;
    event.preventDefault();
    event.stopPropagation();
    const controls = liveRenderer(this.viewer)?.rig.controls;
    if (controls) controls.enabled = false;
    this.dragging = true;
  };

  private readonly onPointerMove = (event: PointerEvent) => {
    if (this.dragging) {
      this.dragCut(event);
      return;
    }
    if (this.tool === 'orbit') {
      this.cursor.visible = false;
      return;
    }
    const hit = this.pick(event);
    const active = this.pins.find((pin) => pin.id === this.activeId);
    if (!hit) {
      this.cursor.visible = false;
      this.listeners.probe(null);
      return;
    }
    this.cursor.visible = true;
    this.cursor.position.copy(hit.point);
    this.listeners.probe(this.caption(hit, active?.point));
  };

  private caption(hit: { point: Vector3; name: string }, from?: Vector3): string {
    const distance = from ? ` · ${formatCm(hit.point.distanceTo(from))} from the active mark` : '';
    return `${hit.name}${distance}`;
  }

  private dragCut(event: PointerEvent): void {
    const renderer = liveRenderer(this.viewer);
    if (!renderer) return;
    const rect = renderer.canvas.getBoundingClientRect();
    this.ndc.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(this.ndc, renderer.rig.camera);
    renderer.rig.camera.getWorldDirection(this.hitPoint);
    this.dragPlane.setFromNormalAndCoplanarPoint(this.hitPoint, this.planeGroup?.position ?? new Vector3());
    const landed = new Vector3();
    if (!this.raycaster.ray.intersectPlane(this.dragPlane, landed)) return;
    const component = this.axisIndex();
    const low = this.min.getComponent(component);
    const high = this.max.getComponent(component);
    this.cut = Math.min(high, Math.max(low, landed.getComponent(component)));
    this.placePlane();
    this.applyCut();
    this.onChange();
  }

  private readonly onPointerUp = (event: PointerEvent) => {
    const down = this.down;
    this.down = null;
    if (this.dragging) {
      this.dragging = false;
      const controls = liveRenderer(this.viewer)?.rig.controls;
      if (controls) controls.enabled = true;
      return;
    }
    if (this.tool !== 'measure' && this.tool !== 'mark') return;
    if (!down || down.id !== event.pointerId || event.button !== 0) return;
    if (Math.hypot(event.clientX - down.x, event.clientY - down.y) > 6) return;
    const hit = this.pick(event);
    if (!hit) return;
    if (this.tool === 'mark') this.dropNote(hit);
    else this.dropMeasure(hit);
    const keep = [...this.lookups.map((pin) => pin.id), ...this.chartFindings.map((finding) => finding.structureId)];
    this.viewer.select(keep, 'replace');
  };

  private dropMeasure(hit: { point: Vector3; name: string }): void {
    if (!this.pending) {
      this.pending = hit;
      this.onChange();
      return;
    }
    const a = this.pending;
    const id = `m${this.measures.length + 1}`;
    const cm = a.point.distanceTo(hit.point) * 100;
    this.measures = [...this.measures, { id, cm, from: a.name, to: hit.name }];
    const group = makeSegment(a.point, hit.point, '#f4efe4');
    const mid = a.point.clone().add(hit.point).multiplyScalar(0.5);
    group.userData.mid = mid;
    group.userData.cm = cm;
    group.name = id;
    this.root.add(group);
    this.measureGroups.push(group);
    const label = document.createElement('button');
    label.type = 'button';
    label.className = 'measure-tag';
    label.textContent = formatCm(a.point.distanceTo(hit.point));
    label.title = 'Remove this measurement';
    label.addEventListener('click', () => {
      group.removeFromParent();
      label.remove();
      this.measureGroups.splice(this.measureGroups.indexOf(group), 1);
      this.measures = this.measures.filter((item) => item.id !== id);
      this.onChange();
    });
    label.dataset.mid = '1';
    (label as HTMLButtonElement & { mid?: Vector3 }).mid = mid;
    this.labels.append(label);
    this.pending = null;
    this.onChange();
  }

  private dropNote(hit: { point: Vector3; name: string }): void {
    const id = `note-${Date.now()}`;
    const camera = this.camera();
    const normal = camera ? camera.position.clone().sub(hit.point) : new Vector3(0, 0, 1);
    const pin = this.addPin({
      id,
      title: 'Note',
      kicker: hit.name,
      color: '#f3ecdf',
      point: hit.point,
      normal,
      className: 'tag note',
    });
    const input = document.createElement('input');
    input.value = '';
    input.placeholder = 'What is here?';
    input.addEventListener('click', (event) => event.stopPropagation());
    input.addEventListener('keydown', (event) => event.stopPropagation());
    input.addEventListener('input', () => {
      const text = input.value.trim() || 'Note';
      pin.label.querySelector('strong')!.textContent = text;
      const record = this.notes.find((item) => item.id === id);
      if (record) record.text = text;
      pin.title = text;
    });
    pin.label.append(input);
    this.notePins.push(pin);
    this.notes = [...this.notes, { id, text: 'Note', where: hit.name }];
    this.onChange();
    input.focus();
  }

  pinsReady(): boolean {
    return this.pins.length > 0;
  }

  probeCaption(): string | null {
    if (this.tool === 'orbit' || !this.cursor.visible) return null;
    return typeof this.cursor.userData.caption === 'string' ? this.cursor.userData.caption : null;
  }

  pendingMeasure(): string | null {
    return this.pending ? `First point on ${this.pending.name}. Click a second point.` : null;
  }

  private readonly frame = (now: number) => {
    this.raf = requestAnimationFrame(this.frame);
    this.attach();
    const pulse = reducedMotion ? 1 : 1 + Math.sin(now * 0.004) * 0.12;
    for (const pin of this.pins) {
      const ring = pin.group.getObjectByName('ring');
      if (!(ring instanceof Mesh)) continue;
      if (ring.material instanceof MeshBasicMaterial) ring.material.depthTest = pin.id !== this.activeId;
      const scale = pin.id === this.activeId ? pulse + 0.18 : 1;
      ring.scale.setScalar(scale);
    }
    this.placeLabels();
    liveRenderer(this.viewer)?.requestRender();
  };

  private placeLabels(): void {
    const camera = this.camera();
    const renderer = liveRenderer(this.viewer);
    if (!camera || !renderer) return;
    const rect = renderer.canvas.getBoundingClientRect();
    const host = this.labels.getBoundingClientRect();
    const look = new Vector3();
    camera.getWorldDirection(look);
    const pins = [...this.pins, ...this.lookups, ...this.notePins];
    const placed: { x: number; y: number; label: HTMLElement }[] = [];
    for (const pin of pins) {
      const tip = pin.group.getObjectByName('tip');
      const world = new Vector3();
      if (tip) tip.getWorldPosition(world);
      else world.copy(pin.point);
      const toCamera = world.clone().sub(camera.position);
      const projected = world.clone().project(camera);
      const inFront = toCamera.dot(look) > 0;
      const inFrame = Math.abs(projected.x) < 1.15 && Math.abs(projected.y) < 1.15;
      if (!inFront || !inFrame) {
        pin.label.style.display = 'none';
        continue;
      }
      const x = (projected.x * 0.5 + 0.5) * rect.width + (rect.left - host.left);
      const y = (-projected.y * 0.5 + 0.5) * rect.height + (rect.top - host.top);
      pin.label.style.display = '';
      pin.label.style.zIndex = pin.id === this.activeId ? '3' : '1';
      placed.push({ x, y, label: pin.label });
    }
    for (let pass = 0; pass < 8; pass++) {
      for (let i = 0; i < placed.length; i++) {
        for (let j = i + 1; j < placed.length; j++) {
          const a = placed[i]!;
          const b = placed[j]!;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.hypot(dx, dy) || 1;
          if (dist >= 84) continue;
          const push = (84 - dist) / 2;
          a.x -= (dx / dist) * push;
          a.y -= ((dy / dist) || -1) * push;
          b.x += (dx / dist) * push;
          b.y += ((dy / dist) || -1) * push;
        }
      }
    }
    for (const item of placed) {
      const x = Math.min(rect.width - 88, Math.max(88, item.x));
      const y = Math.min(rect.height - 88, Math.max(36, item.y));
      item.label.style.left = `${x}px`;
      item.label.style.top = `${y}px`;
    }
    this.labels.querySelectorAll<HTMLButtonElement>('.measure-tag').forEach((label) => {
      const mid = (label as HTMLButtonElement & { mid?: Vector3 }).mid;
      if (!mid) return;
      if (mid.clone().sub(camera.position).dot(look) <= 0) {
        label.style.display = 'none';
        return;
      }
      const projected = mid.clone().project(camera);
      label.style.display = '';
      label.style.left = `${(projected.x * 0.5 + 0.5) * rect.width + (rect.left - host.left)}px`;
      label.style.top = `${(-projected.y * 0.5 + 0.5) * rect.height + (rect.top - host.top)}px`;
    });
  }

  dispose(): void {
    cancelAnimationFrame(this.raf);
    const canvas = liveRenderer(this.viewer)?.canvas;
    canvas?.removeEventListener('pointerdown', this.onPointerDown, true);
    canvas?.removeEventListener('pointermove', this.onPointerMove);
    canvas?.removeEventListener('pointerup', this.onPointerUp);
    canvas?.removeEventListener('pointerleave', this.onPointerLeave);
    this.root.removeFromParent();
  }

  private readonly onPointerLeave = () => {
    if (this.dragging) return;
    this.cursor.visible = false;
  };
}

function formatCm(metres: number): string {
  return `${(metres * 100).toFixed(1)} cm`;
}
