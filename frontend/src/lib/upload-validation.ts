export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export function validateCsvUpload(file: Pick<File, "name" | "size">): string | null {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    return "Choose a CSV file.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "CSV files must be 25 MB or smaller.";
  }
  return null;
}
