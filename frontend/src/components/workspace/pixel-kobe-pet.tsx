"use client";

import { cn } from "@/lib/utils";

const PALETTE = {
  b: "#b65b22",
  g: "#fdb927",
  h: "#24150f",
  o: "#1b1210",
  p: "#552583",
  s: "#9f6845",
  w: "#f8e7c7",
} as const;

const PIXELS = [
  "..................",
  ".......oooo.......",
  "......ohhhho......",
  ".....ohhhhhho.....",
  ".....oshshso......",
  ".....osssssso.....",
  "......oswso.......",
  ".......oooo.......",
  "......ooppo.......",
  ".....ooppppo......",
  "....oopggppo......",
  "...oopgppgpoo.....",
  "...oopgppgpoo.....",
  "....ooppppo.......",
  ".....ooppo........",
  ".....oossoo.......",
  ".....os..so.......",
  ".....os..so.......",
  "....oos..soo......",
  "...ooos..sooo.....",
  "...obb....bbo.....",
  "..obbb....bbbo....",
  "...ooo....ooo.....",
  "..................",
];

type PixelKobePetProps = React.ComponentProps<"svg"> & {
  title?: string;
};

export function PixelKobePet({
  className,
  title = "Kobe-inspired pixel agent",
  ...props
}: PixelKobePetProps) {
  const width = Math.max(...PIXELS.map((row) => row.length));
  const height = PIXELS.length;

  return (
    <svg
      aria-hidden={title ? undefined : true}
      className={cn("block", className)}
      role={title ? "img" : undefined}
      shapeRendering="crispEdges"
      viewBox={`0 0 ${width} ${height}`}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      {PIXELS.flatMap((row, y) =>
        [...row].map((pixel, x) => {
          if (pixel === ".") {
            return null;
          }

          return (
            <rect
              fill={PALETTE[pixel as keyof typeof PALETTE]}
              height="1"
              key={`${x}-${y}`}
              width="1"
              x={x}
              y={y}
            />
          );
        }),
      )}
    </svg>
  );
}
