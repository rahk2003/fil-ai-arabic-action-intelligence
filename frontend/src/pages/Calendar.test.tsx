import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CalendarPage from "./Calendar";

afterEach(() => vi.restoreAllMocks());

const task = {
  id: 1, conversation_id: null, title: "اجتماع المشروع", description: "مراجعة الخطة",
  status: "pending", workflow_status: "rescheduled", priority: "high",
  deadline: "2026-10-22T14:00:00+03:00", original_deadline: "2026-10-18T10:00:00+03:00",
  original_message_id: 1, original_message: "اجتماع المشروع يوم الأحد الساعة 10 صباحًا.", source: "api",
  received_at: "2026-10-14T09:00:00+03:00", last_change_summary: "تم تغيير الموعد.", overdue: false,
  model_version: "tfidf-logreg:intent_baseline", created_at: "2026-10-14T09:00:00+03:00", updated_at: "2026-10-14T10:00:00+03:00",
};
const calendar = {
  timezone: "Asia/Riyadh", range_start: "2026-09-27T00:00:00+03:00", range_end: "2026-11-08T00:00:00+03:00",
  events: [
    { id: "old", task_id: 1, suggestion_id: null, kind: "historical", color: "red", label: "الموعد القديم", title: "اجتماع المشروع — الموعد القديم", starts_at: task.original_deadline, recorded_at: task.updated_at, task_status: "rescheduled", is_current: false, source_message: "تم تغيير الموعد" },
    { id: "new", task_id: 1, suggestion_id: null, kind: "current", color: "green", label: "الموعد المحدّث", title: "اجتماع المشروع", starts_at: task.deadline, recorded_at: task.updated_at, task_status: "rescheduled", is_current: true, source_message: task.original_message },
  ], unscheduled_tasks: [], pending_unscheduled: [],
};

test("Calendar renders historical red and current green markers for one task", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
    const url = String(input);
    const body = url.includes("/api/tasks/1") ? { ...task, history: [{ id: 1, task_id: 1, event_type: "rescheduled", old_value: JSON.stringify({ deadline: task.original_deadline }), new_value: JSON.stringify({ deadline: task.deadline }), evidence: "أجلوه", summary: "تم تغيير الموعد", related_message_id: 2, related_message: "أجلوه للخميس", model_prediction_id: 3, model_intent: "reschedule", model_identifier: "tfidf-logreg:intent_baseline", confirmed: 1, created_at: task.updated_at }] } : calendar;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  render(<CalendarPage />);
  await waitFor(() => expect(screen.getByText("اجتماع المشروع — الموعد القديم")).toBeInTheDocument());
  expect(screen.getAllByText("اجتماع المشروع").length).toBeGreaterThan(0);
  expect(screen.getByText("موعد قديم")).toBeInTheDocument();
  expect(screen.getByText("موعد محدّث")).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole("button", { name: /اجتماع المشروع/ }).at(-1)!);
  await waitFor(() => expect(screen.getByText("المصدر والمواعيد")).toBeInTheDocument());
  expect(screen.getByText("السجل الكامل")).toBeInTheDocument();
});

test("Calendar supports day view, today navigation, search, and history toggle", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify(calendar), { status: 200, headers: { "Content-Type": "application/json" } }));
  render(<CalendarPage />);
  await waitFor(() => expect(screen.getByText("اجتماع المشروع — الموعد القديم")).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "يومي" }));
  fireEvent.click(screen.getByRole("button", { name: "اليوم" }));
  fireEvent.change(screen.getByLabelText("البحث في التقويم"), { target: { value: "غير موجود" } });
  fireEvent.click(screen.getByRole("button", { name: "عرض السجل الكامل" }));
  await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("include_history=false"), expect.any(Object)));
});
