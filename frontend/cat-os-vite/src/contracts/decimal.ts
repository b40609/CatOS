/**
 * Decimal strings exactly as the backend serialises them ("999.91375990").
 * The UI formats them with string arithmetic only; it never converts them to
 * JS numbers to add, subtract or compare money.
 */
export type DecimalString = string;
