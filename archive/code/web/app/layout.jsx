import PlatformShell from "../components/platform-shell";
import "./globals.css";

const themeInitScript = `
(() => {
  try {
    const key = "quant-strategy-lab-theme";
    const stored = window.localStorage.getItem(key);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = stored === "dark" || stored === "light" ? stored : prefersDark ? "dark" : "light";
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
  } catch {
    document.documentElement.style.colorScheme = "light";
  }
})();
`;

export const metadata = {
  title: {
    default: "Quant Strategy Lab",
    template: "%s | Quant Strategy Lab",
  },
  description: "面向个人与小团队的量化策略实验平台，覆盖行情、新闻事件、策略实验室与回测记录。",
  openGraph: {
    title: "Quant Strategy Lab",
    description: "行情、新闻事件、策略实验室与回测记录。",
    type: "website",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className="bg-white text-zinc-950 dark:bg-[#080b10] dark:text-zinc-100" suppressHydrationWarning>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <a
          href="#main-content"
          className="skip-link fixed left-4 top-4 z-50 rounded-full bg-zinc-950 px-4 py-2 text-sm text-white shadow-[0_18px_40px_-18px_rgba(15,23,42,0.45)] dark:bg-white dark:text-zinc-950"
        >
          跳到主要内容
        </a>
        <PlatformShell>{children}</PlatformShell>
      </body>
    </html>
  );
}
