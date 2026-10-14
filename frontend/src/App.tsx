import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";

const Overview = lazy(() => import("./pages/Overview"));
const Calendar = lazy(() => import("./pages/Calendar"));
const Analyzer = lazy(() => import("./pages/Analyzer"));
const Tasks = lazy(() => import("./pages/Tasks"));
const Conversations = lazy(() => import("./pages/Conversations"));
const Evaluation = lazy(() => import("./pages/Evaluation"));
const Dataset = lazy(() => import("./pages/Dataset"));
const Feedback = lazy(() => import("./pages/Feedback"));
const ErrorAnalysis = lazy(() => import("./pages/ErrorAnalysis"));

export default function App() {
  return <Suspense fallback={<div className="p-8 text-center text-slate-500">جاري تحميل الصفحة…</div>}><Routes><Route element={<Layout />}><Route index element={<Calendar />} /><Route path="tasks" element={<Tasks />} /><Route path="analyzer" element={<Analyzer />} /><Route path="conversations" element={<Conversations />} /><Route path="overview" element={<Overview />} /><Route path="evaluation" element={<Evaluation />} /><Route path="dataset" element={<Dataset />} /><Route path="errors" element={<ErrorAnalysis />} /><Route path="feedback" element={<Feedback />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes></Suspense>;
}
