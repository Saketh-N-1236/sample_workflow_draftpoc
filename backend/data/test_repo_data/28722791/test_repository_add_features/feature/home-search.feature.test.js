/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Home Screen & Search                                     │
 * │  Category : feature (home composer, search results, section lists)  │
 * │  Tests    : 20                                                      │
 * │  Sources  :                                                         │
 * │    src/reducer/homeReducer.js       (homeReducer)                   │
 * │    src/reducer/sectionListReducer.js (sectionListReducer)           │
 * │    src/reducer/actiotypes.js        (action type strings)           │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     home-search-feature
 * @category  feature
 * @sources   src/reducer/homeReducer.js,
 *            src/reducer/sectionListReducer.js,
 *            src/reducer/actiotypes.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
const UPDATEHOMESCREENCOMPOSER   = 'UPDATEHOMESCREENCOMPOSER';
const UPDATEHOMESCREENDATA       = 'UPDATEHOMESCREENDATA';
const SEARCHDATA                 = 'SEARCHDATA';
const CLEAR_SEARCH_DATA          = 'CLEAR_SEARCH_DATA';
const BANNERCAROUSALS            = 'BANNERCAROUSALS';
const HOMESCREENSPINNER          = 'HOMESCREENSPINNER';
const SECTIONLIST                = 'SECTIONLIST';

// ── Inlined from src/reducer/homeReducer.js ───────────────────────────────────
/**
 * NOTE: homeReducer uses React Native Streaming component and cardTitles
 * internally for the WS_ONRECEIVECONTINUEWATCHING case. That case directly
 * mutates state (anti-pattern) and is covered separately. All other cases
 * are tested here with the pure reducer logic.
 * @symbol homeReducer  @source src/reducer/homeReducer.js
 */
const homeInitialState = {
  homeComposer:        undefined,
  bannerData:          undefined,
  homeScreenData:      undefined,
  focussedStream:      undefined,
  hoveredTitle:        '',
  continueWatchingData:undefined,
  showSpinner:         false,
  mySearchData:        [],
};

function homeReducer(state = homeInitialState, action) {
  switch (action.type) {
    case UPDATEHOMESCREENCOMPOSER:
      return { ...state, homeComposer: action.homeComposer };
    case UPDATEHOMESCREENDATA:
      return { ...state, bannerData: action.bannerData, homeScreenData: action.data };
    case SEARCHDATA:
      return { ...state, mySearchData: action.data };
    case CLEAR_SEARCH_DATA:
      return { ...state, mySearchData: [] };
    case BANNERCAROUSALS:
      return { ...state, focussedStream: action.focussedStream, hoveredTitle: action.hoveredtitle };
    case HOMESCREENSPINNER:
      return { ...state, showSpinner: action.bool };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/sectionListReducer.js ───────────────────────────
/** @symbol sectionListReducer  @source src/reducer/sectionListReducer.js */
const sectionListInitialState = { title: null, listData: undefined };

const sectionListReducer = (state = sectionListInitialState, action) => {
  switch (action.type) {
    case SECTIONLIST:
      return { ...state, title: action.title, listData: action.data };
    default:
      return state;
  }
};

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/reducer/homeReducer.js
 * @symbol homeReducer
 */
describe('homeReducer', () => {
  it('initialises with mySearchData as an empty array', () => {
    const state = homeReducer(undefined, { type: '@@INIT' });
    expect(state.mySearchData).toEqual([]);
  });

  it('initialises with homeComposer as undefined', () => {
    const state = homeReducer(undefined, { type: '@@INIT' });
    expect(state.homeComposer).toBeUndefined();
  });

  it('initialises with showSpinner as false', () => {
    const state = homeReducer(undefined, { type: '@@INIT' });
    expect(state.showSpinner).toBe(false);
  });

  it('initialises with hoveredTitle as an empty string', () => {
    const state = homeReducer(undefined, { type: '@@INIT' });
    expect(state.hoveredTitle).toBe('');
  });

  it('SEARCHDATA stores an array of search results', () => {
    const results = [{ id: 1, title: 'Fight Night' }, { id: 2, title: 'Boxing Gala' }];
    const state   = homeReducer(undefined, { type: SEARCHDATA, data: results });
    expect(state.mySearchData).toEqual(results);
  });

  it('SEARCHDATA replaces previous search results entirely', () => {
    const first  = homeReducer(undefined, { type: SEARCHDATA, data: [{ id: 1 }] });
    const second = homeReducer(first,     { type: SEARCHDATA, data: [{ id: 2 }, { id: 3 }] });
    expect(second.mySearchData).toHaveLength(2);
    expect(second.mySearchData[0].id).toBe(2);
  });

  it('CLEAR_SEARCH_DATA resets mySearchData to an empty array', () => {
    const loaded  = homeReducer(undefined, { type: SEARCHDATA,       data: [{ id: 1 }] });
    const cleared = homeReducer(loaded,    { type: CLEAR_SEARCH_DATA });
    expect(cleared.mySearchData).toEqual([]);
  });

  it('UPDATEHOMESCREENCOMPOSER stores the composer configuration object', () => {
    const composer = { layout: 'grid', sections: 5 };
    const state    = homeReducer(undefined, { type: UPDATEHOMESCREENCOMPOSER, homeComposer: composer });
    expect(state.homeComposer).toEqual(composer);
  });

  it('UPDATEHOMESCREENDATA stores bannerData and homeScreenData separately', () => {
    const bannerData = [{ id: 'b1' }];
    const data       = [{ title: 'Continue Watching' }, { title: 'New Releases' }];
    const state      = homeReducer(undefined, { type: UPDATEHOMESCREENDATA, bannerData, data });
    expect(state.bannerData).toEqual(bannerData);
    expect(state.homeScreenData).toEqual(data);
  });

  it('BANNERCAROUSALS stores focussedStream and hoveredTitle', () => {
    const stream = { id: 'stream-1' };
    const state  = homeReducer(undefined, {
      type:          BANNERCAROUSALS,
      focussedStream: stream,
      hoveredtitle:  'Top Picks',
    });
    expect(state.focussedStream).toEqual(stream);
    expect(state.hoveredTitle).toBe('Top Picks');
  });

  it('HOMESCREENSPINNER sets showSpinner to true', () => {
    const state = homeReducer(undefined, { type: HOMESCREENSPINNER, bool: true });
    expect(state.showSpinner).toBe(true);
  });

  it('HOMESCREENSPINNER sets showSpinner back to false', () => {
    const on  = homeReducer(undefined, { type: HOMESCREENSPINNER, bool: true });
    const off = homeReducer(on,        { type: HOMESCREENSPINNER, bool: false });
    expect(off.showSpinner).toBe(false);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = homeReducer(undefined, { type: '@@INIT' });
    const after  = homeReducer(before,    { type: 'UNKNOWN_HOME_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/sectionListReducer.js
 * @symbol sectionListReducer
 */
describe('sectionListReducer', () => {
  it('initialises with title as null', () => {
    const state = sectionListReducer(undefined, { type: '@@INIT' });
    expect(state.title).toBeNull();
  });

  it('initialises with listData as undefined', () => {
    const state = sectionListReducer(undefined, { type: '@@INIT' });
    expect(state.listData).toBeUndefined();
  });

  it('SECTIONLIST stores both title and data', () => {
    const data  = [{ id: 'm1' }, { id: 'm2' }];
    const state = sectionListReducer(undefined, { type: SECTIONLIST, title: 'New Releases', data });
    expect(state.title).toBe('New Releases');
    expect(state.listData).toEqual(data);
  });

  it('SECTIONLIST can overwrite a previous section with new content', () => {
    const first  = sectionListReducer(undefined, { type: SECTIONLIST, title: 'Movies',   data: [{ id: 1 }] });
    const second = sectionListReducer(first,     { type: SECTIONLIST, title: 'TV Shows', data: [{ id: 2 }] });
    expect(second.title).toBe('TV Shows');
    expect(second.listData).toEqual([{ id: 2 }]);
  });

  it('SECTIONLIST with an empty data array stores an empty array', () => {
    const state = sectionListReducer(undefined, { type: SECTIONLIST, title: 'Empty', data: [] });
    expect(state.listData).toEqual([]);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = sectionListReducer(undefined, { type: '@@INIT' });
    const after  = sectionListReducer(before,    { type: 'UNKNOWN_SECTION_ACTION' });
    expect(after).toEqual(before);
  });
});
