import { CLUBS, type TeamId } from "@/lib/mock";

const STRIP: Record<TeamId, string> = {
  t_home: "border-home",
  t_away: "border-away",
};

/** On-air scorebug. Sized in container units so it scales with the program monitor. */
export function Scorebug({
  score,
  clock,
}: {
  score: Record<TeamId, number>;
  clock: string;
}) {
  return (
    <div className="absolute top-[3.5cqw] left-[3.5cqw] flex h-[4.4cqw] font-broadcast text-[2.6cqw] leading-none font-semibold text-ink uppercase">
      {(["t_home", "t_away"] as const).map((team) => (
        <div key={team} className="flex items-stretch bg-page/95">
          <span
            className={`flex items-center border-b-[0.35cqw] px-[1.3cqw] tracking-wide ${STRIP[team]}`}
          >
            {CLUBS[team].short}
          </span>
          <span className="flex w-[3.8cqw] items-center justify-center bg-panel font-bold tabular-nums">
            {score[team]}
          </span>
        </div>
      ))}
      <span className="flex items-center bg-raised/95 px-[1.3cqw] tabular-nums">
        {clock}
      </span>
    </div>
  );
}
