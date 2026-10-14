export type Intent = "new_task" | "reschedule" | "cancellation" | "info_only";
export type ModelChoice = "baseline" | "camelbert";
export type Priority = "low" | "medium" | "high" | "urgent";
export type TaskStatus = "pending" | "completed" | "canceled";
export type WorkflowStatus = "pending" | "in_progress" | "completed" | "rescheduled" | "canceled";

export interface Prediction {
  label: Intent;
  confidence: number | null;
  uncalibrated_score: number | null;
  probabilities: Record<string, number>;
  model_name: string;
  model_identifier: string;
  inference_latency_ms: number;
  warning: string | null;
}
export interface ActionItem {
  intent: Intent;
  action_text: string | null;
  datetime_text: string | null;
  normalized_datetime: string | null;
  is_ambiguous: boolean;
  warnings: string[];
  requires_action: boolean;
  evidence: string;
  requires_confirmation: boolean;
}
export interface Analysis {
  message: string;
  prediction: Prediction;
  actions: ActionItem[];
  context: { suggestion: string; candidates: Array<{ task_id: number | string; task_text: string; score: number; lexical_score?: number; semantic_score?: number | null; is_probable_duplicate: boolean; basis?: string; supporting_evidence?: { shared_terms: string[]; recent_context: boolean } }>; matching_method?: "embeddings" | "lexical_fallback" | "no_candidates"; embedding_model?: string | null; embedding_status?: { enabled: boolean; loaded: boolean; model_name: string | null; method: string; device: string | null; dimension: number | null; warning: string | null } };
  interpretation: { action_type: "create_task" | "update_task_scope" | "update_task_requirement" | "update_task_priority" | "reschedule_task" | "cancel_task" | "mark_complete" | "add_instruction" | "no_action" | "needs_clarification"; action_label_ar: string; classifier_label: Intent; extracted_intent: Intent | null; classifier_extraction_consistency: "agree" | "conflict" | "unsupported_classifier_label"; related_task_id: number | string | null; related_task_text: string | null; evidence: string; proposed_change: string | null; missing_details: string[]; requires_confirmation: boolean; abstained: boolean; basis: string };
  warnings: string[];
  automatic_execution: boolean;
}
export interface AnalyzeResponse { message_id: number; prediction_id: number; suggestion_id: number | null; analysis: Analysis; }
export interface CompareAnalyzeResponse {
  message_id: number;
  results: Record<ModelChoice, AnalyzeResponse>;
  same_message: boolean;
}
export interface Task {
  id: number; conversation_id: number | null; title: string; description: string | null; status: TaskStatus; workflow_status: WorkflowStatus; priority: Priority;
  deadline: string | null; original_deadline: string | null; original_message_id: number | null;
  original_message: string | null; source: string | null; received_at: string | null;
  last_change_summary: string | null; overdue: boolean; model_version: string | null;
  created_at: string; updated_at: string;
}
export interface TaskEvent { id: number; task_id: number; event_type: string; old_value: string | null; new_value: string | null; evidence: string | null; summary: string | null; related_message_id: number | null; related_message: string | null; model_prediction_id: number | null; model_intent: string | null; model_identifier: string | null; confirmed: number; created_at: string; }
export interface TaskDetail extends Task { history: TaskEvent[]; }
export interface TaskSuggestion {
  id: number; message_id: number; prediction_id: number; task_id: number | null;
  suggestion_type: "new_task" | "reschedule" | "cancellation";
  suggested_title: string | null; description: string | null; current_deadline: string | null;
  proposed_deadline: string | null; evidence: string; reason: string | null;
  review_status: "pending" | "confirmed" | "rejected"; model_identifier: string | null;
  predicted_intent: Intent | null; uncalibrated_score: number | null; created_at: string; resolved_at: string | null;
}
export interface TaskImportRow {
  row_number: number; title: string; description: string | null; deadline: string | null;
  priority: Priority; status: "pending" | "in_progress" | "completed" | "canceled";
  notes: string | null; valid: boolean; duplicate: boolean; errors: string[];
}
export interface TaskImportPreview {
  filename: string; columns: string[]; mapping: Record<string, string>; rows: TaskImportRow[];
  summary: { total: number; valid: number; duplicates: number; invalid: number };
}
export type CalendarColor = "red" | "green" | "purple" | "yellow" | "gray";
export interface CalendarEvent {
  id: string; task_id: number | null; suggestion_id: number | null;
  kind: "current" | "historical" | "pending"; color: CalendarColor;
  label: string; title: string; starts_at: string; recorded_at: string | null;
  task_status: string; is_current: boolean; source_message: string | null;
}
export interface CalendarResponse {
  timezone: "Asia/Riyadh"; range_start: string; range_end: string;
  events: CalendarEvent[]; unscheduled_tasks: Task[]; pending_unscheduled: TaskSuggestion[];
}
export interface ComparisonExample {
  message: string; expected_label: Intent;
  baseline_prediction: Intent; baseline_score: number; baseline_latency_ms: number; baseline_correct: boolean;
  camelbert_prediction: Intent; camelbert_score: number; camelbert_latency_ms: number; camelbert_correct: boolean;
  reference_status: string;
}
export interface ModelComparisonEvidence {
  examples: ComparisonExample[];
  metrics: Record<string, Record<string, string | number>>;
  confusion_matrices: Record<string, Record<string, Record<string, number>>>;
  methodology: {
    saved_prediction_rows: number; data_provenance: string; reference_labels: string;
    independent_test: boolean; leakage_warning: string; selection_rule: string;
    available_genuine_improvements: number; errors: Record<string, number>;
  };
}
export interface ErrorAnalysisData {
  failures: Array<{ message: string; expected_label: Intent | null; baseline_prediction: Intent | null; camelbert_prediction: Intent | null; category: string; explanation: string | null; source: string; validity: string; synthetic: boolean }>;
  sections: Record<string, { saved_errors?: number; reported_errors?: number; rows?: number; independent_for_baseline?: boolean; independent_comparison?: boolean; prediction_rows_available?: boolean; human_verified?: boolean; note: string }>;
}
export interface ModelStatus {
  identifier: string; backend: string; path?: string; available: boolean; loaded: boolean;
  device: string | null; labels: Record<string, string> | string[] | null; warning: string | null;
}
export interface Analytics {
  model: { active: string; warning: string | null; transformer_trained: boolean; available: Record<ModelChoice, ModelStatus>; camelbert_reported_accuracy: number; camelbert_metric_provenance: string; reported_colab_125: { baseline_accuracy: number; baseline_macro_f1: number; camelbert_accuracy: number; camelbert_macro_f1: number } };
  baseline: { accuracy?: number; macro_precision?: number; macro_recall?: number; macro_f1?: number; holdout_rows?: number; misclassifications?: number };
  class_metrics: Array<{ intent: Intent; precision: number; recall: number; f1_score: number; support: number }>;
  confusion_matrix: Array<Record<string, string | number>>;
  model_comparison: Array<{ model: string; status: string; accuracy: number; macro_f1: number; weighted_f1: number }>;
  dataset: { total_rows?: number; split_counts?: Record<string, number>; scenarios?: number; intents?: number; normalized_duplicate_groups?: number; date_or_time_annotated_rows?: number; warning?: string; registry?: Array<{ key: string; name: string; examples: number; source: string; label_schema: string; language: string; status: "synthetic" | "published" | "human_reviewed"; usage: string; models: string[]; splits: string; license: string; limitations: string; file_available: boolean }> };
  context_matching?: { model: { model_name: string; device: string; dimension: number }; data_provenance: string; validation_rows: number; test_rows: number; thresholds: { lexical: number; embeddings: number }; test: { lexical: { accuracy: number; precision: number; recall: number; f1: number }; embeddings: { accuracy: number; precision: number; recall: number; f1: number } }; false_matches_test: { lexical: number; embeddings: number }; limitations: string[] };
  application: { task_counts: Record<TaskStatus, number>; prediction_count: number; feedback_candidate_count: number };
  limitations: string[];
}
