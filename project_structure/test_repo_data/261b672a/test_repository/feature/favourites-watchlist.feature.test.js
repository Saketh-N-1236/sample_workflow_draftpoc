/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Favourites, Watchlist & Toast Reducers                   │
 * │  Category : feature (full reducer flow, single-feature scope)       │
 * │  Tests    : 8                                                        │
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

const favouritesInitialState = {
  userFavourites:  [],
  favouritesFetched: false,
};

/** @symbol favouritesReducer  @source src/reducer/favouritesReducer.js */
const favouritesReducer = (state = favouritesInitialState, action) => {
  switch (action.type) {
    case favouritesActions.UPDATEALLFAVOURITIESDETAILS:
      return {
        ...state,
        userFavourites:   action.userFavourites,
        favouritesFetched: action.favouritesFetched,
      };
    default:
      return state;
  }
};

// ── Inlined from src/reducer/toastReducer.js ─────────────────────────────────
/** @symbol toastReducer  @source src/reducer/toastReducer.js */
const toastInitialState = { showToast: null };

const toastReducer = (state = toastInitialState, action) => {
  switch (action.type) {
    case TOAST:
      return { ...state, showToast: action.toast };
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

  it('UPDATEALLFAVOURITIESDETAILS replaces the favourites list', () => {
    const favs  = [{ id: 'm1' }, { id: 'm2' }];
    const state = favouritesReducer(undefined, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    favs,
      favouritesFetched: true,
    });
    expect(state.userFavourites).toEqual(favs);
  });

  it('sets favouritesFetched to true once the list is loaded', () => {
    const state = favouritesReducer(undefined, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    [{ id: 'm1' }],
      favouritesFetched: true,
    });
    expect(state.favouritesFetched).toBe(true);
  });

  it('returns unchanged state for an unknown action', () => {
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

  it('TOAST action stores the toast message in showToast', () => {
    const state = toastReducer(undefined, {
      type:  TOAST,
      toast: { message: 'Card added successfully', type: 'success' },
    });
    expect(state.showToast.message).toBe('Card added successfully');
  });

  it('resets showToast to null when null is dispatched', () => {
    const withToast    = toastReducer(undefined, { type: TOAST, toast: { message: 'hi' } });
    const withoutToast = toastReducer(withToast,  { type: TOAST, toast: null });
    expect(withoutToast.showToast).toBeNull();
  });

  it('returns unchanged state for an unknown action', () => {
    const before = toastReducer(undefined, { type: '@@INIT' });
    const after  = toastReducer(before, { type: 'UNKNOWN_TOAST_ACTION' });
    expect(after).toEqual(before);
  });
});
