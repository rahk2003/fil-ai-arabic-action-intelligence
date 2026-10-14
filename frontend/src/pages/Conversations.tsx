import { FormEvent, useEffect, useMemo, useState } from "react";
import { Check, CircleHelp, GitCompareArrows, MessagesSquare, Pencil, ShieldAlert, X } from "lucide-react";
import { api } from "../lib/api";
import type { Analysis, ModelChoice, Task } from "../types";
import { Badge, ErrorState, PageHeader } from "../components/ui";

type ConversationItem = { sequence: number; message_id: number; prediction_id: number; suggestion_id: number | null; analysis: Analysis; before_after: null | { before: string; after: string; change_type: Analysis["interpretation"]["action_type"]; related_task_id: number | string | null; missing_details: string[]; requires_confirmation: boolean } };
type ConversationResult = { conversation_id: number; analyses: ConversationItem[]; automatic_task_mutations: boolean };
const intentNames = { new_task: "مهمة جديدة", reschedule: "إعادة جدولة", cancellation: "إلغاء", info_only: "معلومات فقط" };
const operationNames: Record<Analysis["interpretation"]["action_type"], string> = { create_task: "إنشاء مهمة", update_task_scope: "تعديل نطاق المهمة", update_task_requirement: "إضافة متطلب", update_task_priority: "تعديل الأولوية", reschedule_task: "إعادة جدولة", cancel_task: "إلغاء مهمة", mark_complete: "تسجيل الإكمال", add_instruction: "إضافة تعليمات", no_action: "لا إجراء", needs_clarification: "يحتاج توضيحًا" };

export default function Conversations() {
  const [text, setText] = useState("حلل كل البيانات\nخلاص حلل بس جزء");
  const [model, setModel] = useState<ModelChoice>("baseline");
  const [result, setResult] = useState<ConversationResult | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [targets, setTargets] = useState<Record<number, string>>({});
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [states, setStates] = useState<Record<number, string>>({});
  const [createdBySequence, setCreatedBySequence] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(false); const [busy, setBusy] = useState<number | null>(null); const [error, setError] = useState<string | null>(null);
  useEffect(() => { void api.tasks().then(setTasks).catch(() => undefined); }, []);

  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(null); setStates({}); setCreatedBySequence({});
    try {
      const response = await api.analyzeConversation(text.split("\n").map(value => value.trim()).filter(Boolean), new Date().toISOString(), model) as ConversationResult;
      setResult(response); setEdits(Object.fromEntries(response.analyses.map(item => [item.sequence, item.analysis.interpretation.proposed_change ?? item.analysis.message]))); setTasks(await api.tasks());
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر التحليل"); } finally { setLoading(false); }
  }
  function resolvedTaskId(item: ConversationItem) {
    const explicit = Number(targets[item.sequence]); if (explicit) return explicit;
    const related = item.analysis.interpretation.related_task_id; if (typeof related === "number") return related;
    const match = typeof related === "string" ? related.match(/^conversation-(\d+)$/) : null; return match ? createdBySequence[Number(match[1])] : undefined;
  }
  async function confirm(item: ConversationItem) {
    const interpretation = item.analysis.interpretation; const operation = interpretation.action_type;
    if (operation === "no_action" || operation === "needs_clarification") return;
    setBusy(item.sequence); setError(null);
    try {
      if (operation === "create_task") {
        if (!item.suggestion_id) throw new Error("لا يوجد اقتراح محفوظ لإنشاء هذه المهمة.");
        const task = await api.confirmSuggestion(item.suggestion_id, { confirmed: true, title: edits[item.sequence] || interpretation.proposed_change || item.analysis.message, description: item.analysis.message, deadline: item.analysis.actions[0]?.normalized_datetime ?? undefined, reason: "تأكيد إنشاء المهمة من ذكاء المحادثة" });
        setCreatedBySequence(previous => ({ ...previous, [item.sequence]: task.id }));
      } else {
        const taskId = resolvedTaskId(item); if (!taskId) throw new Error("يجب اختيار المهمة المرتبطة قبل تأكيد التغيير.");
        const task = tasks.find(value => value.id === taskId); const value = edits[item.sequence] || interpretation.proposed_change || item.analysis.message;
        const update: Parameters<typeof api.updateTask>[1] = { event_type: operation === "reschedule_task" ? "rescheduled" : operation === "cancel_task" ? "canceled" : operation === "mark_complete" ? "completed" : "edited", evidence: item.analysis.message, reason: `${operationNames[operation]}: ${value}`, confirmed: true };
        if (operation === "reschedule_task") { if (!value || !/\d{4}-\d{2}-\d{2}/.test(value)) throw new Error("يلزم إدخال موعد ميلادي واضح قبل إعادة الجدولة."); update.deadline = value; }
        else if (["update_task_scope", "update_task_requirement", "add_instruction"].includes(operation)) update.description = [task?.description, `${operationNames[operation]}: ${value}`].filter(Boolean).join("\n");
        else if (operation === "update_task_priority") update.priority = /عاجل/.test(value) ? "urgent" : "high";
        await api.updateTask(taskId, update);
      }
      setStates(previous => ({ ...previous, [item.sequence]: "confirmed" })); setTasks(await api.tasks());
    } catch (reason) { setError(reason instanceof Error ? reason.message : "تعذر تأكيد التغيير"); } finally { setBusy(null); }
  }
  const activeTasks = useMemo(() => tasks.filter(task => !["completed", "canceled"].includes(task.workflow_status)), [tasks]);

  return <><PageHeader eyebrow="ذكاء سياق المحادثة" title="المحادثات" description="تحليل الرسائل بالتسلسل، واقتراح تغيير على المهمة نفسها دون تعديل تلقائي." /><div className="grid gap-6 xl:grid-cols-[.78fr_1.22fr]">
    <form onSubmit={submit} className="panel h-fit"><label htmlFor="conversation-model" className="label">نموذج التصنيف</label><select id="conversation-model" className="input mt-1" value={model} onChange={event => setModel(event.target.value as ModelChoice)}><option value="baseline">النموذج الأساسي</option><option value="camelbert">CAMeLBERT المحسّن</option></select><label htmlFor="conversation-messages" className="label mt-5">كل رسالة في سطر مستقل</label><textarea id="conversation-messages" className="input min-h-64" value={text} onChange={event => setText(event.target.value)} /><button className="btn-primary mt-5 w-full" disabled={loading}><MessagesSquare size={18} />{loading ? "جاري التحليل..." : "تحليل المحادثة"}</button><p className="mt-3 text-xs leading-5 text-slate-500">التصنيف الخام لا يساوي قرار تحديث المهمة. كل عملية تحتاج مراجعة وتأكيدًا صريحًا.</p></form>
    <section className="space-y-4">{error && <ErrorState message={error} />}{!result && !error && <div className="panel flex min-h-64 flex-col items-center justify-center text-slate-500"><GitCompareArrows className="mb-3 h-11 w-11 text-iris" />لا توجد نتيجة بعد</div>}{result?.analyses.map(item => {
      const analysis = item.analysis; const interpretation = analysis.interpretation; const change = item.before_after; const state = states[item.sequence]; const needsTarget = !["create_task", "no_action"].includes(interpretation.action_type) && !resolvedTaskId(item);
      return <article key={item.sequence} className="panel"><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-bold text-iris">الرسالة {item.sequence}</span><Badge tone={interpretation.abstained ? "amber" : "iris"}>{operationNames[interpretation.action_type]}</Badge></div><p className="mt-3 text-lg font-semibold">{analysis.message}</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-slate-100 p-3 dark:bg-slate-900"><p className="text-xs text-slate-500">تصنيف النموذج الخام</p><p className="mt-1 font-bold">{intentNames[analysis.prediction.label]}</p><p className="mt-1 text-xs text-slate-500" dir="ltr">{analysis.prediction.model_identifier} · {analysis.prediction.inference_latency_ms.toFixed(1)} ms</p></div><div className="rounded-xl bg-slate-100 p-3 dark:bg-slate-900"><p className="text-xs text-slate-500">التفسير السياقي</p><p className="mt-1 font-bold">{operationNames[interpretation.action_type]}</p><p className="mt-1 text-xs text-slate-500">الدليل: «{interpretation.evidence}»</p><p className="mt-2 text-xs font-bold text-iris">طريقة الربط: {analysis.context.matching_method === "embeddings" ? "تمثيلات دلالية محلية + أدلة سياقية" : analysis.context.matching_method === "lexical_fallback" ? "مطابقة لفظية احتياطية" : "لا يوجد مرشح سابق"}</p></div></div>
        {interpretation.classifier_extraction_consistency !== "agree" && <div className="mt-3 flex gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"><ShieldAlert className="shrink-0" size={18} />يوجد تعارض بين التصنيف الخام واستخراج الإجراء؛ لم يُستخدم التصنيف وحده لتغيير المهمة.</div>}
        {change && <div className="mt-4 grid gap-3 md:grid-cols-2"><div className="rounded-xl bg-rose-50 p-4 dark:bg-rose-950/30"><p className="text-xs font-bold text-rose-600">قبل</p><p className="mt-2">{change.before}</p></div><div className="rounded-xl bg-emerald-50 p-4 dark:bg-emerald-950/30"><p className="text-xs font-bold text-emerald-600">بعد — مقترح</p><input aria-label={`التغيير المقترح للرسالة ${item.sequence}`} className="input mt-2" value={edits[item.sequence] ?? change.after} onChange={event => setEdits(previous => ({ ...previous, [item.sequence]: event.target.value }))} /></div></div>}
        {interpretation.missing_details.length > 0 && <p className="mt-3 flex gap-2 rounded-xl border border-amber-200 p-3 text-sm"><CircleHelp size={18} className="shrink-0 text-amber-500" />المطلوب توضيحه: {interpretation.missing_details.join("، ")}</p>}
        {needsTarget && <label className="label mt-4">المهمة المرتبطة<select className="input mt-1" value={targets[item.sequence] ?? ""} onChange={event => setTargets(previous => ({ ...previous, [item.sequence]: event.target.value }))}><option value="">اختيار مهمة موجودة</option>{activeTasks.map(task => <option key={task.id} value={task.id}>{task.title}</option>)}</select></label>}
        <div className="mt-4 flex flex-wrap gap-2">{!interpretation.abstained && state !== "confirmed" && <button onClick={() => void confirm(item)} disabled={busy === item.sequence} className="btn-primary !py-2"><Check size={16} />{busy === item.sequence ? "جاري الحفظ..." : "تأكيد"}</button>}{state !== "confirmed" && <button onClick={() => setStates(previous => ({ ...previous, [item.sequence]: "editing" }))} className="btn-secondary !py-2"><Pencil size={16} />تعديل</button>}{state !== "confirmed" && <button onClick={() => setStates(previous => ({ ...previous, [item.sequence]: "rejected" }))} className="btn-secondary !py-2"><X size={16} />رفض</button>}{(interpretation.abstained || interpretation.missing_details.length > 0) && <button onClick={() => setStates(previous => ({ ...previous, [item.sequence]: "clarification" }))} className="btn-secondary !py-2"><CircleHelp size={16} />طلب توضيح</button>}{state && <Badge tone={state === "confirmed" ? "green" : state === "rejected" ? "rose" : "amber"}>{state === "confirmed" ? "تم الحفظ في سجل المهمة" : state === "rejected" ? "مرفوض — لم يحدث تعديل" : state === "clarification" ? "بانتظار توضيح" : "وضع التعديل"}</Badge>}</div>
      </article>;
    })}</section>
  </div></>;
}
