/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Favourites Sort Order (Scenario 30)                      │
 * │  Category : feature (reducer + action creator flow)                 │
 * │  Tests    : 12                                                       │
 * │  Sources  :                                                          │
 * │    src/reducer/actiotypes.js       (TOGGLE_FAVOURITES_SORT)         │
 * │    src/reducer/actions.js          (toggleFavouritesSort)           │
 * │    src/reducer/favouritesReducer.js (sortOrder field)               │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     favourites-sort-feature
 * @category  feature
 * @sources   src/reducer/actiotypes.js,
 *            src/reducer/actions.js,
 *            src/reducer/favouritesReducer.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
/** @symbol TOGGLE_FAVOURITES_SORT  @source src/reducer/actiotypes.js */
const TOGGLE_FAVOURITES_SORT = 'TOGGLE_FAVOURITES_SORT';

// ── Inlined from src/reducer/actions.js ──────────────────────────────────────
/** @symbol toggleFavouritesSort  @source src/reducer/actions.js */
const toggleFavouritesSort = () => ({ type: TOGGLE_FAVOURITES_SORT });

// ── Inlined from src/reducer/favouritesReducer.js ────────────────────────────
/** @symbol favouritesActions  @source src/reducer/favouritesReducer.js */
const favouritesActions = {
  UPDATEALLFAVOURITIESDETAILS: 'UPDATE_STORED_USER_ALL_FAVOURITIES_DETAILS',
};

/** @symbol favouritesReducer  @source src/reducer/favouritesReducer.js */
const favInitialState = {
  userFavourites:   [],
  favouritesFetched: null,
  sortOrder:        'api',
};

const favouritesReducer = (state = favInitialState, action) => {
  switch (action.type) {
    case favouritesActions.UPDATEALLFAVOURITIESDETAILS: {
      const userFavourites =
        state.sortOrder === 'recent'
          ? [...action.userFavourites].sort((a, b) => b.modelId - a.modelId)
          : action.userFavourites;
      return {
        ...state,
        userFavourites,
        favouritesFetched: action.favouritesFetched,
      };
    }
    case TOGGLE_FAVOURITES_SORT:
      return {
        ...state,
        sortOrder: state.sortOrder === 'api' ? 'recent' : 'api',
      };
    default:
      return state;
  }
};

// ─────────────────────────────────────────────────────────────────────────────
// describe('TOGGLE_FAVOURITES_SORT') — 2 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('TOGGLE_FAVOURITES_SORT', () => {
  it("equals the string 'TOGGLE_FAVOURITES_SORT'", () => {
    expect(TOGGLE_FAVOURITES_SORT).toBe('TOGGLE_FAVOURITES_SORT');
  });

  it('is a non-empty string', () => {
    expect(typeof TOGGLE_FAVOURITES_SORT).toBe('string');
    expect(TOGGLE_FAVOURITES_SORT.length).toBeGreaterThan(0);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// describe('toggleFavouritesSort') — 3 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('toggleFavouritesSort', () => {
  it('returns an action with type TOGGLE_FAVOURITES_SORT', () => {
    expect(toggleFavouritesSort().type).toBe(TOGGLE_FAVOURITES_SORT);
  });

  it('returns a plain object with no extra fields', () => {
    const action = toggleFavouritesSort();
    expect(Object.keys(action)).toEqual(['type']);
  });

  it('returns the same shape when called multiple times', () => {
    expect(toggleFavouritesSort()).toEqual(toggleFavouritesSort());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// describe('favouritesReducer — sortOrder') — 7 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('favouritesReducer — sortOrder', () => {
  it("initialises sortOrder as 'api' (API order is the default)", () => {
    const state = favouritesReducer(undefined, { type: '@@INIT' });
    expect(state.sortOrder).toBe('api');
  });

  it("TOGGLE_FAVOURITES_SORT switches sortOrder from 'api' to 'recent'", () => {
    const state = favouritesReducer(undefined, toggleFavouritesSort());
    expect(state.sortOrder).toBe('recent');
  });

  it("TOGGLE_FAVOURITES_SORT switches sortOrder back from 'recent' to 'api'", () => {
    const toggled = favouritesReducer(undefined, toggleFavouritesSort());
    const restored = favouritesReducer(toggled, toggleFavouritesSort());
    expect(restored.sortOrder).toBe('api');
  });

  it('TOGGLE_FAVOURITES_SORT is a pure toggle — toggling twice returns to original', () => {
    const base   = favouritesReducer(undefined, { type: '@@INIT' });
    const after2 = favouritesReducer(
      favouritesReducer(base, toggleFavouritesSort()),
      toggleFavouritesSort(),
    );
    expect(after2.sortOrder).toBe(base.sortOrder);
  });

  it("UPDATEALLFAVOURITIESDETAILS stores items in API order when sortOrder is 'api'", () => {
    const items = [{ modelId: 1 }, { modelId: 3 }, { modelId: 2 }];
    const state = favouritesReducer(undefined, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    items,
      favouritesFetched: true,
    });
    expect(state.userFavourites).toEqual(items);
  });

  it("UPDATEALLFAVOURITIESDETAILS sorts by modelId descending when sortOrder is 'recent'", () => {
    const withRecent = favouritesReducer(undefined, toggleFavouritesSort());
    const items = [{ modelId: 1 }, { modelId: 3 }, { modelId: 2 }];
    const state = favouritesReducer(withRecent, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    items,
      favouritesFetched: true,
    });
    expect(state.userFavourites.map(i => i.modelId)).toEqual([3, 2, 1]);
  });

  it('UPDATEALLFAVOURITIESDETAILS does not mutate the original action.userFavourites array', () => {
    const withRecent = favouritesReducer(undefined, toggleFavouritesSort());
    const items = [{ modelId: 1 }, { modelId: 3 }];
    const original = [...items];
    favouritesReducer(withRecent, {
      type:              favouritesActions.UPDATEALLFAVOURITIESDETAILS,
      userFavourites:    items,
      favouritesFetched: true,
    });
    expect(items).toEqual(original);
  });
});
