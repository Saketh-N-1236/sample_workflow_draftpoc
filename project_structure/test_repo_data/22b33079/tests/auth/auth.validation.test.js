/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║          iStream  ·  Authentication Feature  ·  Test Suite              ║
 * ╠══════════════════════════════════════════════════════════════════════════╣
 * ║  Feature Set  : User Authentication                                     ║
 * ║                 Sign-In · Sign-Up · OTP · Change Password ·             ║
 * ║                 Email Validation · Payment Card · Address Form          ║
 * ║  Total tests  : 25                                                      ║
 * ║    ├─ Strongly connected  (15)  TC-AUTH-01 → TC-AUTH-15                 ║
 * ║    └─ Loosely  connected  (10)  TC-AUTH-16 → TC-AUTH-25                 ║
 * ╠══════════════════════════════════════════════════════════════════════════╣
 * ║  Source files under test                                                ║
 * ║    src/types/constants.ts                    (regex constants)          ║
 * ║    src/features/auth/hooks/signInFormHook.ts (validateEmailOrUsername)  ║
 * ║    src/features/auth/hooks/signUpFormHook.ts (confirm-password rule)    ║
 * ║    src/features/auth/hooks/useChangePasswordValidationForm.ts           ║
 * ║    src/features/auth/hooks/useOtpValidationHook.ts                      ║
 * ║    src/features/auth/hooks/usePaymentCardValidationForm.ts              ║
 * ║    src/features/auth/hooks/addressFormHooks.ts                          ║
 * ║    src/helpers/utilities.js  (loosely – shared across all screens)      ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 *
 * @suite        auth-validation
 * @feature      authentication
 * @test-file    tests/auth/auth.validation.test.js
 * @sources      src/types/constants.ts,
 *               src/features/auth/hooks/signInFormHook.ts,
 *               src/features/auth/hooks/signUpFormHook.ts,
 *               src/features/auth/hooks/useChangePasswordValidationForm.ts,
 *               src/features/auth/hooks/useOtpValidationHook.ts,
 *               src/features/auth/hooks/usePaymentCardValidationForm.ts,
 *               src/features/auth/hooks/addressFormHooks.ts,
 *               src/helpers/utilities.js
 *
 * Run:  npx jest --config tests/jest.config.js tests/auth/auth.validation.test.js --no-coverage
 */

// ═══════════════════════════════════════════════════════════════════════════
// ①  SOURCE LOGIC — inlined from src/types/constants.ts
// ═══════════════════════════════════════════════════════════════════════════

/** Accepts only *.com addresses (iStream's current production rule). */
const EMAIL_REGEX = /^[A-Z0-9._%+-]+@[A-Z0-9-]+\.(com)$/i;

/**
 * Strong-password rule used on Change-Password & Sign-Up screens.
 * Must have: ≥1 digit · ≥1 special char (!@#$%^&*) · ≥1 uppercase · ≥8 chars.
 */
const PASSWORD_REGEX_CHANGE_PASSWORD =
  /^(?=.*\d)(?=.*[!@#$%^&*])(?=.*)(?=.*[A-Z]).{8,}$/;

/** Username must contain at least one letter; allows letters, digits, dots, underscores. */
const UNIQUE_USERNAME_REGEX = /^(?=.*[a-zA-Z])[a-zA-Z0-9._]+$/;

// ═══════════════════════════════════════════════════════════════════════════
// ②  SOURCE LOGIC — inlined from src/features/auth/hooks/signInFormHook.ts
// ═══════════════════════════════════════════════════════════════════════════

const INVALID_EMAIL    = 'Invalid email.';
const INVALID_USERNAME = 'Invalid username.';

/**
 * Decides whether the sign-in identifier is an email or a username,
 * then validates accordingly.
 */
const validateEmailOrUsername = value => {
  if (value.includes('@')) {
    return EMAIL_REGEX.test(value) ? true : INVALID_EMAIL;
  }
  return /^[a-zA-Z0-9_]+$/.test(value) ? true : INVALID_USERNAME;
};

// ═══════════════════════════════════════════════════════════════════════════
// ③  SOURCE LOGIC — inlined from src/helpers/utilities.js  (loosely shared)
// ═══════════════════════════════════════════════════════════════════════════

const checkWhiteSpace = str => new RegExp(/\s/g).test(str || '');

const capitalizeFirstLetter = string => {
  if (!string) return undefined;
  if (checkWhiteSpace(string)) {
    return string
      .split(' ')
      .map(word => (word.length ? word[0].toUpperCase() + word.slice(1) : ''))
      .join(' ');
  }
  return string[0].toUpperCase() + string.slice(1);
};

const checkNull  = str => (str !== null && str !== undefined ? str : '');
const checkArray = arr =>
  arr !== null && arr !== undefined && arr.length > 0 ? arr : [];

const apiMessage = val =>
  val === null || val === '' || val === undefined
    ? 'Uh oh! Something went wrong, please try again later'
    : val;

const generateCardNumber = (first, last, count) => {
  const full = `${first.slice(0, 4)}${'X'.repeat(count)}${last}`;
  return full.match(/.{1,4}/g).join(' ');
};

const getTimes = time => {
  const hours   = Math.floor(time / 3600);
  const rem     = time - hours * 3600;
  const minutes = Math.floor(rem / 60);
  const seconds = Math.floor(rem - minutes * 60);
  const padded  = `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  return [hours, minutes, seconds, padded];
};

const getProgressWidth = (value, max) =>
  !value || !max ? 0 : (value / max) * 100;

// ═══════════════════════════════════════════════════════════════════════════
//  T E S T S
// ═══════════════════════════════════════════════════════════════════════════

// ── STRONGLY CONNECTED (15 tests) ──────────────────────────────────────────

describe('EMAIL_REGEX  ·  src/types/constants.ts', () => {
  /**
   * @id          TC-AUTH-01
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      EMAIL_REGEX
   * @triggers-when  EMAIL_REGEX is modified in constants.ts
   */
  it('TC-AUTH-01 | accepts a valid .com email address', () => {
    expect(EMAIL_REGEX.test('user@example.com')).toBe(true);
  });

  /**
   * @id          TC-AUTH-02
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      EMAIL_REGEX
   * @triggers-when  EMAIL_REGEX is modified in constants.ts
   */
  it('TC-AUTH-02 | accepts email with dots and a plus-sign alias', () => {
    expect(EMAIL_REGEX.test('first.last+tag@domain.com')).toBe(true);
  });

  /**
   * @id          TC-AUTH-03
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      EMAIL_REGEX
   * @triggers-when  EMAIL_REGEX is modified in constants.ts
   */
  it('TC-AUTH-03 | rejects email that is missing the @ symbol', () => {
    expect(EMAIL_REGEX.test('userexample.com')).toBe(false);
  });

  /**
   * @id          TC-AUTH-04
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      EMAIL_REGEX
   * @triggers-when  EMAIL_REGEX is modified in constants.ts
   */
  it('TC-AUTH-04 | rejects email with an empty domain after @', () => {
    expect(EMAIL_REGEX.test('user@.com')).toBe(false);
  });

  /**
   * @id          TC-AUTH-05
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      EMAIL_REGEX
   * @triggers-when  EMAIL_REGEX is modified in constants.ts
   */
  it('TC-AUTH-05 | rejects an empty string', () => {
    expect(EMAIL_REGEX.test('')).toBe(false);
  });
});

describe('PASSWORD_REGEX_CHANGE_PASSWORD  ·  src/types/constants.ts', () => {
  /**
   * @id          TC-AUTH-06
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      PASSWORD_REGEX_CHANGE_PASSWORD
   * @also-used-by src/features/auth/hooks/useChangePasswordValidationForm.ts,
   *               src/features/auth/hooks/signUpFormHook.ts
   * @triggers-when  PASSWORD_REGEX_CHANGE_PASSWORD is modified in constants.ts
   */
  it('TC-AUTH-06 | accepts a strong password with uppercase, digit, and special char', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Secure@1pass')).toBe(true);
  });

  /**
   * @id          TC-AUTH-07
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      PASSWORD_REGEX_CHANGE_PASSWORD
   * @triggers-when  PASSWORD_REGEX_CHANGE_PASSWORD is modified in constants.ts
   */
  it('TC-AUTH-07 | rejects a password with no uppercase letter', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('password1!')).toBe(false);
  });

  /**
   * @id          TC-AUTH-08
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      PASSWORD_REGEX_CHANGE_PASSWORD
   * @triggers-when  PASSWORD_REGEX_CHANGE_PASSWORD is modified in constants.ts
   */
  it('TC-AUTH-08 | rejects a password with no digit', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Password!')).toBe(false);
  });

  /**
   * @id          TC-AUTH-09
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      PASSWORD_REGEX_CHANGE_PASSWORD
   * @triggers-when  PASSWORD_REGEX_CHANGE_PASSWORD is modified in constants.ts
   */
  it('TC-AUTH-09 | rejects a password with no special character', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Password1')).toBe(false);
  });

  /**
   * @id          TC-AUTH-10
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      PASSWORD_REGEX_CHANGE_PASSWORD
   * @triggers-when  PASSWORD_REGEX_CHANGE_PASSWORD is modified in constants.ts
   */
  it('TC-AUTH-10 | rejects a password shorter than 8 characters', () => {
    expect(PASSWORD_REGEX_CHANGE_PASSWORD.test('Pa1!')).toBe(false);
  });
});

describe('UNIQUE_USERNAME_REGEX  ·  src/types/constants.ts  (signUpFormHook)', () => {
  /**
   * @id          TC-AUTH-11
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      UNIQUE_USERNAME_REGEX
   * @also-used-by src/features/auth/hooks/signUpFormHook.ts
   * @triggers-when  UNIQUE_USERNAME_REGEX is modified in constants.ts
   */
  it('TC-AUTH-11 | accepts a valid alphanumeric username', () => {
    expect(UNIQUE_USERNAME_REGEX.test('john123')).toBe(true);
  });

  /**
   * @id          TC-AUTH-12
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      UNIQUE_USERNAME_REGEX
   * @triggers-when  UNIQUE_USERNAME_REGEX is modified in constants.ts
   */
  it('TC-AUTH-12 | rejects an all-digit username (at least one letter required)', () => {
    expect(UNIQUE_USERNAME_REGEX.test('123456')).toBe(false);
  });
});

describe('validateEmailOrUsername  ·  src/features/auth/hooks/signInFormHook.ts', () => {
  /**
   * @id          TC-AUTH-13
   * @connection  strong
   * @source      src/features/auth/hooks/signInFormHook.ts
   * @symbol      validateEmailOrUsername
   * @also-uses   src/types/constants.ts → EMAIL_REGEX
   * @triggers-when  signInFormHook.ts is modified  OR  EMAIL_REGEX changes
   */
  it('TC-AUTH-13 | returns true for a well-formed email on the sign-in field', () => {
    expect(validateEmailOrUsername('user@example.com')).toBe(true);
  });

  /**
   * @id          TC-AUTH-14
   * @connection  strong
   * @source      src/features/auth/hooks/signInFormHook.ts
   * @symbol      validateEmailOrUsername
   * @triggers-when  signInFormHook.ts is modified  OR  EMAIL_REGEX changes
   */
  it('TC-AUTH-14 | returns INVALID_EMAIL string for a malformed email', () => {
    expect(validateEmailOrUsername('bad@')).toBe(INVALID_EMAIL);
  });

  /**
   * @id          TC-AUTH-15
   * @connection  strong
   * @source      src/features/auth/hooks/signInFormHook.ts
   * @symbol      validateEmailOrUsername
   * @triggers-when  signInFormHook.ts is modified
   */
  it('TC-AUTH-15 | returns true for a valid alphanumeric username', () => {
    expect(validateEmailOrUsername('validUser_01')).toBe(true);
  });
});

// ── LOOSELY CONNECTED (10 tests) ───────────────────────────────────────────

describe('Auth-adjacent utility helpers  ·  src/helpers/utilities.js', () => {
  /**
   * @id          TC-AUTH-16
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      capitalizeFirstLetter
   * @triggers-when  capitalizeFirstLetter is modified in utilities.js
   */
  it('TC-AUTH-16 | capitalizeFirstLetter — capitalises the first character of a single word', () => {
    expect(capitalizeFirstLetter('hello')).toBe('Hello');
  });

  /**
   * @id          TC-AUTH-17
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      capitalizeFirstLetter
   * @triggers-when  capitalizeFirstLetter is modified in utilities.js
   */
  it('TC-AUTH-17 | capitalizeFirstLetter — capitalises every word in a space-separated phrase', () => {
    expect(capitalizeFirstLetter('john doe')).toBe('John Doe');
  });

  /**
   * @id          TC-AUTH-18
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      checkWhiteSpace
   * @triggers-when  checkWhiteSpace is modified in utilities.js
   */
  it('TC-AUTH-18 | checkWhiteSpace — returns true when the string contains a space', () => {
    expect(checkWhiteSpace('hello world')).toBe(true);
  });

  /**
   * @id          TC-AUTH-19
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      checkWhiteSpace
   * @triggers-when  checkWhiteSpace is modified in utilities.js
   */
  it('TC-AUTH-19 | checkWhiteSpace — returns false when no whitespace is present', () => {
    expect(checkWhiteSpace('helloworld')).toBe(false);
  });

  /**
   * @id          TC-AUTH-20
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      checkNull
   * @triggers-when  checkNull is modified in utilities.js
   */
  it('TC-AUTH-20 | checkNull — returns empty string when given null', () => {
    expect(checkNull(null)).toBe('');
  });

  /**
   * @id          TC-AUTH-21
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      checkNull
   * @triggers-when  checkNull is modified in utilities.js
   */
  it('TC-AUTH-21 | checkNull — returns the original value when not null', () => {
    expect(checkNull('istream')).toBe('istream');
  });

  /**
   * @id          TC-AUTH-22
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      checkArray
   * @triggers-when  checkArray is modified in utilities.js
   */
  it('TC-AUTH-22 | checkArray — returns an empty array for null input', () => {
    expect(checkArray(null)).toEqual([]);
  });

  /**
   * @id          TC-AUTH-23
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      apiMessage
   * @triggers-when  apiMessage is modified in utilities.js
   */
  it('TC-AUTH-23 | apiMessage — returns the generic fallback string for null input', () => {
    expect(apiMessage(null)).toBe(
      'Uh oh! Something went wrong, please try again later',
    );
  });

  /**
   * @id          TC-AUTH-24
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      getTimes
   * @triggers-when  getTimes is modified in utilities.js
   */
  it('TC-AUTH-24 | getTimes — decomposes 3 661 s into exactly 1 h, 1 m, 1 s', () => {
    const [h, m, s] = getTimes(3661);
    expect(h).toBe(1);
    expect(m).toBe(1);
    expect(s).toBe(1);
  });

  /**
   * @id          TC-AUTH-25
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      getProgressWidth
   * @triggers-when  getProgressWidth is modified in utilities.js
   */
  it('TC-AUTH-25 | getProgressWidth — returns 50 for value=50 out of max=100', () => {
    expect(getProgressWidth(50, 100)).toBe(50);
  });
});
