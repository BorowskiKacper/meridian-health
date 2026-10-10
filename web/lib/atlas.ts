import type { Finding } from "./types";

type Placement = Pick<Finding, "structureId" | "outward" | "view">;

/**
 * Chart regions (body_regions.mesh_name) onto Svitylo atlas structures.
 *
 * The atlas is built from the Z-Anatomy male model, so it has no female
 * reproductive organs and no breast tissue as an organ. Breast and cervix map
 * to the nearest surface region until a second model is available.
 */
const BY_MESH_NAME: Record<string, Placement> = {
  Heart: { structureId: "cardiovascular.heart", outward: [0.35, 0.55, 0.85], view: "anterior" },
  Lung: { structureId: "visceral.left_lung", outward: [1, 0.15, 0.55], view: "left" },
  Colon: { structureId: "visceral.colon", outward: [0.25, -0.35, 0.95], view: "anterior" },
  Pancreas: { structureId: "visceral.pancreas", outward: [0.2, 0.3, 1], view: "anterior" },
  Kidney: { structureId: "visceral.kidney_l", outward: [1, 0.1, -0.4], view: "posterior" },
  Liver: { structureId: "visceral.liver", outward: [-0.65, 0.25, 1], view: "anterior" },
  Thyroid: { structureId: "visceral.thyroid_gland", outward: [0.2, 0.6, 1], view: "anterior" },
  Breast: { structureId: "regions.mammary_region_l", outward: [0.55, 0.35, 1], view: "anterior" },
  Cervix: { structureId: "regions.hypogastric_region_l", outward: [0.2, -0.45, 1], view: "anterior" },
};

export function placeOnAtlas(meshName: string, regionKey: string): Placement {
  return (
    BY_MESH_NAME[meshName] ?? {
      structureId: regionKey,
      outward: [0, 0.2, 1],
      view: "anterior",
    }
  );
}
