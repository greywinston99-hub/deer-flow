"use client";

import { useParams } from "next/navigation";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ReportPlaceholderPage() {
  const params = useParams();
  const projectId = decodeURIComponent(String(params.project_id));

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-72 border-r flex flex-col">
        <div className="p-4 border-b">
          <div className="text-xs text-muted-foreground mb-1">
            <Link href="/workspace/cer/governance/run-home" className="hover:underline">
              ← Run Home
            </Link>
          </div>
          <h2 className="text-sm font-semibold font-mono">{projectId}</h2>
          <p className="text-xs text-muted-foreground mt-1">CER Report</p>
        </div>

        {/* Navigation */}
        <div className="p-2 space-y-1 flex-1 overflow-y-auto">
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1">INTAKE</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../intake`}>Intake Status</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../intake/classification`}>Classification</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../intake/human-gate`}>Human Gate</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../intake/locked-pack`}>Locked Pack</Link>
          </Button>
          <div className="text-[10px] font-medium text-muted-foreground mb-1 px-1 mt-3">CER REVIEW</div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../upload`}>Upload Evidence</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../gate-1`}>G1 Route Review</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../gate-3`}>G3 BRR Review</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7" asChild>
            <Link href={`../artifacts`}>Artifacts</Link>
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs h-7 bg-primary/10" asChild>
            <Link href={`./`}>Report</Link>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-xl font-bold">CER Report</h1>
            <p className="text-sm text-muted-foreground">
              Final Clinical Evaluation Report generation
            </p>
          </div>

          {/* Placeholder Card */}
          <Card className="border-dashed border-2">
            <CardContent className="pt-8 pb-8">
              <div className="text-center space-y-4">
                <div className="text-6xl">📝</div>
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold">Report Generation Coming Soon</h2>
                  <p className="text-sm text-muted-foreground max-w-md mx-auto">
                    The final CER document generation capability is not yet implemented. This will
                    produce the formal Clinical Evaluation Report based on completed Gate 1 and Gate
                    3 reviews.
                  </p>
                </div>

                <div className="flex flex-col items-center gap-2 pt-4">
                  <Badge variant="outline" className="px-3 py-1">
                    Phase 2 Feature
                  </Badge>
                  <p className="text-xs text-muted-foreground">
                    Requires Gate 1 and Gate 3 completion
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* What's Needed */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">What&apos;s Needed First</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0 ${
                      true ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {true ? "✓" : "1"}
                  </div>
                  <div>
                    <div className="text-sm font-medium">Complete Intake Process</div>
                    <div className="text-xs text-muted-foreground">
                      Ensure all evidence files are classified and approved
                    </div>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0 ${
                      true ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {true ? "✓" : "2"}
                  </div>
                  <div>
                    <div className="text-sm font-medium">Gate 1 Route Review</div>
                    <div className="text-xs text-muted-foreground">
                      Equivalence route adjudication must be completed
                    </div>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0 ${
                      true ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {true ? "✓" : "3"}
                  </div>
                  <div>
                    <div className="text-sm font-medium">Gate 3 BRR Review</div>
                    <div className="text-xs text-muted-foreground">
                      Benefit-risk assessment must be completed
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Navigation */}
          <div className="flex justify-between">
            <Button variant="outline" asChild>
              <Link href={`../gate-3`}>← Back to Gate 3</Link>
            </Button>
            <Button asChild>
              <Link href={`../artifacts`}>View Artifacts</Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
