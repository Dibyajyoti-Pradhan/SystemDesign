import { redirect } from "next/navigation";

// Old route — folded into /questions (which now hosts the unified practice
// hub: pick a question, choose Yourself or AI vs AI, see history + delete).
export default function OldAiVsAiIndex() {
  redirect("/questions");
}
