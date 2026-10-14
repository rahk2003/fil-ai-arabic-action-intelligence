import type { Analytics, AnalyzeResponse, CalendarResponse, CompareAnalyzeResponse, ErrorAnalysisData, Intent, ModelChoice, ModelComparisonEvidence, ModelStatus, Priority, Task, TaskDetail, TaskEvent, TaskImportPreview, TaskImportRow, TaskSuggestion } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail ?? `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; database: string; model: string; model_warning: string | null; models: Record<ModelChoice, ModelStatus>; embeddings: { enabled: boolean; loaded: boolean; model_name: string; method: string; device: string | null; dimension: number | null; warning: string | null } | null }>("/api/health"),
  analytics: () => request<Analytics>("/api/analytics"),
  datasetSamples: (dataset: "baseline_96" | "massive_ar_sa" | "saudi_challenge", query = "", limit = 25) => request<{ dataset: string; source_file: string; rows: Array<Record<string, unknown>>; returned: number }>(`/api/datasets/samples?dataset=${dataset}&query=${encodeURIComponent(query)}&limit=${limit}`),
  analyze: (message: string, referenceTime?: string, model: ModelChoice = "baseline") => request<AnalyzeResponse>("/api/analyze", {
    method: "POST", body: JSON.stringify({ message, reference_time: referenceTime || null, model }),
  }),
  compareModels: (message: string, referenceTime?: string) => request<CompareAnalyzeResponse>("/api/analyze/compare", {
    method: "POST", body: JSON.stringify({ message, reference_time: referenceTime || null }),
  }),
  analyzeConversation: (messages: string[], referenceTime?: string, model: ModelChoice = "baseline") => request<{ conversation_id: number; analyses: Array<Record<string, unknown>>; automatic_task_mutations: boolean }>("/api/conversations/analyze", {
    method: "POST", body: JSON.stringify({ messages, reference_time: referenceTime || null, model }),
  }),
  tasks: (status?: string) => request<Task[]>(`/api/tasks${status ? `?status=${status}` : ""}`),
  calendar: (start: string, end: string, includeHistory = true) => request<CalendarResponse>(`/api/calendar?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&include_history=${includeHistory}`),
  task: (id: number) => request<TaskDetail>(`/api/tasks/${id}`),
  createTask: (data: { title: string; description?: string; deadline?: string; priority: Priority; original_message?: string; model_version?: string; confirmed: boolean }) => request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(data) }),
  previewTaskImport: (filename: string, contentBase64: string) => request<TaskImportPreview>("/api/tasks/import/preview", { method: "POST", body: JSON.stringify({ filename, content_base64: contentBase64 }) }),
  commitTaskImport: (rows: TaskImportRow[]) => request<{ imported: number; skipped: number; failed: number; task_ids: number[]; skipped_rows: Array<{ row_number: number; reason: string }> }>("/api/tasks/import/commit", { method: "POST", body: JSON.stringify({ rows, confirmed: true }) }),
  taskImportTemplate: (format: "csv" | "xlsx") => request<{ filename: string; content_base64: string }>(`/api/tasks/import/template?format=${format}`),
  updateTask: (id: number, data: { event_type: string; title?: string; description?: string; deadline?: string; priority?: Priority; evidence?: string; reason?: string; confirmed: boolean }) => request<Task>(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  taskHistory: (id: number) => request<TaskEvent[]>(`/api/tasks/${id}/history`),
  taskSuggestions: (status = "pending") => request<TaskSuggestion[]>(`/api/task-suggestions?status=${status}`),
  confirmSuggestion: (id: number, data: { confirmed: boolean; task_id?: number; title?: string; description?: string; deadline?: string; priority?: Priority; reason?: string }) => request<Task>(`/api/task-suggestions/${id}/confirm`, { method: "POST", body: JSON.stringify(data) }),
  rejectSuggestion: (id: number, data: { confirmed: boolean; reason?: string }) => request<TaskSuggestion>(`/api/task-suggestions/${id}/reject`, { method: "POST", body: JSON.stringify(data) }),
  modelComparisonEvidence: (limit = 10) => request<ModelComparisonEvidence>(`/api/evaluation/model-comparison?limit=${limit}`),
  errorAnalysis: () => request<ErrorAnalysisData>("/api/evaluation/errors"),
  feedback: (data: { prediction_id?: number; message_id?: number; corrected_intent?: Intent; reviewer?: string; notes?: string; confirmed: boolean }) => request<{ id: number; review_status: string; online_retraining: boolean }>("/api/feedback", { method: "POST", body: JSON.stringify(data) }),
};
