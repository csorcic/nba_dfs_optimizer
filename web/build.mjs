// Build the phone app into docs/ for GitHub Pages. No bundler: files are copied as-is.
//   node build.mjs
// docs/data/ (slate files from the pipeline) and docs/SETUP.md are left alone.
import { createHash } from "node:crypto";
import { cpSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = dirname(fileURLToPath(import.meta.url));
const DOCS = join(WEB, "..", "docs");

const copies = [
  // [source, destination in docs/]
  ["app/app.js", "app/app.js"],
  ["app/state.js", "app/state.js"],
  ["app/worker.js", "app/worker.js"],
  ["app/review.js", "app/review.js"],
  ["app/styles.css", "app/styles.css"],
  ...["rules.js", "model.js", "solvers.js", "optimizer.js", "csv.js"].map((f) => [`src/optimizer/${f}`, `app/optimizer/${f}`]),
  ["node_modules/highs/build/highs.mjs", "vendor/highs.mjs"],
  ["node_modules/highs/build/highs.wasm", "vendor/highs.wasm"],
  ["node_modules/javascript-lp-solver/dist/index.browser.mjs", "vendor/lp-solver.mjs"],
  ["app/manifest.webmanifest", "manifest.webmanifest"],
  ["app/icons/icon-192.png", "icons/icon-192.png"],
  ["app/icons/icon-512.png", "icons/icon-512.png"],
  ["app/icons/maskable-512.png", "icons/maskable-512.png"],
];

// Version = hash of everything shipped, so phones pick up each new build.
const hash = createHash("sha256");
for (const [src] of [...copies, ["app/index.html"], ["app/sw.js"]]) hash.update(readFileSync(join(WEB, src)));
const version = hash.digest("hex").slice(0, 10);

for (const dir of ["app", "vendor", "icons"]) rmSync(join(DOCS, dir), { recursive: true, force: true });
const stamp = (text) => text.replaceAll("__VERSION__", version);
for (const [src, dest] of copies) {
  const to = join(DOCS, dest);
  mkdirSync(dirname(to), { recursive: true });
  if (/\.(js|mjs|css|html)$/.test(src) && !src.startsWith("node_modules")) writeFileSync(to, stamp(readFileSync(join(WEB, src), "utf8")));
  else cpSync(join(WEB, src), to);
}
writeFileSync(join(DOCS, "index.html"), stamp(readFileSync(join(WEB, "app/index.html"), "utf8")));
const shell = ["./", "index.html", ...copies.map(([, d]) => d)];
writeFileSync(join(DOCS, "sw.js"), stamp(readFileSync(join(WEB, "app/sw.js"), "utf8")).replace("__SHELL__", JSON.stringify(shell)));
writeFileSync(join(DOCS, ".nojekyll"), "");

const files = readdirSync(DOCS, { recursive: true }).filter((f) => !String(f).startsWith("data"));
console.log(`Built version ${version} into ${relative(process.cwd(), DOCS) || "."} (${files.length} files)`);
