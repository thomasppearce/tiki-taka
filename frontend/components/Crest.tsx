import type { ClubRef } from "@/lib/contracts.generated";

/**
 * A fictional club's crest in its own brand color: the one place brand colors appear (data views
 * encode sides by role instead). The initial switches to dark ink on light club colors.
 */
export function Crest({ club, size = 24 }: { club: ClubRef; size?: number }) {
  const light = luminance(club.color) > 0.35;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      role="img"
      aria-label={club.name}
      className="shrink-0"
    >
      <circle cx="12" cy="12" r="11" style={{ fill: club.color }} />
      <circle
        cx="12"
        cy="12"
        r="8.5"
        fill="none"
        className={light ? "stroke-ink-on-fill/30" : "stroke-ink/30"}
        strokeWidth="1"
      />
      <text
        x="12"
        y="12.5"
        textAnchor="middle"
        dominantBaseline="middle"
        className={`font-broadcast text-[11px] font-bold ${light ? "fill-ink-on-fill" : "fill-ink"}`}
      >
        {club.name[0]}
      </text>
    </svg>
  );
}

/** Relative luminance of a #rrggbb color (WCAG). */
function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}
