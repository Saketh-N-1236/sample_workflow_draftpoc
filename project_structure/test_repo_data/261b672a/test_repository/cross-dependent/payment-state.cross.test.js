/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  CROSS-DEPENDENT · Payment Reducer + Actions + Storage              │
 * │  Category : cross-dependent (spans multiple source files)           │
 * │  Tests    : 12                                                       │
 * │  Sources  :                                                          │
 * │    src/reducer/paymentReducer.js   (paymentActions, paymentReducer)  │
 * │    src/reducer/actions.js          (updateUserCards, updatePayment…) │
 * │    src/services/storage.ts         (storageKeys)                     │
 * │    src/types/constants.ts          (CARD_NUMBER_REGEX)               │
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
  CLEARCARDS:              'CLEAR_USER_CARDS',
};

const paymentInitialState = {
  userCards:           [],
  cardsFetched:        false,
  paymentPlantDetails: undefined,
};

/** @symbol paymentReducer  @source src/reducer/paymentReducer.js */
function paymentReducer(state = paymentInitialState, action) {
  switch (action.type) {
    case paymentActions.UPDATEALLCARDDETAILS:
      return { ...state, userCards: action.userCards, cardsFetched: action.cardsFetched };
    case paymentActions.UPDATEPAYMENTPLANDETAILS:
      return { ...state, paymentPlantDetails: action.payload };
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
});

/** @symbol updatePaymentPlanDetails  @source src/reducer/actions.js */
const updatePaymentPlanDetails = payload => ({
  type: paymentActions.UPDATEPAYMENTPLANDETAILS,
  payload,
});

// ── Inlined from src/services/storage.ts ─────────────────────────────────────
/** @symbol storageKeys  @source src/services/storage.ts */
const storageKeys = {
  token:                 'TOKEN',
  stripePaymentDetails:  'STRIPEPAYMENTDETAILS',
  subscriptionDetails:   'SUBSCRIPTION_DETAILS',
};

// ── Inlined from src/types/constants.ts ──────────────────────────────────────
/** @symbol CARD_NUMBER_REGEX  @source src/types/constants.ts */
const CARD_NUMBER_REGEX =
  /^([0-9 ]{17,17}|[0-9 ]{18,18}|[0-9 ]{19,19})$/;

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

  it('does not mutate userCards when a plan update is dispatched', () => {
    const withCards = paymentReducer(undefined, updateUserCards([{ id: 'c1' }], true));
    const withPlan  = paymentReducer(withCards, updatePaymentPlanDetails({ id: 'p1' }));
    expect(withPlan.userCards).toEqual([{ id: 'c1' }]);
  });
});

/**
 * Cross-dependency: CLEARCARDS action (paymentReducer.js) — new action added
 * in Scenario 2; tests verify reducer + action key contract together.
 *
 * @source src/reducer/paymentReducer.js
 * @symbol paymentActions
 * @symbol paymentReducer
 */
describe('paymentActions.CLEARCARDS resets payment state', () => {
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
});

/**
 * Cross-dependency: storageKeys (storage.ts) values used during payment flow —
 * storage key names must align with what the payment screens write/read.
 *
 * @source src/services/storage.ts
 * @source src/types/constants.ts
 * @symbol storageKeys
 * @symbol CARD_NUMBER_REGEX
 */
describe('storageKeys align with payment flow expectations', () => {
  it('storageKeys.stripePaymentDetails equals STRIPEPAYMENTDETAILS', () => {
    expect(storageKeys.stripePaymentDetails).toBe('STRIPEPAYMENTDETAILS');
  });

  it('storageKeys.token equals TOKEN', () => {
    expect(storageKeys.token).toBe('TOKEN');
  });
});

/**
 * Cross-dependency: CARD_NUMBER_REGEX (constants.ts) validates input that
 * goes through the payment checkout flow (payment API path).
 *
 * @source src/types/constants.ts
 * @source src/reducer/paymentReducer.js
 * @symbol CARD_NUMBER_REGEX
 * @symbol paymentActions
 */
describe('CARD_NUMBER_REGEX validates checkout flow input', () => {
  it('accepts a standard 19-character card number with spaces', () => {
    // 19 chars: "4111 1111 1111 1111" (4+1+4+1+4+1+4 = 19)
    expect(CARD_NUMBER_REGEX.test('4111 1111 1111 1111')).toBe(true);
  });

  it('rejects a card number shorter than 17 characters', () => {
    expect(CARD_NUMBER_REGEX.test('4111 1111 1111')).toBe(false);
  });

  it('rejects a card number that contains letters', () => {
    expect(CARD_NUMBER_REGEX.test('4111 ABCD 1111 1111 ')).toBe(false);
  });
});
