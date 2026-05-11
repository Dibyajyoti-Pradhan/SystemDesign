import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { AssistantPanel } from "@/components/AssistantPanel";

export const metadata: Metadata = {
  title: "CareerLab — AI System Design Interview Prep",
  description: "AI voice interviewer + live whiteboard + real-time feedback.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <div className="scr" style={{ minHeight: "100vh" }}>
          <Sidebar />
          <main className="main">{children}</main>
          <AssistantPanel />
        </div>
      </body>
    </html>
  );
}
