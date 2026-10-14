import { useCallback } from "react";
import { ArrowLeft, BrainCircuit, CalendarDays, Clock3, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { Badge, ErrorState, LoadingState, MetricCard, PageHeader } from "../components/ui";

function riyadhDay(value: Date) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Riyadh", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(value);
  const map = Object.fromEntries(parts.map(part => [part.type, part.value])); return `${map.year}-${map.month}-${map.day}`;
}
function displayDate(value: string | null) { return value ? new Intl.DateTimeFormat("ar-SA-u-ca-gregory", { timeZone: "Asia/Riyadh", dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "دون موعد"; }

export default function Overview() {
  const resource = useAsync(useCallback(async () => { const [analytics, tasks, suggestions, health] = await Promise.all([api.analytics(), api.tasks(), api.taskSuggestions(), api.health()]); return { analytics, tasks, suggestions, health }; }, []));
  if (resource.loading) return <LoadingState />;
  if (resource.error || !resource.data) return <ErrorState message={resource.error ?? "لا توجد بيانات"} />;
  const { analytics, tasks, suggestions, health } = resource.data; const todayKey = riyadhDay(new Date());
  const today = tasks.filter(task => task.deadline && riyadhDay(new Date(task.deadline)) === todayKey && !["completed", "canceled"].includes(task.workflow_status));
  const upcoming = tasks.filter(task => task.deadline && riyadhDay(new Date(task.deadline)) > todayKey && !["completed", "canceled"].includes(task.workflow_status));
  const overdue = tasks.filter(task => task.overdue); const recent = [...tasks].sort((a, b) => +new Date(b.updated_at) - +new Date(a.updated_at)).slice(0, 5);
  return <>
    <PageHeader eyebrow="مساحة العمل" title="نظرة عامة على المهام" description="أهم المواعيد والمراجعات والتغييرات الأخيرة، دون إغراق الشاشة بتفاصيل التقييم." action={<div className="flex gap-2"><Link to="/" className="btn-secondary"><CalendarDays size={18} /> التقويم</Link><Link to="/analyzer" className="btn-primary">تحليل رسالة <ArrowLeft size={18} /></Link></div>} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="مهام اليوم" value={today.length} accent="green" /><MetricCard label="قادمة" value={upcoming.length} /><MetricCard label="متأخرة" value={overdue.length} accent="amber" /><MetricCard label="بانتظار المراجعة" value={suggestions.length} accent="amber" /></div>
    <div className="mt-6 grid gap-6 xl:grid-cols-[1.25fr_.75fr]"><section className="panel"><div className="flex items-center justify-between"><h2 className="text-lg font-bold">آخر تحديثات المهام</h2><Link to="/tasks" className="text-sm font-bold text-iris">عرض كل المهام</Link></div><div className="mt-4 divide-y divide-slate-200 dark:divide-slate-800">{recent.map(task => <Link key={task.id} to="/tasks" className="flex items-center justify-between gap-4 py-3"><div><b>{task.title}</b><p className="mt-1 text-xs text-slate-500">{task.last_change_summary || "لا توجد تغييرات لاحقة"}</p></div><span className="whitespace-nowrap text-xs text-slate-500">{displayDate(task.deadline)}</span></Link>)}{recent.length === 0 && <p className="py-8 text-center text-sm text-slate-500">لا توجد مهام محفوظة بعد.</p>}</div></section><section className="panel"><h2 className="text-lg font-bold">اختصارات سريعة</h2><div className="mt-4 grid gap-3"><Link to="/" className="btn-secondary justify-start"><CalendarDays size={18} /> فتح التقويم الذكي</Link><Link to="/tasks" className="btn-secondary justify-start"><Clock3 size={18} /> إدارة المهام والمراجعات</Link><Link to="/conversations" className="btn-secondary justify-start"><ArrowLeft size={18} /> تحليل محادثة</Link></div></section></div>
    <details className="panel mt-6"><summary className="flex cursor-pointer items-center gap-2 font-bold"><BrainCircuit className="text-iris" size={20} /> معلومات النماذج والحدود العلمية</summary><div className="mt-4 flex flex-wrap gap-2"><Badge tone="green">النموذج الافتراضي: {health.models.baseline.identifier}</Badge>{health.models.camelbert.available && <Badge tone="iris">CAMeLBERT مضبوط دقيقًا ومتاح</Badge>}</div><p className="mt-3 text-sm text-slate-500">اختيار CAMeLBERT يتم صراحةً من صفحة التحليل، ولا يحدث استبدال صامت عند فشل التحميل.</p><ul className="mt-4 grid gap-2 text-sm text-slate-600 dark:text-slate-300">{analytics.limitations.map(item => <li key={item} className="rounded-xl bg-slate-100 p-3 dark:bg-slate-900">{item}</li>)}</ul></details>
  </>;
}
