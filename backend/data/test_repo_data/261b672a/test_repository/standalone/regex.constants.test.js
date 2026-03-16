/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  STANDALONE · Regex Constants                                       │
 * │  Category : standalone (no cross-file dependencies)                 │
 * │  Tests    : 15                                                       │
 * │  Source   : src/types/constants.ts                                  │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     regex-constants
 * @category  standalone
 * @source    src/types/constants.ts
 *
 * Every regex is inlined from the source file so this suite runs with
 * zero imports from the application code.
 */

// ── Inlined from src/types/constants.ts ──────────────────────────────────────
/** @symbol EMAIL_REGEX */
const EMAIL_REGEX = /^[A-Z0-9._%+-]+@[A-Z0-9-]+\.(com)$/i;

/** @symbol PASSWORD_REGEX */
const PASSWORD_REGEX =
  /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]{8,30}$/;

/** @symbol PASSWORD_REGEX_CHANGE_PASSWORD */
const PASSWORD_REGEX_CHANGE_PASSWORD =
  /^(?=.*\d)(?=.*[!@#$%^&*])(?=.*)(?=.*[A-Z]).{8,30}$/;

/** @symbol CARD_REGEX */
const CARD_REGEX = /^[0-9\s]*$/;

/** @symbol EXPIRY_DATE_REGEX */
const EXPIRY_DATE_REGEX = /\b(0[1-9]|1[0-2])\/?([0-9]{4}|[0-9]{2})\b/;

/** @symbol SECURITY_CODE_REGEX */
const SECURITY_CODE_REGEX = /^[0-9]*$/;

/** @symbol PHONE_REGEX */
const PHONE_REGEX = /^\+?[0-9]{10,15}$/;

/** @symbol UNIQUE_USERNAME_REGEX */
const UNIQUE_USERNAME_REGEX = /^(?=.*[a-zA-Z])[a-zA-Z0-9._]+$/;

/** @symbol CARD_NUMBER_REGEX */
const CARD_NUMBER_REGEX =
  /^([0-9 ]{17,17}|[0-9 ]{18,18}|[0-9 ]{19,19})$/;

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/types/constants.ts
 * @symbol EMAIL_REGEX
 */
describe('EMAIL_REGEX', () => {
  it('accepts a valid .com email address', () => {
    expect(EMAIL_REGEX.test('user@example.com')).toBe(true);
  });

  it('rejects an email address missing the @ symbol', () => {
    expect(EMAIL_REGEX.test('userexample.com')).toBe(false);
  });

  it('rejects a non-.com domain (e.g. .org)', () => {
    expect(EMAIL_REGEX.test('user@example.org')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol PASSWORD_REGEX_CHANGE_PASSWORD
 */
describe('PASSWORD_REGEX_CHANGE_PASSWORD', () => {
  it('accepts a password meeting all requirements', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Secure@1pass')).toBe(true);
  });

  it('rejects a password without an uppercase letter', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('secure@1pass')).toBe(false);
  });

  it('rejects a password without a special character', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Secure1pass')).toBe(false);
  });

  it('rejects a password longer than 30 characters', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Secure@1pass' + 'x'.repeat(20))).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol CARD_REGEX
 */
describe('CARD_REGEX', () => {
  it('accepts a string of digits and spaces', () => {
    expect(CARD_REGEX.test('4111 1111 1111 1111')).toBe(true);
  });

  it('rejects letters inside a card number', () => {
    expect(CARD_REGEX.test('4111 ABCD 1111 1111')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol PHONE_REGEX
 */
describe('PHONE_REGEX', () => {
  it('accepts a 10-digit phone number', () => {
    expect(PHONE_REGEX.test('9876543210')).toBe(true);
  });

  it('accepts a phone number with a + country prefix', () => {
    expect(PHONE_REGEX.test('+919876543210')).toBe(true);
  });

  it('rejects a phone number shorter than 10 digits', () => {
    expect(PHONE_REGEX.test('98765')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol UNIQUE_USERNAME_REGEX
 */
describe('UNIQUE_USERNAME_REGEX', () => {
  it('accepts a valid alphanumeric username with a letter', () => {
    expect(UNIQUE_USERNAME_REGEX.test('john_doe42')).toBe(true);
  });

  it('rejects a username made entirely of digits', () => {
    expect(UNIQUE_USERNAME_REGEX.test('123456')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol CARD_NUMBER_REGEX
 */
describe('CARD_NUMBER_REGEX', () => {
  it('accepts a properly spaced 19-character card number', () => {
    // 19 chars: "4111 1111 1111 1111" (4+1+4+1+4+1+4 = 19)
    expect(CARD_NUMBER_REGEX.test('4111 1111 1111 1111')).toBe(true);
  });

  it('rejects a card number shorter than 17 characters', () => {
    expect(CARD_NUMBER_REGEX.test('4111 1111 1111')).toBe(false);
  });
});
