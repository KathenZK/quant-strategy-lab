import "./globals.css";

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
      <body>{children}</body>
    </html>
  );
}
