import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Tasks from "./Tasks";

const task = {
  id: 1, conversation_id: null, title: "إرسال التقرير", description: "إرسال النسخة النهائية",
  status: "pending", workflow_status: "rescheduled", priority: "high",
  deadline: "2026-10-16T14:00:00+03:00", original_deadline: "2026-10-15T10:00:00+03:00",
  original_message_id: 10, original_message: "أرسلي التقرير الخميس الساعة 10 صباحًا",
  source: "api", received_at: "2026-10-14T09:00:00+03:00",
  last_change_summary: "تم تغيير الموعد من الخميس 10 صباحًا إلى الخميس 2 ظهرًا.",
  overdue: false, model_version: "camelbert-da:FIL_AI_CAMeLBERT",
  created_at: "2026-10-14T09:00:00+03:00", updated_at: "2026-10-14T10:00:00+03:00",
};

afterEach(() => vi.restoreAllMocks());

test("Task dashboard renders persisted table fields and pending review", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("task-suggestions") ? [{
      id: 2, message_id: 11, prediction_id: 12, task_id: 1, suggestion_type: "cancellation",
      suggested_title: "إرسال التقرير", description: null, current_deadline: task.deadline,
      proposed_deadline: null, evidence: "خلاص ألغوا إرسال التقرير", reason: "ربط النظام الرسالة بمهمة موجودة اعتمادًا على سياق الرسالة؛ يلزم التأكيد.",
      review_status: "pending", model_identifier: "camelbert-da:FIL_AI_CAMeLBERT",
      predicted_intent: "cancellation", uncalibrated_score: 0.88,
      created_at: "2026-10-14T11:00:00+03:00", resolved_at: null,
    }] : [task];
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });

  render(<Tasks />);
  await waitFor(() => expect(screen.getAllByText("إرسال التقرير").length).toBeGreaterThan(0));
  expect(screen.getByText("الموعد الأصلي")).toBeInTheDocument();
  expect(screen.getByText("آخر تغيير")).toBeInTheDocument();
  expect(screen.getByText("إلغاء محتمل")).toBeInTheDocument();
  expect(screen.getByText("تم تغيير الموعد من الخميس 10 صباحًا إلى الخميس 2 ظهرًا.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("بحث في المهام"), { target: { value: "غير موجود" } });
  expect(screen.getByText("لا توجد مهام مطابقة")).toBeInTheDocument();
});

test("Task row opens persisted history in the details panel", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    let body: unknown = [];
    if (url.endsWith("/api/tasks")) body = [task];
    if (url.endsWith("/api/tasks/1")) body = { ...task, history: [{
      id: 3, task_id: 1, event_type: "rescheduled", old_value: JSON.stringify({ deadline: task.original_deadline }),
      new_value: JSON.stringify({ deadline: task.deadline }), evidence: "خلوه الخميس 2",
      summary: task.last_change_summary, related_message_id: 11, related_message: "خلوه الخميس 2",
      model_prediction_id: 12, model_intent: "reschedule", model_identifier: "camelbert-da:FIL_AI_CAMeLBERT",
      confirmed: 1, created_at: "2026-10-14T10:00:00+03:00",
    }] };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });

  render(<Tasks />);
  await waitFor(() => expect(screen.getByText("إرسال التقرير")).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /التفاصيل/ }));
  await waitFor(() => expect(screen.getByText("سجل التغييرات والرسائل اللاحقة")).toBeInTheDocument());
  expect(screen.getByText("«خلوه الخميس 2»")).toBeInTheDocument();
  expect(screen.getByText(/تنبؤ النموذج:/)).toBeInTheDocument();
});
