/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Auth, Login, Language, Content Reducers                  │
 * │  Category : feature (auth state, login session, language, rating)   │
 * │  Tests    : 30                                                      │
 * │  Sources  :                                                         │
 * │    src/reducer/signUpReducer.js          (signUpReducer)            │
 * │    src/reducer/loginUserNameReducer.js   (loginUserNameReducer)     │
 * │    src/reducer/userDetailsLoginReducer.js (userDetailsLoginReducer) │
 * │    src/reducer/languagereducer.js        (languagereducer)          │
 * │    src/reducer/ComposerReducer.js        (composerReducer)          │
 * │    src/reducer/shimmerReducers.js        (ShimmerReducer)           │
 * │    src/reducer/RatingReducer.js          (ratingReducer)            │
 * │    src/reducer/actiotypes.js             (action type strings)      │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     auth-reducers-feature
 * @category  feature
 * @sources   src/reducer/signUpReducer.js,
 *            src/reducer/loginUserNameReducer.js,
 *            src/reducer/userDetailsLoginReducer.js,
 *            src/reducer/languagereducer.js,
 *            src/reducer/ComposerReducer.js,
 *            src/reducer/shimmerReducers.js,
 *            src/reducer/RatingReducer.js,
 *            src/reducer/actiotypes.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
const SIGNUPDATA   = 'SIGNUPDATA';
const SIGNUPSUCCESS = 'SIGNUPSUCCESS';
const LOGINUSERNAME = 'LOGINUSERNAME';
const LOGINSUCCESS  = 'LOGINSUCCESS';
const LANGUAGE      = 'LANGUAGE';
const COMPOSERDATA  = 'COMPOSERDATA';
const UPDATE_SHIMMER = 'UPDATE_SHIMMER';
const RATING        = 'RATING';

// ── Inlined from src/reducer/signUpReducer.js ────────────────────────────────
/** @symbol signUpReducer  @source src/reducer/signUpReducer.js */
const signUpInitialState = { isAuthenticated: false };

const signUpReducer = (state = signUpInitialState, action) => {
  switch (action.type) {
    case SIGNUPDATA:
      return { ...state, data: action.data };
    case SIGNUPSUCCESS:
      return { ...state, isAuthenticated: action.isAuthenticated };
    default:
      return state;
  }
};

// ── Inlined from src/reducer/loginUserNameReducer.js ─────────────────────────
/** @symbol loginUserNameReducer  @source src/reducer/loginUserNameReducer.js */
const loginUserNameInitialState = { loginuserName: '' };

function loginUserNameReducer(state = loginUserNameInitialState, action) {
  switch (action.type) {
    case LOGINUSERNAME:
      return { ...state, loginuserName: action.data };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/userDetailsLoginReducer.js ──────────────────────
/** @symbol userDetailsLoginReducer  @source src/reducer/userDetailsLoginReducer.js */
const userDetailsLoginInitialState = { userId: '', data: [] };

function userDetailsLoginReducer(state = userDetailsLoginInitialState, action) {
  switch (action.type) {
    case LOGINSUCCESS:
      return {
        ...state,
        data:       action.data,
        loginToken: action.data.token,
        userId:     action.data.userId,
      };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/languagereducer.js ──────────────────────────────
/** @symbol languagereducer  @source src/reducer/languagereducer.js */
const languageInitialState = { selectlanguage: 'en' };

function languagereducer(state = languageInitialState, action) {
  switch (action.type) {
    case LANGUAGE:
      return { ...state, selectlanguage: action.data };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/ComposerReducer.js ──────────────────────────────
/** @symbol composerReducer  @source src/reducer/ComposerReducer.js */
const composerInitialState = { loginData: [] };

function composerReducer(state = composerInitialState, action) {
  switch (action.type) {
    case COMPOSERDATA:
      return { ...state, loginData: action.data };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/shimmerReducers.js ──────────────────────────────
/** @symbol ShimmerReducer  @source src/reducer/shimmerReducers.js */
const shimmerInitialState = { shimmerStatus: false };

function ShimmerReducer(state = shimmerInitialState, action) {
  switch (action.type) {
    case UPDATE_SHIMMER:
      return { ...state, shimmerStatus: action.payload };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/RatingReducer.js ────────────────────────────────
/** @symbol ratingReducer  @source src/reducer/RatingReducer.js */
const ratingInitialState = { ratedData: [] };

function ratingReducer(state = ratingInitialState, action) {
  switch (action.type) {
    case RATING:
      return { ...state, ratedData: action.rate };
    default:
      return state;
  }
}

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/reducer/signUpReducer.js
 * @symbol signUpReducer
 */
describe('signUpReducer', () => {
  it('initialises with isAuthenticated as false', () => {
    const state = signUpReducer(undefined, { type: '@@INIT' });
    expect(state.isAuthenticated).toBe(false);
  });

  it('SIGNUPDATA stores the registration form data', () => {
    const data  = { email: 'user@example.com', username: 'testuser' };
    const state = signUpReducer(undefined, { type: SIGNUPDATA, data });
    expect(state.data).toEqual(data);
  });

  it('SIGNUPSUCCESS sets isAuthenticated to true on successful registration', () => {
    const state = signUpReducer(undefined, { type: SIGNUPSUCCESS, isAuthenticated: true });
    expect(state.isAuthenticated).toBe(true);
  });

  it('SIGNUPSUCCESS with false resets isAuthenticated (e.g. on logout)', () => {
    const authed = signUpReducer(undefined, { type: SIGNUPSUCCESS, isAuthenticated: true });
    const reset  = signUpReducer(authed,    { type: SIGNUPSUCCESS, isAuthenticated: false });
    expect(reset.isAuthenticated).toBe(false);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = signUpReducer(undefined, { type: '@@INIT' });
    const after  = signUpReducer(before,    { type: 'UNKNOWN_SIGNUP_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/loginUserNameReducer.js
 * @symbol loginUserNameReducer
 */
describe('loginUserNameReducer', () => {
  it('initialises with loginuserName as an empty string', () => {
    const state = loginUserNameReducer(undefined, { type: '@@INIT' });
    expect(state.loginuserName).toBe('');
  });

  it('LOGINUSERNAME stores the typed username', () => {
    const state = loginUserNameReducer(undefined, { type: LOGINUSERNAME, data: 'john_doe' });
    expect(state.loginuserName).toBe('john_doe');
  });

  it('LOGINUSERNAME can overwrite a previously stored username', () => {
    const first  = loginUserNameReducer(undefined, { type: LOGINUSERNAME, data: 'john_doe' });
    const second = loginUserNameReducer(first,     { type: LOGINUSERNAME, data: 'jane_doe' });
    expect(second.loginuserName).toBe('jane_doe');
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = loginUserNameReducer(undefined, { type: '@@INIT' });
    const after  = loginUserNameReducer(before,    { type: 'UNKNOWN_LOGIN_USERNAME_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/userDetailsLoginReducer.js
 * @symbol userDetailsLoginReducer
 */
describe('userDetailsLoginReducer', () => {
  it('initialises with userId as an empty string', () => {
    const state = userDetailsLoginReducer(undefined, { type: '@@INIT' });
    expect(state.userId).toBe('');
  });

  it('initialises with data as an empty array', () => {
    const state = userDetailsLoginReducer(undefined, { type: '@@INIT' });
    expect(state.data).toEqual([]);
  });

  it('LOGINSUCCESS stores the full login response in data', () => {
    const loginData = { userId: 'u-123', token: 'abc-token', name: 'John' };
    const state     = userDetailsLoginReducer(undefined, { type: LOGINSUCCESS, data: loginData });
    expect(state.data).toEqual(loginData);
  });

  it('LOGINSUCCESS extracts userId from the response', () => {
    const loginData = { userId: 'u-456', token: 'xyz-token' };
    const state     = userDetailsLoginReducer(undefined, { type: LOGINSUCCESS, data: loginData });
    expect(state.userId).toBe('u-456');
  });

  it('LOGINSUCCESS stores the auth token in loginToken', () => {
    const loginData = { userId: 'u-789', token: 'bearer-token-xyz' };
    const state     = userDetailsLoginReducer(undefined, { type: LOGINSUCCESS, data: loginData });
    expect(state.loginToken).toBe('bearer-token-xyz');
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = userDetailsLoginReducer(undefined, { type: '@@INIT' });
    const after  = userDetailsLoginReducer(before,    { type: 'UNKNOWN_LOGIN_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/languagereducer.js
 * @symbol languagereducer
 */
describe('languagereducer', () => {
  it("initialises with default language code 'en'", () => {
    const state = languagereducer(undefined, { type: '@@INIT' });
    expect(state.selectlanguage).toBe('en');
  });

  it('LANGUAGE stores a new language code', () => {
    const state = languagereducer(undefined, { type: LANGUAGE, data: 'fr' });
    expect(state.selectlanguage).toBe('fr');
  });

  it('LANGUAGE can switch between multiple languages', () => {
    const french   = languagereducer(undefined, { type: LANGUAGE, data: 'fr' });
    const spanish  = languagereducer(french,    { type: LANGUAGE, data: 'es' });
    expect(spanish.selectlanguage).toBe('es');
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = languagereducer(undefined, { type: '@@INIT' });
    const after  = languagereducer(before,    { type: 'UNKNOWN_LANGUAGE_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/ComposerReducer.js
 * @symbol composerReducer
 */
describe('composerReducer', () => {
  it('initialises with loginData as an empty array', () => {
    const state = composerReducer(undefined, { type: '@@INIT' });
    expect(state.loginData).toEqual([]);
  });

  it('COMPOSERDATA stores the composer configuration data', () => {
    const data  = [{ type: 'banner', items: 5 }, { type: 'carousel', items: 10 }];
    const state = composerReducer(undefined, { type: COMPOSERDATA, data });
    expect(state.loginData).toEqual(data);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = composerReducer(undefined, { type: '@@INIT' });
    const after  = composerReducer(before,    { type: 'UNKNOWN_COMPOSER_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/shimmerReducers.js
 * @symbol ShimmerReducer
 */
describe('ShimmerReducer', () => {
  it('initialises with shimmerStatus as false', () => {
    const state = ShimmerReducer(undefined, { type: '@@INIT' });
    expect(state.shimmerStatus).toBe(false);
  });

  it('UPDATE_SHIMMER sets shimmerStatus to true when loading starts', () => {
    const state = ShimmerReducer(undefined, { type: UPDATE_SHIMMER, payload: true });
    expect(state.shimmerStatus).toBe(true);
  });

  it('UPDATE_SHIMMER sets shimmerStatus back to false when loading ends', () => {
    const loading = ShimmerReducer(undefined, { type: UPDATE_SHIMMER, payload: true });
    const done    = ShimmerReducer(loading,   { type: UPDATE_SHIMMER, payload: false });
    expect(done.shimmerStatus).toBe(false);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = ShimmerReducer(undefined, { type: '@@INIT' });
    const after  = ShimmerReducer(before,    { type: 'UNKNOWN_SHIMMER_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/RatingReducer.js
 * @symbol ratingReducer
 */
describe('ratingReducer', () => {
  it('initialises with ratedData as an empty array', () => {
    const state = ratingReducer(undefined, { type: '@@INIT' });
    expect(state.ratedData).toEqual([]);
  });

  it('RATING stores the rated content data', () => {
    const rate  = [{ contentId: 'm1', score: 5 }];
    const state = ratingReducer(undefined, { type: RATING, rate });
    expect(state.ratedData).toEqual(rate);
  });

  it('RATING replaces any previously stored rated data', () => {
    const first  = ratingReducer(undefined, { type: RATING, rate: [{ contentId: 'm1', score: 4 }] });
    const second = ratingReducer(first,     { type: RATING, rate: [{ contentId: 'm2', score: 5 }] });
    expect(second.ratedData).toHaveLength(1);
    expect(second.ratedData[0].contentId).toBe('m2');
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = ratingReducer(undefined, { type: '@@INIT' });
    const after  = ratingReducer(before,    { type: 'UNKNOWN_RATING_ACTION' });
    expect(after).toEqual(before);
  });
});
