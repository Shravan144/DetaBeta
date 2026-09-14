const TARGET_HINTS = ["target", "label", "class", "outcome", "survived", "churn", "y"];

export function pickDefaultTarget(columns: string[]): string | null {
  return columns.find((column) => TARGET_HINTS.includes(column.toLowerCase())) ?? null;
}
