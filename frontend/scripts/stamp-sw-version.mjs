// Stamps a fresh cache version into the built dist/sw.js so every production
// build gets its own service worker cache name automatically. This runs
// AFTER `vite build` and edits only the *output* file — the source
// public/sw.js keeps the literal "__CACHE_VERSION__" placeholder, so it never
// shows a diff just from rebuilding.
//
// Why this matters: the service worker's activate handler deletes any cache
// whose name doesn't match the current CACHE_NAME. If the cache name never
// changed between deploys, that cleanup would never run and Patti's browser
// could keep re-serving old cached files indefinitely. Stamping a new,
// unique version on every build guarantees the old cache always gets cleaned
// up and the new build's assets always get fetched fresh at least once.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const swPath = join(__dirname, "..", "dist", "sw.js");

const version = new Date().toISOString().replace(/[-:.TZ]/g, "");
const contents = readFileSync(swPath, "utf8");
const stamped = contents.replaceAll("__CACHE_VERSION__", version);

if (stamped === contents) {
  throw new Error(`stamp-sw-version: placeholder __CACHE_VERSION__ not found in ${swPath}`);
}

writeFileSync(swPath, stamped);
console.log(`stamp-sw-version: dist/sw.js cache version set to ${version}`);
