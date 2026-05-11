import type { Config } from "drizzle-kit";

const url = process.env.DATABASE_URL ?? "sqlite:./local.db";
const isSqlite = !url || url.startsWith("sqlite:") || url === "FILL_FROM_NEON";

export default {
  schema: "./src/db/schema.ts",
  out: "./.drizzle",
  ...(isSqlite
    ? { dialect: "sqlite", dbCredentials: { url: "./local.db" } }
    : { dialect: "postgresql", dbCredentials: { url } }),
} satisfies Config;
