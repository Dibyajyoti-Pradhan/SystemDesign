import { redirect } from "next/navigation";

// Old route — folded into /questions. Kept as redirect so existing bookmarks
// still land somewhere useful.
export default function OldInterviewIndex() {
  redirect("/questions");
}
