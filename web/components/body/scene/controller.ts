import { createAtlasViewer, type AtlasViewer } from "@authorod/svitylo-3d-anatomy-atlas/core";
import { SceneOverlay } from "./overlay";
import { initialSnapshot, type CutAxis, type LookupHit, type SceneFinding, type SceneSnapshot, type Tool } from "./types";

const STAGE = {
  background: "#101a17",
  colors: { highlight: "#6fd6c1", hover: "#bbf2e9", ghostTint: "#d8e4df" },
};

function toolHint(tool: Tool, pending: string | null): string {
  if (tool === "probe") return "Move over the model. Distance is from the active mark.";
  if (tool === "measure") return pending ?? "Click two points on the surface.";
  if (tool === "mark") return "Click the surface to stick a note there.";
  return pending ?? "";
}

/** Owns one atlas viewer and its overlay. React reads it through `onChange` snapshots. */
export class BodyScene {
  private viewer: AtlasViewer | null = null;
  private overlay: SceneOverlay | null = null;
  private findings: SceneFinding[] = [];
  private snapshot: SceneSnapshot = { ...initialSnapshot };
  private probeText: string | null = null;
  private walkToken = 0;
  private disposed = false;
  private onActive: ((id: string) => void) | null = null;

  constructor(
    private readonly container: HTMLElement,
    private readonly labels: HTMLElement,
    private readonly onChange: (snapshot: SceneSnapshot) => void,
  ) {}

  onActiveChange(listener: (id: string) => void): void {
    this.onActive = listener;
  }

  async boot(contextIds: string[], findings: SceneFinding[]): Promise<void> {
    this.findings = findings;
    this.teardown();
    this.patch({ status: "loading", error: null, progress: 0.08, loadingText: "Opening the anatomy" });

    let viewer: AtlasViewer;
    try {
      viewer = await createAtlasViewer({
        container: this.container,
        dataUrl: "/anatomy-data/1.1.0/",
        quality: "standard",
        lang: "en",
        ...STAGE,
      });
    } catch (error) {
      this.fail(error, "The 3D viewer could not start.");
      return;
    }
    if (this.disposed) {
      viewer.dispose();
      return;
    }
    this.viewer = viewer;
    this.overlay = new SceneOverlay(viewer, this.labels, {
      change: () => this.refresh(),
      probe: (text) => {
        this.probeText = text;
        this.refresh();
      },
    });
    viewer.on("progress", (event) => {
      const ratio = event.totalFiles ? event.loadedFiles / event.totalFiles : 0;
      this.patch({
        progress: Math.max(0.08, ratio),
        loadingText:
          event.phase === "loading"
            ? `Loading tissue ${event.loadedFiles} of ${event.totalFiles}`
            : event.failedFiles
              ? `${event.failedFiles} files failed`
              : "Placing the marks",
      });
    });

    try {
      const ids = [...new Set([...contextIds, ...findings.map((f) => f.structureId)])];
      const result = await viewer.addStructures(ids, { select: false, focus: false });
      if (this.disposed) return;
      await this.apply(true);
      let hud = "";
      if (result.failed.length) hud = `${result.failed.length} files did not load. The marks that did are on the model.`;
      if (findings.length && !this.overlay.pinsReady()) hud = "The scene loaded, but a mark could not find its surface.";
      this.patch({ status: "ready", hud });
    } catch (error) {
      this.fail(error, "The anatomy files could not be loaded.");
    }
  }

  async setFindings(findings: SceneFinding[]): Promise<void> {
    this.findings = findings;
    if (this.snapshot.status === "ready") await this.apply(false);
  }

  choose(id: string, fromWalk = false): void {
    const finding = this.findings.find((f) => f.id === id);
    if (!this.overlay || !finding) return;
    if (!fromWalk) this.stopWalk();
    this.overlay.setActive(finding.id);
    this.overlay.focusFinding(finding);
    this.refresh();
  }

  setTool(tool: Tool): void {
    this.probeText = null;
    this.overlay?.setTool(tool);
  }

  toggleImpacts(): void {
    if (this.overlay) this.overlay.setImpacts(!this.overlay.impacts);
  }

  toggleCutaway(): void {
    if (this.overlay) this.overlay.setCutaway(!this.overlay.cutaway);
  }

  setCutAxis(axis: CutAxis): void {
    this.overlay?.setCutAxis(axis);
  }

  setCutT(t: number): void {
    this.overlay?.setCutT(t);
  }

  clearMeasures(): void {
    this.overlay?.clearMeasures();
  }

  clearNotes(): void {
    this.overlay?.clearNotes();
  }

  async walk(): Promise<void> {
    if (!this.overlay) return;
    if (this.snapshot.walking) {
      this.stopWalk();
      return;
    }
    const token = ++this.walkToken;
    this.patch({ walking: true });
    for (const finding of [...this.findings]) {
      if (token !== this.walkToken || this.disposed) return;
      this.choose(finding.id, true);
      await new Promise((resolve) => window.setTimeout(resolve, 2200));
    }
    if (token === this.walkToken) this.stopWalk();
  }

  stopWalk(): void {
    this.walkToken++;
    if (this.snapshot.walking) this.patch({ walking: false });
  }

  search(query: string): LookupHit[] {
    const viewer = this.viewer;
    if (!viewer || query.trim().length < 2) return [];
    return viewer.catalog.search.search(query.trim(), { lang: "en", limit: 6 }).map((hit) => {
      const label = viewer.catalog.names.label(hit.id, "en");
      const latin = viewer.catalog.names.label(hit.id, "la");
      return { id: hit.id, label, latin: latin && latin !== label ? latin : undefined };
    });
  }

  async reveal(hit: LookupHit): Promise<void> {
    const viewer = this.viewer;
    if (!viewer || !this.overlay) return;
    this.stopWalk();
    await viewer.addStructures([hit.id], { select: false, focus: false });
    viewer.focus([hit.id]);
    this.overlay.addLookup(hit.id, hit.label);
    viewer.select([hit.id, ...this.findings.map((f) => f.structureId)], "replace");
    this.refresh();
  }

  clearLookups(): void {
    this.overlay?.clearLookups();
  }

  latin(structureId: string): string | undefined {
    return this.viewer?.catalog.names.label(structureId, "la");
  }

  resetView(): void {
    this.viewer?.setView("anterior");
  }

  dispose(): void {
    this.disposed = true;
    this.walkToken++;
    this.teardown();
  }

  private async apply(focus: boolean): Promise<void> {
    const viewer = this.viewer;
    const overlay = this.overlay;
    if (!viewer || !overlay) return;
    const ids = this.findings.map((f) => f.structureId);
    if (ids.length) await viewer.addStructures(ids, { select: false, focus: false });
    if (this.disposed) return;
    overlay.setFindings(this.findings);
    if (ids.length) viewer.select(ids, "replace");
    else viewer.clearSelection();
    viewer.setTransparency(0.78);
    overlay.rebuild();
    if (focus) viewer.setView("anterior");
    this.refresh();
  }

  private refresh(): void {
    const overlay = this.overlay;
    if (!overlay) return;
    const pending = overlay.pendingMeasure();
    const hud = overlay.tool === "orbit" ? (pending ?? "") : (this.probeText ?? toolHint(overlay.tool, pending));
    const previous = this.snapshot.activeId;
    this.patch({
      tool: overlay.tool,
      impacts: overlay.impacts,
      cutaway: overlay.cutaway,
      cutAxis: overlay.cutAxis,
      cutT: overlay.cutT(),
      cutCaption: overlay.cutCaption(),
      activeId: overlay.activeId,
      measures: overlay.measures.length,
      notes: overlay.notes.length,
      hud,
    });
    if (overlay.activeId && overlay.activeId !== previous) this.onActive?.(overlay.activeId);
  }

  private patch(next: Partial<SceneSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...next };
    if (!this.disposed) this.onChange(this.snapshot);
  }

  private fail(error: unknown, fallback: string): void {
    this.patch({ status: "error", error: error instanceof Error ? error.message : fallback });
  }

  private teardown(): void {
    this.overlay?.dispose();
    this.overlay = null;
    this.viewer?.dispose();
    this.viewer = null;
    this.container.replaceChildren();
    this.labels.replaceChildren();
  }
}
