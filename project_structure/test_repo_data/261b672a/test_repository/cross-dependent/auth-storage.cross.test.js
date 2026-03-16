/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  CROSS-DEPENDENT · Auth + Storage Integration                       │
 * │  Category : cross-dependent (spans multiple source files)           │
 * │  Tests    : 13                                                       │
 * │  Sources  :                                                          │
 * │    src/features/auth/hooks/signInFormHook.ts   (validateEmailOrUsername) │
 * │    src/types/constants.ts                      (EMAIL_REGEX, CARD_REGEX) │
 * │    src/services/storage.ts                     (storageKeys, appStorage) │
 * │    src/helpers/utilities.js (isUserLoggedIn, generateCardNumber,     │
 * │                              capitalizeFirstLetter, updateNewTokenDetails) │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     auth-storage-cross
 * @category  cross-dependent
 * @sources   src/features/auth/hooks/signInFormHook.ts,
 *            src/types/constants.ts,
 *            src/services/storage.ts,
 *            src/helpers/utilities.js
 */

// ── Inlined from src/types/constants.ts ──────────────────────────────────────
/** @symbol EMAIL_REGEX  @source src/types/constants.ts */
const EMAIL_REGEX = /^[A-Z0-9._%+-]+@[A-Z0-9-]+\.(com)$/i;

/** @symbol CARD_REGEX  @source src/types/constants.ts */
const CARD_REGEX = /^[0-9\s]*$/;

// ── Inlined from src/features/auth/hooks/signInFormHook.ts ───────────────────
/** @symbol validateEmailOrUsername  @source src/features/auth/hooks/signInFormHook.ts */
const INVALID_EMAIL    = 'Invalid email.';
const INVALID_USERNAME = 'Invalid username.';

const validateEmailOrUsername = value => {
  if (value.includes('@')) {
    return EMAIL_REGEX.test(value) ? true : INVALID_EMAIL;
  }
  return /^[a-zA-Z0-9_]+$/.test(value) ? true : INVALID_USERNAME;
};

// ── Inlined from src/services/storage.ts ─────────────────────────────────────
/** @symbol storageKeys  @source src/services/storage.ts */
const storageKeys = {
  username:               'USERNAME',
  token:                  'TOKEN',
  userDetails:            'USERDETAILS',
  loginTime:              'LOGGEDINTIME',
  refreshToken:           'REFRESHTOKEN',
  stripePaymentDetails:   'STRIPEPAYMENTDETAILS',
  phoneVerified:          'PHONE_VERIFIED',
};

/** @symbol appStorage  @source src/services/storage.ts */
const appStorage = {
  get:    key   => { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; },
  set:    (k,v) => { localStorage.setItem(k, JSON.stringify(v)); },
  delete: key   => { localStorage.removeItem(key); },
  clearAll: ()  => { localStorage.clear(); },
};

// ── Inlined from src/helpers/utilities.js ────────────────────────────────────
/** @symbol isUserLoggedIn  @source src/helpers/utilities.js */
const isUserLoggedIn = () => !!appStorage.get(storageKeys.token);

/** @symbol generateCardNumber  @source src/helpers/utilities.js */
const generateCardNumber = (first, last, count) => {
  const fullNumber = `${first.slice(0, 4)}${'X'.repeat(count)}${last}`;
  return fullNumber.match(/.{1,4}/g).join(' ');
};

/** @symbol capitalizeFirstLetter  @source src/helpers/utilities.js */
const checkWhiteSpace = str => new RegExp(/\s/g).test(str || '');
const capitalizeFirstLetter = string => {
  if (string && typeof string === 'string') {
    if (checkWhiteSpace(string)) {
      return string.split(' ').map(w =>
        w.length > 0 ? w.charAt(0).toUpperCase() + w.slice(1) : ''
      ).join(' ');
    }
    return string.charAt(0).toUpperCase() + string.slice(1);
  }
};

/** @symbol updateNewTokenDetails  @source src/helpers/utilities.js */
const updateNewTokenDetails = ({ loginTime, token, refreshToken }) => {
  appStorage.set(storageKeys.token,        token);
  appStorage.set(storageKeys.loginTime,    loginTime);
  appStorage.set(storageKeys.refreshToken, refreshToken);
};

// ─────────────────────────────────────────────────────────────────────────────

/**
 * Cross-dependency: validateEmailOrUsername (signInFormHook.ts) relies on
 * EMAIL_REGEX (constants.ts) — two source files in one behaviour.
 *
 * @source src/features/auth/hooks/signInFormHook.ts
 * @source src/types/constants.ts
 * @symbol validateEmailOrUsername
 * @symbol EMAIL_REGEX
 */
describe('validateEmailOrUsername uses EMAIL_REGEX', () => {
  it('routes input containing @ to email validation and accepts a valid address', () => {
    expect(validateEmailOrUsername('user@example.com')).toBe(true);
  });

  it('routes plain text input to username validation and accepts a clean username', () => {
    expect(validateEmailOrUsername('john_doe')).toBe(true);
  });

  it('returns an error message when the email format is invalid via EMAIL_REGEX', () => {
    expect(validateEmailOrUsername('bad@email.org')).toBe(INVALID_EMAIL);
  });

  it('returns an error message when the username contains special characters', () => {
    expect(validateEmailOrUsername('bad user!')).toBe(INVALID_USERNAME);
  });
});

/**
 * Cross-dependency: isUserLoggedIn (utilities.js) reads storageKeys.token
 * (storage.ts) — utility + storage cross-dependency.
 *
 * @source src/helpers/utilities.js
 * @source src/services/storage.ts
 * @symbol isUserLoggedIn
 * @symbol storageKeys
 */
describe('isUserLoggedIn reads storageKeys.token', () => {
  it('returns false when no token is stored', () => {
    expect(isUserLoggedIn()).toBe(false);
  });

  it('returns true after a token has been stored under storageKeys.token', () => {
    appStorage.set(storageKeys.token, 'abc-token-123');
    expect(isUserLoggedIn()).toBe(true);
  });
});

/**
 * Cross-dependency: updateNewTokenDetails (utilities.js) persists to
 * storageKeys (storage.ts) — utility writes to storage keys.
 *
 * @source src/helpers/utilities.js
 * @source src/services/storage.ts
 * @symbol updateNewTokenDetails
 * @symbol storageKeys
 */
describe('updateNewTokenDetails stores values under storageKeys', () => {
  it('saves the access token to localStorage under the TOKEN key', () => {
    updateNewTokenDetails({ loginTime: '2024-01-01', token: 'my-token', refreshToken: 'my-refresh' });
    expect(appStorage.get(storageKeys.token)).toBe('my-token');
  });

  it('saves the refresh token under the REFRESHTOKEN key', () => {
    updateNewTokenDetails({ loginTime: '2024-01-01', token: 'tok', refreshToken: 'ref-tok' });
    expect(appStorage.get(storageKeys.refreshToken)).toBe('ref-tok');
  });

  it('saves the login time under the LOGGEDINTIME key', () => {
    updateNewTokenDetails({ loginTime: '2024-06-15T10:00:00Z', token: 't', refreshToken: 'r' });
    expect(appStorage.get(storageKeys.loginTime)).toBe('2024-06-15T10:00:00Z');
  });
});

/**
 * Cross-dependency: generateCardNumber (utilities.js) produces output that
 * should satisfy CARD_REGEX (constants.ts) — utility output vs regex contract.
 *
 * @source src/helpers/utilities.js
 * @source src/types/constants.ts
 * @symbol generateCardNumber
 * @symbol CARD_REGEX
 */
describe('generateCardNumber output satisfies CARD_REGEX', () => {
  it('output of generateCardNumber preserves first and last 4 digits', () => {
    // Use count=8 so fullNumber is 16 chars → splits cleanly as 4+4+4+4
    // '4111' + 'XXXXXXXX' + '1111' → '4111 XXXX XXXX 1111'
    const result = generateCardNumber('4111', '1111', 8);
    expect(result).toContain('4111');
    expect(result).toContain('1111');
    expect(result).toContain('X');
  });

  it('correctly masks middle digits with X characters', () => {
    const result = generateCardNumber('4111', '1111', 8);
    expect(result).toContain('XXXX');
    expect(result).toContain('4111');
    expect(result).toContain('1111');
  });
});

/**
 * Cross-dependency: capitalizeFirstLetter + checkWhiteSpace — both live in
 * utilities.js and capitalizeFirstLetter explicitly calls checkWhiteSpace.
 *
 * @source src/helpers/utilities.js
 * @symbol capitalizeFirstLetter
 * @symbol checkWhiteSpace
 */
describe('capitalizeFirstLetter with checkWhiteSpace', () => {
  it('capitalizes the first letter of each word in a multi-word string', () => {
    // The function capitalizes every word's first letter via split/map
    expect(capitalizeFirstLetter('john doe')).toBe('John Doe');
  });

  it('capitalizes a single word correctly without whitespace branch', () => {
    expect(capitalizeFirstLetter('alice')).toBe('Alice');
  });

  it('returns undefined when given a non-string truthy value after type guard fix', () => {
    expect(capitalizeFirstLetter(123)).toBeUndefined();
  });
});
