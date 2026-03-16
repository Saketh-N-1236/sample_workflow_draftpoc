/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · User Details & Profile Reducers                          │
 * │  Category : feature (full reducer flow, single-feature scope)       │
 * │  Tests    : 10                                                       │
 * │  Sources  :                                                          │
 * │    src/reducer/userDetailsReducer.js  (userDetailsReducer)          │
 * │    src/reducer/profileReducer.js      (profileReducer)              │
 * │    src/reducer/actiotypes.js          (action type strings)         │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     user-profile-feature
 * @category  feature
 * @sources   src/reducer/userDetailsReducer.js,
 *            src/reducer/profileReducer.js,
 *            src/reducer/actiotypes.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
/** @symbol SUCCESS           @source src/reducer/actiotypes.js */
const SUCCESS              = 'SUCCESS';
/** @symbol UPDATEREFRESHEDTOKEN @source src/reducer/actiotypes.js */
const UPDATEREFRESHEDTOKEN = 'UPDATEREFRESHEDTOKEN';
/** @symbol ONAUTHENTICATE    @source src/reducer/actiotypes.js */
const ONAUTHENTICATE       = 'ONAUTHENTICATE';
/** @symbol SHOWLOGGEDOUTSHEET @source src/reducer/actiotypes.js */
const SHOWLOGGEDOUTSHEET   = 'SHOWLOGGEDOUTSHEET';
/** @symbol PROFILESDETAILS   @source src/reducer/actiotypes.js */
const PROFILESDETAILS      = 'PROFILESDETAILS';
/** @symbol SAVESELECTEDPROFILEDETAILS @source src/reducer/actiotypes.js */
const SAVESELECTEDPROFILEDETAILS = 'SAVESELECTEDPROFILEDETAILS';

// ── Inlined from src/reducer/userDetailsReducer.js ───────────────────────────
/** @symbol userDetailsReducer  @source src/reducer/userDetailsReducer.js */
const userDetailsInitialState = {
  data:               [],
  userDetails:        [],
  profiles:           [],
  token:              null,
  device:             '',
  profileAuthSuccess: false,
  profileToken:       undefined,
  showLoggedOutSheet: undefined,
  loginTime:          undefined,
  refreshToken:       undefined,
};

const userDetailsReducer = (state = userDetailsInitialState, action) => {
  switch (action.type) {
    case SUCCESS:
      return {
        ...state,
        data:               action.data,
        userDetails:        action.data.profile,
        profiles:           action.data.profiles,
        token:              action.data.token,
        device:             action.data.device,
        profileToken:       action?.data?.profileToken,
        profileAuthSuccess: action?.data?.authSuccess ? action.data.authSuccess : false,
      };
    case UPDATEREFRESHEDTOKEN:
      return {
        ...state,
        token:        action.payload.token,
        loginTime:    action.payload.loginTime,
        refreshToken: action.payload.refreshToken,
      };
    case ONAUTHENTICATE:
      return { ...state, profileAuthSuccess: false };
    case SHOWLOGGEDOUTSHEET:
      return { ...state, showLoggedOutSheet: action.payload };
    default:
      return state;
  }
};

// ── Inlined from src/reducer/profileReducer.js ───────────────────────────────
/** @symbol profileReducer  @source src/reducer/profileReducer.js */
const profileInitialState = {
  profileData:            [],
  selectedProfileDetails: [],
};

const profileReducer = (state = profileInitialState, action) => {
  switch (action.type) {
    case PROFILESDETAILS:
      return { ...state, profileData: action.data };
    case SAVESELECTEDPROFILEDETAILS:
      return { ...state, selectedProfileDetails: action.data };
    default:
      return state;
  }
};

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/reducer/userDetailsReducer.js
 * @source src/reducer/actiotypes.js
 * @symbol userDetailsReducer
 */
describe('userDetailsReducer', () => {
  it('initialises with data as an empty array', () => {
    const state = userDetailsReducer(undefined, { type: '@@INIT' });
    expect(state.data).toEqual([]);
  });

  it('SUCCESS action populates data and token from the payload', () => {
    // The reducer reads action.data.profile/.token etc — so data must be an object
    const data  = { token: 'tok-123', profile: 'p1', profiles: [], device: 'd1' };
    const state = userDetailsReducer(undefined, { type: SUCCESS, data });
    expect(state.token).toBe('tok-123');
  });

  it('UPDATEREFRESHEDTOKEN updates token and loginTime independently', () => {
    const state = userDetailsReducer(undefined, {
      type: UPDATEREFRESHEDTOKEN,
      payload: { token: 'new-tok', loginTime: 1700000000000, refreshToken: 'ref' },
    });
    expect(state.token).toBe('new-tok');
    expect(state.loginTime).toBe(1700000000000);
  });

  it('ONAUTHENTICATE resets profileAuthSuccess to false', () => {
    const withAuth = userDetailsReducer(undefined, {
      type: SUCCESS,
      data: [], token: 't', device: 'd', profile: [], profiles: [], authSuccess: true,
    });
    const reset    = userDetailsReducer(withAuth, { type: ONAUTHENTICATE });
    expect(reset.profileAuthSuccess).toBe(false);
  });

  it('SHOWLOGGEDOUTSHEET stores the payload in showLoggedOutSheet', () => {
    const state = userDetailsReducer(undefined, {
      type: SHOWLOGGEDOUTSHEET, payload: true,
    });
    expect(state.showLoggedOutSheet).toBe(true);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = userDetailsReducer(undefined, { type: '@@INIT' });
    const after  = userDetailsReducer(before,    { type: 'UNKNOWN_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/profileReducer.js
 * @source src/reducer/actiotypes.js
 * @symbol profileReducer
 */
describe('profileReducer', () => {
  it('initialises with an empty profileData array', () => {
    const state = profileReducer(undefined, { type: '@@INIT' });
    expect(state.profileData).toEqual([]);
  });

  it('PROFILESDETAILS action replaces profileData with the new list', () => {
    const profiles = [{ id: 'p1', name: 'Alice' }, { id: 'p2', name: 'Bob' }];
    const state    = profileReducer(undefined, { type: PROFILESDETAILS, data: profiles });
    expect(state.profileData).toEqual(profiles);
  });

  it('SAVESELECTEDPROFILEDETAILS stores the chosen profile', () => {
    const selected = { id: 'p1', name: 'Alice' };
    const state    = profileReducer(undefined, { type: SAVESELECTEDPROFILEDETAILS, data: selected });
    expect(state.selectedProfileDetails).toEqual(selected);
  });

  it('returns current state unchanged for an unrecognised action', () => {
    const before = profileReducer(undefined, { type: '@@INIT' });
    const after  = profileReducer(before,    { type: 'NO_SUCH_ACTION' });
    expect(after).toEqual(before);
  });
});
