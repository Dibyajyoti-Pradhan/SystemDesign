import { compileMDX } from "next-mdx-remote/rsc";
import remarkGfm from "remark-gfm";
import { Mermaid } from "./Mermaid";

const components = {
  Mermaid,
  pre: (props: React.HTMLAttributes<HTMLPreElement>) => {
    const child = (props.children as any)?.props;
    const className: string = child?.className ?? "";
    const code: string = child?.children ?? "";
    if (className.includes("language-mermaid")) {
      return <Mermaid chart={String(code).trim()} />;
    }
    return <pre {...props} />;
  },
};

export async function MdxRenderer({ source }: { source: string }) {
  try {
    const { content } = await compileMDX({
      source,
      components: components as any,
      options: {
        parseFrontmatter: false,
        mdxOptions: { remarkPlugins: [remarkGfm] },
      },
    });
    return content;
  } catch {
    return (
      <pre style={{ whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--ink-2)", lineHeight: 1.6 }}>
        {source}
      </pre>
    );
  }
}
