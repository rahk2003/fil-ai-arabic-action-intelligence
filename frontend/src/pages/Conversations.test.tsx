import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Conversations from "./Conversations";

afterEach(() => vi.restoreAllMocks());

const task = { id: 5, conversation_id: 1, title: "حلل كل البيانات", description: "حلل كل البيانات", status: "pending", workflow_status: "pending", priority: "medium", deadline: null, original_deadline: null, original_message_id: 1, original_message: "حلل كل البيانات", source: "conversation_api", received_at: "2026-10-14T12:00:00+03:00", last_change_summary: "تم الإنشاء", overdue: false, model_version: "tfidf-logreg:intent_baseline", created_at: "2026-10-14T12:00:00+03:00", updated_at: "2026-10-14T12:00:00+03:00" };
function analysis(message: string, label: string, actionType: string, related: string | null) {
  return { message, prediction: { label, confidence: .4, uncalibrated_score: .4, probabilities: {}, model_name: "tfidf-logreg:intent_baseline", model_identifier: "tfidf-logreg:intent_baseline", inference_latency_ms: 1.2, warning: null }, actions: [{ intent: actionType === "create_task" ? "new_task" : "new_task", action_text: message, datetime_text: null, normalized_datetime: null, is_ambiguous: false, warnings: [], requires_action: true, evidence: message, requires_confirmation: true }], context: { suggestion: "possibly_related", candidates: [], matching_method: "embeddings", embedding_model: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" }, interpretation: { action_type: actionType, action_label_ar: actionType, classifier_label: label, extracted_intent: "new_task", classifier_extraction_consistency: label === "cancellation" ? "conflict" : "agree", related_task_id: related, related_task_text: related ? "حلل كل البيانات" : null, evidence: message, proposed_change: message, missing_details: actionType === "update_task_scope" ? ["تحديد الجزء المطلوب"] : [], requires_confirmation: true, abstained: false, basis: "test" }, warnings: [], automatic_execution: false };
}

test("Conversation keeps raw classification separate and persists scope update on the same task", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    let body: unknown = [];
    if (url === "/api/conversations/analyze") body = { conversation_id: 1, automatic_task_mutations: false, analyses: [
      { sequence: 1, message_id: 1, prediction_id: 1, suggestion_id: 11, analysis: analysis("حلل كل البيانات", "new_task", "create_task", null), before_after: null },
      { sequence: 2, message_id: 2, prediction_id: 2, suggestion_id: null, analysis: analysis("خلاص حلل بس جزء", "cancellation", "update_task_scope", "conversation-1"), before_after: { before: "حلل كل البيانات", after: "خلاص حلل بس جزء", change_type: "update_task_scope", related_task_id: "conversation-1", missing_details: ["تحديد الجزء المطلوب"], requires_confirmation: true } },
    ] };
    else if (url.includes("/task-suggestions/11/confirm") || (url === "/api/tasks/5" && init?.method === "PATCH")) body = task;
    else if (url === "/api/tasks") body = url.includes("status") ? [] : [];
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  render(<Conversations />);
  fireEvent.click(screen.getByRole("button", { name: "تحليل المحادثة" }));
  await waitFor(() => expect(screen.getAllByText("تعديل نطاق المهمة", { exact: true }).length).toBe(2));
  expect(screen.getByText("إلغاء", { exact: true })).toBeInTheDocument();
  expect(screen.getAllByText(/تمثيلات دلالية محلية/).length).toBe(2);
  expect(screen.getByText(/يوجد تعارض بين التصنيف الخام/)).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole("button", { name: "تأكيد" })[0]);
  await waitFor(() => expect(screen.getByText("تم الحفظ في سجل المهمة")).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "تأكيد" }));
  await waitFor(() => expect(screen.getAllByText("تم الحفظ في سجل المهمة").length).toBe(2));
  const update = fetchMock.mock.calls.find(call => call[0] === "/api/tasks/5" && (call[1] as RequestInit)?.method === "PATCH");
  expect(update).toBeTruthy();
  expect(JSON.parse(String((update![1] as RequestInit).body))).toMatchObject({ event_type: "edited", evidence: "خلاص حلل بس جزء", confirmed: true });
});
