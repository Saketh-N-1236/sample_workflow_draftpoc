/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  CROSS-DEPENDENT · Payment Reducer + Actions + Storage              │
 * │  Category : cross-dependent (spans multiple source files)           │
 * │  Tests    : 28                                                       │
 * │  Sources  :                                                          │
 * │    src/reducer/paymentReducer.js   (paymentActions, paymentReducer)  │
 * │    src/reducer/actions.js          (updateUserCards, updatePayment…) │
 * │    src/services/storage.ts         (storageKeys)                     │
 * │    src/types/constants.ts          (FULL_CARD_REGEX)                 │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     payment-state-cross
 * @category  cross-dependent
 * @sources   src/reducer/paymentReducer.js,
 *            src/reducer/actions.js,
 *            src/services/storage.ts,
 *            src/types/constants.ts
 */

// ── Inlined from src/reducer/paymentReducer.js ───────────────────────────────
/** @symbol paymentActions  @source src/reducer/paymentReducer.js */
const paymentActions = {
  UPDATEALLCARDDETAILS:    'UPDATE_STORED_USER_ALL_CARD_DETAILS',
  UPDATEPAYMENTPLANDETAILS:'UPDATE_PAYMENT_PLAN_DETAILS',
  RESETPAYMENT:            'RESET_PAYMENT_STATE',
  CLEARCARDS:              'CLEAR_USER_CARDS',
};

const paymentInitialState = {
  userCards:           [],
  cardsFetched:        false,
  paymentPlantDetails: undefined,
  paymentError:        null,
};

/** @symbol paymentReducer  @source src/reducer/paymentReducer.js */
function paymentReducer(state = paymentInitialState, action) {
  switch (action.type) {
    case paymentActions.UPDATEALLCARDDETAILS:
      return { ...state, userCards: action.userCards, cardsFetched: action.cardsFetched };
    case paymentActions.UPDATEPAYMENTPLANDETAILS:
      return { ...state, paymentPlantDetails: action.payload };
    case paymentActions.RESETPAYMENT:
      return { ...paymentInitialState };
    case paymentActions.CLEARCARDS:
      return { ...state, userCards: [], cardsFetched: false };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/actions.js ──────────────────────────────────────
/** @symbol updateUserCards  @source src/reducer/actions.js */
const updateUserCards = (userCards, cardsFetched = false) => ({
  type: paymentActions.UPDATEALLCARDDETAILS,
  userCards,
  cardsFetched,
  normalisedCards: Array.isArray(userCards)
    ? userCards.map(c => ({ ...c, last4: String(c?.last4 ?? '') }))
    : [],
});

/** @symbol updatePaymentPlanDetails  @source src/reducer/actions.js */
const updatePaymentPlanDetails = (payload, billingCycle = 'monthly') => ({
  type: paymentActions.UPDATEPAYMENTPLANDETAILS,
  payload,
  billingCycle,
});

// ── Inlined from src/services/storage.ts ─────────────────────────────────────
/** @symbol storageKeys  @source src/services/storage.ts */
const storageKeys = {
  token:                'ACCESS_TOKEN',
  sessionId:            'SESSION_ID',
  stripePaymentDetails: 'STRIPEPAYMENTDETAILS',
  subscriptionDetails:  'SUBSCRIPTION_DETAILS',
};

// ── Inlined from src/types/constants.ts ──────────────────────────────────────
/** @symbol FULL_CARD_REGEX  @source src/types/constants.ts */
const FULL_CARD_REGEX =
  /^([0-9 ]{16,16}|[0-9 ]{17,17}|[0-9 ]{18,18}|[0-9 ]{19,19})$/;

// ─────────────────────────────────────────────────────────────────────────────

/**
 * Cross-dependency: updateUserCards action creator (actions.js) dispatched
 * into paymentReducer (paymentReducer.js) — two files, one flow.
 *
 * @source src/reducer/actions.js
 * @source src/reducer/paymentReducer.js
 * @symbol updateUserCards
 * @symbol paymentReducer
 */
describe('updateUserCards action dispatched into paymentReducer', () => {
  it('populates userCards in state after dispatch', () => {
    const cards  = [{ id: '1', last4: '1111' }];
    const action = updateUserCards(cards, true);
    const state  = paymentReducer(undefined, action);
    expect(state.userCards).toEqual(cards);
  });

  it('sets cardsFetched to true when cards are provided', () => {
    const action = updateUserCards([{ id: '2' }], true);
    const state  = paymentReducer(undefined, action);
    expect(state.cardsFetched).toBe(true);
  });

  it('clears userCards when dispatched with an empty array', () => {
    const filled  = paymentReducer(undefined, updateUserCards([{ id: '1' }], true));
    const cleared = paymentReducer(filled, updateUserCards([], false));
    expect(cleared.userCards).toEqual([]);
    expect(cleared.cardsFetched).toBe(false);
  });

  it('sets cardsFetched to false by default when the second argument is omitted', () => {
    const action = updateUserCards([]);
    expect(action.cardsFetched).toBe(false);
  });
});

/**
 * Cross-dependency: updateUserCards (actions.js) builds a normalisedCards
 * array ensuring last4 is always a string — analytics contract.
 *
 * @source src/reducer/actions.js
 * @symbol updateUserCards
 * @symbol normalisedCards
 */
describe('updateUserCards normalisedCards contract', () => {
  it('normalisedCards includes last4 coerced to a string for each card', () => {
    const action = updateUserCards([{ id: '1', last4: 1234 }], true);
    expect(action.normalisedCards[0].last4).toBe('1234');
  });

  it('normalisedCards converts a missing last4 to an empty string', () => {
    const action = updateUserCards([{ id: '2' }], true);
    expect(action.normalisedCards[0].last4).toBe('');
  });

  it('normalisedCards is an empty array when given an empty cards list', () => {
    const action = updateUserCards([], true);
    expect(action.normalisedCards).toEqual([]);
  });

  it('normalisedCards preserves all other card fields unchanged', () => {
    const action = updateUserCards([{ id: 'c1', brand: 'Visa', last4: '9999' }], true);
    expect(action.normalisedCards[0].brand).toBe('Visa');
    expect(action.normalisedCards[0].id).toBe('c1');
  });
});

/**
 * Cross-dependency: updatePaymentPlanDetails (actions.js) and the
 * UPDATEPAYMENTPLANDETAILS case inside paymentReducer (paymentReducer.js).
 *
 * @source src/reducer/actions.js
 * @source src/reducer/paymentReducer.js
 * @symbol updatePaymentPlanDetails
 * @symbol paymentReducer
 */
describe('updatePaymentPlanDetails action and paymentReducer', () => {
  it('stores the subscription plan object in paymentPlantDetails', () => {
    const plan   = { id: 'plan-1', name: 'Premium', price: 9.99 };
    const action = updatePaymentPlanDetails(plan);
    const state  = paymentReducer(undefined, action);
    expect(state.paymentPlantDetails).toEqual(plan);
  });

  it('defaults billingCycle to monthly when no second argument is supplied', () => {
    const action = updatePaymentPlanDetails({ id: 'plan-1' });
    expect(action.billingCycle).toBe('monthly');
  });

  it('uses the provided billingCycle when passed explicitly', () => {
    const action = updatePaymentPlanDetails({ id: 'plan-2' }, 'annual');
    expect(action.billingCycle).toBe('annual');
  });

  it('does not mutate userCards when a plan update is dispatched', () => {
    const withCards = paymentReducer(undefined, updateUserCards([{ id: 'c1' }], true));
    const withPlan  = paymentReducer(withCards, updatePaymentPlanDetails({ id: 'p1' }));
    expect(withPlan.userCards).toEqual([{ id: 'c1' }]);
  });
});

/**
 * Cross-dependency: RESETPAYMENT action resets the full payment state to the
 * initial state — tests the new action added to paymentReducer.
 *
 * @source src/reducer/paymentReducer.js
 * @symbol paymentActions.RESETPAYMENT
 * @symbol paymentReducer
 */
describe('paymentActions.RESETPAYMENT restores initial payment state', () => {
  it('resets userCards to an empty array', () => {
    const loaded = paymentReducer(undefined, updateUserCards([{ id: 'c1' }], true));
    const reset  = paymentReducer(loaded, { type: paymentActions.RESETPAYMENT });
    expect(reset.userCards).toEqual([]);
  });

  it('resets cardsFetched to false', () => {
    const loaded = paymentReducer(undefined, updateUserCards([{ id: 'c1' }], true));
    const reset  = paymentReducer(loaded, { type: paymentActions.RESETPAYMENT });
    expect(reset.cardsFetched).toBe(false);
  });

  it('resets paymentPlantDetails to undefined', () => {
    const withPlan = paymentReducer(undefined, updatePaymentPlanDetails({ id: 'p1' }));
    const reset    = paymentReducer(withPlan, { type: paymentActions.RESETPAYMENT });
    expect(reset.paymentPlantDetails).toBeUndefined();
  });

  it('resets paymentError to null', () => {
    const reset = paymentReducer(undefined, { type: paymentActions.RESETPAYMENT });
    expect(reset.paymentError).toBeNull();
  });
});

/**
 * Cross-dependency: CLEARCARDS action (paymentReducer.js) tests.
 *
 * @source src/reducer/paymentReducer.js
 * @symbol paymentActions.CLEARCARDS
 * @symbol paymentReducer
 */
describe('paymentActions.CLEARCARDS resets only card data', () => {
  it('resets userCards to an empty array', () => {
    const loaded  = paymentReducer(undefined, updateUserCards([{ id: '1' }], true));
    const cleared = paymentReducer(loaded, { type: paymentActions.CLEARCARDS });
    expect(cleared.userCards).toEqual([]);
  });

  it('resets cardsFetched back to false after clearing', () => {
    const loaded  = paymentReducer(undefined, updateUserCards([{ id: '1' }], true));
    const cleared = paymentReducer(loaded, { type: paymentActions.CLEARCARDS });
    expect(cleared.cardsFetched).toBe(false);
  });

  it('CLEARCARDS preserves paymentPlantDetails when clearing cards', () => {
    const withPlan  = paymentReducer(undefined, updatePaymentPlanDetails({ id: 'p1' }));
    const withCards = paymentReducer(withPlan, updateUserCards([{ id: 'c1' }], true));
    const cleared   = paymentReducer(withCards, { type: paymentActions.CLEARCARDS });
    expect(cleared.paymentPlantDetails).toEqual({ id: 'p1' });
  });
});

/**
 * Cross-dependency: storageKeys (storage.ts) values used during payment flow.
 *
 * @source src/services/storage.ts
 * @source src/types/constants.ts
 * @symbol storageKeys
 * @symbol FULL_CARD_REGEX
 */
describe('storageKeys align with payment flow expectations', () => {
  it('storageKeys.stripePaymentDetails equals STRIPEPAYMENTDETAILS', () => {
    expect(storageKeys.stripePaymentDetails).toBe('STRIPEPAYMENTDETAILS');
  });

  it('storageKeys.token equals ACCESS_TOKEN', () => {
    expect(storageKeys.token).toBe('ACCESS_TOKEN');
  });

  it('storageKeys.subscriptionDetails equals SUBSCRIPTION_DETAILS', () => {
    expect(storageKeys.subscriptionDetails).toBe('SUBSCRIPTION_DETAILS');
  });
});

/**
 * Cross-dependency: FULL_CARD_REGEX (constants.ts) validates input that
 * goes through the payment checkout flow.
 *
 * @source src/types/constants.ts
 * @source src/reducer/paymentReducer.js
 * @symbol FULL_CARD_REGEX
 */
describe('FULL_CARD_REGEX validates payment checkout input', () => {
  it('accepts a standard 19-character spaced card number', () => {
    expect(FULL_CARD_REGEX.test('4111 1111 1111 1111')).toBe(true);
  });

  it('accepts a 16-character contiguous card number', () => {
    expect(FULL_CARD_REGEX.test('4111111111111111')).toBe(true);
  });

  it('rejects a card number shorter than 16 characters', () => {
    expect(FULL_CARD_REGEX.test('4111 1111 1111')).toBe(false);
  });

  it('rejects a card number that contains letters', () => {
    expect(FULL_CARD_REGEX.test('4111 ABCD 1111 1111 ')).toBe(false);
  });
});
