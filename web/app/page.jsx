import DashboardClient from "../components/dashboard-client";
import { fetchSignalLabJson } from "../lib/signal-lab-api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "策略实验台",
  description: "查看策略排行、实验批次、权益曲线与运行指纹，支持后续扩展为 SEO 友好的公开页面。",
};

export default async function HomePage() {
  let initialRuns = [];
  let initialError = "";

  try {
    const payload = await fetchSignalLabJson("/api/runs");
    initialRuns = payload.runs ?? [];
  } catch (error) {
    initialError = error instanceof Error ? error.message : "Failed to load runs.";
  }

  return <DashboardClient initialRuns={initialRuns} initialError={initialError} />;
}
