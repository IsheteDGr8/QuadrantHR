/**
 * PII redaction for HR Copilot surfaces (chat, activity, tickets, work queue).
 *
 * Masks common US/intl identity patterns in free text while leaving structure
 * intact so the UI still reads naturally. Prefer applying this at display and
 * API boundaries — never rely on the model alone to avoid leaking PII.
 */

export type PiiKind =
  | "ssn"
  | "credit_card"
  | "phone"
  | "email"
  | "dob"
  | "passport"
  | "bank_account"
  | "routing"
  | "ip"

export type RedactOptions = {
  /** Which detectors to run. Default: all. */
  kinds?: PiiKind[]
  /** When true, keep the last 4 digits of SSN / card / account. Default true. */
  keepLast4?: boolean
  /** Marker prefix, e.g. [REDACTED:SSN]. */
  marker?: (kind: PiiKind) => string
}

const DEFAULT_KINDS: PiiKind[] = [
  "ssn",
  "credit_card",
  "phone",
  "email",
  "dob",
  "passport",
  "bank_account",
  "routing",
  "ip",
]

function defaultMarker(kind: PiiKind): string {
  return `[REDACTED:${kind.toUpperCase()}]`
}

/** SSN: 123-45-6789 or 123456789 (not starting with 000/666/9xx). */
const SSN_RE = /\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b/g

/** Credit card: 13–19 digits, often grouped. Luhn-checked in replace. */
const CC_CANDIDATE_RE =
  /\b(?:\d[ -]*?){13,19}\b/g

/** US/CA-ish phones; avoid matching bare 7-digit IDs when possible. */
const PHONE_RE =
  /(?<!\w)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)/g

const EMAIL_RE =
  /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi

/** DOB-ish: labeled dates or MM/DD/YYYY. */
const DOB_LABELED_RE =
  /\b(?:dob|date\s*of\s*birth|born(?:\s+on)?)\s*[:\-]?\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b/gi
const DOB_NUMERIC_RE =
  /\b(?:0?[1-9]|1[0-2])[\/\-](?:0?[1-9]|[12]\d|3[01])[\/\-](?:19|20)\d{2}\b/g

const PASSPORT_RE =
  /\b(?:passport(?:\s*(?:no|number|#))?)\s*[:\-]?\s*[A-Z0-9]{6,9}\b/gi

const ROUTING_RE =
  /\b(?:routing(?:\s*(?:no|number|#))?|aba)\s*[:\-]?\s*\d{9}\b/gi

const BANK_ACCT_RE =
  /\b(?:account(?:\s*(?:no|number|#))?|acct)\s*[:\-]?\s*\d{6,17}\b/gi

const IP_RE =
  /\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b/g

function luhnOk(digits: string): boolean {
  let sum = 0
  let alt = false
  for (let i = digits.length - 1; i >= 0; i--) {
    let n = Number(digits[i])
    if (alt) {
      n *= 2
      if (n > 9) n -= 9
    }
    sum += n
    alt = !alt
  }
  return sum % 10 === 0
}

function last4Mask(raw: string, keepLast4: boolean, kind: PiiKind, marker: (k: PiiKind) => string) {
  if (!keepLast4) return marker(kind)
  const digits = raw.replace(/\D/g, "")
  if (digits.length < 4) return marker(kind)
  return `${marker(kind)}…${digits.slice(-4)}`
}

export function redactPii(input: string, options: RedactOptions = {}): string {
  if (!input) return input
  const kinds = new Set(options.kinds ?? DEFAULT_KINDS)
  const keepLast4 = options.keepLast4 !== false
  const marker = options.marker ?? defaultMarker
  let text = input

  if (kinds.has("ssn")) {
    text = text.replace(SSN_RE, (m) => last4Mask(m, keepLast4, "ssn", marker))
  }
  if (kinds.has("credit_card")) {
    text = text.replace(CC_CANDIDATE_RE, (m, offset: number) => {
      const digits = m.replace(/\D/g, "")
      if (digits.length < 13 || digits.length > 19) return m
      // Chat ids are `chat-<unix-ms>-xxxx` — 13 ungrouped digits look like a PAN
      // and Luhn can pass. Never treat those as cards.
      if (digits.length === 13 && !/[ -]/.test(m)) return m
      const before = text.slice(Math.max(0, offset - 5), offset)
      if (/chat-?$/i.test(before)) return m
      if (!luhnOk(digits)) return m
      return last4Mask(m, keepLast4, "credit_card", marker)
    })
  }
  if (kinds.has("email")) {
    text = text.replace(EMAIL_RE, () => marker("email"))
  }
  if (kinds.has("phone")) {
    text = text.replace(PHONE_RE, (m) => last4Mask(m, keepLast4, "phone", marker))
  }
  if (kinds.has("dob")) {
    text = text.replace(DOB_LABELED_RE, () => marker("dob"))
    text = text.replace(DOB_NUMERIC_RE, () => marker("dob"))
  }
  if (kinds.has("passport")) {
    text = text.replace(PASSPORT_RE, () => marker("passport"))
  }
  if (kinds.has("routing")) {
    text = text.replace(ROUTING_RE, () => marker("routing"))
  }
  if (kinds.has("bank_account")) {
    text = text.replace(BANK_ACCT_RE, () => marker("bank_account"))
  }
  if (kinds.has("ip")) {
    text = text.replace(IP_RE, () => marker("ip"))
  }
  return text
}

/** Deep-redact every string leaf in a JSON-like value. */
export function redactPiiDeep<T>(value: T, options?: RedactOptions): T {
  if (value == null) return value
  if (typeof value === "string") return redactPii(value, options) as T
  if (Array.isArray(value)) {
    return value.map((v) => redactPiiDeep(v, options)) as T
  }
  if (typeof value === "object") {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      // Never leak raw values under known sensitive field names.
      const key = k.toLowerCase()
      if (
        /(ssn|social|taxid|tax_id|passport|credit.?card|card.?number|cvv|routing|account.?number|dob|dateofbirth|password|secret|api[_-]?key)/i.test(
          key,
        ) &&
        typeof v === "string"
      ) {
        out[k] = redactPii(v, options)
      } else {
        out[k] = redactPiiDeep(v, options)
      }
    }
    return out as T
  }
  return value
}

export function containsPii(input: string, options?: RedactOptions): boolean {
  if (!input) return false
  return redactPii(input, options) !== input
}
