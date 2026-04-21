/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Favourites, Watchlist & Toast Reducers                   │
 * │  Category : feature (full reducer flow, single-feature scope)       │
 * │  Tests    : 24                                                       │
 * │  Sources  :                                                          │
 * │    src/reducer/favouritesReducer.js  (favouritesReducer)            │
 * │    src/reducer/toastReducer.js       (toastReducer)                 │
 * │    src/reducer/actiotypes.js         (action type strings)          │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     favourites-watchlist-feature
 * @category  feature
 * @sources   src/reducer/favouritesReducer.js,
 *            src/reducer/toastReducer.js,
 *            src/reducer/actiotypes.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
/** @symbol TOAST  @source src/reducer/actiotypes.js */
const TOAST = 'TOAST';

// ── Inlined from src/reducer/favouritesReducer.js ────────────────────────────
/** @symbol favouritesActions  @source src/reducer/favouritesReducer.js */
const favouritesActions = {
  UPDATEALLFAVOURITIESDETAILS: 'UPDATE_STORED_USER_ALL_FAVOURITIES_DETAILS',
};

/**
 * NOTE: actual initial state has favouritesFetched: null (not false).
 * @symbol favouritesReducer  @source src/reducer/favouritesReducer.js
 */
const favouritesInitialState = {
  userFavourites:    [],
  favouritesFetched: null,
};

const favouritesReducer = (state = favouritesInitialState, action) => {
  switch (action.type) {
    case favouritesActions.UPDATEALLFAVOURITIESDETAILS:
      return {
        ...state,
        userFavourites:    action.userFavourites,
        favouritesFetched: action.favouritesFetched,
      };
    default:
      return state;
  }
};

// ── Inlined from src/reducer/toastReducer.js ─────────────────────────────────
/**
 * NOTE: actual initial state has toastType: 'warning' (not 'info').
 * @symbol toastReducer  @source src/reducer/toastReducer.js
 */
const toastInitialState = {
  showToast:  null,
  toastType:  'warning',
  toastQueue: [],
};

const toastReducer = (state = toastInitialState, action) => {
  switch (action.type) {
    case TOAST:
      return {
        ...state,
        showToast:  action.toast,
        toastType:  action.toastType ?? state.toastType,
        toastQueue: action.queue     ?? state.toastQueue,
      };
    case 'CLEARTOAST':
      return { ...state, showToast: null };
    default:
      return state;
  }
};

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/reducer/favouritesReducer.js
 * @source src/reducer/actiotypes.js
 * @symbol favouritesReducer
 * @symbol favouritesActions
 */
describe('favouritesReducer', () => {
  it('starts with an empty userFavourites list', () => {
    const state = favouritesReducer(undefined, { type: '@@INIT' });
    expect(state.userFavourites).toEqual([]);
  });

  it('starts with favouritesFetched as null', () => {
    const state = favouritesReducer(undefined, { type: '@@INIT' });
    expect(state.favouritesFetched).toBeNull();
  });

  it('UPDATEALLFAVOURITIESDETAILS replaces the entire favourites list', () => {
    const favs  = [{ id: 'm1' }, { id: 'm2' }];
    const state = favouritesReducer(undefined, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    favs,
      favouritesFetched: true,
    });
    expect(state.userFavourites).toEqual(favs);
  });

  it('sets favouritesFetched to true once the list is successfully loaded', () => {
    const state = favouritesReducer(undefined, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    [{ id: 'm1' }],
      favouritesFetched: true,
    });
    expect(state.favouritesFetched).toBe(true);
  });

  it('sets favouritesFetched to false when load fails (empty list)', () => {
    const state = favouritesReducer(undefined, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    [],
      favouritesFetched: false,
    });
    expect(state.favouritesFetched).toBe(false);
    expect(state.userFavourites).toEqual([]);
  });

  it('replaces a populated list with an empty list when dispatched again', () => {
    const loaded  = favouritesReducer(undefined, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    [{ id: 'm1' }],
      favouritesFetched: true,
    });
    const cleared = favouritesReducer(loaded, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    [],
      favouritesFetched: false,
    });
    expect(cleared.userFavourites).toEqual([]);
  });

  it('reflects the exact number of items provided in the action', () => {
    const items = [{ id: '1' }, { id: '2' }, { id: '3' }];
    const state = favouritesReducer(undefined, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    items,
      favouritesFetched: true,
    });
    expect(state.userFavourites).toHaveLength(3);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = favouritesReducer(undefined, { type: '@@INIT' });
    const after  = favouritesReducer(before, { type: 'RANDOM_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/toastReducer.js
 * @source src/reducer/actiotypes.js
 * @symbol toastReducer
 */
describe('toastReducer', () => {
  it('initialises with showToast as null', () => {
    const state = toastReducer(undefined, { type: '@@INIT' });
    expect(state.showToast).toBeNull();
  });

  it('initialises with the default toastType as warning', () => {
    const state = toastReducer(undefined, { type: '@@INIT' });
    expect(state.toastType).toBe('warning');
  });

  it('initialises with an empty toastQueue array', () => {
    const state = toastReducer(undefined, { type: '@@INIT' });
    expect(state.toastQueue).toEqual([]);
  });

  it('TOAST action stores the toast message object in showToast', () => {
    const toast = { message: 'Card added successfully', type: 'success' };
    const state = toastReducer(undefined, { type: TOAST, toast });
    expect(state.showToast).toEqual(toast);
  });

  it('TOAST action updates toastType when a new type is provided', () => {
    const state = toastReducer(undefined, {
      type:      TOAST,
      toast:     { message: 'Error occurred' },
      toastType: 'error',
    });
    expect(state.toastType).toBe('error');
  });

  it('TOAST action retains the previous toastType when none is provided', () => {
    const state = toastReducer(undefined, {
      type:  TOAST,
      toast: { message: 'Hello' },
    });
    expect(state.toastType).toBe('warning');
  });

  it('TOAST action stores a queue when a queue is provided', () => {
    const queue = [{ message: 'msg1' }, { message: 'msg2' }];
    const state = toastReducer(undefined, {
      type:  TOAST,
      toast: { message: 'hi' },
      queue,
    });
    expect(state.toastQueue).toEqual(queue);
  });

  it('CLEARTOAST action resets showToast back to null', () => {
    const withToast    = toastReducer(undefined, { type: TOAST, toast: { message: 'hi' } });
    const withoutToast = toastReducer(withToast,  { type: 'CLEARTOAST' });
    expect(withoutToast.showToast).toBeNull();
  });

  it('CLEARTOAST does not change toastType or toastQueue', () => {
    const base = toastReducer(undefined, {
      type:      TOAST,
      toast:     { message: 'hi' },
      toastType: 'success',
      queue:     [{ message: 'q1' }],
    });
    const cleared = toastReducer(base, { type: 'CLEARTOAST' });
    expect(cleared.toastType).toBe('success');
    expect(cleared.toastQueue).toEqual([{ message: 'q1' }]);
  });

  it('TOAST action with null toast stores null in showToast', () => {
    const withToast    = toastReducer(undefined, { type: TOAST, toast: { message: 'hi' } });
    const withoutToast = toastReducer(withToast,  { type: TOAST, toast: null });
    expect(withoutToast.showToast).toBeNull();
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = toastReducer(undefined, { type: '@@INIT' });
    const after  = toastReducer(before, { type: 'UNKNOWN_TOAST_ACTION' });
    expect(after).toEqual(before);
  });

  it('accumulates multiple TOAST dispatches with the latest message', () => {
    const first  = toastReducer(undefined, { type: TOAST, toast: { message: 'first' } });
    const second = toastReducer(first,     { type: TOAST, toast: { message: 'second' } });
    expect(second.showToast.message).toBe('second');
  });
});
