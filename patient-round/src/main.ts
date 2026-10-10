import '@fontsource/fraunces/500.css';
import '@fontsource/outfit/400.css';
import '@fontsource/outfit/500.css';
import { createAtlasViewer, type AtlasViewer } from '@authorod/svitylo-3d-anatomy-atlas/core';
import { contextIds, type Finding } from './case.ts';
import { Fusion } from './fusion.ts';
import { SceneOverlay, type CutAxis, type Tool } from './overlay.ts';
import './style.css';

const stage = document.querySelector<HTMLElement>('#stage')!;
const view = document.querySelector<HTMLElement>('#view')!;
const labels = document.querySelector<HTMLElement>('#labels')!;
const hud = document.querySelector<HTMLElement>('#hud')!;
const findingsList = document.querySelector<HTMLOListElement>('#findings')!;
const loadingText = document.querySelector<HTMLElement>('#loading-text')!;
const loadingBar = document.querySelector<HTMLElement>('#loading-bar')!;
const failure = document.querySelector<HTMLElement>('#failure')!;
const failureText = document.querySelector<HTMLElement>('#failure-text')!;
const walkButton = document.querySelector<HTMLButtonElement>('#walk')!;
const walkHint = document.querySelector<HTMLElement>('#walk-hint')!;
const lookupForm = document.querySelector<HTMLFormElement>('#lookup')!;
const lookupQuery = document.querySelector<HTMLInputElement>('#lookup-query')!;
const lookupResults = document.querySelector<HTMLUListElement>('#lookup-results')!;

let viewer: AtlasViewer | null = null;
let overlay: SceneOverlay | null = null;
let walkToken = 0;
const fusion = new Fusion();

function latinOf(id: string): string | undefined {
  return viewer?.catalog.names.label(id, 'la');
}

function endWalk(): void {
  walkButton.dataset.running = 'false';
  walkButton.textContent = 'Walk the marks';
  walkHint.textContent = 'Flies the camera to each mark still on the body.';
}

function refresh(): void {
  if (!overlay) return;
  stage.dataset.tool = overlay.tool;
  document.querySelectorAll<HTMLButtonElement>('[data-tool]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.tool === overlay!.tool));
  });
  document.querySelector<HTMLButtonElement>('#impacts')!.setAttribute('aria-pressed', String(overlay.impacts));
  document.querySelector<HTMLButtonElement>('#cutaway')!.setAttribute('aria-pressed', String(overlay.cutaway));
  const cut = document.querySelector<HTMLElement>('#cut-controls')!;
  cut.hidden = !overlay.cutaway;
  document.querySelectorAll<HTMLButtonElement>('[data-axis]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.axis === overlay!.cutAxis));
  });
  const range = document.querySelector<HTMLInputElement>('#cut-range')!;
  if (document.activeElement !== range) range.value = String(Math.round(overlay.cutT() * 1000));
  document.querySelector<HTMLElement>('#cut-caption')!.textContent = overlay.cutCaption();
  findingsList.querySelectorAll<HTMLButtonElement>('.finding').forEach((button) => {
    button.classList.toggle('is-current', button.dataset.finding === overlay!.activeId);
  });
  if (overlay.activeId && overlay.activeId !== fusion.activeId) {
    fusion.activeId = overlay.activeId;
    fusion.showDesk('region');
    fusion.render(latinOf);
  }
  const pending = overlay.pendingMeasure();
  if (overlay.tool === 'orbit') hud.textContent = pending ?? '';
  else if (!overlay.probeCaption()) hud.textContent = pending ?? toolHint(overlay.tool);
  walkButton.setAttribute('aria-pressed', walkButton.dataset.running === 'true' ? 'true' : 'false');
}

function toolHint(tool: Tool): string {
  if (tool === 'probe') return 'Move over the model. Distance is from the active mark.';
  if (tool === 'measure') return overlay?.pendingMeasure() ?? 'Click two points on the surface.';
  if (tool === 'mark') return 'Click the surface to stick a note there.';
  return '';
}

function choose(finding: Finding, fromWalk = false): void {
  if (!overlay) return;
  if (!fromWalk) {
    walkToken++;
    endWalk();
    fusion.showDesk('region');
  }
  fusion.activeId = finding.id;
  overlay.setActive(finding.id);
  overlay.focusFinding(finding);
  fusion.render(latinOf);
  refresh();
}

async function applyBody(focus: boolean): Promise<void> {
  if (!viewer || !overlay) return;
  const visible = fusion.visible();
  const ids = visible.map((finding) => finding.structureId);
  if (ids.length) await viewer.addStructures(ids, { select: false, focus: false });
  overlay.setFindings(visible);
  if (ids.length) viewer.select(ids, 'replace');
  else viewer.clearSelection();
  viewer.setTransparency(0.78);
  overlay.rebuild();
  const active = fusion.active();
  if (focus && active) {
    overlay.setActive(active.id);
    overlay.focusFinding(active);
  }
  fusion.render(latinOf);
  refresh();
}

async function boot(): Promise<void> {
  stage.dataset.state = 'loading';
  failure.hidden = true;
  loadingText.textContent = 'Opening the films…';
  loadingBar.style.width = '8%';
  viewer?.dispose();
  overlay?.dispose();
  view.replaceChildren();
  labels.replaceChildren();

  try {
    viewer = await createAtlasViewer({
      container: view,
      dataUrl: '/anatomy-data/1.1.0/',
      quality: 'standard',
      lang: 'en',
      background: '#12151c',
      colors: { highlight: '#ffc56a', hover: '#ffe3b0', ghostTint: '#d5dde8' },
    });
  } catch (error) {
    fail(error instanceof Error ? error.message : 'The 3D viewer could not start.');
    return;
  }

  const atlas = viewer;
  overlay = new SceneOverlay(atlas, labels, {
    change: refresh,
    probe: (text) => {
      hud.textContent = text ?? (overlay ? toolHint(overlay.tool) : '');
    },
  });
  atlas.on('progress', (event) => {
    const ratio = event.totalFiles ? event.loadedFiles / event.totalFiles : 0;
    loadingBar.style.width = `${Math.max(8, Math.round(ratio * 100))}%`;
    loadingText.textContent =
      event.phase === 'loading'
        ? `Loading tissue ${event.loadedFiles} of ${event.totalFiles}`
        : event.failedFiles
          ? `${event.failedFiles} files failed`
          : 'Placing the marks…';
  });
  fusion.render(latinOf);
  refresh();

  try {
    const ids = [...new Set([...contextIds, ...fusion.approved.map((finding) => finding.structureId)])];
    const result = await atlas.addStructures(ids, { select: false, focus: false });
    await applyBody(true);
    stage.dataset.state = 'ready';
    if (result.failed.length) hud.textContent = `${result.failed.length} files did not load. The marks that did are on the model.`;
    if (!overlay.pinsReady()) hud.textContent = 'The scene loaded, but a mark could not find its surface.';
  } catch (error) {
    fail(error instanceof Error ? error.message : 'The anatomy files could not be loaded.');
  }
}

function fail(message: string): void {
  stage.dataset.state = 'error';
  failure.hidden = false;
  failureText.textContent = message;
}

async function walk(): Promise<void> {
  if (!overlay) return;
  if (walkButton.dataset.running === 'true') {
    walkToken++;
    endWalk();
    refresh();
    return;
  }
  const token = ++walkToken;
  walkButton.dataset.running = 'true';
  walkButton.textContent = 'Stop the walk';
  for (const finding of fusion.visible()) {
    if (token !== walkToken) return;
    walkHint.textContent = finding.note;
    choose(finding, true);
    await pause(2200);
  }
  if (token === walkToken) endWalk();
}

function pause(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

document.querySelectorAll<HTMLButtonElement>('[data-tool]').forEach((button) => {
  button.addEventListener('click', () => {
    const tool = button.dataset.tool as Tool;
    overlay?.setTool(tool);
    hud.textContent = toolHint(tool);
  });
});

document.querySelector<HTMLButtonElement>('#impacts')!.addEventListener('click', () => {
  if (!overlay) return;
  overlay.setImpacts(!overlay.impacts);
});

document.querySelector<HTMLButtonElement>('#cutaway')!.addEventListener('click', () => {
  if (!overlay) return;
  overlay.setCutaway(!overlay.cutaway);
});

document.querySelectorAll<HTMLButtonElement>('[data-axis]').forEach((button) => {
  button.addEventListener('click', () => overlay?.setCutAxis(button.dataset.axis as CutAxis));
});

document.querySelector<HTMLInputElement>('#cut-range')!.addEventListener('input', (event) => {
  const value = Number((event.target as HTMLInputElement).value);
  overlay?.setCutT(value / 1000);
});

walkButton.addEventListener('click', () => void walk());
document.querySelector<HTMLButtonElement>('#retry')!.addEventListener('click', () => void boot());

lookupQuery.addEventListener('input', () => {
  const query = lookupQuery.value.trim();
  lookupResults.replaceChildren();
  if (!viewer || query.length < 2) {
    lookupResults.hidden = true;
    return;
  }
  const hits = viewer.catalog.search.search(query, { lang: 'en', limit: 6 });
  lookupResults.hidden = hits.length === 0;
  for (const hit of hits) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = viewer.catalog.names.label(hit.id, 'en');
    button.addEventListener('click', () => void reveal(hit.id, button.textContent || hit.id));
    item.append(button);
    lookupResults.append(item);
  }
});

lookupForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const first = lookupResults.querySelector('button');
  first?.click();
});

async function reveal(id: string, title: string): Promise<void> {
  if (!viewer || !overlay) return;
  walkToken++;
  endWalk();
  lookupResults.hidden = true;
  lookupQuery.value = title;
  await viewer.addStructures([id], { select: false, focus: false });
  viewer.focus([id]);
  overlay.addLookup(id, title);
  const keep = [id, ...fusion.visible().map((finding) => finding.structureId)];
  viewer.select(keep, 'replace');
  refresh();
}

window.addEventListener('keydown', (event) => {
  if (event.target instanceof HTMLInputElement || event.metaKey || event.ctrlKey || event.altKey) return;
  const visible = fusion.visible();
  const digit = Number(event.key);
  if (digit >= 1 && digit <= visible.length) {
    const finding = visible[digit - 1];
    if (finding) choose(finding);
    return;
  }
  const key = event.key.toLowerCase();
  if (key === 'escape') overlay?.setTool('orbit');
  if (key === 'p') overlay?.setTool('probe');
  if (key === 'm') overlay?.setTool('measure');
  if (key === 'n') overlay?.setTool('mark');
  if (key === 'o') overlay?.setTool('orbit');
  if (key === 'i') overlay?.setImpacts(!overlay?.impacts);
  if (key === 'c') overlay?.setCutaway(!overlay?.cutaway);
});

fusion.bind({
  onVisible: () => void applyBody(false),
  onFocus: (finding) => choose(finding),
});

void boot();
