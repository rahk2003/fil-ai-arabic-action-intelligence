"""FI'L AI | فِعل — local, no-paid-API Gradio dashboard."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import gradio as gr
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fil_ai.config import INTENT_AR, TIMEZONE  # noqa: E402
from fil_ai.pipeline import ActionIntelligencePipeline  # noqa: E402
from fil_ai.storage import TaskStore  # noqa: E402

pipeline = ActionIntelligencePipeline()
store = TaskStore()


def task_frame(status: str | None = None) -> pd.DataFrame:
    rows = store.list_tasks(None if status == "all" else status)
    columns = ["id", "title", "status", "deadline", "model_version", "updated_at"]
    return pd.DataFrame(rows, columns=columns)


def analyze_message(message: str, reference_time: str) -> tuple[dict, str]:
    if not message or not message.strip():
        return {}, "⚠️ اكتبي رسالة أولًا."
    try:
        analysis = pipeline.analyze(
            message,
            reference_time=reference_time.strip() or None,
            previous_tasks=store.list_tasks("pending"),
        )
        store.save_analysis(message, analysis)
    except Exception as error:
        return {}, f"⚠️ تعذر التحليل: {type(error).__name__}: {error}"
    prediction = analysis["prediction"]
    confidence = prediction["confidence"]
    status = (
        f"**النية:** {INTENT_AR[prediction['label']]}  \n"
        f"**النموذج:** `{prediction['model_name']}`  \n"
    )
    status += f"**الثقة التقريبية:** {confidence:.1%}" if confidence is not None else "**الثقة:** غير متاحة"
    if analysis["warnings"]:
        status += "  \n⚠️ " + " — ".join(analysis["warnings"])
    status += "  \nلن تُنفذ أو تُحفظ أي مهمة بدون تأكيدك."
    return analysis, status


def create_task(title: str, deadline: str, confirmed: bool) -> tuple[str, pd.DataFrame]:
    try:
        task_id = store.create_task(title, deadline=deadline or None, confirmed=confirmed)
    except (PermissionError, ValueError) as error:
        return f"⚠️ {error}", task_frame()
    return f"✅ تم إنشاء المهمة المحلية رقم {task_id} بعد التأكيد.", task_frame()


def update_task(task_id: float, event_type: str, new_deadline: str, evidence: str, confirmed: bool) -> tuple[str, pd.DataFrame]:
    try:
        store.update_task(
            int(task_id), event_type=event_type, new_deadline=new_deadline or None,
            evidence=evidence or None, confirmed=confirmed,
        )
    except (PermissionError, ValueError, KeyError, TypeError) as error:
        return f"⚠️ {error}", task_frame()
    return f"✅ تم تسجيل `{event_type}` للمهمة {int(task_id)} مع حفظ التاريخ.", task_frame()


def task_history(task_id: float) -> pd.DataFrame:
    try:
        return pd.DataFrame(store.history(int(task_id)))
    except (ValueError, KeyError, TypeError):
        return pd.DataFrame()


def analyze_conversation(messages: str) -> dict:
    lines = [line.strip() for line in messages.splitlines() if line.strip()]
    if not lines:
        return {"error": "أدخلي رسالة واحدة على الأقل، كل رسالة في سطر."}
    temporary_history = store.list_tasks("pending")
    results = []
    for index, line in enumerate(lines, start=1):
        analysis = pipeline.analyze(line, previous_tasks=temporary_history)
        results.append({"sequence": index, **analysis})
        for action in analysis["actions"]:
            if action["intent"] == "new_task" and action.get("action_text"):
                temporary_history.append({"id": f"conversation-{index}", "title": action["action_text"], "original_message": line})
    return {"messages": results, "notice": "Context matches are suggestions only and require confirmation."}


def evaluation_markdown() -> str:
    comparison = ROOT / "reports/model_comparison.md"
    baseline = ROOT / "reports/baseline_error_analysis.md"
    text = comparison.read_text(encoding="utf-8") if comparison.is_file() else "Model comparison has not been run."
    if baseline.is_file():
        text += "\n\n---\n\n" + baseline.read_text(encoding="utf-8")[:6000]
    return text


def dataset_preview(source: str) -> pd.DataFrame:
    if source == "Synthetic seed":
        return pd.read_csv(ROOT / "data/seed_messages.csv").head(50)
    path = ROOT / "data/processed/massive_relevant_candidates.csv"
    if path.is_file():
        return pd.read_csv(path).head(50)
    return pd.DataFrame({"status": ["MASSIVE candidates unavailable; run the documented data scripts."]})


CSS = """
.gradio-container {max-width: 1240px !important;}
.rtl {direction: rtl; text-align: right;}
.hero {background: linear-gradient(120deg,#172033,#3157d5); color:white; padding:24px; border-radius:18px;}
"""

with gr.Blocks(title="FI'L AI | فِعل") as demo:
    gr.HTML("<div class='hero rtl'><h1>FI'L AI | فِعل</h1><h3>Arabic Action Intelligence — From Words to Actions</h3><p>نموذج محلي تعليمي؛ لا ينفذ أي مهمة دون تأكيد المستخدم.</p></div>")
    with gr.Tabs():
        with gr.Tab("1 — محلل الرسائل"):
            with gr.Row():
                with gr.Column(scale=3):
                    message = gr.Textbox(label="الرسالة العربية", lines=5, rtl=True, placeholder="ارسلي التقرير يوم الخميس الساعة 4 العصر")
                    reference = gr.Textbox(label="وقت إنشاء الرسالة — ISO 8601 (اختياري لكن مطلوب للتواريخ النسبية)", value=datetime.now(ZoneInfo(TIMEZONE)).replace(microsecond=0).isoformat())
                    analyze = gr.Button("حلّل الرسالة", variant="primary")
                with gr.Column(scale=2):
                    summary = gr.Markdown()
            structured = gr.JSON(label="التحليل المنظم والأدلة")
            analyze.click(analyze_message, [message, reference], [structured, summary])

        with gr.Tab("2 — لوحة المهام الذكية"):
            gr.Markdown("### إنشاء مهمة محلية يدويًا\nالتأكيد مطلوب قبل أي تغيير في قاعدة البيانات.", elem_classes="rtl")
            with gr.Row():
                task_title = gr.Textbox(label="المهمة", rtl=True)
                task_deadline = gr.Textbox(label="الموعد بصيغة ISO (اختياري)")
                task_confirm = gr.Checkbox(label="أؤكد إنشاء المهمة")
                task_create = gr.Button("إنشاء")
            task_status = gr.Markdown()
            task_table = gr.Dataframe(value=task_frame, interactive=False, label="المهام وسجل الحالة")
            refresh = gr.Button("تحديث القائمة")
            task_create.click(create_task, [task_title, task_deadline, task_confirm], [task_status, task_table])
            refresh.click(task_frame, outputs=task_table)
            gr.Markdown("### تحديث مهمة موجودة", elem_classes="rtl")
            with gr.Row():
                update_id = gr.Number(label="رقم المهمة", precision=0)
                update_event = gr.Dropdown(["rescheduled", "canceled", "completed"], value="rescheduled", label="نوع التحديث")
                update_deadline = gr.Textbox(label="الموعد الجديد — للتأجيل")
            update_evidence = gr.Textbox(label="الرسالة/الدليل", rtl=True)
            update_confirm = gr.Checkbox(label="أؤكد تعديل المهمة")
            update_button = gr.Button("تطبيق التحديث")
            update_button.click(update_task, [update_id, update_event, update_deadline, update_evidence, update_confirm], [task_status, task_table])
            with gr.Row():
                history_id = gr.Number(label="رقم المهمة لعرض التاريخ", precision=0)
                history_button = gr.Button("عرض التاريخ")
            history_table = gr.Dataframe(interactive=False, label="Task event history")
            history_button.click(task_history, history_id, history_table)

        with gr.Tab("3 — ذكاء المحادثة"):
            conversation = gr.Textbox(label="كل رسالة في سطر مستقل", lines=9, rtl=True, placeholder="اجتماعنا يوم الأحد الساعة 10\nخلاص خلوه الخميس الساعة 12")
            conversation_button = gr.Button("حلّل التسلسل", variant="primary")
            conversation_output = gr.JSON(label="العلاقات والتحديثات المقترحة")
            conversation_button.click(analyze_conversation, conversation, conversation_output)

        with gr.Tab("4 — تقييم النموذج"):
            gr.Markdown("النتائج أدناه فعلية وموسومة بوضوح بأنها من بيانات اصطناعية صغيرة. لا توجد نتيجة Transformer ما لم يُدرّب فعليًا.")
            evaluation = gr.Markdown(value=evaluation_markdown)
            gr.Button("تحديث التقييم").click(evaluation_markdown, outputs=evaluation)

        with gr.Tab("5 — مستكشف البيانات"):
            source = gr.Dropdown(["Synthetic seed", "MASSIVE review candidates"], value="Synthetic seed", label="المصدر")
            preview = gr.Dataframe(value=dataset_preview("Synthetic seed"), interactive=False)
            source.change(dataset_preview, source, preview)
            gr.Markdown("`Synthetic seed` أمثلة مكتوبة يدويًا. MASSIVE بيانات مساعد صوتي منشورة بترخيص CC BY 4.0، وليست رسائل عمل ولا تحمل تسميات FI'L AI دون مراجعة بشرية.")


if __name__ == "__main__":
    demo.launch(css=CSS)
