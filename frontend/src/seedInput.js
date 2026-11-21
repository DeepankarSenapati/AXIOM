export const MAX_SEED = 4_294_967_295;
const SEED_ERROR = "Enter a whole number from 0 to 4,294,967,295.";

// Keep invalid text visible for correction; valid input is always numeric.
export function parseSeedInput(input) {
  const text = String(input);
  if (!/^[0-9]+$/.test(text)) return { value: text, error: SEED_ERROR };
  const value = Number(text);
  if (!Number.isSafeInteger(value) || value > MAX_SEED) return { value: text, error: SEED_ERROR };
  return { value, error: "" };
}
