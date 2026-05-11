import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { AssistantPanel } from "@/components/AssistantPanel";
import { DevLoggerInit } from "@/components/DevLoggerInit";

export const metadata: Metadata = {
  title: { default: "CareerLab", template: "%s · CareerLab" },
  description: "AI-powered interview prep — system design, coding, spaced repetition.",
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
        {process.env.NODE_ENV !== "production" && <DevLoggerInit />}
      </body>
    </html>
  );
}
