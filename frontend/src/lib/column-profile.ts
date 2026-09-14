export type NamedColumnProfile = { name: string };

export function findColumnProfile<T extends NamedColumnProfile>(columns: T[], name: string): T | undefined {
  return columns.find((column) => column.name === name);
}
