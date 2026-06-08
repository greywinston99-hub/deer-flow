"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Skeleton } from "@/components/ui/skeleton";

export default function ReviewAgentTeamsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/workspace/cer/governance/agent-teams");
  }, [router]);

  return (
    <div className="flex items-center justify-center h-full">
      <div className="space-y-4 text-center">
        <Skeleton className="h-8 w-48 mx-auto" />
        <p className="text-sm text-muted-foreground">跳转至 Agent Teams...</p>
      </div>
    </div>
  );
}
