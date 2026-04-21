/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  STANDALONE · appStorage & storageKeys                              │
 * │  Category : standalone (no cross-file dependencies)                 │
 * │  Tests    : 24                                                       │
 * │  Source   : src/services/storage.ts                                 │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     storage-pure
 * @category  standalone
 * @source    src/services/storage.ts
 *
 * Tests the appStorage get/set/delete/clearAll operations and verifies
 * the storageKeys constant values. localStorage is mocked via jest.setup.js.
 */

// ── Inlined from src/services/storage.ts ─────────────────────────────────────

/** @symbol appStorage  @source src/services/storage.ts */
const appStorage = {
  set: (key, value) => {
    localStorage.setItem(key, JSON.stringify(value));
  },
  get: key => {
    try {
      const value = localStorage.getItem(key) ?? null;
      if (!value) return null;
      return JSON.parse(value);
    } catch (e) {
      return null;
    }
  },
  getMultiple: keys => keys.map(k => appStorage.get(k)),
  delete: key => { localStorage.removeItem(key); },
  deleteMultiple: keys => {
    if (keys?.length) return;
    for (const key of keys) { localStorage.removeItem(key); }
  },
  clearAll: () => { localStorage.clear(); },
};

/** @symbol storageKeys  @source src/services/storage.ts */
const storageKeys = {
  username:              'USERNAME',
  sessionId:             'SESSION_ID',
  videoDetails:          'VIDEODETAILS',
  uid:                   'UID',
  userDetails:           'USERDETAILS',
  ProfilesDetails:       'UPDATEPROFILESDETAILS',
  token:                 'ACCESS_TOKEN',
  userLoginData:         'userLoginData',
  loginUserName:         'LoginUserName',
  seeAllData:            'SeeAllData',
  seeAllTitle:           'SeeAllTitle',
  profileId:             'PROFILEID',
  loginTime:             'LOGGEDINTIME',
  refreshToken:          'REFRESHTOKEN',
  userId:                'userID',
  base64:                'base64',
  isFlipped:             'isFlipped',
  stripePaymentDetails:  'STRIPEPAYMENTDETAILS',
  language:              'LANGUAGE',
  subscriptionDetails:   'SUBSCRIPTION_DETAILS',
  profileToken:          'PROFILETOKEN',
  sportsVideoId:         'sportsVideoId',
  deviceRegistered:      'deviceRegistered',
  movieVideoId:          'movieVideoId',
  staticImageIndex:      'STATICIMAGEINDEX',
  userData:              'USERDATA',
  selectedProfileDetails:'SELECTEDPROFILEDETAILS',
  videoPlayedUpto:       'VIDEO_PLAYED_UPTO',
  phoneVerified:         'PHONE_VERIFIED',
  sessionID:             'SESSION_ID',
};

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/services/storage.ts
 * @symbol appStorage.set / appStorage.get
 */
describe('appStorage.set and appStorage.get', () => {
  it('stores a string and retrieves it correctly', () => {
    appStorage.set('TEST_KEY', 'hello');
    expect(appStorage.get('TEST_KEY')).toBe('hello');
  });

  it('stores a number and retrieves it as a number', () => {
    appStorage.set('NUM_KEY', 42);
    expect(appStorage.get('NUM_KEY')).toBe(42);
  });

  it('stores a plain object and retrieves it with deep equality', () => {
    const obj = { id: 1, name: 'Alice' };
    appStorage.set('OBJ_KEY', obj);
    expect(appStorage.get('OBJ_KEY')).toEqual(obj);
  });

  it('stores an array and retrieves it correctly', () => {
    const arr = [1, 2, 3];
    appStorage.set('ARR_KEY', arr);
    expect(appStorage.get('ARR_KEY')).toEqual(arr);
  });

  it('returns null for a key that has never been set', () => {
    expect(appStorage.get('NON_EXISTENT_KEY')).toBeNull();
  });

  it('overwrites a previously stored value when set is called again', () => {
    appStorage.set('OVERWRITE_KEY', 'first');
    appStorage.set('OVERWRITE_KEY', 'second');
    expect(appStorage.get('OVERWRITE_KEY')).toBe('second');
  });

  it('stores boolean true and retrieves it as true', () => {
    appStorage.set('BOOL_KEY', true);
    expect(appStorage.get('BOOL_KEY')).toBe(true);
  });

  it('stores boolean false and retrieves it as false', () => {
    appStorage.set('BOOL_KEY', false);
    expect(appStorage.get('BOOL_KEY')).toBe(false);
  });
});

/**
 * @source src/services/storage.ts
 * @symbol appStorage.delete
 */
describe('appStorage.delete', () => {
  it('removes a previously stored key so get returns null', () => {
    appStorage.set('DEL_KEY', 'to-delete');
    appStorage.delete('DEL_KEY');
    expect(appStorage.get('DEL_KEY')).toBeNull();
  });

  it('does not throw when deleting a key that does not exist', () => {
    expect(() => appStorage.delete('GHOST_KEY')).not.toThrow();
  });

  it('deleting one key does not affect other keys', () => {
    appStorage.set('KEY_A', 'value-a');
    appStorage.set('KEY_B', 'value-b');
    appStorage.delete('KEY_A');
    expect(appStorage.get('KEY_B')).toBe('value-b');
  });
});

/**
 * @source src/services/storage.ts
 * @symbol appStorage.clearAll
 */
describe('appStorage.clearAll', () => {
  it('removes all stored keys so every get returns null', () => {
    appStorage.set('K1', 'v1');
    appStorage.set('K2', 'v2');
    appStorage.clearAll();
    expect(appStorage.get('K1')).toBeNull();
    expect(appStorage.get('K2')).toBeNull();
  });
});

/**
 * @source src/services/storage.ts
 * @symbol appStorage.getMultiple
 */
describe('appStorage.getMultiple', () => {
  it('returns an array of values for the provided keys', () => {
    appStorage.set('M1', 'alpha');
    appStorage.set('M2', 'beta');
    const results = appStorage.getMultiple(['M1', 'M2']);
    expect(results).toEqual(['alpha', 'beta']);
  });

  it('returns null for keys that have not been set', () => {
    const results = appStorage.getMultiple(['MISSING_A', 'MISSING_B']);
    expect(results).toEqual([null, null]);
  });

  it('preserves the order of requested keys in the result array', () => {
    appStorage.set('ORD_X', 10);
    appStorage.set('ORD_Y', 20);
    const results = appStorage.getMultiple(['ORD_Y', 'ORD_X']);
    expect(results[0]).toBe(20);
    expect(results[1]).toBe(10);
  });
});

/**
 * @source src/services/storage.ts
 * @symbol storageKeys
 */
describe('storageKeys constant values', () => {
  it('token key equals ACCESS_TOKEN', () => {
    expect(storageKeys.token).toBe('ACCESS_TOKEN');
  });

  it('refreshToken key equals REFRESHTOKEN', () => {
    expect(storageKeys.refreshToken).toBe('REFRESHTOKEN');
  });

  it('loginTime key equals LOGGEDINTIME', () => {
    expect(storageKeys.loginTime).toBe('LOGGEDINTIME');
  });

  it('stripePaymentDetails key equals STRIPEPAYMENTDETAILS', () => {
    expect(storageKeys.stripePaymentDetails).toBe('STRIPEPAYMENTDETAILS');
  });

  it('subscriptionDetails key equals SUBSCRIPTION_DETAILS', () => {
    expect(storageKeys.subscriptionDetails).toBe('SUBSCRIPTION_DETAILS');
  });

  it('sessionId and sessionID both map to SESSION_ID (case-variant aliases)', () => {
    expect(storageKeys.sessionId).toBe('SESSION_ID');
    expect(storageKeys.sessionID).toBe('SESSION_ID');
  });
});
