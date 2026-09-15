/**
 * CSV export, in the browser, with no dependency.
 *
 * ENTERPRISE TOOLS ALWAYS HAVE THIS AND ITS ABSENCE IS NOTICED. What leaves
 * here is what is on screen, INCLUDING the absence words: a cell reading "not
 * enough data to say" exports as that sentence and not as an empty cell,
 * because an empty cell in a spreadsheet is read as zero by the next person to
 * open it, which is the collapse the whole system is built to prevent, escaping
 * through the export button.
 */
export function toCsv(headers: string[], rows: string[][]): string {
  const escape = (cell: string) =>
    /[",\n]/.test(cell) ? `"${cell.replace(/"/g, '""')}"` : cell;
  return [headers, ...rows]
    .map((row) => row.map(escape).join(','))
    .join('\n');
}

export function downloadCsv(name: string, headers: string[], rows: string[][]) {
  const blob = new Blob([toCsv(headers, rows)],
                        { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
