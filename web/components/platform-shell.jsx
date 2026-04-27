"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChartLineUp,
  Database,
  Flask,
  GearSix,
  House,
  ListChecks,
  MagnifyingGlass,
  NewspaperClipping,
  Pulse,
} from "@phosphor-icons/react";

const navItems = [
  { href: "/", label: "总览", eyebrow: "Desk", icon: House },
  { href: "/markets", label: "行情", eyebrow: "Markets", icon: ChartLineUp },
  { href: "/lab", label: "策略实验室", eyebrow: "Lab", icon: Flask },
  { href: "/backtests", label: "回测记录", eyebrow: "Runs", icon: ListChecks },
  { href: "/news", label: "新闻事件", eyebrow: "Events", icon: NewspaperClipping },
  { href: "/data-sources", label: "数据源", eyebrow: "Sources", icon: Database },
  { href: "/settings", label: "设置", eyebrow: "Config", icon: GearSix },
];

const railEvents = [
  { label: "BTC ETF flow", value: "+$186M", tone: "text-emerald-600" },
  { label: "OKX symbols", value: "182", tone: "text-zinc-950" },
  { label: "News latency", value: "8m", tone: "text-amber-600" },
];

function isActive(pathname, href) {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function PlatformShell({ children }) {
  const pathname = usePathname();

  return (
    <div className="min-h-[100dvh] bg-[#f7f8f4] text-zinc-950">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[252px] border-r border-zinc-200/80 bg-white/92 px-3 py-4 shadow-[22px_0_70px_-55px_rgba(37,61,56,0.3)] backdrop-blur-xl lg:block">
        <Link href="/" className="group flex items-center gap-3 rounded-[1.25rem] border border-zinc-200 bg-zinc-50 px-3 py-3">
          <div className="grid size-10 place-items-center rounded-2xl bg-teal-600 text-white shadow-[0_18px_45px_-24px_rgba(15,118,110,0.65)]">
            <Pulse size={21} weight="fill" />
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-teal-700">Quant Lab</div>
            <div className="mt-0.5 text-sm font-semibold tracking-[-0.02em] text-zinc-950">策略实验平台</div>
          </div>
        </Link>

        <nav className="mt-5 space-y-1.5" aria-label="主导航">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`group flex items-center gap-3 rounded-2xl px-3 py-3 text-sm ${
                  active
                    ? "border border-teal-200 bg-teal-50 text-zinc-950 shadow-[0_18px_40px_-32px_rgba(15,118,110,0.45)]"
                    : "border border-transparent text-zinc-500 hover:border-zinc-200 hover:bg-zinc-50 hover:text-zinc-950"
                }`}
              >
                <Icon size={19} weight={active ? "fill" : "regular"} className={active ? "text-teal-700" : "text-zinc-500 group-hover:text-zinc-700"} />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{item.label}</span>
                  <span className="mt-0.5 block text-[10px] uppercase tracking-[0.18em] text-zinc-500">{item.eyebrow}</span>
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-4 left-3 right-3 rounded-[1.35rem] border border-zinc-200 bg-zinc-50 p-3">
          <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.18em] text-zinc-500">
            <span>Research mode</span>
            <span className="size-2 rounded-full bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.9)]" />
          </div>
          <div className="mt-3 text-sm font-medium text-zinc-950">个人工作台</div>
          <p className="mt-1.5 text-xs leading-5 text-zinc-500">行情偏实时，回测使用可复现数据快照。</p>
        </div>
      </aside>

      <div className="lg:pl-[252px]">
        <header className="sticky top-0 z-20 border-b border-zinc-200/80 bg-white/88 px-4 py-3 backdrop-blur-xl md:px-6">
          <div className="flex items-center gap-3">
            <div className="flex min-w-0 flex-1 items-center gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-zinc-500">
              <MagnifyingGlass size={18} />
              <span className="truncate text-sm">搜索 BTC、OKX、资金费率、策略模板或新闻事件</span>
            </div>
            <div className="hidden items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 md:flex">
              <Pulse size={16} />
              API online
            </div>
          </div>
        </header>

        <div className="grid min-h-[calc(100dvh-65px)] grid-cols-1 2xl:grid-cols-[minmax(0,1fr)_270px]">
          <main id="main-content" className="relative min-w-0 px-4 py-5 md:px-6 md:py-6">
            {children}
          </main>

          <aside className="hidden border-l border-zinc-200/80 bg-white/70 px-4 py-6 2xl:block">
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">情报栏</div>
            <div className="mt-4 space-y-3">
              {railEvents.map((item) => (
                <div key={item.label} className="rounded-2xl border border-zinc-200 bg-white p-3 shadow-[0_18px_50px_-42px_rgba(37,61,56,0.25)]">
                  <div className="text-xs text-zinc-500">{item.label}</div>
                  <div className={`mt-1 font-mono text-lg font-semibold tabular-nums ${item.tone}`}>{item.value}</div>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-2xl border border-zinc-200 bg-white p-3 shadow-[0_18px_50px_-42px_rgba(37,61,56,0.25)]">
              <div className="text-xs font-semibold text-zinc-950">下一步</div>
              <p className="mt-2 text-xs leading-5 text-zinc-500">从行情页选标的，进入策略实验室生成回测任务，再沉淀到回测记录。</p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
