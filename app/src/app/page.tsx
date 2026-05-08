import { redirect } from "next/navigation";

// Default landing — go to System Design. Tracks are first-class destinations
// (System Design / Coding) accessible via the sidebar switcher and at /[track].
export default function Home() {
  redirect("/system-design");
}
