"use client";

interface ScoreHeatmapProps {
  distribution: Record<string, number>;
  maxGoals?: number;
}

export function ScoreHeatmap({ distribution, maxGoals = 5 }: ScoreHeatmapProps) {
  const max = Math.max(...Object.values(distribution));

  const pct = (p: number) => `${(p * 100).toFixed(1)}%`;
  const opacity = (p: number) => Math.max(0.05, p / max);

  return (
    <div className="overflow-x-auto">
      <table className="text-xs border-collapse w-full">
        <thead>
          <tr>
            <th className="p-1 text-wm-muted text-right pr-2">H↓ A→</th>
            {Array.from({ length: maxGoals + 1 }, (_, j) => (
              <th key={j} className="p-1 text-center text-wm-muted w-12">{j}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: maxGoals + 1 }, (_, i) => (
            <tr key={i}>
              <td className="p-1 text-wm-muted text-right pr-2 font-medium">{i}</td>
              {Array.from({ length: maxGoals + 1 }, (_, j) => {
                const key  = `${i}:${j}`;
                const prob = distribution[key] ?? 0;
                const isWin  = i > j;
                const isDraw = i === j;
                const baseColor = isWin ? "bg-blue-600" : isDraw ? "bg-gray-500" : "bg-red-600";
                return (
                  <td
                    key={j}
                    className={`p-1 text-center rounded transition-all ${baseColor}`}
                    style={{ opacity: opacity(prob) }}
                    title={`${key}: ${pct(prob)}`}
                  >
                    <span className="text-white font-mono">{pct(prob)}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-wm-muted mt-2">
        Blau = Heimsieg · Grau = Unentschieden · Rot = Auswärtssieg. Intensität = Wahrscheinlichkeit.
      </p>
    </div>
  );
}
