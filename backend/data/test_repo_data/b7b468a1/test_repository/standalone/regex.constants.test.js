/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  STANDALONE · Regex Constants                                       │
 * │  Category : standalone (no cross-file dependencies)                 │
 * │  Tests    : 56                                                       │
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
const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.com$/;

/** @symbol USERNAME_REGEX */
const USERNAME_REGEX = /^[a-zA-Z][a-zA-Z ]{2,24}$/;

/** @symbol PASSWORD_REGEX */
const PASSWORD_REGEX =
  /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]{10,30}$/;

/** @symbol PASSWORD_REGEX_CHANGE_PASSWORD */
const PASSWORD_REGEX_CHANGE_PASSWORD =
  /^(?=.*\d)(?=.*[!@#$%^&*])(?=.*)(?=.*[A-Z]).{8,30}$/;

/** @symbol CARD_REGEX — current source: digits only, no spaces */
const CARD_REGEX = /^[0-9]*$/;

/** @symbol EXPIRY_DATE_REGEX */
const EXPIRY_DATE_REGEX = /\b(0[1-9]|1[0-2])\/?([0-9]{4}|[0-9]{2})\b/;

/** @symbol SECURITY_CODE_REGEX */
const SECURITY_CODE_REGEX = /^[0-9]*$/;

/** @symbol FULL_CARD_REGEX */
const FULL_CARD_REGEX =
  /^([0-9 ]{16,16}|[0-9 ]{17,17}|[0-9 ]{18,18}|[0-9 ]{19,19})$/;

/** @symbol PHONE_REGEX */
const PHONE_REGEX = /^[0-9]{10,15}$/;

/** @symbol UNIQUE_USERNAME_REGEX */
const UNIQUE_USERNAME_REGEX = /^(?=.*[a-zA-Z])[a-zA-Z0-9._]+$/;

/** @symbol PINCODE */
const PINCODE = /^[0-9]{0,6}$/;

/** @symbol KEYBOARDTYPENUMBER */
const KEYBOARDTYPENUMBER = /^\d+$/;

/** @symbol KEYBOARDTYPEALPHABETS */
const KEYBOARDTYPEALPHABETS = /^[A-Za-z ]+$/;

/** @symbol PRICEREGEX */
const PRICEREGEX = /^\d+(\.\d{0,2})?$/;

/** @symbol ADDRESS */
const ADDRESS = /^[a-zA-Z0-9!\n-._ :/ , ]{3,80}$/;

/** @symbol CHECKSPACES */
const CHECKSPACES = /^(\w+\s?)*\s*$/;

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/types/constants.ts
 * @symbol EMAIL_REGEX
 */
describe('EMAIL_REGEX', () => {
  it('accepts a standard valid .com email address', () => {
    expect(EMAIL_REGEX.test('user@example.com')).toBe(true);
  });

  it('rejects an email address that is missing the @ symbol', () => {
    expect(EMAIL_REGEX.test('userexample.com')).toBe(false);
  });

  it('rejects a non-.com domain such as .org', () => {
    expect(EMAIL_REGEX.test('user@example.org')).toBe(false);
  });

  it('rejects a non-.com domain such as .net', () => {
    expect(EMAIL_REGEX.test('user@example.net')).toBe(false);
  });

  it('accepts an email with a + sign in the local part', () => {
    expect(EMAIL_REGEX.test('user+tag@example.com')).toBe(true);
  });

  it('rejects an email that begins with the @ symbol', () => {
    expect(EMAIL_REGEX.test('@example.com')).toBe(false);
  });

  it('accepts an email with dots in the local part', () => {
    expect(EMAIL_REGEX.test('first.last@domain.com')).toBe(true);
  });

  it('rejects an email that has no domain after @', () => {
    expect(EMAIL_REGEX.test('user@.com')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol USERNAME_REGEX
 */
describe('USERNAME_REGEX', () => {
  it('accepts a username of 3 or more characters starting with a letter', () => {
    expect(USERNAME_REGEX.test('Alice')).toBe(true);
  });

  it('accepts a username with internal spaces', () => {
    expect(USERNAME_REGEX.test('John Doe')).toBe(true);
  });

  it('rejects a username that starts with a digit', () => {
    expect(USERNAME_REGEX.test('1Alice')).toBe(false);
  });

  it('rejects a username that is fewer than 3 characters total', () => {
    expect(USERNAME_REGEX.test('Al')).toBe(false);
  });

  it('rejects a username containing digits after the first character', () => {
    expect(USERNAME_REGEX.test('Alice123')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol PASSWORD_REGEX
 */
describe('PASSWORD_REGEX', () => {
  it('accepts a valid password with at least one letter and one digit (10+ chars)', () => {
    expect(PASSWORD_REGEX.test('Password1234')).toBe(true);
  });

  it('rejects a password shorter than 10 characters', () => {
    expect(PASSWORD_REGEX.test('Pass1')).toBe(false);
  });

  it('rejects a password that contains only letters (no digit)', () => {
    expect(PASSWORD_REGEX.test('PasswordOnly')).toBe(false);
  });

  it('rejects a password that contains only digits (no letter)', () => {
    expect(PASSWORD_REGEX.test('1234567890')).toBe(false);
  });

  it('accepts a password that includes allowed special characters', () => {
    expect(PASSWORD_REGEX.test('Pass@word123')).toBe(true);
  });

  it('rejects a password longer than 30 characters', () => {
    expect(PASSWORD_REGEX.test('P1' + 'a'.repeat(30))).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol PASSWORD_REGEX_CHANGE_PASSWORD
 */
describe('PASSWORD_REGEX_CHANGE_PASSWORD', () => {
  it('accepts a password meeting all requirements: digit, special, uppercase, 8+ chars', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Secure@1pass')).toBe(true);
  });

  it('rejects a password without an uppercase letter', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('secure@1pass')).toBe(false);
  });

  it('rejects a password without a special character', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Secure1pass1')).toBe(false);
  });

  it('rejects a password shorter than 8 characters', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Sec@1pa')).toBe(false);
  });

  it('rejects a password longer than 30 characters', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Secure@1pass' + 'x'.repeat(20))).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol CARD_REGEX
 * Current source value: /^[0-9]*$/ — digits only, spaces are NOT allowed.
 */
describe('CARD_REGEX', () => {
  it('accepts a string of contiguous digits only', () => {
    expect(CARD_REGEX.test('4111111111111111')).toBe(true);
  });

  it('rejects a card number that contains spaces', () => {
    expect(CARD_REGEX.test('4111 1111 1111 1111')).toBe(false);
  });

  it('rejects letters inside a card number', () => {
    expect(CARD_REGEX.test('4111ABCD11111111')).toBe(false);
  });

  it('accepts an empty string (zero or more digits)', () => {
    expect(CARD_REGEX.test('')).toBe(true);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol FULL_CARD_REGEX
 */
describe('FULL_CARD_REGEX', () => {
  it('accepts a standard 19-character spaced card number (e.g. "4111 1111 1111 1111")', () => {
    expect(FULL_CARD_REGEX.test('4111 1111 1111 1111')).toBe(true);
  });

  it('accepts a 16-character contiguous card number', () => {
    expect(FULL_CARD_REGEX.test('4111111111111111')).toBe(true);
  });

  it('rejects a card number that is shorter than 16 characters', () => {
    expect(FULL_CARD_REGEX.test('411111111111111')).toBe(false);
  });

  it('rejects a card number that is longer than 19 characters', () => {
    expect(FULL_CARD_REGEX.test('41111111111111111111')).toBe(false);
  });

  it('rejects a card number containing letters', () => {
    expect(FULL_CARD_REGEX.test('4111 ABCD 1111 1111')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol EXPIRY_DATE_REGEX
 */
describe('EXPIRY_DATE_REGEX', () => {
  it('accepts a valid expiry in MM/YY format', () => {
    expect(EXPIRY_DATE_REGEX.test('12/25')).toBe(true);
  });

  it('accepts a valid expiry in MM/YYYY format', () => {
    expect(EXPIRY_DATE_REGEX.test('06/2026')).toBe(true);
  });

  it('accepts a valid expiry without a separator (MMYY)', () => {
    expect(EXPIRY_DATE_REGEX.test('0125')).toBe(true);
  });

  it('rejects month 13 as it is not a valid month', () => {
    expect(EXPIRY_DATE_REGEX.test('13/25')).toBe(false);
  });

  it('rejects month 00 as it is not a valid month', () => {
    expect(EXPIRY_DATE_REGEX.test('00/25')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol SECURITY_CODE_REGEX
 */
describe('SECURITY_CODE_REGEX', () => {
  it('accepts a 3-digit CVV code', () => {
    expect(SECURITY_CODE_REGEX.test('123')).toBe(true);
  });

  it('accepts a 4-digit security code (e.g. Amex)', () => {
    expect(SECURITY_CODE_REGEX.test('1234')).toBe(true);
  });

  it('rejects a code containing letters', () => {
    expect(SECURITY_CODE_REGEX.test('12A')).toBe(false);
  });

  it('accepts an empty string (zero or more digits)', () => {
    expect(SECURITY_CODE_REGEX.test('')).toBe(true);
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

  it('accepts a 15-digit international phone number', () => {
    expect(PHONE_REGEX.test('919876543210123')).toBe(true);
  });

  it('rejects a phone number shorter than 10 digits', () => {
    expect(PHONE_REGEX.test('98765')).toBe(false);
  });

  it('rejects a phone number that contains a + prefix', () => {
    expect(PHONE_REGEX.test('+919876543210')).toBe(false);
  });

  it('rejects a phone number that contains letters', () => {
    expect(PHONE_REGEX.test('98765ABCDE')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol UNIQUE_USERNAME_REGEX
 */
describe('UNIQUE_USERNAME_REGEX', () => {
  it('accepts a valid alphanumeric username that contains at least one letter', () => {
    expect(UNIQUE_USERNAME_REGEX.test('john_doe42')).toBe(true);
  });

  it('rejects a username made entirely of digits', () => {
    expect(UNIQUE_USERNAME_REGEX.test('123456')).toBe(false);
  });

  it('accepts a username with dots like user.name', () => {
    expect(UNIQUE_USERNAME_REGEX.test('john.doe')).toBe(true);
  });

  it('rejects a username with spaces', () => {
    expect(UNIQUE_USERNAME_REGEX.test('john doe')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol PINCODE
 */
describe('PINCODE', () => {
  it('accepts a 6-digit pin code', () => {
    expect(PINCODE.test('123456')).toBe(true);
  });

  it('accepts an empty string (no digits yet entered)', () => {
    expect(PINCODE.test('')).toBe(true);
  });

  it('rejects a 7-digit input that exceeds the maximum length', () => {
    expect(PINCODE.test('1234567')).toBe(false);
  });

  it('rejects input containing letters', () => {
    expect(PINCODE.test('12345A')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol KEYBOARDTYPENUMBER
 */
describe('KEYBOARDTYPENUMBER', () => {
  it('accepts a string of digits', () => {
    expect(KEYBOARDTYPENUMBER.test('12345')).toBe(true);
  });

  it('rejects input containing letters', () => {
    expect(KEYBOARDTYPENUMBER.test('123abc')).toBe(false);
  });

  it('rejects an empty string (requires at least one digit)', () => {
    expect(KEYBOARDTYPENUMBER.test('')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol KEYBOARDTYPEALPHABETS
 */
describe('KEYBOARDTYPEALPHABETS', () => {
  it('accepts a string of letters only', () => {
    expect(KEYBOARDTYPEALPHABETS.test('HelloWorld')).toBe(true);
  });

  it('accepts letters with spaces', () => {
    expect(KEYBOARDTYPEALPHABETS.test('John Doe')).toBe(true);
  });

  it('rejects input containing digits', () => {
    expect(KEYBOARDTYPEALPHABETS.test('John123')).toBe(false);
  });

  it('rejects input containing special characters', () => {
    expect(KEYBOARDTYPEALPHABETS.test('John@Doe')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol PRICEREGEX
 */
describe('PRICEREGEX', () => {
  it('accepts an integer price', () => {
    expect(PRICEREGEX.test('100')).toBe(true);
  });

  it('accepts a price with up to 2 decimal places', () => {
    expect(PRICEREGEX.test('9.99')).toBe(true);
  });

  it('rejects a price with more than 2 decimal places', () => {
    expect(PRICEREGEX.test('9.999')).toBe(false);
  });

  it('rejects input containing letters', () => {
    expect(PRICEREGEX.test('9.99abc')).toBe(false);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol ADDRESS
 */
describe('ADDRESS', () => {
  it('accepts a valid address string of 3+ characters', () => {
    expect(ADDRESS.test('123 Main St')).toBe(true);
  });

  it('rejects an address shorter than 3 characters', () => {
    expect(ADDRESS.test('AB')).toBe(false);
  });

  it('accepts an address with digits, hyphens and spaces', () => {
    expect(ADDRESS.test('Flat-5, Tower A')).toBe(true);
  });
});

/**
 * @source src/types/constants.ts
 * @symbol CHECKSPACES
 */
describe('CHECKSPACES', () => {
  it('accepts a single word with no spaces', () => {
    expect(CHECKSPACES.test('hello')).toBe(true);
  });

  it('accepts multiple words separated by single spaces', () => {
    expect(CHECKSPACES.test('hello world')).toBe(true);
  });

  it('accepts an empty string', () => {
    expect(CHECKSPACES.test('')).toBe(true);
  });
});
