import { useCallback, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { Badge, ErrorState, LoadingState, PageHeader } from "../components/ui";

const categoryNames: Record<string, string> = { all: "كل الفئات", negation: "النفي والمنع", deadline_or_rescheduling: "الموعد وإعادة الجدولة", informational: "الرسائل المعلوماتية", cancellation: "الإلغاء", dialect: "التعبيرات اللهجية", ambiguous_reference: "مرجع ملتبس", multiple_actions: "أفعال متعددة", contextual_updates: "تحديث سياقي", approval_status: "الاعتماد والإكمال", informational_with_time: "معلومة زمنية", negation_ambiguous: "نفي ملتبس", other: "أخرى" };
const sourceNames: Record<string, string> = { all: "كل المصادر", original_baseline_24: "تحليل أخطاء النموذج الأساسي", overlapping_repository_24: "تشخيص المستودع المتداخل", manual_saudi_challenge: "تحديات عربية سعودية" };

export default function ErrorAnalysis() {
  const [category, setCategory] = useState("all"); const [source, setSource] = useState("all");
  const resource = useAsync(useCallback(() => api.errorAnalysis(), []));
  if (resource.loading) return <LoadingState />;
  if (resource.error || !resource.data) return <ErrorState message={resource.error ?? "لا توجد بيانات"} />;
  const data = resource.data;
  const categories = Array.from(new Set(data.failures.map(row => row.category)));
  const filtered = data.failures.filter(row => (category === "all" || row.category === category) && (source === "all" || row.source === source));
  return <>
    <PageHeader eyebrow="تدقيق علمي" title="تحليل الأخطاء" description="فصل واضح بين اختبار النموذج الأساسي، نتائج Colab الإجمالية، التشخيص المتداخل، وأمثلة التحدي الاصطناعية." />
    <div className="grid gap-4 lg:grid-cols-4">{Object.entries(data.sections).map(([key, section]) => <section key={key} className="panel !p-4"><h2 className="font-bold">{key === "original_baseline" ? "أخطاء النموذج الأساسي" : key === "colab_125" ? "تقييم Colab الاصطناعي" : key === "overlapping_24" ? "تشخيص 24 المتداخل" : "تحديات عربية سعودية"}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{section.note}</p></section>)}</div>
    <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100"><AlertTriangle className="mt-0.5 shrink-0" /><div><h2 className="font-bold">ما الذي لا يمكن إثباته؟</h2><p className="mt-2 text-sm leading-7">لم يُحفظ ملف تنبؤات اختبار Colab ذي 125 رسالة، لذلك لا تُعرض له أمثلة أخطاء أو مصفوفة التباس مصطنعة. كما أن مقارنة الـ24 رسالة مع CAMeLBERT متداخلة مع بيانات الضبط وليست دليل تعميم مستقلًا.</p></div></div>
    <section className="panel mt-6"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-lg font-bold">الأخطاء المدعومة بالملفات المحفوظة</h2><p className="mt-1 text-sm text-slate-500">يظهر {filtered.length} سجلًا. التفسيرات المنقولة من التقرير تبقى فرضيات تحليلية وليست أسبابًا تجريبية مثبتة.</p></div><div className="flex flex-wrap gap-2"><select className="input min-w-48" value={source} onChange={event => setSource(event.target.value)}>{Object.entries(sourceNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><select className="input min-w-48" value={category} onChange={event => setCategory(event.target.value)}><option value="all">كل الفئات</option>{categories.map(value => <option key={value} value={value}>{categoryNames[value] ?? value}</option>)}</select></div></div><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[1350px] text-right text-sm"><thead className="text-slate-500"><tr><th className="pb-3">الرسالة</th><th>المرجع</th><th>النموذج الأساسي</th><th>CAMeLBERT</th><th>فئة الخطأ</th><th>التفسير</th><th>المصدر والصلاحية</th></tr></thead><tbody className="divide-y divide-slate-200 dark:divide-slate-800">{filtered.map((row, index) => <tr key={`${row.source}-${index}`} className="align-top"><td className="py-4 max-w-72 font-semibold">{row.message}</td><td className="py-4" dir="ltr">{row.expected_label ?? "يحتاج سياقًا"}</td><td className="py-4" dir="ltr">{row.baseline_prediction ?? "—"}</td><td className="py-4" dir="ltr">{row.camelbert_prediction ?? "غير مشغّل"}</td><td className="py-4"><Badge tone="amber">{categoryNames[row.category] ?? row.category}</Badge></td><td className="py-4 max-w-96 text-slate-600 dark:text-slate-300">{row.explanation || "لم يُثبت سبب الخطأ."}</td><td className="py-4 max-w-64"><p>{sourceNames[row.source] ?? row.source}</p><p className="mt-1 text-xs text-slate-500">{row.validity}</p></td></tr>)}</tbody></table></div></section>
  </>;
}
