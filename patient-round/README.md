# Patient round

A fictional trauma round on the [Svitylo 3D Anatomy Atlas](https://github.com/authorOd/3d-anatomy-atlas). Nora Ellison’s injuries are marked on the model. The tools that matter — pins, impact arrows, a surface probe, calipers, stuck notes, and a cutaway plane — live in the 3D scene.

The same screen is the web dashboard from the routing design. The timeline and specialty decide which approved findings stay solid on the body. Chat classifies a request as a chart update, a clinical question, or a screening check, and can only queue a suggestion. Approving a suggestion is what writes the chart and refreshes the model.

This is a teaching toy. It is not a diagnosis, and the atlas models are a preview that has not had a full anatomical review.

## Run

The atlas checkout has to sit next to this folder as `../3d-anatomy-atlas` (it is included in this project). `ATLAS_ROOT` overrides that.

```sh
cd patient-round
npm install
npm run dev
```

Open http://127.0.0.1:43131/

`npm run dev` links the atlas source, its Three.js build, and the 1.1.0 anatomy release into this folder. Those links are local and are not committed.

## In the scene

- **Marks** sit on the surface of each finding. Click one, or press 1–6, to fly there. Critical and watch structures stay solid; the rest of the loaded body is translucent.
- **Impacts** draws the handlebar blow into the sixth left rib and the kerb blow into the left tibia.
- **Probe** follows the surface under the cursor and gives the distance to the active mark.
- **Measure** takes two clicks and leaves the distance, in centimetres, on the model.
- **Mark** sticks a note to the point you click.
- **Cutaway** drops tissue on the far side of a plane. Drag the bright handle in the scene, or use the slider. Marked structures stay.

Look up any other structure by name. It is added to the scene with its own pin.
