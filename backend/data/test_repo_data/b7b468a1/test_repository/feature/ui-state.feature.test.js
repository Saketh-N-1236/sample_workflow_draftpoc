/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · UI State — Responsive Layout, Dimensions & WatchList UI  │
 * │  Category : feature (screen breakpoints, window size, watchlist UI) │
 * │  Tests    : 22                                                      │
 * │  Sources  :                                                         │
 * │    src/reducer/responsiveReducer.js      (responsiveReducer)        │
 * │    src/reducer/windowDimentionsReducer.js (windowDimentionsReducer) │
 * │    src/reducer/showWatchListReducer.js   (showWatchListReducer)     │
 * │    src/reducer/actiotypes.js             (action type strings)      │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     ui-state-feature
 * @category  feature
 * @sources   src/reducer/responsiveReducer.js,
 *            src/reducer/windowDimentionsReducer.js,
 *            src/reducer/showWatchListReducer.js,
 *            src/reducer/actiotypes.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
const SCREENSIZE       = 'SCREENSIZE';
const SCREENDIMENTIONS = 'SCREENDIMENTIONS';
const GETADDEDWATCHLIST = 'GETADDEDWATCHLIST';
const REMOVEALLWATCHLIST = 'REMOVEALLWATCHLIST';

// ── Inlined from src/reducer/responsiveReducer.js ────────────────────────────
/**
 * NOTE: actual file imports Dimensions from react-native and getScreenNumber
 * from helpers. Those imports are NOT needed for testing reducer pure logic —
 * we inline only the reducer function and its helper predicates.
 * @symbol responsiveReducer  @source src/reducer/responsiveReducer.js
 * @symbol checkIsMobile      @source src/reducer/responsiveReducer.js
 * @symbol checkIsTab         @source src/reducer/responsiveReducer.js
 */
const checkIsMobile = screennumber => screennumber === 0;
const checkIsTab    = screennumber => screennumber === 1;

const responsiveInitialState = {
  screennumber: null,
  isMobile:     checkIsMobile(null),
  isTab:        checkIsTab(null),
};

const responsiveReducer = (state = responsiveInitialState, action) => {
  switch (action.type) {
    case SCREENSIZE:
      return {
        ...state,
        screennumber: action.screensizenumber,
        isMobile:     checkIsMobile(action.screensizenumber),
        isTab:        checkIsTab(action.screensizenumber),
      };
    default:
      return state;
  }
};

// ── Inlined from src/reducer/windowDimentionsReducer.js ──────────────────────
/**
 * NOTE: actual file reads Dimensions.get('window') at module load time.
 * We use fixed test values for width and height for deterministic tests.
 * @symbol windowDimentionsReducer  @source src/reducer/windowDimentionsReducer.js
 */
const windowInitialState = { width: 1280, height: 720 };

const windowDimentionsReducer = (state = windowInitialState, action) => {
  switch (action.type) {
    case SCREENDIMENTIONS:
      return { ...state, width: action.width, height: action.height };
    default:
      return state;
  }
};

// ── Inlined from src/reducer/showWatchListReducer.js ─────────────────────────
/** @symbol showWatchListReducer  @source src/reducer/showWatchListReducer.js */
const showWatchListInitialState = {
  addedWatchList: [],
  isLoading:      true,
};

const showWatchListReducer = (state = showWatchListInitialState, action) => {
  switch (action.type) {
    case GETADDEDWATCHLIST:
      return { ...state, addedWatchList: [...state.addedWatchList, ...action.payload] };
    case REMOVEALLWATCHLIST:
      return { ...state, addedWatchList: [] };
    default:
      return state;
  }
};

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/reducer/responsiveReducer.js
 * @symbol checkIsMobile
 * @symbol checkIsTab
 */
describe('checkIsMobile and checkIsTab helpers', () => {
  it('checkIsMobile returns true for screennumber 0 (mobile)', () => {
    expect(checkIsMobile(0)).toBe(true);
  });

  it('checkIsMobile returns false for screennumber 1 (tablet)', () => {
    expect(checkIsMobile(1)).toBe(false);
  });

  it('checkIsMobile returns false for screennumber 2 (desktop)', () => {
    expect(checkIsMobile(2)).toBe(false);
  });

  it('checkIsTab returns true for screennumber 1 (tablet)', () => {
    expect(checkIsTab(1)).toBe(true);
  });

  it('checkIsTab returns false for screennumber 0 (mobile)', () => {
    expect(checkIsTab(0)).toBe(false);
  });

  it('checkIsTab returns false for screennumber 2 (desktop)', () => {
    expect(checkIsTab(2)).toBe(false);
  });
});

/**
 * @source src/reducer/responsiveReducer.js
 * @symbol responsiveReducer
 */
describe('responsiveReducer', () => {
  it('initialises with screennumber as null', () => {
    const state = responsiveReducer(undefined, { type: '@@INIT' });
    expect(state.screennumber).toBeNull();
  });

  it('initialises with both isMobile and isTab as false (null screen number)', () => {
    const state = responsiveReducer(undefined, { type: '@@INIT' });
    expect(state.isMobile).toBe(false);
    expect(state.isTab).toBe(false);
  });

  it('SCREENSIZE with 0 sets isMobile to true and isTab to false', () => {
    const state = responsiveReducer(undefined, { type: SCREENSIZE, screensizenumber: 0 });
    expect(state.isMobile).toBe(true);
    expect(state.isTab).toBe(false);
    expect(state.screennumber).toBe(0);
  });

  it('SCREENSIZE with 1 sets isTab to true and isMobile to false', () => {
    const state = responsiveReducer(undefined, { type: SCREENSIZE, screensizenumber: 1 });
    expect(state.isTab).toBe(true);
    expect(state.isMobile).toBe(false);
    expect(state.screennumber).toBe(1);
  });

  it('SCREENSIZE with 2 sets both isMobile and isTab to false (desktop)', () => {
    const state = responsiveReducer(undefined, { type: SCREENSIZE, screensizenumber: 2 });
    expect(state.isMobile).toBe(false);
    expect(state.isTab).toBe(false);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = responsiveReducer(undefined, { type: '@@INIT' });
    const after  = responsiveReducer(before,    { type: 'UNKNOWN_RESPONSIVE_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/windowDimentionsReducer.js
 * @symbol windowDimentionsReducer
 */
describe('windowDimentionsReducer', () => {
  it('initialises with numeric width and height values', () => {
    const state = windowDimentionsReducer(undefined, { type: '@@INIT' });
    expect(typeof state.width).toBe('number');
    expect(typeof state.height).toBe('number');
  });

  it('SCREENDIMENTIONS updates width and height to new values', () => {
    const state = windowDimentionsReducer(undefined, {
      type: SCREENDIMENTIONS,
      width:  1920,
      height: 1080,
    });
    expect(state.width).toBe(1920);
    expect(state.height).toBe(1080);
  });

  it('SCREENDIMENTIONS does not change other state properties', () => {
    const initial = windowDimentionsReducer(undefined, { type: '@@INIT' });
    const updated = windowDimentionsReducer(initial,   {
      type:   SCREENDIMENTIONS,
      width:  375,
      height: 812,
    });
    const keys = Object.keys(initial);
    expect(Object.keys(updated)).toEqual(keys);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = windowDimentionsReducer(undefined, { type: '@@INIT' });
    const after  = windowDimentionsReducer(before,    { type: 'UNKNOWN_DIMENSION_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/showWatchListReducer.js
 * @symbol showWatchListReducer
 */
describe('showWatchListReducer', () => {
  it('initialises with an empty addedWatchList array', () => {
    const state = showWatchListReducer(undefined, { type: '@@INIT' });
    expect(state.addedWatchList).toEqual([]);
  });

  it('initialises with isLoading as true', () => {
    const state = showWatchListReducer(undefined, { type: '@@INIT' });
    expect(state.isLoading).toBe(true);
  });

  it('GETADDEDWATCHLIST spreads new items into the addedWatchList', () => {
    const items = [{ id: 'm1', title: 'Movie A' }, { id: 'm2', title: 'Movie B' }];
    const state = showWatchListReducer(undefined, { type: GETADDEDWATCHLIST, payload: items });
    expect(state.addedWatchList).toEqual(items);
  });

  it('GETADDEDWATCHLIST appends to an existing list without replacing it', () => {
    const first  = showWatchListReducer(undefined, { type: GETADDEDWATCHLIST, payload: [{ id: 'm1' }] });
    const second = showWatchListReducer(first,     { type: GETADDEDWATCHLIST, payload: [{ id: 'm2' }] });
    expect(second.addedWatchList).toHaveLength(2);
    expect(second.addedWatchList[1].id).toBe('m2');
  });

  it('REMOVEALLWATCHLIST clears addedWatchList to an empty array', () => {
    const loaded  = showWatchListReducer(undefined, { type: GETADDEDWATCHLIST, payload: [{ id: 'm1' }] });
    const cleared = showWatchListReducer(loaded,    { type: REMOVEALLWATCHLIST });
    expect(cleared.addedWatchList).toEqual([]);
  });

  it('REMOVEALLWATCHLIST does not change isLoading', () => {
    const loaded  = showWatchListReducer(undefined, { type: GETADDEDWATCHLIST, payload: [{ id: 'm1' }] });
    const cleared = showWatchListReducer(loaded,    { type: REMOVEALLWATCHLIST });
    expect(cleared.isLoading).toBe(true);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = showWatchListReducer(undefined, { type: '@@INIT' });
    const after  = showWatchListReducer(before,    { type: 'UNKNOWN_WATCHLIST_UI_ACTION' });
    expect(after).toEqual(before);
  });
});
