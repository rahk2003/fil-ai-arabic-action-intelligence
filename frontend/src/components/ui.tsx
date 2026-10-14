import type { ReactNode } from "react";
import { AlertTriangle, Inbox, LoaderCircle } from "lucide-react";

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <header className="mb-7 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
    <div><p className="mb-2 text-xs font-bold uppercase tracking-[.2em] text-iris">{eyebrow}</p><h1 className="text-3xl font-bold tracking-tight md:text-4xl">{title}</h1><p className="mt-2 max-w-3xl text-slate-600 dark:text-slate-400">{description}</p></div>{action}
  </header>;
}
export function MetricCard({ label, value, note, accent = "iris" }: { label: string; value: string | number; note?: string; accent?: "iris" | "green" | "amber" }) {
  const color = accent === "green" ? "bg-emerald-400" : accent === "amber" ? "bg-amber-400" : "bg-iris";
  return <div className="panel relative overflow-hidden"><span className={`absolute inset-y-0 right-0 w-1 ${color}`} /><p className="text-sm text-slate-500 dark:text-slate-400">{label}</p><p className="mt-2 text-3xl font-bold">{value}</p>{note && <p className="mt-2 text-xs text-slate-500">{note}</p>}</div>;
}
export function LoadingState({ label = "جاري تحميل البيانات..." }: { label?: string }) { return <div className="panel flex items-center justify-center gap-3 py-14 text-slate-500"><LoaderCircle className="animate-spin" />{label}</div>; }
export function ErrorState({ message }: { message: string }) { return <div role="alert" className="panel flex items-start gap-3 border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200"><AlertTriangle className="mt-0.5 shrink-0" /><div><p className="font-bold">تعذر إكمال الطلب</p><p className="text-sm">{message}</p></div></div>; }
export function EmptyState({ title, text }: { title: string; text: string }) { return <div className="panel flex flex-col items-center py-14 text-center"><Inbox className="mb-3 h-10 w-10 text-slate-400" /><p className="font-bold">{title}</p><p className="mt-1 text-sm text-slate-500">{text}</p></div>; }
export function Badge({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "green" | "amber" | "rose" | "iris" }) {
  const styles = { slate: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200", green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200", amber: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200", rose: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200", iris: "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200" };
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${styles[tone]}`}>{children}</span>;
}
