# Hack Knight Fall 2026 — chart and 3D body

The routing design and the anatomy round are one patient. The web dashboard is the 3D body, a timeline, chat, and an approval queue. Chat can only propose chart changes. The body updates after a doctor approves.

| Path | What it is |
| --- | --- |
| [system-design-routing-2.md](system-design-routing-2.md) | Current routing graph. One chat entry. Snowflake is REST, not MCP. |
| [system-design-routing.md](system-design-routing.md) | Previous routing graph |
| [system-design-graph.md](system-design-graph.md) | Full system graph, including the 3D body and approval queue |
| [patient-round](patient-round/) | The dashboard on the Svitylo atlas |
| [3d-anatomy-atlas](3d-anatomy-atlas/) | The atlas, copied unchanged from [authorOd/3d-anatomy-atlas](https://github.com/authorOd/3d-anatomy-atlas) |

```sh
cd 3d-anatomy-atlas
pnpm install

cd ../patient-round
npm install
npm run dev
```

The dashboard is at http://127.0.0.1:43131/

The atlas’s own demo, from `3d-anatomy-atlas`, is `pnpm demo:dev`.
