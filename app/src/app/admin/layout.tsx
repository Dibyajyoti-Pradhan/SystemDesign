import Link from "next/link";

export const dynamic = "force-dynamic";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <header style={{ borderBottom: "1px solid var(--line)" }}>
        <div style={{ maxWidth: "1120px", margin: "0 auto", padding: "0 24px", height: 44, display: "flex", alignItems: "center", gap: 24 }}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>CareerLab Admin</span>
          <nav style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 13, color: "var(--mute)" }}>
            <Link href="/admin" style={{ color: "inherit", textDecoration: "none" }}>
              Dashboard
            </Link>
            <Link href="/admin/cards" style={{ color: "inherit", textDecoration: "none" }}>
              Cards
            </Link>
          </nav>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
