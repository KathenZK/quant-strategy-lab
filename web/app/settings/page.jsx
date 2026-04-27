import { signalLabApiBaseUrl } from "../../lib/signal-lab-api";

export const metadata = {
  title: "设置",
  description: "查看本地 API、数据快照和 ToC 演进预留项。",
};

const readinessItems = [
  "用户与权限：第一阶段不启用登录，但页面和 API 命名避免绑定单用户。",
  "额度与配额：策略实验任务已有 job 边界，后续可挂接 quota。",
  "数据授权：行情和新闻都通过后端代理，避免前端直接暴露上游密钥。",
  "多资产模型：crypto、stock、prediction market 统一收敛到 Instrument。",
];

export default function SettingsPage() {
  return (
    <div className="grid gap-5 xl:grid-cols-[420px_1fr]">
      <section className="rounded-[1.75rem] border border-zinc-200 bg-white p-5 shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">Local settings</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-zinc-950">设置</h1>
        <p className="mt-3 text-sm leading-6 text-zinc-600">当前仍是个人/小团队工作台，配置以本地 Signal Lab API 和数据湖为中心。</p>
        <div className="mt-5 rounded-2xl border border-zinc-200 bg-zinc-50 p-4">
          <div className="text-xs text-zinc-500">SIGNAL_LAB_API_BASE_URL</div>
          <div className="mt-2 break-all font-mono text-sm text-zinc-950">{signalLabApiBaseUrl()}</div>
        </div>
      </section>

      <section className="rounded-[1.75rem] border border-zinc-200 bg-white p-5 shadow-[0_24px_80px_-60px_rgba(37,61,56,0.28)]">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">ToC readiness</div>
        <h2 className="mt-2 text-2xl font-semibold text-zinc-950">ToC 演进预留边界</h2>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {readinessItems.map((item) => (
            <div key={item} className="rounded-2xl border border-zinc-200 bg-zinc-50 p-4 text-sm leading-6 text-zinc-600">
              {item}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
