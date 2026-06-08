"use client";

import Link from "next/link";

interface Crumb {
  label: string;
  href?: string;
}

interface GovernanceBreadcrumbProps {
  crumbs: Crumb[];
}

export function GovernanceBreadcrumb({ crumbs }: GovernanceBreadcrumbProps) {
  return (
    <nav aria-label="breadcrumb" className="text-xs text-muted-foreground mb-2">
      <ol className="flex items-center gap-1">
        <li>
          {crumbs[0]?.href ? (
            <Link href={crumbs[0].href} className="hover:text-foreground transition-colors">
              {crumbs[0].label}
            </Link>
          ) : (
            <span>{crumbs[0]?.label}</span>
          )}
        </li>
        {crumbs.slice(1).map((crumb, i) => (
          <li key={i} className="flex items-center gap-1">
            <span className="text-muted-foreground">/</span>
            {crumb.href ? (
              <Link href={crumb.href} className="hover:text-foreground transition-colors">
                {crumb.label}
              </Link>
            ) : (
              <span className="text-foreground">{crumb.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
