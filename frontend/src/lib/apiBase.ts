// Zentrale Backend-URL mit Safety-Net.
// Falls NEXT_PUBLIC_API_URL leer ist ODER noch auf das alte (gelöschte) Backend zeigt,
// wird automatisch das produktive Backend (-phwx) verwendet. So hängt das Frontend nicht
// an einer falsch gesetzten Vercel-Variable.
const PROD = "https://wm2026-backend-phwx.onrender.com";
const RAW = process.env.NEXT_PUBLIC_API_URL ?? "";

export const API_BASE =
  !RAW || RAW.includes("wm2026-backend.onrender.com") ? PROD : RAW;
