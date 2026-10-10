// The atlas source imports its own TypeScript files with `.js` specifiers (TypeScript's
// NodeNext convention). Turbopack only maps those back to `.ts` inside this app, so point
// each relative `.js` import at the `.ts` file that actually exists beside it.
const { existsSync } = require("node:fs");
const { dirname, resolve } = require("node:path");

const specifier = /(\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)(['"])(\.{1,2}\/[^'"\n]+?)\.js\2/g;

module.exports = function atlasTsLoader(source) {
  const dir = dirname(this.resourcePath);
  return source.replace(specifier, (match, lead, quote, path) =>
    existsSync(resolve(dir, `${path}.ts`)) ? `${lead}${quote}${path}.ts${quote}` : match,
  );
};
