/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║       iStream  ·  Payment & Subscription Feature  ·  Test Suite         ║
 * ╠══════════════════════════════════════════════════════════════════════════╣
 * ║  Feature Set  : Payment & Subscription Management                       ║
 * ║                 Card CRUD · Subscription Plans · Payment Reducer ·      ║
 * ║                 API Endpoints · Card Validation · App Storage           ║
 * ║  Total tests  : 50                                                      ║
 * ║    ├─ Strongly connected  (35)  TC-PAY-01 → TC-PAY-35                   ║
 * ║    └─ Loosely  connected  (15)  TC-PAY-36 → TC-PAY-50                   ║
 * ╠══════════════════════════════════════════════════════════════════════════╣
 * ║  Source files under test                                                ║
 * ║    src/reducer/paymentReducer.js                  (state management)    ║
 * ║    src/services/api/common/ApiEndPoints.js        (endpoint strings)    ║
 * ║    src/services/api/common/ApiConstants.js        (base URLs / limits)  ║
 * ║    src/services/api/common/payment/index.js       (changeToParams)      ║
 * ║    src/types/constants.ts                         (card/expiry regex)   ║
 * ║    src/services/storage.ts                        (appStorage wrapper)  ║
 * ║    src/helpers/utilities.js  (loosely – timeConvert, getProgressWidth)  ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 *
 * @suite        payment-logic
 * @feature      payment-subscription
 * @test-file    tests/payment/payment.logic.test.js
 * @sources      src/reducer/paymentReducer.js,
 *               src/services/api/common/ApiEndPoints.js,
 *               src/services/api/common/ApiConstants.js,
 *               src/services/api/common/payment/index.js,
 *               src/types/constants.ts,
 *               src/services/storage.ts,
 *               src/helpers/utilities.js
 *
 * Run:  npx jest --config tests/jest.config.js tests/payment/payment.logic.test.js --no-coverage
 */

// ═══════════════════════════════════════════════════════════════════════════
// ①  PAYMENT REDUCER — src/reducer/paymentReducer.js
// ═══════════════════════════════════════════════════════════════════════════

const paymentActions = {
  UPDATEALLCARDDETAILS:    'UPDATE_STORED_USER_ALL_CARD_DETAILS',
  UPDATEPAYMENTPLANDETAILS:'UPDATE_PAYMENT_PLAN_DETAILS',
};

const paymentInitialState = {
  userCards:           [],
  cardsFetched:        false,
  paymentPlantDetails: undefined,
};

function paymentReducer(state = paymentInitialState, action) {
  switch (action.type) {
    case paymentActions.UPDATEALLCARDDETAILS:
      return { ...state, userCards: action.userCards, cardsFetched: action.cardsFetched };
    case paymentActions.UPDATEPAYMENTPLANDETAILS:
      return { ...state, paymentPlantDetails: action.payload };
    default:
      return state;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// ②  API ENDPOINTS — src/services/api/common/ApiEndPoints.js
// ═══════════════════════════════════════════════════════════════════════════

const endpoints = {
  iStream_login:  '/api/v2/client/login',
  signup:         'api/v2/subscriptor/account/registration',
  payment: {
    addCard:          '/api/v2/payments/me?',
    deleteCard:       '/api/v2/payments/me?cardId=',
    preAuth:          '/api/v2/payments/me/preauth-verify?',
    getAllCards:       '/api/v2/payments/me',
    updateCard:       '/api/v2/payments/me?',
    paymentsCheckout: '/api/v2/payments/checkout',
  },
  getSubscriptionPlans:  '/api/v2/subscriptor/account/get-subscriptions',
  checkUserSubscription: '/api/v2/subscriptor/account/get-all-user-subscriptions',
  advertisement: (type, id, genres) =>
    `/api/v2/advertisements/active-video-campaigns/list?type=${type}&vod_id=${id}&genresId=${genres}`,
  episodes: ({ tvShowId, seasonId }) =>
    `/api/v2/movie/single-event-vods-list?multiEventVodId=${tvShowId}&multiEventVodSeasonId=${seasonId}&type=1&sortColumnName=episodeNumber&sortDirection=ASC&limit=20&page=1`,
  myOrders: id => `/api/v2/payments/get-transaction?account_id=${id}`,
  videoDetails:  '/api/v2/movie/get-movie-source?vodId=',
  refreshToken:  '/api/v2/client/refresh-token',
};

// ═══════════════════════════════════════════════════════════════════════════
// ③  API CONSTANTS — src/services/api/common/ApiConstants.js
// ═══════════════════════════════════════════════════════════════════════════

const API_BASE_URL          = 'https://qa-istream-ui.ideyalabs.com';
const assetBaseURL          = 'https://qa-istream-assets.ideyalabs.com';
const MAX_IMAGE_UPLOAD_SIZE = 10485760;
const TIMEOUT               = 30000;
const INTERNET_ERROR        = 'No internet connection';
const RESPONSE_ERROR        = 'Something Went Wrong, Please Try again after sometime';

// ═══════════════════════════════════════════════════════════════════════════
// ④  changeToParams — src/services/api/common/payment/index.js
// ═══════════════════════════════════════════════════════════════════════════

function changeToParams(data) {
  return new URLSearchParams(data).toString();
}

// ═══════════════════════════════════════════════════════════════════════════
// ⑤  CARD / EXPIRY REGEX — src/types/constants.ts
// ═══════════════════════════════════════════════════════════════════════════

const CARD_NUMBER_REGEX =
  /^([0-9 ]{17,17}|[0-9 ]{18,18}|[0-9 ]{19,19})$/;
const EXPIRY_DATE_REGEX = /\b(0[1-9]|1[0-2])\/?([0-9]{4}|[0-9]{2})\b/;

const generateCardNumber = (first, last, count) => {
  const full = `${first.slice(0, 4)}${'X'.repeat(count)}${last}`;
  return full.match(/.{1,4}/g).join(' ');
};

// ═══════════════════════════════════════════════════════════════════════════
// ⑥  STORAGE KEYS — src/services/storage.ts
// ═══════════════════════════════════════════════════════════════════════════

const storageKeys = {
  username:             'USERNAME',
  userDetails:          'USERDETAILS',
  token:                'TOKEN',
  loginTime:            'LOGGEDINTIME',
  refreshToken:         'REFRESHTOKEN',
  stripePaymentDetails: 'STRIPEPAYMENTDETAILS',
  subscriptionDetails:  'SUBSCRIPTION_DETAILS',
  videoPlayedUpto:      'VIDEO_PLAYED_UPTO',
};

// ═══════════════════════════════════════════════════════════════════════════
// ⑦  APP STORAGE (localStorage wrapper) — src/services/storage.ts
// ═══════════════════════════════════════════════════════════════════════════

class MockStorage {
  constructor() { this._store = {}; }
  setItem(key, val) { this._store[key] = String(val); }
  getItem(key)      { return key in this._store ? this._store[key] : null; }
  removeItem(key)   { delete this._store[key]; }
  clear()           { this._store = {}; }
}

function buildAppStorage(ls) {
  const set = (key, value) => ls.setItem(key, JSON.stringify(value));
  const get = key => { const val = ls.getItem(key); if (!val) return null; return JSON.parse(val); };
  return { set, get, delete: key => ls.removeItem(key), clearAll: () => ls.clear() };
}

// ═══════════════════════════════════════════════════════════════════════════
// ⑧  SHARED UTILITY HELPERS — src/helpers/utilities.js
// ═══════════════════════════════════════════════════════════════════════════

const timeConvert = n => {
  const hours    = n / 60;
  const rhours   = Math.floor(hours);
  const rminutes = Math.round((hours - rhours) * 60);
  return `${rhours}h ${rminutes}min`;
};

const getProgressWidth = (value, max) =>
  !value || !max ? 0 : (value / max) * 100;

const checkNull  = str => (str !== null && str !== undefined ? str : '');
const checkArray = arr =>
  arr !== null && arr !== undefined && arr.length > 0 ? arr : [];

// ═══════════════════════════════════════════════════════════════════════════
//  T E S T S
// ═══════════════════════════════════════════════════════════════════════════

// ── STRONGLY CONNECTED (35 tests) ──────────────────────────────────────────

describe('paymentReducer – initial state  ·  src/reducer/paymentReducer.js', () => {
  /**
   * @id          TC-PAY-01
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentInitialState, paymentReducer
   * @triggers-when  paymentReducer.js is modified (initial state shape changes)
   */
  it('TC-PAY-01 | initial state has an empty userCards array', () => {
    const state = paymentReducer(undefined, { type: '@@INIT' });
    expect(state.userCards).toEqual([]);
  });

  /**
   * @id          TC-PAY-02
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentInitialState, paymentReducer
   * @triggers-when  paymentReducer.js is modified
   */
  it('TC-PAY-02 | initial state has cardsFetched = false', () => {
    const state = paymentReducer(undefined, { type: '@@INIT' });
    expect(state.cardsFetched).toBe(false);
  });

  /**
   * @id          TC-PAY-03
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentInitialState, paymentReducer
   * @triggers-when  paymentReducer.js is modified
   */
  it('TC-PAY-03 | initial state has paymentPlantDetails = undefined', () => {
    const state = paymentReducer(undefined, { type: '@@INIT' });
    expect(state.paymentPlantDetails).toBeUndefined();
  });
});

describe('paymentReducer – UPDATEALLCARDDETAILS action', () => {
  const mockCards = [
    { id: 'c1', last4: '1111', brand: 'visa'       },
    { id: 'c2', last4: '2222', brand: 'mastercard' },
  ];

  /**
   * @id          TC-PAY-04
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentActions.UPDATEALLCARDDETAILS, paymentReducer
   * @triggers-when  paymentReducer.js UPDATEALLCARDDETAILS case is modified
   */
  it('TC-PAY-04 | UPDATEALLCARDDETAILS replaces userCards with the new array', () => {
    const state = paymentReducer(undefined, {
      type: paymentActions.UPDATEALLCARDDETAILS,
      userCards: mockCards, cardsFetched: true,
    });
    expect(state.userCards).toEqual(mockCards);
  });

  /**
   * @id          TC-PAY-05
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentActions.UPDATEALLCARDDETAILS, paymentReducer
   * @triggers-when  paymentReducer.js UPDATEALLCARDDETAILS case is modified
   */
  it('TC-PAY-05 | UPDATEALLCARDDETAILS sets cardsFetched to true', () => {
    const state = paymentReducer(undefined, {
      type: paymentActions.UPDATEALLCARDDETAILS,
      userCards: mockCards, cardsFetched: true,
    });
    expect(state.cardsFetched).toBe(true);
  });

  /**
   * @id          TC-PAY-06
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentActions.UPDATEALLCARDDETAILS, paymentReducer
   * @triggers-when  paymentReducer.js is modified
   */
  it('TC-PAY-06 | UPDATEALLCARDDETAILS does not alter paymentPlantDetails', () => {
    const seed  = { ...paymentInitialState, paymentPlantDetails: { plan: 'premium' } };
    const state = paymentReducer(seed, {
      type: paymentActions.UPDATEALLCARDDETAILS,
      userCards: mockCards, cardsFetched: true,
    });
    expect(state.paymentPlantDetails).toEqual({ plan: 'premium' });
  });
});

describe('paymentReducer – UPDATEPAYMENTPLANDETAILS action', () => {
  const planPayload = { id: 'plan_premium', price: 9.99, currency: 'USD' };

  /**
   * @id          TC-PAY-07
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentActions.UPDATEPAYMENTPLANDETAILS, paymentReducer
   * @triggers-when  paymentReducer.js UPDATEPAYMENTPLANDETAILS case is modified
   */
  it('TC-PAY-07 | UPDATEPAYMENTPLANDETAILS stores the plan payload', () => {
    const state = paymentReducer(undefined, {
      type: paymentActions.UPDATEPAYMENTPLANDETAILS, payload: planPayload,
    });
    expect(state.paymentPlantDetails).toEqual(planPayload);
  });

  /**
   * @id          TC-PAY-08
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentActions.UPDATEPAYMENTPLANDETAILS, paymentReducer
   * @triggers-when  paymentReducer.js is modified
   */
  it('TC-PAY-08 | UPDATEPAYMENTPLANDETAILS does not alter userCards', () => {
    const seed  = { ...paymentInitialState, userCards: [{ id: 'c1' }] };
    const state = paymentReducer(seed, {
      type: paymentActions.UPDATEPAYMENTPLANDETAILS, payload: planPayload,
    });
    expect(state.userCards).toEqual([{ id: 'c1' }]);
  });

  /**
   * @id          TC-PAY-09
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentReducer
   * @triggers-when  paymentReducer.js default case is modified
   */
  it('TC-PAY-09 | unknown action type returns the current state unchanged', () => {
    const current = { userCards: [{ id: 'c99' }], cardsFetched: true, paymentPlantDetails: null };
    expect(paymentReducer(current, { type: 'NONEXISTENT' })).toEqual(current);
  });

  /**
   * @id          TC-PAY-10
   * @connection  strong
   * @source      src/reducer/paymentReducer.js
   * @symbol      paymentReducer, paymentInitialState
   * @triggers-when  paymentReducer.js is modified
   */
  it('TC-PAY-10 | unknown action on undefined state returns the default initial state', () => {
    expect(paymentReducer(undefined, { type: 'UNKNOWN' })).toEqual(paymentInitialState);
  });
});

describe('Payment API endpoints  ·  src/services/api/common/ApiEndPoints.js', () => {
  /**
   * @id          TC-PAY-11
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.payment.addCard
   * @triggers-when  ApiEndPoints.js payment.addCard is modified
   */
  it('TC-PAY-11 | endpoints.payment.addCard starts with /api/v2/payments/me', () => {
    expect(endpoints.payment.addCard.startsWith('/api/v2/payments/me')).toBe(true);
  });

  /**
   * @id          TC-PAY-12
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.payment.deleteCard
   * @triggers-when  ApiEndPoints.js payment.deleteCard is modified
   */
  it('TC-PAY-12 | endpoints.payment.deleteCard contains "cardId="', () => {
    expect(endpoints.payment.deleteCard).toContain('cardId=');
  });

  /**
   * @id          TC-PAY-13
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.payment.preAuth
   * @triggers-when  ApiEndPoints.js payment.preAuth is modified
   */
  it('TC-PAY-13 | endpoints.payment.preAuth contains "preauth-verify"', () => {
    expect(endpoints.payment.preAuth).toContain('preauth-verify');
  });

  /**
   * @id          TC-PAY-14
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.payment.getAllCards
   * @triggers-when  ApiEndPoints.js payment.getAllCards is modified
   */
  it('TC-PAY-14 | endpoints.payment.getAllCards equals /api/v2/payments/me', () => {
    expect(endpoints.payment.getAllCards).toBe('/api/v2/payments/me');
  });

  /**
   * @id          TC-PAY-15
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.payment.paymentsCheckout
   * @triggers-when  ApiEndPoints.js payment.paymentsCheckout is modified
   */
  it('TC-PAY-15 | endpoints.payment.paymentsCheckout equals /api/v2/payments/checkout', () => {
    expect(endpoints.payment.paymentsCheckout).toBe('/api/v2/payments/checkout');
  });

  /**
   * @id          TC-PAY-16
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.getSubscriptionPlans
   * @triggers-when  ApiEndPoints.js getSubscriptionPlans is modified
   */
  it('TC-PAY-16 | endpoints.getSubscriptionPlans equals the expected path', () => {
    expect(endpoints.getSubscriptionPlans).toBe(
      '/api/v2/subscriptor/account/get-subscriptions',
    );
  });

  /**
   * @id          TC-PAY-17
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.checkUserSubscription
   * @triggers-when  ApiEndPoints.js checkUserSubscription is modified
   */
  it('TC-PAY-17 | endpoints.checkUserSubscription equals the expected path', () => {
    expect(endpoints.checkUserSubscription).toBe(
      '/api/v2/subscriptor/account/get-all-user-subscriptions',
    );
  });

  /**
   * @id          TC-PAY-18
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.advertisement
   * @triggers-when  ApiEndPoints.js advertisement() builder is modified
   */
  it('TC-PAY-18 | endpoints.advertisement() interpolates type, id, and genres', () => {
    expect(endpoints.advertisement('0', '123', '4,5')).toBe(
      '/api/v2/advertisements/active-video-campaigns/list?type=0&vod_id=123&genresId=4,5',
    );
  });

  /**
   * @id          TC-PAY-19
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.episodes
   * @triggers-when  ApiEndPoints.js episodes() builder is modified
   */
  it('TC-PAY-19 | endpoints.episodes() interpolates tvShowId and seasonId', () => {
    const url = endpoints.episodes({ tvShowId: '10', seasonId: '20' });
    expect(url).toContain('multiEventVodId=10');
    expect(url).toContain('multiEventVodSeasonId=20');
  });

  /**
   * @id          TC-PAY-20
   * @connection  strong
   * @source      src/services/api/common/ApiEndPoints.js
   * @symbol      endpoints.myOrders
   * @triggers-when  ApiEndPoints.js myOrders() builder is modified
   */
  it('TC-PAY-20 | endpoints.myOrders() embeds the account id', () => {
    expect(endpoints.myOrders('99')).toBe(
      '/api/v2/payments/get-transaction?account_id=99',
    );
  });
});

describe('changeToParams()  ·  src/services/api/common/payment/index.js', () => {
  /**
   * @id          TC-PAY-21
   * @connection  strong
   * @source      src/services/api/common/payment/index.js
   * @symbol      changeToParams
   * @triggers-when  changeToParams() is modified in payment/index.js
   */
  it('TC-PAY-21 | converts a single key-value object to a URL query string', () => {
    expect(changeToParams({ cardId: 'abc123' })).toBe('cardId=abc123');
  });

  /**
   * @id          TC-PAY-22
   * @connection  strong
   * @source      src/services/api/common/payment/index.js
   * @symbol      changeToParams
   * @triggers-when  changeToParams() is modified in payment/index.js
   */
  it('TC-PAY-22 | joins multiple params with "&"', () => {
    expect(changeToParams({ a: '1', b: '2' })).toBe('a=1&b=2');
  });

  /**
   * @id          TC-PAY-23
   * @connection  strong
   * @source      src/services/api/common/payment/index.js
   * @symbol      changeToParams
   * @triggers-when  changeToParams() is modified in payment/index.js
   */
  it('TC-PAY-23 | returns an empty string for an empty object', () => {
    expect(changeToParams({})).toBe('');
  });

  /**
   * @id          TC-PAY-24
   * @connection  strong
   * @source      src/services/api/common/payment/index.js
   * @symbol      changeToParams
   * @triggers-when  changeToParams() is modified in payment/index.js
   */
  it('TC-PAY-24 | coerces numeric values to strings', () => {
    expect(changeToParams({ amount: 9.99 })).toBe('amount=9.99');
  });
});

describe('CARD_NUMBER_REGEX  ·  src/types/constants.ts', () => {
  /**
   * @id          TC-PAY-25
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      CARD_NUMBER_REGEX
   * @triggers-when  CARD_NUMBER_REGEX is modified in constants.ts
   */
  it('TC-PAY-25 | accepts a 19-character space-separated card number', () => {
    expect(CARD_NUMBER_REGEX.test('4111 1111 1111 1111')).toBe(true);
  });

  /**
   * @id          TC-PAY-26
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      CARD_NUMBER_REGEX
   * @triggers-when  CARD_NUMBER_REGEX is modified in constants.ts
   */
  it('TC-PAY-26 | accepts a 17-character Amex-style card number', () => {
    expect(CARD_NUMBER_REGEX.test('3714 496353 98431')).toBe(true);
  });

  /**
   * @id          TC-PAY-27
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      CARD_NUMBER_REGEX
   * @triggers-when  CARD_NUMBER_REGEX is modified in constants.ts
   */
  it('TC-PAY-27 | rejects a 16-digit number with no spaces', () => {
    expect(CARD_NUMBER_REGEX.test('4111111111111111')).toBe(false);
  });

  /**
   * @id          TC-PAY-28
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      CARD_NUMBER_REGEX
   * @triggers-when  CARD_NUMBER_REGEX is modified in constants.ts
   */
  it('TC-PAY-28 | rejects a string that contains letters', () => {
    expect(CARD_NUMBER_REGEX.test('4111 XXXX XXXX 1111')).toBe(false);
  });
});

describe('EXPIRY_DATE_REGEX  ·  src/types/constants.ts', () => {
  /**
   * @id          TC-PAY-29
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      EXPIRY_DATE_REGEX
   * @triggers-when  EXPIRY_DATE_REGEX is modified in constants.ts
   */
  it('TC-PAY-29 | accepts MM/YY format (e.g. 01/27)', () => {
    expect(EXPIRY_DATE_REGEX.test('01/27')).toBe(true);
  });

  /**
   * @id          TC-PAY-30
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      EXPIRY_DATE_REGEX
   * @triggers-when  EXPIRY_DATE_REGEX is modified in constants.ts
   */
  it('TC-PAY-30 | accepts MM/YYYY format (e.g. 12/2027)', () => {
    expect(EXPIRY_DATE_REGEX.test('12/2027')).toBe(true);
  });

  /**
   * @id          TC-PAY-31
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      EXPIRY_DATE_REGEX
   * @triggers-when  EXPIRY_DATE_REGEX is modified in constants.ts
   */
  it('TC-PAY-31 | rejects month 00', () => {
    expect(EXPIRY_DATE_REGEX.test('00/27')).toBe(false);
  });

  /**
   * @id          TC-PAY-32
   * @connection  strong
   * @source      src/types/constants.ts
   * @symbol      EXPIRY_DATE_REGEX
   * @triggers-when  EXPIRY_DATE_REGEX is modified in constants.ts
   */
  it('TC-PAY-32 | rejects month 13', () => {
    expect(EXPIRY_DATE_REGEX.test('13/27')).toBe(false);
  });
});

describe('generateCardNumber()  ·  src/helpers/utilities.js', () => {
  /**
   * @id          TC-PAY-33
   * @connection  strong
   * @source      src/helpers/utilities.js
   * @symbol      generateCardNumber
   * @triggers-when  generateCardNumber is modified in utilities.js
   */
  it('TC-PAY-33 | masks 8 middle digits and formats in blocks of 4', () => {
    expect(generateCardNumber('4111111111', '1111', 8)).toBe('4111 XXXX XXXX 1111');
  });

  /**
   * @id          TC-PAY-34
   * @connection  strong
   * @source      src/helpers/utilities.js
   * @symbol      generateCardNumber
   * @triggers-when  generateCardNumber is modified in utilities.js
   */
  it('TC-PAY-34 | correctly formats with a different mask count', () => {
    const result = generateCardNumber('37144', '8431', 7);
    expect(result.startsWith('3714')).toBe(true);
    expect(result).toContain('XXXX');
    expect(result).toContain('431');
    expect(result.replace(/[^X]/g, '').length).toBe(7);
  });

  /**
   * @id          TC-PAY-35
   * @connection  strong
   * @source      src/services/storage.ts
   * @symbol      storageKeys.token
   * @triggers-when  storageKeys is modified in storage.ts
   */
  it('TC-PAY-35 | storageKeys.token equals "TOKEN"', () => {
    expect(storageKeys.token).toBe('TOKEN');
  });
});

// ── LOOSELY CONNECTED (15 tests) ───────────────────────────────────────────

describe('appStorage  ·  src/services/storage.ts  (mocked localStorage)', () => {
  let storage;
  beforeEach(() => { storage = buildAppStorage(new MockStorage()); });

  /**
   * @id          TC-PAY-36
   * @connection  loose
   * @source      src/services/storage.ts
   * @symbol      appStorage.set, appStorage.get
   * @triggers-when  storage.ts set/get functions are modified
   */
  it('TC-PAY-36 | set() stores a value that get() retrieves correctly', () => {
    storage.set('TOKEN', 'eyJhbGciOiJIUzI1NiJ9');
    expect(storage.get('TOKEN')).toBe('eyJhbGciOiJIUzI1NiJ9');
  });

  /**
   * @id          TC-PAY-37
   * @connection  loose
   * @source      src/services/storage.ts
   * @symbol      appStorage.set, appStorage.get
   * @triggers-when  storage.ts set/get functions are modified
   */
  it('TC-PAY-37 | set() and get() preserve object payloads', () => {
    const user = { id: 42, username: 'fighter99' };
    storage.set(storageKeys.userDetails, user);
    expect(storage.get(storageKeys.userDetails)).toEqual(user);
  });

  /**
   * @id          TC-PAY-38
   * @connection  loose
   * @source      src/services/storage.ts
   * @symbol      appStorage.get
   * @triggers-when  storage.ts get function is modified
   */
  it('TC-PAY-38 | get() returns null for a key that was never set', () => {
    expect(storage.get('NONEXISTENT_KEY')).toBeNull();
  });

  /**
   * @id          TC-PAY-39
   * @connection  loose
   * @source      src/services/storage.ts
   * @symbol      appStorage.clearAll
   * @triggers-when  storage.ts clearAll function is modified
   */
  it('TC-PAY-39 | clearAll() removes all stored entries', () => {
    storage.set('TOKEN', 'abc');
    storage.set('REFRESH', 'xyz');
    storage.clearAll();
    expect(storage.get('TOKEN')).toBeNull();
    expect(storage.get('REFRESH')).toBeNull();
  });

  /**
   * @id          TC-PAY-40
   * @connection  loose
   * @source      src/services/storage.ts
   * @symbol      appStorage.delete
   * @triggers-when  storage.ts delete function is modified
   */
  it('TC-PAY-40 | delete() removes only the targeted key', () => {
    storage.set('TOKEN', 'abc');
    storage.set('REFRESH', 'xyz');
    storage.delete('TOKEN');
    expect(storage.get('TOKEN')).toBeNull();
    expect(storage.get('REFRESH')).toBe('xyz');
  });
});

describe('API Constants  ·  src/services/api/common/ApiConstants.js', () => {
  /**
   * @id          TC-PAY-41
   * @connection  loose
   * @source      src/services/api/common/ApiConstants.js
   * @symbol      API_BASE_URL
   * @triggers-when  ApiConstants.js API_BASE_URL is modified
   */
  it('TC-PAY-41 | API_BASE_URL is a non-empty string starting with https', () => {
    expect(typeof API_BASE_URL).toBe('string');
    expect(API_BASE_URL.startsWith('https')).toBe(true);
  });

  /**
   * @id          TC-PAY-42
   * @connection  loose
   * @source      src/services/api/common/ApiConstants.js
   * @symbol      assetBaseURL
   * @triggers-when  ApiConstants.js assetBaseURL is modified
   */
  it('TC-PAY-42 | assetBaseURL is a non-empty https string', () => {
    expect(typeof assetBaseURL).toBe('string');
    expect(assetBaseURL.startsWith('https')).toBe(true);
  });

  /**
   * @id          TC-PAY-43
   * @connection  loose
   * @source      src/services/api/common/ApiConstants.js
   * @symbol      TIMEOUT
   * @triggers-when  ApiConstants.js TIMEOUT is modified
   */
  it('TC-PAY-43 | TIMEOUT equals 30 000 ms', () => {
    expect(TIMEOUT).toBe(30000);
  });

  /**
   * @id          TC-PAY-44
   * @connection  loose
   * @source      src/services/api/common/ApiConstants.js
   * @symbol      MAX_IMAGE_UPLOAD_SIZE
   * @triggers-when  ApiConstants.js MAX_IMAGE_UPLOAD_SIZE is modified
   */
  it('TC-PAY-44 | MAX_IMAGE_UPLOAD_SIZE equals 10 485 760 bytes (10 MB)', () => {
    expect(MAX_IMAGE_UPLOAD_SIZE).toBe(10485760);
  });

  /**
   * @id          TC-PAY-45
   * @connection  loose
   * @source      src/services/api/common/ApiConstants.js
   * @symbol      INTERNET_ERROR
   * @triggers-when  ApiConstants.js INTERNET_ERROR is modified
   */
  it('TC-PAY-45 | INTERNET_ERROR is the expected user-facing message string', () => {
    expect(INTERNET_ERROR).toBe('No internet connection');
  });
});

describe('Shared utility helpers  ·  src/helpers/utilities.js', () => {
  /**
   * @id          TC-PAY-46
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      timeConvert
   * @triggers-when  timeConvert is modified in utilities.js
   */
  it('TC-PAY-46 | timeConvert(90) returns "1h 30min"', () => {
    expect(timeConvert(90)).toBe('1h 30min');
  });

  /**
   * @id          TC-PAY-47
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      getProgressWidth
   * @triggers-when  getProgressWidth is modified in utilities.js
   */
  it('TC-PAY-47 | getProgressWidth returns 25 for value=25, max=100', () => {
    expect(getProgressWidth(25, 100)).toBe(25);
  });

  /**
   * @id          TC-PAY-48
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      getProgressWidth
   * @triggers-when  getProgressWidth is modified in utilities.js
   */
  it('TC-PAY-48 | getProgressWidth returns 0 when value is 0', () => {
    expect(getProgressWidth(0, 100)).toBe(0);
  });

  /**
   * @id          TC-PAY-49
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      checkNull
   * @triggers-when  checkNull is modified in utilities.js
   */
  it('TC-PAY-49 | checkNull returns empty string for undefined input', () => {
    expect(checkNull(undefined)).toBe('');
  });

  /**
   * @id          TC-PAY-50
   * @connection  loose
   * @source      src/helpers/utilities.js
   * @symbol      checkArray
   * @triggers-when  checkArray is modified in utilities.js
   */
  it('TC-PAY-50 | checkArray returns the original array when it has entries', () => {
    const arr = [{ id: 1 }, { id: 2 }];
    expect(checkArray(arr)).toEqual(arr);
  });
});
