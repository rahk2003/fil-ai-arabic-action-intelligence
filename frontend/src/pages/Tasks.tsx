import { FormEvent, MouseEvent, useCallback, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDownUp,
  CalendarClock,
  CheckCircle2,
  CirclePlay,
  Eye,
  FileSpreadsheet,
  Inbox,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Upload,
  Download,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import type { Priority, Task, TaskDetail, TaskEvent, TaskImportPreview, TaskSuggestion, WorkflowStatus } from "../types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader } from "../components/ui";

const statusNames: Record<WorkflowStatus, string> = {
  pending: "قيد الانتظار",
  in_progress: "قيد التنفيذ",
  completed: "مكتملة",
  rescheduled: "أُعيدت جدولتها",
  canceled: "ملغاة",
};

const statusTone: Record<WorkflowStatus, "slate" | "iris" | "green" | "amber" | "rose"> = {
  pending: "amber",
  in_progress: "iris",
  completed: "green",
  rescheduled: "slate",
  canceled: "rose",
};

const suggestionNames = {
  new_task: "مهمة جديدة محتملة",
  reschedule: "تغيير موعد محتمل",
  cancellation: "إلغاء محتمل",
};
const priorityNames: Record<Priority, string> = { low: "منخفضة", medium: "متوسطة", high: "عالية", urgent: "عاجلة" };

function displayDate(value: string | null | undefined, withTime = true) {
  if (!value) return "غير محدد";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("ar-SA-u-ca-gregory", {
    dateStyle: "medium",
    ...(withTime ? { timeStyle: "short" as const } : {}),
  }).format(parsed);
}

function eventValues(event: TaskEvent) {
  function parse(value: string | null) {
    if (!value) return {} as Record<string, unknown>;
    try { return JSON.parse(value) as Record<string, unknown>; } catch { return {}; }
  }
  return { before: parse(event.old_value), after: parse(event.new_value) };
}

function stop(event: MouseEvent) { event.stopPropagation(); }

export default function Tasks() {
  const taskLoader = useCallback(() => api.tasks(), []);
  const reviewLoader = useCallback(() => api.taskSuggestions(), []);
  const tasks = useAsync(taskLoader);
  const suggestions = useAsync(reviewLoader);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | WorkflowStatus>("all");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [sort, setSort] = useState<"deadline_asc" | "deadline_desc" | "updated">("deadline_asc");
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importPreview, setImportPreview] = useState<TaskImportPreview | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [targets, setTargets] = useState<Record<number, string>>({});
  const [reviewDeadlines, setReviewDeadlines] = useState<Record<number, string>>({});

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [deadline, setDeadline] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [createStatus, setCreateStatus] = useState<"pending" | "in_progress" | "completed" | "canceled">("pending");
  const [createConfirmed, setCreateConfirmed] = useState(false);

  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editDeadline, setEditDeadline] = useState("");
  const [editPriority, setEditPriority] = useState<Priority>("medium");
  const [editReason, setEditReason] = useState("");
  const [editConfirmed, setEditConfirmed] = useState(false);

  const filteredTasks = useMemo(() => {
    const normalized = search.trim().toLocaleLowerCase("ar");
    return [...(tasks.data ?? [])]
      .filter((task) => statusFilter === "all" || task.workflow_status === statusFilter)
      .filter((task) => !overdueOnly || task.overdue)
      .filter((task) => !normalized || [task.title, task.description, task.original_message, task.source]
        .some((value) => value?.toLocaleLowerCase("ar").includes(normalized)))
      .sort((left, right) => {
        if (sort === "updated") return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
        const leftDate = left.deadline ? new Date(left.deadline).getTime() : Number.POSITIVE_INFINITY;
        const rightDate = right.deadline ? new Date(right.deadline).getTime() : Number.POSITIVE_INFINITY;
        return sort === "deadline_asc" ? leftDate - rightDate : rightDate - leftDate;
      });
  }, [tasks.data, search, statusFilter, overdueOnly, sort]);

  async function refresh() {
    await Promise.all([tasks.run(), suggestions.run()]);
  }

  async function createTask(event: FormEvent) {
    event.preventDefault();
    setLocalError(null);
    try {
      const created = await api.createTask({
        title,
        description: [description, notes ? `ملاحظات: ${notes}` : ""].filter(Boolean).join("\n") || undefined,
        deadline: deadline || undefined,
        priority,
        confirmed: createConfirmed,
      });
      if (createStatus !== "pending") await api.updateTask(created.id, { event_type: createStatus === "in_progress" ? "started" : createStatus === "completed" ? "completed" : "canceled", evidence: "الحالة المختارة عند الإنشاء اليدوي", confirmed: true });
      setTitle(""); setDescription(""); setNotes(""); setDeadline(""); setCreateStatus("pending"); setCreateConfirmed(false); setShowCreate(false);
      await refresh();
    } catch (reason) {
      setLocalError(reason instanceof Error ? reason.message : "تعذر إنشاء المهمة");
    }
  }

  async function previewImport(file: File | undefined) {
    if (!file) return;
    setLocalError(null); setImportResult(null); setImportBusy(true);
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error("الحد الأقصى لحجم الملف هو 2 MB.");
      if (!/\.(csv|xlsx)$/i.test(file.name)) throw new Error("نوع الملف غير مدعوم. استخدم CSV أو XLSX.");
      const content = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error("تعذر قراءة الملف")); reader.onload = () => resolve(String(reader.result).split(",")[1] ?? ""); reader.readAsDataURL(file); });
      setImportPreview(await api.previewTaskImport(file.name, content));
    } catch (reason) { setLocalError(reason instanceof Error ? reason.message : "تعذر معاينة الملف"); }
    finally { setImportBusy(false); }
  }

  async function commitImport() {
    if (!importPreview || !window.confirm("تأكيد استيراد الصفوف الصالحة الظاهرة في المعاينة؟")) return;
    setImportBusy(true); setLocalError(null);
    try {
      const result = await api.commitTaskImport(importPreview.rows.filter(row => row.valid));
      setImportResult(`تم استيراد ${result.imported}، وتخطي ${result.skipped}، وفشل ${result.failed}.`);
      await refresh();
    } catch (reason) { setLocalError(reason instanceof Error ? reason.message : "تعذر استيراد المهام"); }
    finally { setImportBusy(false); }
  }

  async function downloadTemplate(format: "csv" | "xlsx") {
    try {
      const template = await api.taskImportTemplate(format);
      const bytes = Uint8Array.from(atob(template.content_base64), character => character.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: format === "csv" ? "text/csv;charset=utf-8" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = template.filename; anchor.click(); URL.revokeObjectURL(url);
    } catch (reason) { setLocalError(reason instanceof Error ? reason.message : "تعذر تنزيل القالب"); }
  }

  async function openDetail(task: Task) {
    setDetailLoading(true); setLocalError(null);
    try { setDetail(await api.task(task.id)); }
    catch (reason) { setLocalError(reason instanceof Error ? reason.message : "تعذر جلب تفاصيل المهمة"); }
    finally { setDetailLoading(false); }
  }

  async function taskAction(task: Task, eventType: "started" | "completed" | "canceled" | "reopened") {
    const labels = { started: "بدء تنفيذ المهمة", completed: "إكمال المهمة", canceled: "إلغاء المهمة", reopened: "إعادة فتح المهمة" };
    if (!window.confirm(`هل تؤكد ${labels[eventType]} وحفظه في السجل؟`)) return;
    setLocalError(null);
    try {
      await api.updateTask(task.id, { event_type: eventType, confirmed: true });
      await refresh();
      if (detail?.id === task.id) setDetail(await api.task(task.id));
    } catch (reason) {
      setLocalError(reason instanceof Error ? reason.message : "تعذر تحديث المهمة");
    }
  }

  function beginEdit(task: Task) {
    setEditing(task);
    setEditTitle(task.title);
    setEditDescription(task.description ?? "");
    setEditDeadline(task.deadline ?? "");
    setEditPriority(task.priority);
    setEditReason("");
    setEditConfirmed(false);
  }

  async function saveEdit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const deadlineChanged = editDeadline !== (editing.deadline ?? "");
    setLocalError(null);
    try {
      await api.updateTask(editing.id, {
        event_type: deadlineChanged ? "rescheduled" : "edited",
        title: editTitle,
        description: editDescription,
        deadline: editDeadline || undefined,
        priority: editPriority,
        reason: editReason || undefined,
        evidence: "تعديل مؤكد من لوحة إدارة المهام",
        confirmed: editConfirmed,
      });
      setEditing(null);
      await refresh();
      if (detail?.id === editing.id) setDetail(await api.task(editing.id));
    } catch (reason) {
      setLocalError(reason instanceof Error ? reason.message : "تعذر حفظ التعديل");
    }
  }

  async function confirmSuggestion(suggestion: TaskSuggestion) {
    const target = targets[suggestion.id] || (suggestion.task_id ? String(suggestion.task_id) : "");
    if (suggestion.suggestion_type !== "new_task" && !target) {
      setLocalError("يجب اختيار المهمة المرتبطة قبل تأكيد التغيير.");
      return;
    }
    if (!window.confirm("تأكيد تطبيق الاقتراح بعد مراجعته؟")) return;
    setLocalError(null);
    try {
      await api.confirmSuggestion(suggestion.id, {
        confirmed: true,
        task_id: target ? Number(target) : undefined,
        title: suggestion.suggested_title ?? undefined,
        description: suggestion.description ?? undefined,
        deadline: reviewDeadlines[suggestion.id] || suggestion.proposed_deadline || undefined,
        reason: suggestion.reason ?? undefined,
      });
      await refresh();
    } catch (reason) {
      setLocalError(reason instanceof Error ? reason.message : "تعذر تطبيق الاقتراح");
    }
  }

  async function rejectSuggestion(suggestion: TaskSuggestion) {
    if (!window.confirm("تأكيد رفض هذا الاقتراح؟ لن تُعدّل أي مهمة.")) return;
    try {
      await api.rejectSuggestion(suggestion.id, { confirmed: true, reason: "رفضه المستخدم بعد المراجعة" });
      await suggestions.run();
    } catch (reason) {
      setLocalError(reason instanceof Error ? reason.message : "تعذر رفض الاقتراح");
    }
  }

  const data = tasks.data ?? [];
  const pendingReviews = suggestions.data ?? [];
  const activeCount = data.filter((task) => ["pending", "in_progress", "rescheduled"].includes(task.workflow_status)).length;

  return (
    <>
      <PageHeader
        eyebrow="Task workspace"
        title="لوحة إدارة المهام"
        description="مراجعة المهام ومواعيدها ومصادرها وكل تغيير مؤكد في مكان واحد. لا يطبّق الذكاء الاصطناعي أي اقتراح دون موافقة صريحة."
        action={<div className="flex flex-wrap gap-2"><button onClick={() => refresh()} className="btn-secondary"><RefreshCw size={17} /> تحديث</button><button onClick={() => setShowImport(true)} className="btn-secondary"><FileSpreadsheet size={17} /> استيراد ملف</button><button onClick={() => setShowCreate(true)} className="btn-primary"><Plus size={17} /> إضافة مهمة</button></div>}
      />

      {(tasks.error || suggestions.error || localError) && <div className="mb-5"><ErrorState message={localError ?? tasks.error ?? suggestions.error ?? "خطأ غير معروف"} /></div>}

      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="panel !p-4"><p className="text-xs text-slate-500">كل المهام</p><p className="mt-1 text-2xl font-bold">{data.length}</p></div>
        <div className="panel !p-4"><p className="text-xs text-slate-500">مهام نشطة</p><p className="mt-1 text-2xl font-bold text-iris">{activeCount}</p></div>
        <div className="panel !p-4"><p className="text-xs text-slate-500">متأخرة</p><p className="mt-1 text-2xl font-bold text-rose-600">{data.filter((task) => task.overdue).length}</p></div>
        <div className="panel !p-4"><p className="text-xs text-slate-500">بانتظار المراجعة</p><p className="mt-1 text-2xl font-bold text-amber-600">{pendingReviews.length}</p></div>
      </div>

      <section className="panel mb-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><div className="flex items-center gap-2"><Inbox className="text-amber-500" /><h2 className="text-lg font-bold">بانتظار المراجعة</h2></div><p className="mt-1 text-sm text-slate-500">اقتراحات مستخرجة من الرسائل ولم تُحفظ كمهام أو تغييرات بعد.</p></div>
          <Badge tone={pendingReviews.length ? "amber" : "green"}>{pendingReviews.length} اقتراح</Badge>
        </div>
        {suggestions.loading ? <div className="mt-5"><LoadingState /></div> : pendingReviews.length === 0 ? <div className="mt-5 rounded-xl border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500 dark:border-slate-700">لا توجد اقتراحات معلّقة.</div> : (
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            {pendingReviews.map((suggestion) => (
              <article key={suggestion.id} className="rounded-2xl border border-amber-200 bg-amber-50/50 p-4 dark:border-amber-900 dark:bg-amber-950/10">
                <div className="flex flex-wrap items-center justify-between gap-2"><Badge tone={suggestion.suggestion_type === "cancellation" ? "rose" : "amber"}>{suggestionNames[suggestion.suggestion_type]}</Badge><span className="text-xs text-slate-500">{displayDate(suggestion.created_at)}</span></div>
                <h3 className="mt-3 font-bold">{suggestion.suggested_title ?? "اقتراح من رسالة"}</h3>
                <p className="mt-2 rounded-xl bg-white/80 p-3 text-sm dark:bg-slate-900/70">«{suggestion.evidence}»</p>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{suggestion.reason}</p>
                {suggestion.suggestion_type !== "new_task" && (
                  <label className="label mt-4">المهمة المرتبطة<select className="input mt-1" value={targets[suggestion.id] ?? suggestion.task_id ?? ""} onChange={(event) => setTargets({ ...targets, [suggestion.id]: event.target.value })}><option value="">اختيار مهمة</option>{data.filter((task) => !["completed", "canceled"].includes(task.workflow_status)).map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select></label>
                )}
                {(suggestion.suggestion_type === "new_task" || suggestion.suggestion_type === "reschedule") && (
                  <label className="label mt-3">الموعد المقترح<input className="input mt-1" value={reviewDeadlines[suggestion.id] ?? suggestion.proposed_deadline ?? ""} onChange={(event) => setReviewDeadlines({ ...reviewDeadlines, [suggestion.id]: event.target.value })} placeholder="يُترك فارغًا إذا لم يرد موعد واضح" /></label>
                )}
                <div className="mt-4 flex gap-2"><button onClick={() => confirmSuggestion(suggestion)} className="btn-primary !py-2"><ShieldCheck size={16} /> تأكيد</button><button onClick={() => rejectSuggestion(suggestion)} className="btn-secondary !py-2"><X size={16} /> رفض</button></div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="panel !p-0 overflow-hidden">
        <div className="border-b border-slate-200 p-5 dark:border-slate-800">
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-64 flex-1"><span className="label">بحث</span><span className="relative block"><Search className="absolute right-3 top-3.5 text-slate-400" size={18} /><input aria-label="بحث في المهام" className="input pr-10" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="اسم المهمة أو الرسالة أو المصدر" /></span></label>
            <label><span className="label">الحالة</span><select aria-label="تصفية حسب الحالة" className="input min-w-44" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | WorkflowStatus)}><option value="all">كل الحالات</option>{Object.entries(statusNames).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></label>
            <label><span className="label">الترتيب</span><select aria-label="ترتيب المهام" className="input min-w-48" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="deadline_asc">الأقرب موعدًا</option><option value="deadline_desc">الأبعد موعدًا</option><option value="updated">آخر تحديث</option></select></label>
            <label className="flex h-12 items-center gap-2 rounded-xl border border-slate-300 px-4 text-sm dark:border-slate-700"><input type="checkbox" checked={overdueOnly} onChange={(event) => setOverdueOnly(event.target.checked)} /> المتأخرة فقط</label>
          </div>
        </div>

        {tasks.loading ? <div className="p-8"><LoadingState /></div> : filteredTasks.length === 0 ? <div className="p-8"><EmptyState title="لا توجد مهام مطابقة" text="يمكن تعديل البحث أو المرشحات، أو إنشاء مهمة بعد مراجعة الرسالة." /></div> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1350px] text-right text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-950/60"><tr><th className="p-4">المهمة</th><th className="p-4">الرسالة الأصلية / المصدر</th><th className="p-4">تاريخ الاستلام</th><th className="p-4">الموعد الأصلي</th><th className="p-4"><span className="flex items-center gap-1">الموعد الحالي <ArrowDownUp size={13} /></span></th><th className="p-4">الحالة</th><th className="p-4">آخر تغيير</th><th className="p-4">الإجراءات</th></tr></thead>
              <tbody>{filteredTasks.map((task) => (
                <tr key={task.id} onClick={() => openDetail(task)} className="cursor-pointer border-t border-slate-200 align-top transition hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/40">
                  <td className="p-4"><div className="flex items-start gap-2">{task.overdue && <AlertTriangle className="mt-0.5 shrink-0 text-rose-500" size={17} />}<div><p className="font-bold text-slate-900 dark:text-white">{task.title}</p><p className="mt-1 max-w-56 line-clamp-2 text-xs text-slate-500">{task.description || "بدون وصف إضافي"}</p></div></div></td>
                  <td className="p-4"><p className="max-w-64 line-clamp-2">{task.original_message || "أُنشئت يدويًا"}</p><p className="mt-1 text-xs text-slate-400">{task.source || "manual"}</p></td>
                  <td className="p-4 whitespace-nowrap">{displayDate(task.received_at)}</td>
                  <td className="p-4 whitespace-nowrap">{displayDate(task.original_deadline)}</td>
                  <td className={`p-4 whitespace-nowrap font-semibold ${task.overdue ? "text-rose-600" : ""}`}>{displayDate(task.deadline)}{task.overdue && <p className="mt-1 text-xs">متأخرة</p>}</td>
                  <td className="p-4"><Badge tone={statusTone[task.workflow_status]}>{statusNames[task.workflow_status]}</Badge></td>
                  <td className="p-4"><p className="max-w-60 line-clamp-3 text-xs leading-5 text-slate-600 dark:text-slate-300">{task.last_change_summary || "لا توجد تغييرات"}</p></td>
                  <td className="p-4" onClick={stop}><div className="flex min-w-64 flex-wrap gap-2"><button onClick={() => openDetail(task)} className="btn-secondary !px-3 !py-2"><Eye size={15} /> التفاصيل</button>{!["completed", "canceled"].includes(task.workflow_status) && <><button onClick={() => beginEdit(task)} className="btn-secondary !px-3 !py-2"><Pencil size={15} /> تعديل</button>{task.workflow_status !== "in_progress" && <button onClick={() => taskAction(task, "started")} className="btn-secondary !px-3 !py-2"><CirclePlay size={15} /> بدء</button>}<button onClick={() => taskAction(task, "completed")} className="btn-secondary !px-3 !py-2 text-emerald-600"><CheckCircle2 size={15} /> إكمال</button><button onClick={() => taskAction(task, "canceled")} className="btn-secondary !px-3 !py-2 text-rose-600"><Trash2 size={15} /> إلغاء</button></>}{["completed", "canceled"].includes(task.workflow_status) && <button onClick={() => taskAction(task, "reopened")} className="btn-secondary !px-3 !py-2">إعادة فتح</button>}</div></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>

      {showImport && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/60 p-4" onClick={() => setShowImport(false)}><section onClick={(event) => event.stopPropagation()} className="panel max-h-[92vh] w-full max-w-5xl overflow-y-auto"><div className="flex items-center justify-between"><div><p className="text-xs text-slate-500">CSV / XLSX · حد أقصى 2 MB و500 صف</p><h2 className="text-xl font-bold">استيراد المهام مع المعاينة</h2></div><button type="button" onClick={() => setShowImport(false)} aria-label="إغلاق"><X /></button></div><div className="mt-5 flex flex-wrap gap-2"><button onClick={() => void downloadTemplate("csv")} className="btn-secondary !py-2"><Download size={16} /> قالب CSV</button><button onClick={() => void downloadTemplate("xlsx")} className="btn-secondary !py-2"><Download size={16} /> قالب Excel</button><label className="btn-primary cursor-pointer !py-2"><Upload size={16} /> اختيار ملف<input aria-label="ملف استيراد المهام" className="hidden" type="file" accept=".csv,.xlsx" onChange={event => void previewImport(event.target.files?.[0])} /></label></div>{importBusy && <p className="mt-4 text-sm text-slate-500">جاري فحص الملف...</p>}{importResult && <p className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200">{importResult}</p>}{importPreview && <><div className="mt-5 grid gap-3 sm:grid-cols-4"><div className="rounded-xl bg-slate-100 p-3 dark:bg-slate-900"><span className="text-xs text-slate-500">كل الصفوف</span><b className="mt-1 block text-xl">{importPreview.summary.total}</b></div><div className="rounded-xl bg-emerald-50 p-3 dark:bg-emerald-950/30"><span className="text-xs text-slate-500">صالحة</span><b className="mt-1 block text-xl text-emerald-600">{importPreview.summary.valid}</b></div><div className="rounded-xl bg-amber-50 p-3 dark:bg-amber-950/30"><span className="text-xs text-slate-500">مكررة</span><b className="mt-1 block text-xl text-amber-600">{importPreview.summary.duplicates}</b></div><div className="rounded-xl bg-rose-50 p-3 dark:bg-rose-950/30"><span className="text-xs text-slate-500">غير صالحة</span><b className="mt-1 block text-xl text-rose-600">{importPreview.summary.invalid}</b></div></div><div className="mt-5 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800"><table className="w-full min-w-[850px] text-right text-sm"><thead className="bg-slate-50 dark:bg-slate-900"><tr><th className="p-3">الصف</th><th>المهمة</th><th>الموعد</th><th>الأولوية</th><th>الحالة</th><th>نتيجة الفحص</th></tr></thead><tbody>{importPreview.rows.map(row => <tr key={row.row_number} className="border-t border-slate-200 dark:border-slate-800"><td className="p-3">{row.row_number}</td><td>{row.title || "—"}</td><td dir="ltr">{row.deadline || "—"}</td><td>{priorityNames[row.priority]}</td><td>{statusNames[row.status]}</td><td>{row.valid ? <Badge tone="green">صالح</Badge> : <span className="text-rose-600">{row.errors.join("، ")}</span>}</td></tr>)}</tbody></table></div><button onClick={() => void commitImport()} disabled={importBusy || importPreview.summary.valid === 0} className="btn-primary mt-5 w-full"><ShieldCheck size={17} /> تأكيد استيراد {importPreview.summary.valid} صف</button></>}</section></div>}

      {showCreate && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/60 p-4" onClick={() => setShowCreate(false)}><form onSubmit={createTask} onClick={(event) => event.stopPropagation()} className="panel max-h-[92vh] w-full max-w-xl overflow-y-auto"><div className="flex items-center justify-between"><h2 className="text-xl font-bold">إنشاء مهمة يدوية</h2><button type="button" onClick={() => setShowCreate(false)} aria-label="إغلاق"><X /></button></div><label className="label mt-5">اسم المهمة<input className="input mt-1" value={title} onChange={(event) => setTitle(event.target.value)} required /></label><label className="label mt-4">وصف مختصر<textarea className="input mt-1 min-h-20" value={description} onChange={(event) => setDescription(event.target.value)} /></label><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="label">الموعد الميلادي — اختياري<input type="datetime-local" className="input mt-1" value={deadline} onChange={(event) => setDeadline(event.target.value)} /></label><label className="label">الأولوية<select className="input mt-1" value={priority} onChange={(event) => setPriority(event.target.value as Priority)}><option value="low">منخفضة</option><option value="medium">متوسطة</option><option value="high">عالية</option><option value="urgent">عاجلة</option></select></label><label className="label">الحالة<select className="input mt-1" value={createStatus} onChange={(event) => setCreateStatus(event.target.value as typeof createStatus)}><option value="pending">قيد الانتظار</option><option value="in_progress">قيد التنفيذ</option><option value="completed">مكتملة</option><option value="canceled">ملغاة</option></select></label><label className="label sm:col-span-2">ملاحظات<textarea className="input mt-1 min-h-16" value={notes} onChange={(event) => setNotes(event.target.value)} /></label></div><label className="mt-5 flex gap-3 rounded-xl bg-slate-100 p-3 text-sm dark:bg-slate-800"><input type="checkbox" checked={createConfirmed} onChange={(event) => setCreateConfirmed(event.target.checked)} /><span>تمت مراجعة البيانات، وتأكيد إنشاء المهمة.</span></label><button className="btn-primary mt-5 w-full"><Plus size={17} /> إنشاء المهمة</button></form></div>}

      {editing && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/60 p-4" onClick={() => setEditing(null)}><form onSubmit={saveEdit} onClick={(event) => event.stopPropagation()} className="panel max-h-[92vh] w-full max-w-2xl overflow-y-auto"><div className="flex items-center justify-between"><div><p className="text-xs text-slate-500">تعديل المهمة #{editing.id}</p><h2 className="text-xl font-bold">مراجعة التغيير قبل الحفظ</h2></div><button type="button" onClick={() => setEditing(null)} aria-label="إغلاق"><X /></button></div><div className="mt-5 grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-rose-50 p-4 dark:bg-rose-950/20"><p className="text-xs font-bold text-rose-600">قبل</p><p className="mt-2 font-semibold">{editing.title}</p><p className="mt-1 text-sm">{displayDate(editing.deadline)}</p></div><div className="rounded-xl bg-emerald-50 p-4 dark:bg-emerald-950/20"><p className="text-xs font-bold text-emerald-600">بعد — غير محفوظ</p><p className="mt-2 font-semibold">{editTitle}</p><p className="mt-1 text-sm">{displayDate(editDeadline)}</p></div></div><label className="label mt-5">اسم المهمة<input className="input mt-1" value={editTitle} onChange={(event) => setEditTitle(event.target.value)} required /></label><label className="label mt-4">الوصف<textarea className="input mt-1 min-h-20" value={editDescription} onChange={(event) => setEditDescription(event.target.value)} /></label><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="label">الموعد الحالي<input className="input mt-1" value={editDeadline} onChange={(event) => setEditDeadline(event.target.value)} /></label><label className="label">الأولوية<select className="input mt-1" value={editPriority} onChange={(event) => setEditPriority(event.target.value as Priority)}><option value="low">منخفضة</option><option value="medium">متوسطة</option><option value="high">عالية</option><option value="urgent">عاجلة</option></select></label></div><label className="label mt-4">سبب التغيير — اختياري<input className="input mt-1" value={editReason} onChange={(event) => setEditReason(event.target.value)} placeholder="مثال: طلب العميل تأجيل التسليم" /></label><label className="mt-5 flex gap-3 rounded-xl bg-slate-100 p-3 text-sm dark:bg-slate-800"><input type="checkbox" checked={editConfirmed} onChange={(event) => setEditConfirmed(event.target.checked)} /><span>راجعت المقارنة وأؤكد حفظ التغيير في سجل المهمة.</span></label><button className="btn-primary mt-5 w-full">حفظ التغيير المؤكد</button></form></div>}

      {(detail || detailLoading) && <div className="fixed inset-0 z-[90] bg-slate-950/60" onClick={() => setDetail(null)}><aside onClick={(event) => event.stopPropagation()} className="absolute inset-y-0 left-0 w-full max-w-2xl overflow-y-auto bg-white p-6 shadow-2xl dark:bg-slate-950"><div className="flex items-start justify-between gap-4"><div><p className="text-xs text-slate-500">التفاصيل والسجل الكامل</p><h2 className="mt-1 text-2xl font-bold">{detail?.title ?? "جاري التحميل..."}</h2></div><button onClick={() => setDetail(null)} className="rounded-xl border border-slate-200 p-2 dark:border-slate-700" aria-label="إغلاق التفاصيل"><X /></button></div>{detailLoading && !detail ? <LoadingState /> : detail && <><div className="mt-6 grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-slate-100 p-4 dark:bg-slate-900"><p className="text-xs text-slate-500">الحالة الحالية</p><div className="mt-2"><Badge tone={statusTone[detail.workflow_status]}>{statusNames[detail.workflow_status]}</Badge></div></div><div className="rounded-xl bg-slate-100 p-4 dark:bg-slate-900"><p className="text-xs text-slate-500">الموعد الحالي</p><p className="mt-2 font-bold">{displayDate(detail.deadline)}</p></div></div><section className="mt-6"><h3 className="font-bold">المهمة الأصلية</h3><div className="mt-3 rounded-xl border border-slate-200 p-4 text-sm dark:border-slate-800"><p>{detail.original_message || "أُنشئت يدويًا"}</p><dl className="mt-3 grid gap-2 text-slate-500 sm:grid-cols-2"><div><dt className="font-semibold">الموعد الأصلي</dt><dd>{displayDate(detail.original_deadline)}</dd></div><div><dt className="font-semibold">تاريخ الاستلام</dt><dd>{displayDate(detail.received_at)}</dd></div><div><dt className="font-semibold">المصدر</dt><dd>{detail.source || "manual"}</dd></div><div><dt className="font-semibold">النموذج</dt><dd dir="ltr">{detail.model_version || "manual"}</dd></div></dl></div></section><section className="mt-7"><div className="flex items-center gap-2"><CalendarClock className="text-iris" /><h3 className="font-bold">سجل التغييرات والرسائل اللاحقة</h3></div><div className="mt-4 space-y-4">{detail.history.map((event) => { const values = eventValues(event); return <article key={event.id} className="relative border-r-2 border-iris/30 pr-5"><span className="absolute -right-[7px] top-1 h-3 w-3 rounded-full bg-iris" /><div className="flex flex-wrap items-center justify-between gap-2"><Badge tone="iris">{event.summary || event.event_type}</Badge><time className="text-xs text-slate-400">{displayDate(event.created_at)}</time></div>{event.event_type === "rescheduled" && <p className="mt-3 rounded-xl bg-slate-100 p-3 text-sm dark:bg-slate-900">تم تغيير الموعد من <b>{displayDate(String(values.before.deadline ?? ""))}</b> إلى <b>{displayDate(String(values.after.deadline ?? ""))}</b>.</p>}{event.related_message && <div className="mt-3 rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-800"><p className="text-xs font-bold text-slate-500">الرسالة المؤثرة</p><p className="mt-1">«{event.related_message}»</p></div>}{event.evidence && !event.related_message && <p className="mt-2 text-sm text-slate-500">الدليل: {event.evidence}</p>}{event.model_intent && <p className="mt-2 text-xs text-slate-500">تنبؤ النموذج: <b>{event.model_intent}</b> · <span dir="ltr">{event.model_identifier}</span></p>}</article>; })}{detail.history.length === 0 && <p className="text-sm text-slate-500">لا توجد تغييرات مسجلة.</p>}</div></section></>}</aside></div>}
    </>
  );
}
