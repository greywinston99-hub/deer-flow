"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCERAuth } from "@/core/cer_auth";
import type { DevRole } from "@/core/cer_auth/api";

// Hydration guard: Radix Select (used by shadcn Select) is client-only
// and causes hydration mismatches if rendered during SSR. Render only after mount.
function useMounted() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);
  return mounted;
}

export function CERDevRoleSwitcher() {
  const { user, devRole, setDevRole, disableDevMode } = useCERAuth();
  const mounted = useMounted();

  const handleRoleChange = useCallback(
    (role: DevRole) => {
      setDevRole(role);
    },
    [setDevRole]
  );

  // Render nothing during SSR to avoid hydration mismatch with Radix Select
  if (!mounted) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
      {/* Dev mode indicator */}
      <div className="bg-muted border border-border rounded px-3 py-2 shadow-sm">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
            CER Dev Role
          </span>
          <Badge variant="outline" className="text-[9px] bg-amber-50 text-amber-700 border-amber-200">
            DEV ONLY
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={devRole || ""}
            onValueChange={(v) => handleRoleChange(v as DevRole)}
          >
            <SelectTrigger className="h-7 w-48 text-xs">
              <SelectValue placeholder="Select role..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="READ_ONLY_VIEWER">READ_ONLY_VIEWER</SelectItem>
              <SelectItem value="REVIEWER">REVIEWER</SelectItem>
              <SelectItem value="SENIOR_REVIEWER">SENIOR_REVIEWER</SelectItem>
              <SelectItem value="ADMIN">ADMIN</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-[10px] text-muted-foreground"
            onClick={disableDevMode}
          >
            Clear
          </Button>
        </div>
        {user && (
          <div className="mt-1 text-[10px] text-muted-foreground">
            Simulating: <span className="font-mono">{user.user_id}</span> ·{" "}
            <Badge variant="outline" className="text-[9px] h-4">{user.role}</Badge>
          </div>
        )}
      </div>
    </div>
  );
}
