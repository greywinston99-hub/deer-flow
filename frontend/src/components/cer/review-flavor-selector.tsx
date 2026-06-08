"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface ReviewFlavorSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

const FLAVORS = [
  { value: "BALANCED", label: "Balanced Baseline" },
  { value: "STRICT", label: "Strict Initial Review" },
  { value: "FAST_GAP_TRIAGE", label: "Fast Gap Triage" },
  { value: "NB_PREFERENCE", label: "NB Preference Candidate" },
];

export function ReviewFlavorSelector({ value, onChange }: ReviewFlavorSelectorProps) {
  return (
    <div className="space-y-1" data-testid="review-flavor-selector">
      <div className="text-xs text-muted-foreground">
        Review Flavor: contextual preference only — not a legal basis.
      </div>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-[260px]">
          <SelectValue placeholder="Select review flavor" />
        </SelectTrigger>
        <SelectContent>
          {FLAVORS.map((f) => (
            <SelectItem key={f.value} value={f.value}>
              {f.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
