/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  CROSS-DEPENDENT · Auth + Storage Integration                       │
 * │  Category : cross-dependent (spans multiple source files)           │
 * │  Tests    : 25                                                       │
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
const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.com$/;

/** @symbol CARD_REGEX  @source src/types/constants.ts — digits only */
const CARD_REGEX = /^[0-9]*$/;

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
  username:             'USERNAME',
  sessionId:            'SESSION_ID',
  token:                'ACCESS_TOKEN',
  userDetails:          'USERDETAILS',
  loginTime:            'LOGGEDINTIME',
  refreshToken:         'REFRESHTOKEN',
  stripePaymentDetails: 'STRIPEPAYMENTDETAILS',
  subscriptionDetails:  'SUBSCRIPTION_DETAILS',
  phoneVerified:        'PHONE_VERIFIED',
  userData:             'USERDATA',
  userId:               'userID',
  profileId:            'PROFILEID',
};

/** @symbol appStorage  @source src/services/storage.ts */
const appStorage = {
  get:     key      => { const v = localStorage.getItem(key); return v ? JSON.parse(v) : null; },
  set:     (key, v) => { localStorage.setItem(key, JSON.stringify(v)); },
  delete:  key      => { localStorage.removeItem(key); },
  clearAll: ()      => { localStorage.clear(); },
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
  if (string && typeof string === 'string' && string.trim().length > 0) {
    if (checkWhiteSpace(string)) {
      return string
        .split(' ')
        .filter(w => w.length > 0)
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(' ');
    }
    return string.charAt(0).toUpperCase() + string.slice(1);
  }
  return '';
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
  it('routes input containing @ to email validation and accepts a valid .com address', () => {
    expect(validateEmailOrUsername('user@example.com')).toBe(true);
  });

  it('routes plain text input to username validation and accepts a clean alphanumeric username', () => {
    expect(validateEmailOrUsername('john_doe')).toBe(true);
  });

  it('returns an error message when the email format is invalid via EMAIL_REGEX', () => {
    expect(validateEmailOrUsername('bad@email.org')).toBe(INVALID_EMAIL);
  });

  it('returns an error message when the username contains special characters', () => {
    expect(validateEmailOrUsername('bad user!')).toBe(INVALID_USERNAME);
  });

  it('rejects an email address without a domain TLD', () => {
    expect(validateEmailOrUsername('user@domain')).toBe(INVALID_EMAIL);
  });

  it('accepts a username that contains only underscores and alphanumeric characters', () => {
    expect(validateEmailOrUsername('user_123')).toBe(true);
  });

  it('rejects a username that contains hyphens', () => {
    expect(validateEmailOrUsername('user-name')).toBe(INVALID_USERNAME);
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
describe('isUserLoggedIn reads storageKeys.token from appStorage', () => {
  it('returns false when no token is stored', () => {
    expect(isUserLoggedIn()).toBe(false);
  });

  it('returns true after a token has been stored under storageKeys.token', () => {
    appStorage.set(storageKeys.token, 'abc-token-123');
    expect(isUserLoggedIn()).toBe(true);
  });

  it('returns false after the token key is explicitly deleted', () => {
    appStorage.set(storageKeys.token, 'tok');
    appStorage.delete(storageKeys.token);
    expect(isUserLoggedIn()).toBe(false);
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
describe('updateNewTokenDetails stores values under the correct storageKeys', () => {
  it('saves the access token to localStorage under the ACCESS_TOKEN key', () => {
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

  it('makes isUserLoggedIn return true after storing a token via updateNewTokenDetails', () => {
    updateNewTokenDetails({ loginTime: '2024-01-01', token: 'new-token', refreshToken: 'r' });
    expect(isUserLoggedIn()).toBe(true);
  });
});

/**
 * Cross-dependency: generateCardNumber (utilities.js) produces output that
 * can be checked against CARD_REGEX (constants.ts) — utility output vs regex.
 *
 * @source src/helpers/utilities.js
 * @source src/types/constants.ts
 * @symbol generateCardNumber
 * @symbol CARD_REGEX
 */
describe('generateCardNumber output structure', () => {
  it('output of generateCardNumber preserves first 4 and last 4 digits', () => {
    const result = generateCardNumber('4111', '1111', 8);
    expect(result).toContain('4111');
    expect(result).toContain('1111');
  });

  it('correctly masks the middle digits with X characters', () => {
    const result = generateCardNumber('4111', '1111', 8);
    expect(result).toContain('XXXX');
  });

  it('generates a masked number where the masked portion does NOT satisfy CARD_REGEX (contains X)', () => {
    const raw    = generateCardNumber('4111', '9999', 8).replace(/ /g, '');
    expect(CARD_REGEX.test(raw)).toBe(false);
  });

  it('produces the expected fully masked representation', () => {
    expect(generateCardNumber('5500', '4444', 8)).toBe('5500 XXXX XXXX 4444');
  });
});

/**
 * Cross-dependency: capitalizeFirstLetter + checkWhiteSpace — both live in
 * utilities.js; capitalizeFirstLetter explicitly delegates to checkWhiteSpace.
 *
 * @source src/helpers/utilities.js
 * @symbol capitalizeFirstLetter
 * @symbol checkWhiteSpace
 */
describe('capitalizeFirstLetter delegates to checkWhiteSpace for multi-word input', () => {
  it('capitalizes the first letter of each word in a multi-word string', () => {
    expect(capitalizeFirstLetter('john doe')).toBe('John Doe');
  });

  it('capitalizes a single word correctly without the whitespace branch', () => {
    expect(capitalizeFirstLetter('alice')).toBe('Alice');
  });

  it('returns an empty string for null input', () => {
    expect(capitalizeFirstLetter(null)).toBe('');
  });

  it('returns an empty string for an input that is entirely whitespace', () => {
    expect(capitalizeFirstLetter('   ')).toBe('');
  });
});
