import { WorkspaceContainer } from "@/components/workspace/workspace-container";

export default function CERLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <WorkspaceContainer>{children}</WorkspaceContainer>;
}
