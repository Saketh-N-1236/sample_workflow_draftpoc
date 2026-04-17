/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · User Details & Profile Reducers                          │
 * │  Category : feature (full reducer flow, single-feature scope)       │
 * │  Tests    : 26                                                       │
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
const UPDATEREFRESHEDTOKEN = 'REFRESH_TOKEN_UPDATE';
/** @symbol ONAUTHENTICATE    @source src/reducer/actiotypes.js */
const ONAUTHENTICATE       = 'ONAUTHENTICATE';
/** @symbol SHOWLOGGEDOUTSHEET @source src/reducer/actiotypes.js */
const SHOWLOGGEDOUTSHEET   = 'SHOWLOGGEDOUTSHEET';
/** @symbol PROFILESDETAILS   @source src/reducer/actiotypes.js */
const PROFILESDETAILS      = 'PROFILESDETAILS';
/** @symbol SAVESELECTEDPROFILEDETAILS @source src/reducer/actiotypes.js */
const SAVESELECTEDPROFILEDETAILS = 'SAVESELECTEDPROFILEDETAILS';

// ── Inlined from src/reducer/userDetailsReducer.js ───────────────────────────
/**
 * @symbol userDetailsReducer  @source src/reducer/userDetailsReducer.js
 * NOTE: initial data is null (not []) matching actual source.
 */
const userDetailsInitialState = {
  data:               null,
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
      return { ...state, profileAuthSuccess: false, profileToken: undefined };
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
  it('initialises with data as null', () => {
    const state = userDetailsReducer(undefined, { type: '@@INIT' });
    expect(state.data).toBeNull();
  });

  it('initialises with an empty profiles array', () => {
    const state = userDetailsReducer(undefined, { type: '@@INIT' });
    expect(state.profiles).toEqual([]);
  });

  it('initialises with token as null when no storage token exists', () => {
    const state = userDetailsReducer(undefined, { type: '@@INIT' });
    expect(state.token).toBeNull();
  });

  it('initialises profileAuthSuccess as false', () => {
    const state = userDetailsReducer(undefined, { type: '@@INIT' });
    expect(state.profileAuthSuccess).toBe(false);
  });

  it('SUCCESS action populates data and token from the payload', () => {
    const data  = { token: 'tok-123', profile: 'p1', profiles: [], device: 'd1' };
    const state = userDetailsReducer(undefined, { type: SUCCESS, data });
    expect(state.token).toBe('tok-123');
    expect(state.data).toEqual(data);
  });

  it('SUCCESS action sets profiles from payload', () => {
    const profiles = [{ id: 'p1' }, { id: 'p2' }];
    const data     = { token: 't', profile: null, profiles, device: '' };
    const state    = userDetailsReducer(undefined, { type: SUCCESS, data });
    expect(state.profiles).toEqual(profiles);
  });

  it('SUCCESS action sets device from payload', () => {
    const data  = { token: 't', profile: null, profiles: [], device: 'android' };
    const state = userDetailsReducer(undefined, { type: SUCCESS, data });
    expect(state.device).toBe('android');
  });

  it('SUCCESS action sets profileAuthSuccess to true when authSuccess is provided', () => {
    const data  = { token: 't', profile: null, profiles: [], device: '', authSuccess: true };
    const state = userDetailsReducer(undefined, { type: SUCCESS, data });
    expect(state.profileAuthSuccess).toBe(true);
  });

  it('SUCCESS action sets profileToken from the data payload', () => {
    const data  = { token: 't', profile: null, profiles: [], device: '', profileToken: 'pt-abc' };
    const state = userDetailsReducer(undefined, { type: SUCCESS, data });
    expect(state.profileToken).toBe('pt-abc');
  });

  it('UPDATEREFRESHEDTOKEN updates token and loginTime independently', () => {
    const state = userDetailsReducer(undefined, {
      type:    UPDATEREFRESHEDTOKEN,
      payload: { token: 'new-tok', loginTime: 1700000000000, refreshToken: 'ref' },
    });
    expect(state.token).toBe('new-tok');
    expect(state.loginTime).toBe(1700000000000);
  });

  it('UPDATEREFRESHEDTOKEN stores the refresh token', () => {
    const state = userDetailsReducer(undefined, {
      type:    UPDATEREFRESHEDTOKEN,
      payload: { token: 't', loginTime: 0, refreshToken: 'ref-xyz' },
    });
    expect(state.refreshToken).toBe('ref-xyz');
  });

  it('UPDATEREFRESHEDTOKEN does not overwrite data or profiles', () => {
    const withData = userDetailsReducer(undefined, {
      type: SUCCESS,
      data: { token: 't', profile: null, profiles: [{ id: 'p1' }], device: '' },
    });
    const updated  = userDetailsReducer(withData, {
      type:    UPDATEREFRESHEDTOKEN,
      payload: { token: 'new', loginTime: 0, refreshToken: 'r' },
    });
    expect(updated.profiles).toEqual([{ id: 'p1' }]);
  });

  it('ONAUTHENTICATE resets profileAuthSuccess to false', () => {
    const withAuth = userDetailsReducer(undefined, {
      type: SUCCESS,
      data: { token: 't', profile: null, profiles: [], device: '', authSuccess: true },
    });
    const reset    = userDetailsReducer(withAuth, { type: ONAUTHENTICATE });
    expect(reset.profileAuthSuccess).toBe(false);
  });

  it('ONAUTHENTICATE resets profileToken to undefined', () => {
    const withToken = userDetailsReducer(undefined, {
      type: SUCCESS,
      data: { token: 't', profile: null, profiles: [], device: '', profileToken: 'pt' },
    });
    const reset = userDetailsReducer(withToken, { type: ONAUTHENTICATE });
    expect(reset.profileToken).toBeUndefined();
  });

  it('SHOWLOGGEDOUTSHEET stores a truthy payload in showLoggedOutSheet', () => {
    const state = userDetailsReducer(undefined, {
      type: SHOWLOGGEDOUTSHEET, payload: true,
    });
    expect(state.showLoggedOutSheet).toBe(true);
  });

  it('SHOWLOGGEDOUTSHEET stores a string message as the payload', () => {
    const state = userDetailsReducer(undefined, {
      type: SHOWLOGGEDOUTSHEET, payload: 'Session expired',
    });
    expect(state.showLoggedOutSheet).toBe('Session expired');
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

  it('initialises with an empty selectedProfileDetails array', () => {
    const state = profileReducer(undefined, { type: '@@INIT' });
    expect(state.selectedProfileDetails).toEqual([]);
  });

  it('PROFILESDETAILS action replaces profileData with the new list', () => {
    const profiles = [{ id: 'p1', name: 'Alice' }, { id: 'p2', name: 'Bob' }];
    const state    = profileReducer(undefined, { type: PROFILESDETAILS, data: profiles });
    expect(state.profileData).toEqual(profiles);
  });

  it('PROFILESDETAILS action does not affect selectedProfileDetails', () => {
    const selected = { id: 'p1', name: 'Alice' };
    const base     = profileReducer(undefined, { type: SAVESELECTEDPROFILEDETAILS, data: selected });
    const updated  = profileReducer(base, { type: PROFILESDETAILS, data: [{ id: 'p3' }] });
    expect(updated.selectedProfileDetails).toEqual(selected);
  });

  it('SAVESELECTEDPROFILEDETAILS stores the chosen profile object', () => {
    const selected = { id: 'p1', name: 'Alice' };
    const state    = profileReducer(undefined, { type: SAVESELECTEDPROFILEDETAILS, data: selected });
    expect(state.selectedProfileDetails).toEqual(selected);
  });

  it('SAVESELECTEDPROFILEDETAILS overwrites a previously selected profile', () => {
    const first  = profileReducer(undefined, { type: SAVESELECTEDPROFILEDETAILS, data: { id: 'p1' } });
    const second = profileReducer(first,     { type: SAVESELECTEDPROFILEDETAILS, data: { id: 'p2' } });
    expect(second.selectedProfileDetails).toEqual({ id: 'p2' });
  });

  it('PROFILESDETAILS can be dispatched multiple times and always reflects the latest list', () => {
    const first  = profileReducer(undefined, { type: PROFILESDETAILS, data: [{ id: 'p1' }] });
    const second = profileReducer(first,     { type: PROFILESDETAILS, data: [{ id: 'p2' }, { id: 'p3' }] });
    expect(second.profileData).toHaveLength(2);
    expect(second.profileData[0].id).toBe('p2');
  });

  it('returns current state unchanged for an unrecognised action', () => {
    const before = profileReducer(undefined, { type: '@@INIT' });
    const after  = profileReducer(before,    { type: 'NO_SUCH_ACTION' });
    expect(after).toEqual(before);
  });
});
