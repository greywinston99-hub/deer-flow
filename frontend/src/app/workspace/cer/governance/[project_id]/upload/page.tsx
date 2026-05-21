"use client";

import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cerReviewFetch } from "@/core/cer_auth/api";
import { getBackendBaseURL } from "@/core/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type EvidencePackType = "EP-001" | "EP-002" | "EP-003" | "EP-004" | "EP-005";

interface UploadedFile {
  filename: string;
  path: string;
  size_bytes: number;
  converted: boolean;
}

interface UploadResponse {
  project_id: string;
  evidence_pack_type: string;
  uploaded_files: UploadedFile[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EP_TABS: { id: EvidencePackType; label: string; description: string }[] = [
  {
    id: "EP-001",
    label: "EP-001",
    description:
      "Product Definition Pack — Contains intended purpose, device description, claims. Upload CER, IFU, and CEP documents.",
  },
  {
    id: "EP-002",
    label: "EP-002",
    description:
      "SOTA Pack — State of the art literature and clinical evidence. Upload literature search results and clinical evidence.",
  },
  {
    id: "EP-003",
    label: "EP-003",
    description:
      "Equivalence Pack — Predicate device comparison and equivalence evidence. Upload equivalence documentation.",
  },
  {
    id: "EP-004",
    label: "EP-004",
    description:
      "Clinical Evidence Pack — Clinical investigation data, CEP, PMCF, PMS/PSUR. Upload clinical evidence documents.",
  },
  {
    id: "EP-005",
    label: "EP-005",
    description:
      "Risk & Consistency Pack — Risk management file, SSCP, GSPR mapping. Upload risk and consistency documentation.",
  },
];

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

async function uploadEvidencePack(
  projectId: string,
  evidencePackType: EvidencePackType,
  files: File[]
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("evidence_pack_type", evidencePackType);
  for (const file of files) {
    formData.append("files", file);
  }

  const r = await cerReviewFetch(
    `${getBackendBaseURL()}/api/cer-review/${encodeURIComponent(projectId)}/uploads`,
    { method: "POST", body: formData }
  );

  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return r.json() as Promise<UploadResponse>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function UploadPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = decodeURIComponent(String(params.project_id));

  const [activeTab, setActiveTab] = useState<EvidencePackType>("EP-001");
  const [uploading, setUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<Record<EvidencePackType, UploadedFile[]>>({
    "EP-001": [],
    "EP-002": [],
    "EP-003": [],
    "EP-004": [],
    "EP-005": [],
  });
  const [dragOver, setDragOver] = useState(false);

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      if (!files.length) return;

      setUploading(true);
      try {
        const result = await uploadEvidencePack(projectId, activeTab, files);
        setUploadedFiles((prev) => ({
          ...prev,
          [activeTab]: [...(prev[activeTab] || []), ...result.uploaded_files],
        }));
        toast.success(`Uploaded ${result.uploaded_files.length} file(s) to ${activeTab}`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        toast.error(msg);
      } finally {
        setUploading(false);
        // Reset file input
        e.target.value = "";
      }
    },
    [projectId, activeTab]
  );

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const files = Array.from(e.dataTransfer.files);
      if (!files.length) return;

      setUploading(true);
      try {
        const result = await uploadEvidencePack(projectId, activeTab, files);
        setUploadedFiles((prev) => ({
          ...prev,
          [activeTab]: [...(prev[activeTab] || []), ...result.uploaded_files],
        }));
        toast.success(`Uploaded ${result.uploaded_files.length} file(s) to ${activeTab}`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        toast.error(msg);
      } finally {
        setUploading(false);
      }
    },
    [projectId, activeTab]
  );

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const hasAnyFiles = Object.values(uploadedFiles).some((f) => f.length > 0);
  const ep001HasFiles = uploadedFiles["EP-001"].length > 0;

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-80 border-r flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-lg font-semibold">CER Governance</h2>
          </div>
          <p className="text-xs text-muted-foreground">Review Workspace — Governance Data</p>
        </div>
        <div className="p-2 border-b space-y-1">
          <Button variant="ghost" size="sm" className="w-full justify-start text-xs" asChild>
            <a href="/workspace/cer/governance/run-home">🏠 Run Home</a>
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="mb-6">
            <Link
              href={`/workspace/cer/governance/${encodeURIComponent(projectId)}`}
              className="text-sm text-muted-foreground hover:text-foreground mb-2 inline-flex items-center gap-1"
            >
              ← Back to Project
            </Link>
            <h1 className="text-2xl font-bold mb-1">Upload Evidence Packs</h1>
            <p className="text-sm text-muted-foreground">
              Project: <span className="font-mono font-medium">{projectId}</span>
            </p>
          </div>

          {/* EP Tabs */}
          <div className="flex gap-2 mb-4 flex-wrap">
            {EP_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/80"
                }`}
              >
                {tab.label}
                {uploadedFiles[tab.id].length > 0 && (
                  <Badge variant="secondary" className="ml-1.5 text-xs">
                    {uploadedFiles[tab.id].length}
                  </Badge>
                )}
              </button>
            ))}
          </div>

          {/* Active Tab Content */}
          {(() => {
            const tab = EP_TABS.find((t) => t.id === activeTab)!;
            return (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{tab.label}: {tab.label.split(" ")[1]}</CardTitle>
                  <CardDescription>{tab.description}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Dropzone */}
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                      dragOver ? "border-primary bg-primary/5" : "border-muted-foreground/30"
                    }`}
                  >
                    <input
                      type="file"
                      id={`file-input-${activeTab}`}
                      multiple
                      onChange={handleFileChange}
                      accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.md"
                      className="hidden"
                    />
                    <label
                      htmlFor={`file-input-${activeTab}`}
                      className="cursor-pointer flex flex-col items-center gap-2"
                    >
                      <div className="text-4xl">📄</div>
                      <p className="text-sm font-medium">
                        {uploading ? "Uploading..." : "Drop files here or click to upload"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        PDF, Word, Excel, PowerPoint, TXT, MD — up to 50 MB each
                      </p>
                      {uploading && (
                        <div className="mt-2 animate-spin w-5 h-5 border-2 border-primary border-t-transparent rounded-full" />
                      )}
                    </label>
                  </div>

                  {/* Uploaded Files */}
                  {uploadedFiles[activeTab].length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Uploaded Files ({uploadedFiles[activeTab].length})</p>
                      <div className="space-y-1">
                        {uploadedFiles[activeTab].map((file, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between p-2 border rounded text-sm"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-green-600 shrink-0">✓</span>
                              <span className="truncate font-mono text-xs">{file.filename}</span>
                              {file.converted && (
                                <Badge variant="outline" className="text-xs shrink-0">
                                  converted
                                </Badge>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground shrink-0 ml-2">
                              {formatBytes(file.size_bytes)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {uploadedFiles[activeTab].length === 0 && !uploading && (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No files uploaded to {activeTab} yet.
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })()}

          {/* Navigation Buttons */}
          <div className="flex items-center justify-between mt-6 pt-4 border-t">
            <Button
              variant="outline"
              onClick={() => {
                const idx = EP_TABS.findIndex((t) => t.id === activeTab);
                if (idx > 0) setActiveTab(EP_TABS[idx - 1]!.id);
              }}
              disabled={activeTab === "EP-001"}
            >
              ← Prev
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                const idx = EP_TABS.findIndex((t) => t.id === activeTab);
                if (idx < EP_TABS.length - 1) setActiveTab(EP_TABS[idx + 1]!.id);
              }}
              disabled={activeTab === "EP-005"}
            >
              Next →
            </Button>
          </div>

          {/* Summary + Start Run */}
          <div className="mt-6 p-4 border rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Evidence Packs Summary</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {EP_TABS.map((t) => `${t.id}: ${uploadedFiles[t.id].length} file(s)`).join(" · ")}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() =>
                    router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}`)
                  }
                >
                  Back to Project
                </Button>
                <Button
                  onClick={() =>
                    router.push(`/workspace/cer/governance/${encodeURIComponent(projectId)}/upload/start-run`)
                  }
                  disabled={!ep001HasFiles}
                  title={!ep001HasFiles ? "Upload at least EP-001 (Product Definition Pack) to start a run" : ""}
                >
                  Start Run →
                </Button>
              </div>
            </div>
            {!hasAnyFiles && (
              <p className="text-xs text-muted-foreground">
                Upload evidence packs before starting a run. At minimum, EP-001 (Product Definition Pack) is required.
              </p>
            )}
            {hasAnyFiles && !ep001HasFiles && (
              <p className="text-xs text-yellow-600">
                EP-001 is required to start a run. Please upload at least one file to EP-001.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
