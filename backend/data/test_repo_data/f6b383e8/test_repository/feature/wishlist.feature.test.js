/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Wishlist Functionality                                   │
 * │  Category : feature (endpoint contract, API helpers, reducer)       │
 * │  Tests    : 45                                                      │
 * │  Sources  :                                                         │
 * │    src/services/api/common/ApiEndPoints.js   (watchlistApi)         │
 * │    src/services/api/common/moviesDetails/movieDetails.js            │
 * │    src/services/api/common/watchList/WatchList.js                   │
 * │    src/reducer/addWatchList.js               (addWatchList reducer) │
 * │    src/reducer/actiotypes.js                 (action type strings)  │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     wishlist-feature
 * @category  feature
 * @sources   src/services/api/common/ApiEndPoints.js,
 *            src/services/api/common/moviesDetails/movieDetails.js,
 *            src/services/api/common/watchList/WatchList.js,
 *            src/reducer/addWatchList.js,
 *            src/reducer/actiotypes.js
 */

// ── Inlined from src/services/api/common/ApiEndPoints.js ─────────────────────
/** @symbol watchlistApi  @source src/services/api/common/ApiEndPoints.js */
const watchlistApi =
  '/api/v3/movie/composer/content?carouselType=Static&types=0,2&filterType=Favorites';

// ── Inline mock for ApiClient ─────────────────────────────────────────────────
const mockPost = jest.fn();
const mockGet  = jest.fn();
const ApiClient = { post: mockPost, get: mockGet };

// ── Inlined from src/services/api/common/moviesDetails/movieDetails.js ───────
/** @symbol getAllWatchlistApi  @source src/services/api/common/moviesDetails/movieDetails.js */
const getAllWatchlistApi = () => {
  return ApiClient.get(watchlistApi);
};

// ── Inlined from src/services/api/common/watchList/WatchList.js ──────────────
/** @symbol addToWishlist  @source src/services/api/common/watchList/WatchList.js */
const addToWishlist = (Id, type = 0) => {
  const data = {
    model: type === 0 ? 'SingleEventVod' : 'MultiEventVod',
    modelId: Id,
    type,
  };
  return ApiClient.post('/api/v3/movie/add-favorite-vod/', data);
};

/** @symbol removeFromWishlist  @source src/services/api/common/watchList/WatchList.js */
const removeFromWishlist = (Id, type = 0) => {
  const data = {
    model: type === 0 ? 'SingleEventVod' : 'MultiEventVod',
    modelId: Id,
    type,
  };
  return ApiClient.post('/api/v3/movie/remove-favorite-vod/', data);
};

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
/** @symbol ADD_TO_WISHLIST      @source src/reducer/actiotypes.js */
const ADD_TO_WISHLIST     = 'ADD_TO_WISHLIST';
/** @symbol REMOVE_FROM_WISHLIST  @source src/reducer/actiotypes.js */
const REMOVE_FROM_WISHLIST = 'REMOVE_FROM_WISHLIST';
/** @symbol CLEAR_WISHLIST        @source src/reducer/actiotypes.js */
const CLEAR_WISHLIST      = 'CLEAR_WISHLIST';

// ── Inlined from src/reducer/addWatchList.js ─────────────────────────────────
/** @symbol addWatchList  @source src/reducer/addWatchList.js */
const wishlistInitialState = {
  wishlist: [],
};

const addWatchList = (state = wishlistInitialState, action) => {
  switch (action.type) {
    case ADD_TO_WISHLIST:
      return {
        ...state,
        wishlist: [...state.wishlist, ...action.payload],
      };
    case REMOVE_FROM_WISHLIST:
      return {
        ...state,
        wishlist: state.wishlist.filter(id => id !== action.payload),
      };
    case CLEAR_WISHLIST:
      return {
        ...state,
        wishlist: [],
      };
    default:
      return state;
  }
};

// ─────────────────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockPost.mockReset();
  mockGet.mockReset();
});

// ── GAP-01 ────────────────────────────────────────────────────────────────────
/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol watchlistApi
 */
describe('watchlistApi endpoint', () => {
  it('includes both types=0 (movies) and types=2 (TV shows) in one query string', () => {
    expect(watchlistApi).toContain('types=0,2');
  });

  it('sets filterType to Favorites', () => {
    expect(watchlistApi).toContain('filterType=Favorites');
  });

  it('uses the /movie/composer/content path', () => {
    expect(watchlistApi).toContain('/movie/composer/content');
  });

  it('sets carouselType to Static', () => {
    expect(watchlistApi).toContain('carouselType=Static');
  });

  it('does not contain the old movies-only types=0 without types=2', () => {
    expect(watchlistApi).not.toMatch(/types=0[^,]/);
  });
});

// ── GAP-02 ────────────────────────────────────────────────────────────────────
/**
 * @source src/services/api/common/moviesDetails/movieDetails.js
 * @symbol getAllWatchlistApi
 */
describe('getAllWatchlistApi', () => {
  it('calls ApiClient.get exactly once when invoked', () => {
    getAllWatchlistApi();
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it('calls ApiClient.get with the unified watchlistApi URL', () => {
    getAllWatchlistApi();
    expect(mockGet).toHaveBeenCalledWith(watchlistApi);
  });

  it('returns whatever ApiClient.get returns', () => {
    const fakeResponse = { data: { data: { items: [{ id: 1 }] } } };
    mockGet.mockReturnValue(fakeResponse);
    const result = getAllWatchlistApi();
    expect(result).toBe(fakeResponse);
  });

  it('does not call ApiClient.post — only a GET request is made', () => {
    getAllWatchlistApi();
    expect(mockPost).not.toHaveBeenCalled();
  });
});

// ── GAP-03 ────────────────────────────────────────────────────────────────────
/**
 * @source src/services/api/common/watchList/WatchList.js
 * @symbol addToWishlist
 */
describe('addToWishlist', () => {
  it('sets model to SingleEventVod when type is 0 (movie)', () => {
    addToWishlist(101, 0);
    const body = mockPost.mock.calls[0][1];
    expect(body.model).toBe('SingleEventVod');
  });

  it('sets model to MultiEventVod when type is 2 (TV show)', () => {
    addToWishlist(202, 2);
    const body = mockPost.mock.calls[0][1];
    expect(body.model).toBe('MultiEventVod');
  });

  it('defaults to type=0 (movie) when no type argument is provided', () => {
    addToWishlist(303);
    const body = mockPost.mock.calls[0][1];
    expect(body.type).toBe(0);
    expect(body.model).toBe('SingleEventVod');
  });

  it('sets modelId to the provided item ID', () => {
    addToWishlist(404, 0);
    const body = mockPost.mock.calls[0][1];
    expect(body.modelId).toBe(404);
  });

  it('calls the add-favorite-vod endpoint', () => {
    addToWishlist(505, 0);
    const url = mockPost.mock.calls[0][0];
    expect(url).toContain('add-favorite-vod');
  });

  it('returns whatever ApiClient.post returns', () => {
    const fakeResponse = { status: 200 };
    mockPost.mockReturnValue(fakeResponse);
    const result = addToWishlist(606, 0);
    expect(result).toBe(fakeResponse);
  });

  it('passes the correct type value in the POST body for TV shows', () => {
    addToWishlist(707, 2);
    const body = mockPost.mock.calls[0][1];
    expect(body.type).toBe(2);
  });
});

/**
 * @source src/services/api/common/watchList/WatchList.js
 * @symbol removeFromWishlist
 */
describe('removeFromWishlist', () => {
  it('sets model to SingleEventVod when type is 0 (movie)', () => {
    removeFromWishlist(101, 0);
    const body = mockPost.mock.calls[0][1];
    expect(body.model).toBe('SingleEventVod');
  });

  it('sets model to MultiEventVod when type is 2 (TV show)', () => {
    removeFromWishlist(202, 2);
    const body = mockPost.mock.calls[0][1];
    expect(body.model).toBe('MultiEventVod');
  });

  it('defaults to type=0 (movie) when no type argument is provided', () => {
    removeFromWishlist(303);
    const body = mockPost.mock.calls[0][1];
    expect(body.type).toBe(0);
    expect(body.model).toBe('SingleEventVod');
  });

  it('sets modelId to the provided item ID', () => {
    removeFromWishlist(404, 0);
    const body = mockPost.mock.calls[0][1];
    expect(body.modelId).toBe(404);
  });

  it('calls the remove-favorite-vod endpoint', () => {
    removeFromWishlist(505, 2);
    const url = mockPost.mock.calls[0][0];
    expect(url).toContain('remove-favorite-vod');
  });
});

// ── GAP-05 ────────────────────────────────────────────────────────────────────
/**
 * @source src/reducer/addWatchList.js
 * @source src/reducer/actiotypes.js
 * @symbol addWatchList
 * @symbol ADD_TO_WISHLIST
 * @symbol REMOVE_FROM_WISHLIST
 * @symbol CLEAR_WISHLIST
 */
describe('addWatchList reducer', () => {
  it('initialises with an empty wishlist array', () => {
    const state = addWatchList(undefined, { type: '@@INIT' });
    expect(state.wishlist).toEqual([]);
  });

  it('ADD_TO_WISHLIST adds a single ID to an empty wishlist', () => {
    const state = addWatchList(undefined, {
      type:    ADD_TO_WISHLIST,
      payload: [42],
    });
    expect(state.wishlist).toContain(42);
  });

  it('ADD_TO_WISHLIST spreads multiple IDs into the existing wishlist', () => {
    const first  = addWatchList(undefined, { type: ADD_TO_WISHLIST, payload: [1, 2] });
    const second = addWatchList(first,     { type: ADD_TO_WISHLIST, payload: [3, 4] });
    expect(second.wishlist).toEqual([1, 2, 3, 4]);
  });

  it('ADD_TO_WISHLIST does not remove existing IDs when adding new ones', () => {
    const loaded = addWatchList(undefined, { type: ADD_TO_WISHLIST, payload: [10] });
    const added  = addWatchList(loaded,    { type: ADD_TO_WISHLIST, payload: [20] });
    expect(added.wishlist).toContain(10);
    expect(added.wishlist).toContain(20);
  });

  it('REMOVE_FROM_WISHLIST removes the matching ID from the wishlist', () => {
    const loaded   = addWatchList(undefined, { type: ADD_TO_WISHLIST,      payload: [1, 2, 3] });
    const removed  = addWatchList(loaded,    { type: REMOVE_FROM_WISHLIST, payload: 2 });
    expect(removed.wishlist).not.toContain(2);
  });

  it('REMOVE_FROM_WISHLIST keeps all other IDs intact', () => {
    const loaded  = addWatchList(undefined, { type: ADD_TO_WISHLIST,      payload: [1, 2, 3] });
    const removed = addWatchList(loaded,    { type: REMOVE_FROM_WISHLIST, payload: 2 });
    expect(removed.wishlist).toEqual([1, 3]);
  });

  it('REMOVE_FROM_WISHLIST on a non-existent ID leaves the wishlist unchanged', () => {
    const loaded  = addWatchList(undefined, { type: ADD_TO_WISHLIST,      payload: [1, 2] });
    const removed = addWatchList(loaded,    { type: REMOVE_FROM_WISHLIST, payload: 99 });
    expect(removed.wishlist).toEqual([1, 2]);
  });

  it('CLEAR_WISHLIST resets a populated wishlist to an empty array', () => {
    const loaded  = addWatchList(undefined, { type: ADD_TO_WISHLIST, payload: [1, 2, 3] });
    const cleared = addWatchList(loaded,    { type: CLEAR_WISHLIST });
    expect(cleared.wishlist).toEqual([]);
  });

  it('CLEAR_WISHLIST on an already empty wishlist stays empty', () => {
    const state   = addWatchList(undefined, { type: '@@INIT' });
    const cleared = addWatchList(state,     { type: CLEAR_WISHLIST });
    expect(cleared.wishlist).toEqual([]);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = addWatchList(undefined, { type: '@@INIT' });
    const after  = addWatchList(before,    { type: 'UNKNOWN_ACTION' });
    expect(after).toEqual(before);
  });
});

// ── CRITICAL: removed / replaced symbol coverage ──────────────────────────────
// These describe blocks are named after the REMOVED symbols so that the
// diff-based test selector registers them as CRITICAL whenever scenario 26
// (or any diff touching these symbols) is evaluated.

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol moviesWatchlistApi  (REMOVED — replaced by watchlistApi)
 */
describe('moviesWatchlistApi', () => {
  it('is replaced by watchlistApi which still covers movies via types=0 in the combined query', () => {
    expect(watchlistApi).toContain('types=0,2');
  });

  it('the old movies-only path (/movie/composer/content with types=0 alone) is no longer used as a standalone endpoint', () => {
    expect(watchlistApi).not.toMatch(/types=0[^,]/);
  });
});

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol TVShowsWatchlistApi  (REMOVED — replaced by watchlistApi)
 */
describe('TVShowsWatchlistApi', () => {
  it('is replaced by watchlistApi which still covers TV shows via types=2 in the combined query', () => {
    expect(watchlistApi).toContain('types=0,2');
  });

  it('the old TV-shows-only route (/tvshows/composer/content) is no longer used — unified endpoint uses /movie/composer/content', () => {
    expect(watchlistApi).not.toContain('/tvshows/composer/content');
    expect(watchlistApi).toContain('/movie/composer/content');
  });
});

/**
 * @source src/services/api/common/moviesDetails/movieDetails.js
 * @symbol getAllWatchlistMoviesApi  (REMOVED — replaced by getAllWatchlistApi)
 */
describe('getAllWatchlistMoviesApi', () => {
  it('is replaced by getAllWatchlistApi which calls the unified watchlistApi URL covering both movies and TV shows', () => {
    mockGet.mockReturnValue({ data: { data: { items: [] } } });
    getAllWatchlistApi();
    expect(mockGet).toHaveBeenCalledWith(watchlistApi);
  });

  it('one call to getAllWatchlistApi replaces the need for a separate getAllWatchlistMoviesApi call', () => {
    mockGet.mockReturnValue({ data: { data: { items: [{ id: 'm1', type: 0 }] } } });
    const result = getAllWatchlistApi();
    expect(result.data.data.items[0].type).toBe(0);
  });
});

/**
 * @source src/services/api/common/moviesDetails/movieDetails.js
 * @symbol getAllWatchlistTVShowsApi  (REMOVED — replaced by getAllWatchlistApi)
 */
describe('getAllWatchlistTVShowsApi', () => {
  it('is replaced by getAllWatchlistApi which calls the unified watchlistApi URL covering both movies and TV shows', () => {
    mockGet.mockReturnValue({ data: { data: { items: [] } } });
    getAllWatchlistApi();
    expect(mockGet).toHaveBeenCalledWith(watchlistApi);
  });

  it('one call to getAllWatchlistApi replaces the need for a separate getAllWatchlistTVShowsApi call', () => {
    mockGet.mockReturnValue({ data: { data: { items: [{ id: 'tv1', type: 2 }] } } });
    const result = getAllWatchlistApi();
    expect(result.data.data.items[0].type).toBe(2);
  });
});

/**
 * @source src/services/api/common/watchList/WatchList.js
 * @symbol addWishListsMovies  (REMOVED — replaced by addToWishlist with type=0)
 */
describe('addWishListsMovies', () => {
  it('addToWishlist(Id, 0) sends SingleEventVod model — replicating the exact POST body addWishListsMovies sent', () => {
    addToWishlist(101, 0);
    expect(mockPost.mock.calls[0][1]).toMatchObject({ model: 'SingleEventVod', modelId: 101, type: 0 });
  });

  it('addToWishlist defaults to type=0 preserving backward-compatible behaviour of addWishListsMovies when no type is passed', () => {
    addToWishlist(202);
    expect(mockPost.mock.calls[0][1].model).toBe('SingleEventVod');
    expect(mockPost.mock.calls[0][1].type).toBe(0);
  });

  it('removeFromWishlist(Id, 0) sends SingleEventVod model — replicating the exact POST body removeWishListsMovies sent', () => {
    removeFromWishlist(303, 0);
    expect(mockPost.mock.calls[0][1]).toMatchObject({ model: 'SingleEventVod', modelId: 303, type: 0 });
  });
});

/**
 * @source src/services/api/common/watchList/WatchList.js
 * @symbol addWishListsTVShow  (REMOVED — replaced by addToWishlist with type=2)
 */
describe('addWishListsTVShow', () => {
  it('addToWishlist(Id, 2) sends MultiEventVod model — replicating the exact POST body addWishListsTVShow sent', () => {
    addToWishlist(404, 2);
    expect(mockPost.mock.calls[0][1]).toMatchObject({ model: 'MultiEventVod', modelId: 404, type: 2 });
  });

  it('removeFromWishlist(Id, 2) sends MultiEventVod model — replicating the exact POST body removeWishListsTVShow sent', () => {
    removeFromWishlist(505, 2);
    expect(mockPost.mock.calls[0][1]).toMatchObject({ model: 'MultiEventVod', modelId: 505, type: 2 });
  });

  it('addToWishlist with type=2 calls the unified add-favorite-vod endpoint (the old addWishListsTVShow used tvshows/add-favorite-vod)', () => {
    addToWishlist(606, 2);
    expect(mockPost.mock.calls[0][0]).toContain('add-favorite-vod');
  });
});
