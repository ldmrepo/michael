import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

export function requireNodeSqlite(): typeof import("node:sqlite") {
  return require("node:sqlite") as typeof import("node:sqlite");
}
