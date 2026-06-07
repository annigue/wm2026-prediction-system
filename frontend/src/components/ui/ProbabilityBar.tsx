"use client";

interface ProbabilityBarProps {
  homeProb: number;
  drawProb: number;
  awayProb: number;
  homeLabel?: string;
  awayLabel?: string;
  showLabels?: boolean;
}

export function ProbabilityBar({
  homeProb,
  drawProb,
  awayProb,
  homeLabel = "Heim",
  awayLabel = "Auswärts",
  showLabels = true,
}: ProbabilityBarProps) {
  const fmt = (n: number) => `${(n * 100).toFixed(0)}%`;

  return (
    <div className="space-y-1">
      {showLabels && (
        <div className="flex justify-between text-xs text-wm-muted">
          <span>{homeLabel}</span>
          <span>Unentschieden</span>
          <span>{awayLabel}</span>
        </div>
      )}
      <div className="flex h-6 rounded-full overflow-hidden gap-px">
        <div
          className="bg-blue-600 flex items-center justify-center text-xs font-semibold text-white transition-all duration-500"
          style={{ width: `${homeProb * 100}%` }}
          title={`${homeLabel}: ${fmt(homeProb)}`}
        >
          {homeProb > 0.12 && fmt(homeProb)}
        </div>
        <div
          className="bg-gray-600 flex items-center justify-center text-xs font-semibold text-white transition-all duration-500"
          style={{ width: `${drawProb * 100}%` }}
          title={`Unentschieden: ${fmt(drawProb)}`}
        >
          {drawProb > 0.12 && fmt(drawProb)}
        </div>
        <div
          className="bg-red-600 flex items-center justify-center text-xs font-semibold text-white transition-all duration-500"
          style={{ width: `${awayProb * 100}%` }}
          title={`${awayLabel}: ${fmt(awayProb)}`}
        >
          {awayProb > 0.12 && fmt(awayProb)}
        </div>
      </div>
      <div className="flex justify-between text-xs font-medium">
        <span className="text-blue-400">{fmt(homeProb)}</span>
        <span className="text-gray-400">{fmt(drawProb)}</span>
        <span className="text-red-400">{fmt(awayProb)}</span>
      </div>
    </div>
  );
}
