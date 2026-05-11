interface DepthTabsProps {
  tldr: React.ReactNode;
  standard: React.ReactNode;
  deep: React.ReactNode;
  depth?: string;
}

export function DepthTabs({ tldr, standard, deep, depth }: DepthTabsProps) {
  const active = depth === "tldr" ? tldr : depth === "deep" ? deep : standard;
  return <div className="prose-system">{active}</div>;
}
