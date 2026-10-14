import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, Check, ChevronLeft, ChevronRight, Clock3, History, RotateCcw, Search, X } from "lucide-react";
import { api } from "../lib/api";
import type { CalendarColor, CalendarEvent, CalendarResponse, TaskDetail } from "../types";
import { Badge, ErrorState, LoadingState, PageHeader } from "../components/ui";

type ViewMode = "month" | "week" | "day";
type StatusFilter = "all" | "active" | "completed" | "rescheduled" | "canceled" | "pending_review";

const WEEKDAYS = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
const colorStyles: Record<CalendarColor, string> = {
  red: "border-rose-500 bg-rose-100 text-rose-900 dark:bg-rose-950/50 dark:text-rose-100",
  green: "border-emerald-500 bg-emerald-100 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-100",
  purple: "border-violet-500 bg-violet-100 text-violet-900 dark:bg-violet-950/50 dark:text-violet-100",
  yellow: "border-amber-400 bg-amber-100 text-amber-950 dark:bg-amber-950/50 dark:text-amber-100",
  gray: "border-slate-400 bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
};
const legend: Array<[CalendarColor, string]> = [
  ["red", "موعد قديم"], ["green", "موعد محدّث"], ["purple", "مهمة عادية"],
  ["yellow", "بانتظار التأكيد"], ["gray", "ملغاة"],
];
const statusNames: Record<string, string> = { pending: "قيد الانتظار", in_progress: "قيد التنفيذ", completed: "مكتملة", rescheduled: "أُعيدت جدولتها", canceled: "ملغاة" };
function historyDeadline(value: string | null) { if (!value) return null; try { return (JSON.parse(value) as { deadline?: string }).deadline ?? null; } catch { return null; } }

function riyadhToday() {
  const parts = new Intl.DateTimeFormat("en", { timeZone: "Asia/Riyadh", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts();
  const value = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return new Date(Date.UTC(Number(value.year), Number(value.month) - 1, Number(value.day)));
}
function dayKey(date: Date) { return date.toISOString().slice(0, 10); }
function fromDayKey(value: string) { const [year, month, day] = value.split("-").map(Number); return new Date(Date.UTC(year, month - 1, day)); }
function addDays(date: Date, count: number) { const next = new Date(date); next.setUTCDate(next.getUTCDate() + count); return next; }
function startOfWeek(date: Date) { return addDays(date, -date.getUTCDay()); }
function eventDay(value: string) {
  const parts = new Intl.DateTimeFormat("en", { timeZone: "Asia/Riyadh", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(value));
  const map = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${map.year}-${map.month}-${map.day}`;
}
function arabicDate(value: string | null | undefined, withTime = true) {
  if (!value) return "غير محدد";
  const date = new Date(value); if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ar-SA-u-ca-gregory", { timeZone: "Asia/Riyadh", dateStyle: "medium", ...(withTime ? { timeStyle: "short" } : {}) }).format(date);
}
function monthTitle(date: Date) { return new Intl.DateTimeFormat("ar-SA-u-ca-gregory", { timeZone: "UTC", month: "long", year: "numeric" }).format(date); }
function toRiyadhIso(value: string) { return value ? `${value}:00+03:00` : undefined; }

function bounds(view: ViewMode, cursor: Date) {
  if (view === "day") return [cursor, addDays(cursor, 1)] as const;
  if (view === "week") { const start = startOfWeek(cursor); return [start, addDays(start, 7)] as const; }
  const first = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth(), 1));
  const start = startOfWeek(first);
  return [start, addDays(start, 42)] as const;
}

export default function CalendarPage() {
  const [cursor, setCursor] = useState(riyadhToday);
  const [view, setView] = useState<ViewMode>("month");
  const [historyMode, setHistoryMode] = useState(true);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [data, setData] = useState<CalendarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [rescheduleAt, setRescheduleAt] = useState("");
  const [start, end] = useMemo(() => bounds(view, cursor), [view, cursor]);

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      setData(await api.calendar(`${dayKey(start)}T00:00:00+03:00`, `${dayKey(end)}T00:00:00+03:00`, historyMode));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تحميل التقويم"); }
    finally { setLoading(false); }
  }, [start, end, historyMode]);
  useEffect(() => { void refresh(); }, [refresh]);

  const visibleEvents = useMemo(() => (data?.events ?? []).filter(event => {
    const haystack = `${event.title} ${event.source_message ?? ""}`.toLowerCase();
    const matchesSearch = haystack.includes(search.trim().toLowerCase());
    const matchesStatus = status === "all"
      || (status === "active" && ["pending", "in_progress", "rescheduled"].includes(event.task_status))
      || event.task_status === status;
    return matchesSearch && matchesStatus;
  }), [data, search, status]);
  const byDay = useMemo(() => {
    const result = new Map<string, CalendarEvent[]>();
    visibleEvents.forEach(event => result.set(eventDay(event.starts_at), [...(result.get(eventDay(event.starts_at)) ?? []), event]));
    return result;
  }, [visibleEvents]);

  async function openEvent(event: CalendarEvent) {
    setSelected(event); setDetail(null); setRescheduleAt("");
    if (event.task_id) {
      try {
        const task = await api.task(event.task_id); setDetail(task); setEditTitle(task.title); setEditDescription(task.description ?? "");
      } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تحميل المهمة"); }
    }
  }
  async function openTask(taskId: number) {
    const event: CalendarEvent = { id: `unscheduled-${taskId}`, task_id: taskId, suggestion_id: null, kind: "current", color: "purple", label: "دون موعد", title: "", starts_at: new Date().toISOString(), recorded_at: null, task_status: "pending", is_current: true, source_message: null };
    await openEvent(event);
  }
  async function mutate(eventType: string, extra: Record<string, string | undefined> = {}) {
    if (!detail || !window.confirm("تأكيد حفظ هذا التغيير في قاعدة البيانات؟")) return;
    setActionBusy(true); setError(null);
    try {
      await api.updateTask(detail.id, { event_type: eventType, confirmed: true, ...extra });
      const updated = await api.task(detail.id); setDetail(updated); setEditTitle(updated.title); setEditDescription(updated.description ?? "");
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تحديث المهمة"); }
    finally { setActionBusy(false); }
  }
  async function reviewSuggestion(confirm: boolean) {
    if (!selected?.suggestion_id || !window.confirm(confirm ? "تأكيد تطبيق الاقتراح على قاعدة البيانات؟" : "تأكيد رفض الاقتراح؟")) return;
    setActionBusy(true); setError(null);
    try {
      if (confirm) await api.confirmSuggestion(selected.suggestion_id, { confirmed: true, task_id: selected.task_id ?? undefined, title: selected.title, deadline: selected.starts_at });
      else await api.rejectSuggestion(selected.suggestion_id, { confirmed: true, reason: "رُفض من التقويم" });
      setSelected(null); setDetail(null); await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر مراجعة الاقتراح"); }
    finally { setActionBusy(false); }
  }
  function move(direction: number) {
    setCursor(current => view === "month"
      ? new Date(Date.UTC(current.getUTCFullYear(), current.getUTCMonth() + direction, 1))
      : addDays(current, direction * (view === "week" ? 7 : 1)));
  }

  const days = useMemo(() => Array.from({ length: view === "month" ? 42 : view === "week" ? 7 : 1 }, (_, index) => addDays(start, index)), [view, start]);
  const currentMonth = cursor.getUTCMonth();
  return <>
    <PageHeader eyebrow="Asia/Riyadh" title="التقويم الذكي" description="المواعيد المؤكدة وسجل تغييراتها في تقويم واحد؛ الموعد القديم علامة تاريخية وليس مهمة مكررة." />
    <section className="panel !p-0 overflow-hidden">
      <div className="flex flex-col gap-4 border-b border-slate-200 p-4 dark:border-slate-800 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-secondary !px-3" onClick={() => move(1)} aria-label="التالي"><ChevronRight size={18} /></button>
          <button className="btn-secondary !px-3" onClick={() => move(-1)} aria-label="السابق"><ChevronLeft size={18} /></button>
          <button className="btn-secondary" onClick={() => setCursor(riyadhToday())}>اليوم</button>
          <h2 className="min-w-44 text-xl font-black">{monthTitle(cursor)}</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {(["month", "week", "day"] as ViewMode[]).map(mode => <button key={mode} onClick={() => setView(mode)} className={view === mode ? "btn-primary" : "btn-secondary"}>{mode === "month" ? "شهري" : mode === "week" ? "أسبوعي" : "يومي"}</button>)}
        </div>
      </div>
      <div className="grid gap-3 border-b border-slate-200 p-4 dark:border-slate-800 md:grid-cols-[1fr_auto_auto]">
        <label className="relative"><Search className="absolute right-3 top-3 text-slate-400" size={18} /><input aria-label="البحث في التقويم" className="input pr-10" placeholder="البحث باسم المهمة أو نص الرسالة" value={search} onChange={event => setSearch(event.target.value)} /></label>
        <select aria-label="حالة أحداث التقويم" className="input min-w-44" value={status} onChange={event => setStatus(event.target.value as StatusFilter)}><option value="all">كل المهام</option><option value="active">النشطة</option><option value="completed">المكتملة</option><option value="rescheduled">المعاد جدولتها</option><option value="canceled">الملغاة</option><option value="pending_review">بانتظار التأكيد</option></select>
        <button onClick={() => setHistoryMode(value => !value)} className={historyMode ? "btn-primary" : "btn-secondary"}><History size={17} />{historyMode ? "عرض السجل الكامل" : "الجدول الحالي فقط"}</button>
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-2 px-4 py-3 text-xs text-slate-600 dark:text-slate-300">{legend.map(([color, label]) => <span key={color} className="flex items-center gap-2"><i className={`h-3 w-3 rounded-full border ${colorStyles[color]}`} />{label}</span>)}</div>
      {error && <div className="m-4"><ErrorState message={error} /></div>}
      {loading ? <div className="min-h-[620px] p-8"><LoadingState /></div> : <div className="overflow-x-auto">
        {view !== "day" && <div className="grid min-w-[900px] grid-cols-7 border-t border-slate-200 text-center text-xs font-bold text-slate-500 dark:border-slate-800">{WEEKDAYS.map(day => <div key={day} className="border-l border-slate-200 p-3 last:border-l-0 dark:border-slate-800">{day}</div>)}</div>}
        <div className={view === "day" ? "min-h-[620px] p-5" : "grid min-h-[650px] min-w-[900px] grid-cols-7"}>{days.map(day => {
          const key = dayKey(day); const items = byDay.get(key) ?? [];
          return <section key={key} className={`${view === "day" ? "" : "min-h-32 border-l border-t border-slate-200 p-2 last:border-l-0 dark:border-slate-800"} ${view === "month" && day.getUTCMonth() !== currentMonth ? "bg-slate-50/70 opacity-55 dark:bg-slate-950/40" : ""}`}>
            <button onClick={() => { setCursor(day); setView("day"); }} className={`${dayKey(riyadhToday()) === key ? "bg-iris text-white" : "hover:bg-slate-100 dark:hover:bg-slate-800"} mb-2 inline-flex h-8 min-w-8 items-center justify-center rounded-full px-2 text-sm font-bold`}>{day.getUTCDate()}</button>
            <div className={view === "day" ? "grid gap-3 md:grid-cols-2 xl:grid-cols-3" : "space-y-1.5"}>{items.map(item => <button key={item.id} onClick={() => void openEvent(item)} className={`w-full rounded-lg border-r-4 p-2 text-right text-xs transition hover:-translate-y-0.5 hover:shadow ${colorStyles[item.color]}`}><span className="block truncate font-bold">{item.title}</span><span className="mt-1 flex items-center gap-1 opacity-75"><Clock3 size={11} />{arabicDate(item.starts_at).split("،").at(-1)}</span>{view === "day" && <span className="mt-2 block">{item.label}</span>}</button>)}</div>
            {view === "day" && items.length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 p-12 text-center text-slate-500 dark:border-slate-700">لا توجد مواعيد في هذا اليوم.</div>}
          </section>;
        })}</div>
      </div>}
    </section>

    {!!data && (data.unscheduled_tasks.length > 0 || data.pending_unscheduled.length > 0) && <section className="panel mt-6"><div className="flex items-center gap-2"><CalendarDays className="text-iris" /><h2 className="text-lg font-bold">مهام دون موعد محدد</h2></div><p className="mt-1 text-sm text-slate-500">تظهر هنا بدل إسناد تاريخ غير موجود في الرسالة.</p><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{data.unscheduled_tasks.map(task => <button key={task.id} onClick={() => void openTask(task.id)} className="rounded-xl border border-slate-200 p-4 text-right dark:border-slate-800"><strong>{task.title}</strong><p className="mt-2 line-clamp-2 text-sm text-slate-500">{task.original_message ?? "أُنشئت يدويًا"}</p></button>)}{data.pending_unscheduled.map(item => <article key={item.id} className="rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30"><Badge tone="amber">بانتظار التأكيد</Badge><strong className="mt-2 block">{item.suggested_title}</strong><p className="mt-2 text-sm text-slate-500">{item.evidence}</p></article>)}</div></section>}

    {selected && <div className="fixed inset-0 z-[90] bg-slate-950/60" onClick={() => { setSelected(null); setDetail(null); }}><aside onClick={event => event.stopPropagation()} className="absolute inset-y-0 left-0 w-full max-w-2xl overflow-y-auto bg-white p-6 shadow-2xl dark:bg-slate-950"><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold text-iris">{selected.label}</p><h2 className="mt-1 text-2xl font-black">{detail?.title || selected.title || "تفاصيل المهمة"}</h2></div><button aria-label="إغلاق تفاصيل التقويم" className="rounded-xl border border-slate-200 p-2 dark:border-slate-800" onClick={() => { setSelected(null); setDetail(null); }}><X /></button></div>
      {selected.kind === "pending" ? <div className="mt-6 space-y-4"><div className={`rounded-xl border-r-4 p-4 ${colorStyles.yellow}`}><p className="font-bold">اقتراح لم يُطبّق بعد</p><p className="mt-2 text-sm">{selected.source_message}</p><p className="mt-2 text-sm">الموعد المقترح: {arabicDate(selected.starts_at)}</p></div><div className="flex gap-3"><button disabled={actionBusy} onClick={() => void reviewSuggestion(true)} className="btn-primary"><Check size={17} />تأكيد الاقتراح</button><button disabled={actionBusy} onClick={() => void reviewSuggestion(false)} className="btn-secondary"><X size={17} />رفض</button></div></div> : !detail ? <div className="mt-8"><LoadingState /></div> : <>
        <div className="mt-6 grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-slate-100 p-4 dark:bg-slate-900"><p className="text-xs text-slate-500">الحالة</p><p className="mt-2 font-bold">{statusNames[detail.workflow_status] ?? detail.workflow_status}</p></div><div className="rounded-xl bg-slate-100 p-4 dark:bg-slate-900"><p className="text-xs text-slate-500">الموعد الحالي</p><p className="mt-2 font-bold">{arabicDate(detail.deadline)}</p></div></div>
        <section className="mt-6 rounded-2xl border border-slate-200 p-4 dark:border-slate-800"><h3 className="font-bold">المصدر والمواعيد</h3><p className="mt-3">«{detail.original_message ?? "أُنشئت يدويًا"}»</p><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-slate-500">تاريخ استلام الرسالة</dt><dd>{arabicDate(detail.received_at)}</dd></div><div><dt className="text-slate-500">الموعد الأصلي</dt><dd>{arabicDate(detail.original_deadline)}</dd></div><div><dt className="text-slate-500">الموعد الحالي</dt><dd>{arabicDate(detail.deadline)}</dd></div><div><dt className="text-slate-500">مصدر التحليل</dt><dd>{detail.model_version ?? "يدوي"}</dd></div></dl></section>
        <section className="mt-6"><h3 className="font-bold">إجراءات مؤكدة</h3><div className="mt-3 flex flex-wrap gap-2"><button disabled={actionBusy} className="btn-secondary" onClick={() => void mutate("completed")}>إكمال</button><button disabled={actionBusy} className="btn-secondary" onClick={() => void mutate("canceled")}>إلغاء</button><button disabled={actionBusy} className="btn-secondary" onClick={() => void mutate("reopened")}><RotateCcw size={16} />إعادة فتح</button></div><div className="mt-4 flex flex-col gap-2 sm:flex-row"><input aria-label="موعد إعادة الجدولة" type="datetime-local" className="input" value={rescheduleAt} onChange={event => setRescheduleAt(event.target.value)} /><button disabled={!rescheduleAt || actionBusy} className="btn-primary shrink-0" onClick={() => void mutate("rescheduled", { deadline: toRiyadhIso(rescheduleAt), reason: "إعادة جدولة مؤكدة من التقويم" })}>إعادة الجدولة</button></div></section>
        <section className="mt-6"><h3 className="font-bold">تعديل المهمة</h3><div className="mt-3 space-y-3"><input aria-label="عنوان المهمة في التقويم" className="input" value={editTitle} onChange={event => setEditTitle(event.target.value)} /><textarea aria-label="وصف المهمة في التقويم" className="input min-h-24" value={editDescription} onChange={event => setEditDescription(event.target.value)} /><button disabled={actionBusy || !editTitle.trim()} className="btn-secondary" onClick={() => void mutate("edited", { title: editTitle, description: editDescription, reason: "تعديل مؤكد من التقويم" })}>حفظ التعديل</button></div></section>
        <section className="mt-7"><h3 className="font-bold">السجل الكامل</h3><div className="mt-4 space-y-4">{detail.history.map(event => <article key={event.id} className="border-r-2 border-iris/30 pr-4"><div className="flex items-center justify-between gap-3"><Badge tone="iris">{event.summary ?? event.event_type}</Badge><time className="text-xs text-slate-400">{arabicDate(event.created_at)}</time></div>{event.event_type === "rescheduled" && <p className="mt-2 text-sm">كان الموعد <b>{arabicDate(historyDeadline(event.old_value))}</b>، وأصبح <b>{arabicDate(historyDeadline(event.new_value))}</b>.</p>}{event.related_message && <p className="mt-2 rounded-lg bg-slate-100 p-3 text-sm dark:bg-slate-900">«{event.related_message}»</p>}{event.model_identifier && <details className="mt-2 text-xs text-slate-500"><summary className="cursor-pointer">تفاصيل مصدر التحليل</summary><p className="mt-1" dir="ltr">{event.model_intent} · {event.model_identifier}</p></details>}</article>)}</div></section>
      </>}</aside></div>}
  </>;
}
