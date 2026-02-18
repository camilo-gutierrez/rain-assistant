/**
 * Deploy script: copies Next.js static export output to the parent static/ directory
 * so FastAPI can serve it as before.
 *
 * Run after `next build`:
 *   node scripts/deploy.mjs
 */

import { cpSync, rmSync, existsSync, mkdirSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendDir = join(__dirname, "..");
const outDir = join(frontendDir, "out");
const staticDir = join(frontendDir, "..", "static");

if (!existsSync(outDir)) {
  console.error("Error: out/ directory not found. Run 'npm run build' first.");
  process.exit(1);
}

// Backup old static dir if it exists
const backupDir = join(frontendDir, "..", "static_backup");
if (existsSync(staticDir)) {
  if (existsSync(backupDir)) {
    rmSync(backupDir, { recursive: true, force: true });
  }
  cpSync(staticDir, backupDir, { recursive: true });
  console.log("Backed up static/ to static_backup/");
}

// Clean static dir
if (existsSync(staticDir)) {
  rmSync(staticDir, { recursive: true, force: true });
}
mkdirSync(staticDir, { recursive: true });

// Copy build output
cpSync(outDir, staticDir, { recursive: true });
console.log("Copied out/ → static/");

// Ensure sw.js is at the root of static
const swSrc = join(outDir, "sw.js");
const swDst = join(staticDir, "sw.js");
if (existsSync(swSrc) && !existsSync(swDst)) {
  cpSync(swSrc, swDst);
}

// Recreate __init__.py for pip packaging (setuptools needs it)
writeFileSync(
  join(staticDir, "__init__.py"),
  "# This file makes static/ discoverable by setuptools for pip packaging.\n"
);

console.log("Deploy complete! FastAPI will serve the new frontend from static/");
