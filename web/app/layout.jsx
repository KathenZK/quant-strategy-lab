import { Geist, Geist_Mono } from "next/font/google";

import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata = {
  title: {
    default: "Quant Strategy Lab",
    template: "%s | Quant Strategy Lab",
  },
  description: "策略实验、回测分析与运行指纹面板，面向量化研究与策略筛选的 Next.js 前端入口。",
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body className={`${geist.variable} ${geistMono.variable} bg-[#f3f5f1] text-zinc-950`}>
        <a
          href="#main-content"
          className="skip-link fixed left-4 top-4 z-50 rounded-full bg-zinc-950 px-4 py-2 text-sm text-white shadow-[0_18px_40px_-18px_rgba(15,23,42,0.45)]"
        >
          跳到主要内容
        </a>
        {children}
      </body>
    </html>
  );
}
