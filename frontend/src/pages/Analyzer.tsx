import { FormEvent, useEffect, useState } from "react";
import { AlertTriangle, BrainCircuit, Check, GitCompareArrows, Play, Save, Sparkles, X } from "lucide-react";
import { api } from "../lib/api";
import type { AnalyzeResponse, Intent, ModelChoice, ModelComparisonEvidence } from "../types";
import { Badge, ErrorState, PageHeader } from "../components/ui";

const intentNames: Record<Intent, string> = {
  new_task: "مهمة جديدة",
  reschedule: "تغيير موعد",
  cancellation: "إلغاء",
  info_only: "معلومة فقط",
};

const modelNames: Record<ModelChoice, string> = {
  baseline: "Baseline — TF-IDF + Logistic Regression",
  camelbert: "CAMeLBERT-DA — Fine-tuned",
};

function PredictionPanel({
  result,
  selectedForFeedback,
  onSelectForFeedback,
  expectedLabel,
}: {
  result: AnalyzeResponse;
  selectedForFeedback: boolean;
  onSelectForFeedback: () => void;
  expectedLabel: Intent | null;
}) {
  const { prediction, actions, warnings, interpretation } = result.analysis;
  const displayModel = prediction.model_identifier.includes("camelbert") ? "CAMeLBERT-DA المحسّن" : "النموذج الأساسي";
  return (
    <section className={`panel ${selectedForFeedback ? "ring-2 ring-iris/40" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-iris">{displayModel}</p>
          <p className="mt-2 text-sm text-slate-500">تصنيف النموذج الخام</p>
          <h2 className="mt-1 text-2xl font-bold">{intentNames[prediction.label]}</h2>
          {expectedLabel && <p className={`mt-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold ${prediction.label === expectedLabel ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200" : "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200"}`}>{prediction.label === expectedLabel ? <Check size={14} /> : <X size={14} />}{prediction.label === expectedLabel ? "صحيح بحسب المرجع" : `غير صحيح — المرجع ${intentNames[expectedLabel]}`}</p>}
          {!expectedLabel && <p className="mt-3 text-xs text-slate-500">التصنيف المرجعي غير متوفر</p>}
        </div>
        <div className="grid grid-cols-2 gap-2 text-center text-sm">
          <div className="rounded-xl bg-slate-100 px-3 py-2 dark:bg-slate-800">
            <p className="text-xs text-slate-500">Score غير معاير</p>
            <p className="mt-1 font-bold">
              {prediction.uncalibrated_score == null
                ? "—"
                : `${(prediction.uncalibrated_score * 100).toFixed(1)}%`}
            </p>
          </div>
          <div className="rounded-xl bg-slate-100 px-3 py-2 dark:bg-slate-800">
            <p className="text-xs text-slate-500">زمن inference</p>
            <p className="mt-1 font-bold" dir="ltr">{prediction.inference_latency_ms.toFixed(1)} ms</p>
          </div>
        </div>
      </div>

      <details className="mt-4 rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-800"><summary className="cursor-pointer font-semibold">تفاصيل النموذج والملاحظات التقنية</summary><p className="mt-3 text-xs text-slate-500" dir="ltr">{prediction.model_identifier}</p>{warnings.map(warning => <p key={warning} className="mt-2 text-xs text-amber-700 dark:text-amber-300">⚠ {warning}</p>)}</details>

      {interpretation.classifier_extraction_consistency !== "agree" && <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100"><b>تنبيه اتساق:</b> تصنيف النموذج لا يتفق مع الإجراء المستخرج بالقواعد. لا يُعد الإجراء تصنيف النموذج، ولا يُحفظ أي تغيير قبل المراجعة.</div>}

      <div className="mt-5 border-t border-slate-200 pt-4 dark:border-slate-800">
        <div className="flex items-center justify-between gap-3">
          <div><h3 className="font-bold">الإجراء المستخرج من النص</h3><p className="mt-1 text-xs text-slate-500">نتيجة قواعد لغوية مستقلة عن تصنيف النموذج.</p></div>
          <button type="button" onClick={onSelectForFeedback} className="text-xs font-semibold text-iris hover:underline">
            {selectedForFeedback ? "محدد للتصحيح" : "صحّح هذه النتيجة"}
          </button>
        </div>
        <div className="mt-3 space-y-3">
          {actions.map((action, index) => (
            <article key={`${action.evidence}-${index}`} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={action.intent === "cancellation" ? "rose" : action.intent === "reschedule" ? "amber" : "green"}>
                  {intentNames[action.intent]}
                </Badge>
                {action.is_ambiguous && <Badge>غير مؤكد</Badge>}
              </div>
              <p className="mt-3 font-semibold">{action.action_text ?? "لم يُستخرج إجراء قابل للتنفيذ"}</p>
              <p className="mt-2 text-sm text-slate-500">
                التاريخ: <span dir="ltr">{action.normalized_datetime ?? action.datetime_text ?? "غير متاح"}</span>
              </p>
            </article>
          ))}
        </div>
      </div>
      <div className="mt-4 rounded-xl bg-slate-100 p-4 text-sm dark:bg-slate-900"><div className="flex items-center justify-between gap-3"><b>التفسير السياقي المقترح</b><Badge tone={interpretation.abstained ? "amber" : "iris"}>{interpretation.action_label_ar}</Badge></div>{interpretation.related_task_text && <p className="mt-2">المهمة المرتبطة: {interpretation.related_task_text}</p>}{interpretation.missing_details.length > 0 && <p className="mt-2 text-amber-700 dark:text-amber-300">المطلوب توضيحه: {interpretation.missing_details.join("، ")}</p>}<p className="mt-2 text-xs text-slate-500">لا يوجد تنفيذ تلقائي.</p></div>
    </section>
  );
}

export default function Analyzer() {
  const [message, setMessage] = useState("ارسلي التقرير بكرة الساعة ٩ الصباح");
  const [reference, setReference] = useState("2026-10-14T12:00");
  const [model, setModel] = useState<ModelChoice>("baseline");
  const [results, setResults] = useState<AnalyzeResponse[]>([]);
  const [loading, setLoading] = useState<"single" | "compare" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [corrected, setCorrected] = useState<Intent>("new_task");
  const [feedbackTarget, setFeedbackTarget] = useState<AnalyzeResponse | null>(null);
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);
  const [expectedLabel, setExpectedLabel] = useState<Intent | null>(null);
  const [evidence, setEvidence] = useState<ModelComparisonEvidence | null>(null);
  useEffect(() => { api.modelComparisonEvidence(10).then(setEvidence).catch(() => setEvidence(null)); }, []);

  function acceptResults(next: AnalyzeResponse[]) {
    setResults(next);
    setFeedbackTarget(next[0]);
    setCorrected(next[0].analysis.prediction.label);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading("single");
    setError(null);
    setFeedbackStatus(null);
    setExpectedLabel(null);
    try {
      acceptResults([await api.analyze(message, reference, model)]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "تعذر التحليل");
    } finally {
      setLoading(null);
    }
  }

  async function runComparison(targetMessage: string, referenceLabel: Intent | null = null) {
    setLoading("compare");
    setError(null);
    setFeedbackStatus(null);
    setExpectedLabel(referenceLabel);
    try {
      const response = await api.compareModels(targetMessage, reference);
      acceptResults([response.results.baseline, response.results.camelbert]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "تعذرت مقارنة النموذجين");
    } finally {
      setLoading(null);
    }
  }
  async function compare() { await runComparison(message); }

  function selectForFeedback(result: AnalyzeResponse) {
    setFeedbackTarget(result);
    setCorrected(result.analysis.prediction.label);
    setFeedbackStatus(null);
  }

  async function saveCorrection() {
    if (!feedbackTarget) return;
    try {
      const response = await api.feedback({
        prediction_id: feedbackTarget.prediction_id,
        corrected_intent: corrected,
        confirmed: true,
        notes: `Submitted from React analyzer for ${feedbackTarget.analysis.prediction.model_identifier}`,
      });
      setFeedbackStatus(`حُفظ التصحيح رقم ${response.id} كمرشح مراجَع؛ لم يحدث تدريب تلقائي.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "تعذر حفظ التصحيح");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Arabic NLP"
        title="محلل الرسائل العربية"
        description="اختر النموذج المحلي أو قارن النموذجين على الرسالة نفسها. الدرجات غير معايرة ولا يُنفذ أي تغيير تلقائيًا."
      />
      <div className="grid gap-6 xl:grid-cols-[.9fr_1.1fr]">
        <form onSubmit={submit} className="panel h-fit">
          <label htmlFor="analyzer-message" className="label">الرسالة</label>
          <textarea id="analyzer-message" className="input min-h-40 resize-y" value={message} onChange={(event) => { setMessage(event.target.value); setExpectedLabel(null); }} required />

          <fieldset className="mt-5">
            <legend className="label">نموذج التصنيف</legend>
            <div className="grid gap-2">
              {(Object.entries(modelNames) as Array<[ModelChoice, string]>).map(([value, label]) => (
                <label key={value} className={`cursor-pointer rounded-xl border p-3 text-sm transition ${model === value ? "border-iris bg-iris/5" : "border-slate-200 dark:border-slate-700"}`}>
                  <input type="radio" name="model" value={value} checked={model === value} onChange={() => setModel(value)} className="ml-2" />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>

          <label htmlFor="analyzer-reference" className="label mt-5">وقت إنشاء الرسالة — Asia/Riyadh</label>
          <input id="analyzer-reference" type="datetime-local" className="input" value={reference} onChange={(event) => setReference(event.target.value)} />
          <p className="mt-2 text-xs text-slate-500">مطلوب لتطبيع «بكرة» و«الخميس الجاي» دون اختلاق تاريخ.</p>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <button disabled={loading !== null} className="btn-primary">
              {loading === "single" ? "جاري التحليل..." : <><Sparkles size={18} /> حلّل بالنموذج المحدد</>}
            </button>
            <button type="button" disabled={loading !== null || !message.trim()} onClick={compare} className="btn-secondary">
              {loading === "compare" ? "جاري تشغيل النموذجين..." : <><GitCompareArrows size={18} /> قارن النموذجين</>}
            </button>
          </div>
          <p className="mt-4 text-xs leading-5 text-slate-500">
            نتيجة CAMeLBERT المعلنة 89.6% مبنية على بيانات اصطناعية فقط، وليست تقديرًا للدقة في الاستخدام الواقعي.
          </p>
        </form>

        <div className="space-y-6">
          {error && <ErrorState message={error} />}
          {results.length === 0 && !error && (
            <div className="panel flex min-h-80 flex-col items-center justify-center text-center text-slate-500">
              <BrainCircuit className="mb-4 h-12 w-12 text-iris" />
              <p className="font-bold text-slate-800 dark:text-slate-200">النتيجة ستظهر هنا</p>
              <p className="mt-2 text-sm">لن تُنشأ مهمة حتى تؤكدها يدويًا.</p>
            </div>
          )}
          {results.length === 2 && (
            <div className="rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-200">
              المقارنة أدناه شُغّلت على النص نفسه حرفيًا؛ كل بطاقة تعرض score غير معاير وزمن inference الفعلي لنموذجها.
            </div>
          )}
          {results.map((result) => (
            <PredictionPanel
              key={result.prediction_id}
              result={result}
              selectedForFeedback={feedbackTarget?.prediction_id === result.prediction_id}
              onSelectForFeedback={() => selectForFeedback(result)}
              expectedLabel={expectedLabel}
            />
          ))}
          {feedbackTarget && (
            <section className="panel">
              <h3 className="font-bold">تصحيح بشري</h3>
              <p className="mt-1 text-sm text-slate-500">
                النتيجة المحددة: {feedbackTarget.analysis.prediction.model_identifier}. تُحفظ كمرشح مراجَع فقط؛ لا يوجد Online Retraining.
              </p>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <select aria-label="النية المصححة" className="input" value={corrected} onChange={(event) => setCorrected(event.target.value as Intent)}>
                  {Object.entries(intentNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
                <button type="button" onClick={saveCorrection} className="btn-secondary shrink-0"><Save size={17} /> حفظ التصحيح</button>
              </div>
              {feedbackStatus && <p className="mt-3 flex items-center gap-2 text-sm text-emerald-600"><Check size={16} />{feedbackStatus}</p>}
            </section>
          )}
        </div>
      </div>
      {evidence && <section className="panel mt-7"><div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between"><div><p className="text-xs font-bold uppercase tracking-widest text-iris">قبل الضبط الدقيق وبعده</p><h2 className="mt-1 text-2xl font-black">فروق تشغيل محفوظة للتشخيص</h2><p className="mt-2 max-w-4xl text-sm leading-7 text-slate-500">تعرض هذه البطاقات صفوفًا أخطأ فيها النموذج الأساسي وأصاب فيها CAMeLBERT وفق مرجع اصطناعي متداخل مع الضبط. زر التشغيل يعيد تنفيذ النموذجين فعليًا على النص نفسه.</p></div><Badge tone="iris">{evidence.methodology.available_genuine_improvements} حالات متاحة</Badge></div><div className="mt-5 flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100"><AlertTriangle className="mt-0.5 shrink-0" size={19} /><p>{evidence.methodology.leakage_warning}</p></div><div className="mt-5 grid gap-4 xl:grid-cols-2">{evidence.examples.map((example, index) => <article key={example.message} className="rounded-2xl border border-slate-200 p-5 dark:border-slate-800"><div className="flex items-start justify-between gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-iris/10 text-sm font-black text-iris">{index + 1}</span><button className="btn-secondary !px-3 !py-2" disabled={loading !== null} onClick={() => { setMessage(example.message); void runComparison(example.message, example.expected_label); }}><Play size={15} />تشغيل المقارنة</button></div><p className="mt-4 text-lg font-bold">«{example.message}»</p><p className="mt-2 text-xs text-slate-500">المرجع المحفوظ: <b>{intentNames[example.expected_label]}</b></p><div className="mt-4 grid grid-cols-2 gap-3 text-sm"><div className="rounded-xl bg-rose-50 p-3 text-rose-900 dark:bg-rose-950/25 dark:text-rose-100"><p className="font-bold">Baseline ✕</p><p className="mt-1">{intentNames[example.baseline_prediction]}</p><p className="mt-1 text-xs">{(example.baseline_score * 100).toFixed(1)}% · {example.baseline_latency_ms.toFixed(1)}ms</p></div><div className="rounded-xl bg-emerald-50 p-3 text-emerald-900 dark:bg-emerald-950/25 dark:text-emerald-100"><p className="font-bold">CAMeLBERT ✓</p><p className="mt-1">{intentNames[example.camelbert_prediction]}</p><p className="mt-1 text-xs">{(example.camelbert_score * 100).toFixed(1)}% · {example.camelbert_latency_ms.toFixed(1)}ms</p></div></div><p className="mt-3 text-xs leading-5 text-slate-500">هذه نتيجة فعلية للعينة المحفوظة، لكنها ليست دليلًا مستقلًا على التعميم لأن العينة متداخلة مع بيانات الضبط.</p></article>)}</div></section>}
    </>
  );
}
