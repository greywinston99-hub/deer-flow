declare module "react-markdown" {
  import type { ComponentType, ReactNode } from "react";
  interface ReactMarkdownProps {
    children?: string;
    remarkPlugins?: unknown[];
    className?: string;
  }
  const ReactMarkdown: ComponentType<ReactMarkdownProps>;
  export default ReactMarkdown;
}
