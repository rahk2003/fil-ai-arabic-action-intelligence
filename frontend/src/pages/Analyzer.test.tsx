import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Analyzer from "./Analyzer";
import type { Intent } from "../types";

afterEach(() => vi.restoreAllMocks());

const evidence = {
  examples: [{
    message: "ارسلي التقرير قبل الساعة التاسعة مساء", expected_label: "new_task",
    baseline_prediction: "reschedule", baseline_score: .32, baseline_latency_ms: 1.1, baseline_correct: false,
    camelbert_prediction: "new_task", camelbert_score: .91, camelbert_latency_ms: 40, camelbert_correct: true,
    reference_status: "saved_synthetic_reference_label",
  }],
  metrics: {}, confusion_matrices: {},
  methodology: { saved_prediction_rows: 24, data_provenance: "synthetic", reference_labels: "saved", independent_test: false, leakage_warning: "The 24-row holdout overlaps training.", selection_rule: "saved", available_genuine_improvements: 1, errors: { baseline: 1, camelbert: 0 } },
};

function analysis(model: "baseline" | "camelbert", label: Intent) {
  const identifier = model === "baseline"
    ? "tfidf-logreg:intent_baseline"
    : "camelbert-da:FIL_AI_CAMeLBERT";
  return {
    message: "ارسلي التقرير",
    prediction: {
      label,
      confidence: 0.61,
      uncalibrated_score: 0.61,
      probabilities: {},
      model_name: identifier,
      model_identifier: identifier,
      inference_latency_ms: model === "baseline" ? 1.2 : 22.5,
      warning: null,
    },
    actions: [{
      intent: label,
      action_text: "ارسلي التقرير",
      datetime_text: null,
      normalized_datetime: null,
      is_ambiguous: false,
      warnings: [],
      requires_action: true,
      evidence: "ارسلي التقرير",
      requires_confirmation: true,
    }],
    context: { suggestion: "new_or_unmatched", candidates: [] },
    interpretation: { action_type: label === "info_only" ? "no_action" : "create_task", action_label_ar: label === "info_only" ? "لا إجراء" : "إنشاء مهمة", classifier_label: label, extracted_intent: label, classifier_extraction_consistency: "agree", related_task_id: null, related_task_text: null, evidence: "ارسلي التقرير", proposed_change: label === "info_only" ? null : "ارسلي التقرير", missing_details: [], requires_confirmation: label !== "info_only", abstained: label === "info_only", basis: "test" },
    warnings: [],
    automatic_execution: false,
  };
}

test("Analyzer sends the selected model and renders its real metadata", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async input => new Response(JSON.stringify(
    String(input).includes("model-comparison") ? evidence : { message_id: 1, prediction_id: 2, analysis: analysis("camelbert", "new_task") }
  ), { status: 200, headers: { "Content-Type": "application/json" } }));
  render(<Analyzer />);
  fireEvent.click(screen.getByRole("radio", { name: /CAMeLBERT-DA/ }));
  fireEvent.change(screen.getByLabelText("الرسالة"), { target: { value: "ارسلي التقرير" } });
  fireEvent.click(screen.getByRole("button", { name: /حلّل بالنموذج المحدد/ }));

  await waitFor(() => expect(screen.getByRole("heading", { name: "مهمة جديدة" })).toBeInTheDocument());
  expect(screen.getByText("camelbert-da:FIL_AI_CAMeLBERT")).toBeInTheDocument();
  expect(screen.getByText("22.5 ms")).toBeInTheDocument();
  const request = fetchMock.mock.calls.find(call => call[0] === "/api/analyze")!;
  expect(request[0]).toBe("/api/analyze");
  expect(JSON.parse(String((request[1] as RequestInit).body))).toMatchObject({ model: "camelbert" });
});

test("Compare Both renders baseline and CAMeLBERT results for one API request", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async input => new Response(JSON.stringify(
    String(input).includes("model-comparison") ? evidence : {
      message_id: 7,
      same_message: true,
      results: {
        baseline: { message_id: 7, prediction_id: 8, analysis: analysis("baseline", "info_only") },
        camelbert: { message_id: 7, prediction_id: 9, analysis: analysis("camelbert", "cancellation") },
      },
    }
  ), { status: 200, headers: { "Content-Type": "application/json" } }));
  render(<Analyzer />);
  fireEvent.click(screen.getByRole("button", { name: /قارن النموذجين/ }));

  await waitFor(() => expect(screen.getByText("tfidf-logreg:intent_baseline")).toBeInTheDocument());
  expect(screen.getByText("camelbert-da:FIL_AI_CAMeLBERT")).toBeInTheDocument();
  expect(screen.getByText(/شُغّلت على النص نفسه حرفيًا/)).toBeInTheDocument();
  expect(globalThis.fetch).toHaveBeenCalledWith("/api/analyze/compare", expect.objectContaining({ method: "POST" }));
});

test("Before vs After lists only saved genuine improvements and reruns both models", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async input => new Response(JSON.stringify(
    String(input).includes("model-comparison") ? evidence : {
      message_id: 10, same_message: true,
      results: {
        baseline: { message_id: 10, prediction_id: 11, analysis: analysis("baseline", "reschedule") },
        camelbert: { message_id: 10, prediction_id: 12, analysis: analysis("camelbert", "new_task") },
      },
    }
  ), { status: 200, headers: { "Content-Type": "application/json" } }));
  render(<Analyzer />);
  await waitFor(() => expect(screen.getByText("فروق تشغيل محفوظة للتشخيص")).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "تشغيل المقارنة" }));
  await waitFor(() => expect(screen.getByText("صحيح بحسب المرجع")).toBeInTheDocument());
  expect(screen.getByText(/غير صحيح — المرجع/)).toBeInTheDocument();
});
