"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Database,
  Flask,
  GearSix,
  House,
  ListChecks,
  MagnifyingGlass,
  MoonStars,
  NewspaperClipping,
  Pulse,
  SunDim,
} from "@phosphor-icons/react";

const navItems = [
  { href: "/", label: "总览", eyebrow: "Desk", icon: House },
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

const themeStorageKey = "quant-strategy-lab-theme";

function applyTheme(theme) {
  if (typeof document === "undefined") {
    return;
  }
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
}

function resolveTheme() {
  if (typeof window === "undefined") {
    return "light";
  }
  const storedTheme = window.localStorage.getItem(themeStorageKey);
  if (storedTheme === "dark" || storedTheme === "light") {
    return storedTheme;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function isActive(pathname, href) {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function PlatformShell({ children }) {
  const pathname = usePathname();
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    const resolvedTheme = resolveTheme();
    setTheme(resolvedTheme);
    applyTheme(resolvedTheme);
  }, []);

  function toggleTheme() {
    setTheme((currentTheme) => {
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      window.localStorage.setItem(themeStorageKey, nextTheme);
      applyTheme(nextTheme);
      return nextTheme;
    });
  }

  const isDark = theme === "dark";
  const ThemeIcon = isDark ? SunDim : MoonStars;

  return (
    <div className="min-h-[100dvh] bg-[#f5f6fa] text-zinc-950 dark:bg-[#080b10] dark:text-zinc-100">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[224px] border-r border-zinc-200 bg-white px-3 py-3 dark:border-slate-800 dark:bg-[#0c1118] lg:block">
        <Link href="/" className="group flex items-center gap-3 rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-[#111722]">
          <div className="grid size-9 place-items-center rounded-md bg-[#1f6feb] text-white">
            <Pulse size={21} weight="fill" />
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#1f6feb]">Quant Lab</div>
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
                className={`group flex items-center gap-3 rounded-md px-3 py-2.5 text-sm ${
                  active
                    ? "border border-blue-100 bg-blue-50 text-[#1f6feb] dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-300"
                    : "border border-transparent text-zinc-600 hover:border-zinc-200 hover:bg-zinc-50 hover:text-zinc-950 dark:text-slate-400 dark:hover:border-slate-700 dark:hover:bg-slate-800/60 dark:hover:text-slate-100"
                }`}
              >
                <Icon size={19} weight={active ? "fill" : "regular"} className={active ? "text-[#1f6feb]" : "text-zinc-500 group-hover:text-zinc-700"} />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{item.label}</span>
                  <span className="mt-0.5 block text-[10px] uppercase tracking-[0.14em] text-zinc-400">{item.eyebrow}</span>
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-3 left-3 right-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3">
          <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.14em] text-zinc-500">
            <span>Research mode</span>
            <span className="size-2 rounded-full bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.9)]" />
          </div>
          <div className="mt-3 text-sm font-medium text-zinc-950">个人工作台</div>
          <p className="mt-1.5 text-xs leading-5 text-zinc-500">先聚焦策略实验、新闻事件和回测记录。</p>
        </div>
      </aside>

      <div className="lg:pl-[224px]">
        <header className="sticky top-0 z-20 border-b border-zinc-200 bg-white px-4 py-2.5 dark:border-slate-800 dark:bg-[#0c1118]/95 md:px-5">
          <div className="flex items-center gap-3">
            <div className="flex min-w-0 flex-1 items-center gap-3 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-zinc-500 dark:border-slate-700 dark:bg-[#111722] dark:text-slate-400">
              <MagnifyingGlass size={18} />
              <span className="truncate text-sm">搜索策略模板、回测记录、新闻事件或数据源</span>
            </div>
            <div className="hidden items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 md:flex">
              <Pulse size={16} />
              API online
            </div>
            <button
              type="button"
              onClick={toggleTheme}
              aria-pressed={isDark}
              aria-label={isDark ? "切换为白色模式" : "切换为暗黑模式"}
              className="inline-flex items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 shadow-[0_12px_30px_-24px_rgba(15,23,42,0.45)] hover:border-zinc-300 hover:bg-zinc-50 dark:border-slate-700 dark:bg-[#111722] dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800"
            >
              <ThemeIcon size={16} weight="duotone" />
              <span>{isDark ? "暗黑" : "白色"}</span>
            </button>
          </div>
        </header>

        <div className="grid min-h-[calc(100dvh-65px)] grid-cols-1 2xl:grid-cols-[minmax(0,1fr)_270px]">
          <main id="main-content" className="relative min-w-0 px-4 py-4 md:px-5 md:py-5">
            {children}
          </main>

          <aside className="hidden border-l border-zinc-200/80 bg-white/70 px-4 py-6 2xl:block">
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-500">情报栏</div>
            <div className="mt-4 space-y-3">
              {railEvents.map((item) => (
                <div key={item.label} className="rounded-lg border border-zinc-200 bg-white p-3">
                  <div className="text-xs text-zinc-500">{item.label}</div>
                  <div className={`mt-1 font-mono text-lg font-semibold tabular-nums ${item.tone}`}>{item.value}</div>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-xs font-semibold text-zinc-950">下一步</div>
              <p className="mt-2 text-xs leading-5 text-zinc-500">从策略实验室创建任务，完成后沉淀到回测记录。</p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
