import { redirect } from "next/navigation";

export const metadata = {
  title: "策略实验室",
  description: "创建策略实验、选择数据源和数据快照，并触发回测任务。",
};

export default function HomePage() {
  redirect("/lab");
}
