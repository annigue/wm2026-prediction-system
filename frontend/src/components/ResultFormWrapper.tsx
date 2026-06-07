"use client";

import { useState } from "react";
import { ResultForm } from "./ResultForm";

interface Props {
  matchId:  string;
  homeName: string;
  awayName: string;
  homeFlag: string;
  awayFlag: string;
}

export function ResultFormWrapper(props: Props) {
  const [saved, setSaved] = useState<{ home: number; away: number } | null>(null);

  if (saved) {
    return (
      <div className="text-sm text-green-400 flex items-center gap-2">
        ✓ Ergebnis gespeichert: {saved.home}:{saved.away} — Elo + Prognosen werden aktualisiert…
        <button
          onClick={() => window.location.reload()}
          className="underline text-xs"
        >
          Seite neu laden
        </button>
      </div>
    );
  }

  return (
    <ResultForm
      {...props}
      onSuccess={(result) => setSaved(result)}
    />
  );
}
