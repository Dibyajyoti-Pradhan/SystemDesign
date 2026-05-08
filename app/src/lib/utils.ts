import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function slugify(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function formatDate(date: Date | number | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "number" ? new Date(date * 1000) : date;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function relativeTime(date: Date | null | undefined): string {
  if (!date) return "never";
  const now = Date.now();
  const then = date.getTime();
  const diff = Math.round((then - now) / 1000);
  const abs = Math.abs(diff);
  const fmt = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (abs < 60) return fmt.format(Math.round(diff), "second");
  if (abs < 3600) return fmt.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return fmt.format(Math.round(diff / 3600), "hour");
  if (abs < 86400 * 30) return fmt.format(Math.round(diff / 86400), "day");
  return fmt.format(Math.round(diff / (86400 * 30)), "month");
}
