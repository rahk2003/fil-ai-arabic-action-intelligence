import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Activity, BarChart3, Bot, BrainCircuit, CalendarDays, Database, ListTodo, Menu, MessageSquareMore, Moon, SearchX, Sun, UserRoundCheck, X } from "lucide-react";
import { api } from "../lib/api";

const primaryNav = [
  ["/", "التقويم الذكي", CalendarDays], ["/tasks", "إدارة المهام", ListTodo],
  ["/analyzer", "تحليل رسالة", BrainCircuit], ["/conversations", "المحادثات", MessageSquareMore],
] as const;

const advancedNav = [
  ["/evaluation", "تقييم النماذج", BarChart3], ["/dataset", "مستكشف البيانات", Database],
  ["/errors", "تحليل الأخطاء", SearchX], ["/feedback", "التصحيحات البشرية", UserRoundCheck],
] as const;

export default function Layout() {
  const [dark, setDark] = useState(() => localStorage.getItem("fil-ai-theme") !== "light");
  const [open, setOpen] = useState(false);
  const [health, setHealth] = useState<{ status: string; model: string } | null>(null);
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); localStorage.setItem("fil-ai-theme", dark ? "dark" : "light"); }, [dark]);
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
  return <div className="min-h-screen bg-slate-50 dark:bg-ink">
    <button onClick={() => setOpen(true)} aria-label="فتح القائمة" className="fixed right-4 top-4 z-40 rounded-xl bg-slate-900 p-2 text-white lg:hidden"><Menu /></button>
    {open && <button className="fixed inset-0 z-40 bg-black/50 lg:hidden" aria-label="إغلاق القائمة" onClick={() => setOpen(false)} />}
    <aside className={`fixed inset-y-0 right-0 z-50 flex w-72 flex-col border-l border-white/10 bg-[#0b1424] text-white transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "translate-x-full"}`}>
      <div className="flex items-center justify-between border-b border-white/10 p-6"><div><div className="flex items-center gap-2 text-xl font-bold"><Bot className="text-electric" /> FI'L AI <span className="text-electric">فِعل</span></div><p className="mt-1 text-xs text-slate-400">من الرسائل إلى إجراءات مؤكدة</p></div><button onClick={() => setOpen(false)} className="lg:hidden"><X /></button></div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-4">{primaryNav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)} className={({ isActive }) => `flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition ${isActive ? "bg-white/10 text-electric" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}><Icon size={19} />{label}</NavLink>)}<details className="mt-5 border-t border-white/10 pt-4"><summary className="cursor-pointer px-4 py-2 text-xs font-bold text-slate-400">خيارات متقدمة</summary><div className="mt-1 space-y-1">{advancedNav.map(([to, label, Icon]) => <NavLink key={to} to={to} onClick={() => setOpen(false)} className={({ isActive }) => `flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition ${isActive ? "bg-white/10 text-electric" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}><Icon size={18} />{label}</NavLink>)}</div></details></nav>
      <div className="m-4 rounded-2xl border border-white/10 bg-white/5 p-4"><div className="flex items-center gap-2 text-sm"><Activity size={16} className={health ? "text-emerald-400" : "text-rose-400"} />{health ? "الخدمة متصلة" : "الخدمة غير متصلة"}</div><p className="mt-2 text-xs text-slate-400">{health ? "نماذج التحليل المحلية جاهزة" : "تحقق من تشغيل FastAPI"}</p></div>
    </aside>
    <div className="lg:mr-72"><header className="flex h-16 items-center justify-end border-b border-slate-200 bg-white/80 px-6 backdrop-blur dark:border-slate-800 dark:bg-ink/80"><button onClick={() => setDark(!dark)} aria-label="تبديل المظهر" className="rounded-xl border border-slate-200 p-2 dark:border-slate-700">{dark ? <Sun size={19} /> : <Moon size={19} />}</button></header><main className="mx-auto max-w-[1500px] p-5 md:p-8"><Outlet /></main></div>
  </div>;
}
