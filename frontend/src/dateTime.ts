/** Validate the ISO calendar date from an `<input type="date">`.
 * The returned value is never converted through a timezone-bearing Date.
 */
export function dateOnlyForApi(value: string, fieldLabel: string): string {
  const input = value.trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(input);
  if (!match) throw new Error(`${fieldLabel} is required and must be a valid date.`);
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText), month = Number(monthText), day = Number(dayText);
  const check = new Date(year, month - 1, day);
  if (month < 1 || month > 12 || day < 1 || check.getFullYear() !== year || check.getMonth() !== month - 1 || check.getDate() !== day) {
    throw new Error(`${fieldLabel} is invalid.`);
  }
  return input;
}

/** Render an API `YYYY-MM-DD` date as DD-MM-YYYY without a timezone shift. */
export function formatDateOnly(value: unknown): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ""));
  return match ? `${match[3]}-${match[2]}-${match[1]}` : "-";
}

/** Render an API timestamp as DD-MM-YYYY HH:MM:SS without a timezone shift. */
export function formatDateTime(value: unknown): string {
  if (!value) return "-";
  const str = String(value);
  const match = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/.exec(str);
  if (match) {
    const [, y, m, d, hh, mm, ss] = match;
    return `${d}-${m}-${y} ${hh}:${mm}${ss ? `:${ss}` : ""}`;
  }
  return formatDateOnly(value);
}
