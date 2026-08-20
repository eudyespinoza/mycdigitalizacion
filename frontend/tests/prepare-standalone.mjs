import { cp, mkdir } from "node:fs/promises";
import { join } from "node:path";
import process from "node:process";

const standaloneRoot = join(process.cwd(), ".next", "standalone", "frontend");

// Match the two runtime copies in frontend/Dockerfile before starting server.js.
await mkdir(join(standaloneRoot, ".next"), { recursive: true });
await cp(join(process.cwd(), "public"), join(standaloneRoot, "public"), {
  recursive: true,
  force: true,
});
await cp(join(process.cwd(), ".next", "static"), join(standaloneRoot, ".next", "static"), {
  recursive: true,
  force: true,
});
