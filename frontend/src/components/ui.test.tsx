import { render, screen } from "@testing-library/react";
import { EmptyState, MetricCard } from "./ui";

test("MetricCard renders observed value and note", () => {
  render(<MetricCard label="Macro-F1" value="0.494" note="Synthetic only" />);
  expect(screen.getByText("Macro-F1")).toBeInTheDocument();
  expect(screen.getByText("0.494")).toBeInTheDocument();
  expect(screen.getByText("Synthetic only")).toBeInTheDocument();
});

test("EmptyState communicates the empty condition", () => {
  render(<EmptyState title="لا توجد مهام" text="أنشئ أول مهمة" />);
  expect(screen.getByText("لا توجد مهام")).toBeInTheDocument();
  expect(screen.getByText("أنشئ أول مهمة")).toBeInTheDocument();
});
