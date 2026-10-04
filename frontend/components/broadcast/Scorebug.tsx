import { type Side, club, useMatch } from "@/lib/match";

const STRIP: Record<Side, string> = {
  home: "border-home",
  away: "border-away",
};

/** On-air scorebug. Sized in container units so it scales with the program monitor. */
export function Scorebug({
  score,
  clock,
}: {
  score: Record<Side, number>;
  clock: string;
}) {
  const info = useMatch();
  return (
    <div className="absolute top-[3.5cqw] left-[3.5cqw] flex h-[4.4cqw] font-broadcast text-[2.6cqw] leading-none font-semibold text-ink uppercase">
      {(["home", "away"] as const).map((side) => (
        <div key={side} className="flex items-stretch bg-page/95">
          <span
            className={`flex items-center border-b-[0.35cqw] px-[1.3cqw] tracking-wide ${STRIP[side]}`}
          >
            {club(info, side).short}
          </span>
          <span className="flex w-[3.8cqw] items-center justify-center bg-panel font-bold tabular-nums">
            {score[side]}
          </span>
        </div>
      ))}
      <span className="flex items-center bg-raised/95 px-[1.3cqw] tabular-nums">
        {clock}
      </span>
    </div>
  );
}
