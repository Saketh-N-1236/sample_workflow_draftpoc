/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · App Reducer, Spinner & Action Creators                   │
 * │  Category : feature (full reducer flow, single-feature scope)       │
 * │  Tests    : 30                                                       │
 * │  Sources  :                                                          │
 * │    src/reducer/appReducer.js    (appReducer)                        │
 * │    src/reducer/actiotypes.js    (action type constants)             │
 * │    src/reducer/actions.js       (action creator functions)          │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     reducers-spinners-app-feature
 * @category  feature
 * @sources   src/reducer/appReducer.js,
 *            src/reducer/actiotypes.js,
 *            src/reducer/actions.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
const UPDATEACTIVESCREEN  = 'UPDATEACTIVESCREEN';
const INCREASESPINNERCOUNT = 'INCREASESPINNERCOUNT';
const DECREASESPINNERCOUNT = 'DECREASESPINNERCOUNT';
const GLOBALSEARCH         = 'GLOBALSEARCH';
const NETINFORMATION       = 'NETINFORMATION';
const ACTIVETABHEADER      = 'ACTIVETABHEADER';
const SPORTSACTIVETAB      = 'SPORTSACTIVETAB';
const LOADAPP              = 'LOADAPP';
const EXPANDFAVOURITES     = 'EXPANDFAVOURITES';
const UPDATEFAVOURITES     = 'UPDATEFAVOURITES';
const RESETFAVOURITES      = 'RESETFAVOURITES';
const EXPANDCART           = 'EXPANDCART';
const UPDATECART           = 'UPDATECART';
const RESETCART            = 'RESETCART';
const UPDATESPORTSMENU     = 'UPDATESPORTSMENU';
const SHOWNOINTERNETMODAL  = 'SHOWNOINTERNETMODAL';
const SHOWAUTHENTICATOR    = 'SHOWAUTHENTICATOR';
const SHOWSIGNUPMODAL      = 'SHOWSIGNUPMODAL';
const UPDATECOMPOSER       = 'UPDATECOMPOSER';

// ── Inlined from src/reducer/appReducer.js ────────────────────────────────────
/**
 * @symbol appReducer  @source src/reducer/appReducer.js
 * NOTE: isPotrait and isUserLoggedIn are runtime-only; we use static defaults.
 */
const appInitialState = {
  activeScreen:         undefined,
  spinner:              0,
  searchKey:            '',
  showRegister:         false,
  subscriptionDetails:  {},
  isPotrait:            false,
  internetConnection:   true,
  composer:             undefined,
  favourites:           [],
  addToCart:            [],
  isUserLoggedIn:       false,
  sportsMenu:           false,
  activeTab:            0,
  activeTabScreenName:  '',
  userID:               null,
  showAuthenticator:    undefined,
  sportsActiveTab:      '',
  shownoInternetModal:  false,
  appLoaded:            false,
};

function appReducer(state = appInitialState, action) {
  switch (action.type) {
    case UPDATEACTIVESCREEN:
      return { ...state, activeScreen: action.payload };
    case ACTIVETABHEADER:
      return { ...state, activeTab: action.tab, activeTabScreenName: action.name };
    case SPORTSACTIVETAB:
      return { ...state, sportsActiveTab: action.sportActiveTab };
    case LOADAPP:
      return { ...state, appLoaded: true };
    case NETINFORMATION:
      return { ...state, internetConnection: action.internetConnection };
    case INCREASESPINNERCOUNT:
      return { ...state, spinner: state.spinner + 1 };
    case DECREASESPINNERCOUNT:
      return { ...state, spinner: state.spinner > 0 ? state.spinner - 1 : 0 };
    case SHOWSIGNUPMODAL:
      return { ...state, showRegister: action.showRegister };
    case GLOBALSEARCH:
      return { ...state, searchKey: action.key };
    case UPDATECOMPOSER:
      return { ...state, composer: action.composer };
    case RESETFAVOURITES:
      return { ...state, favourites: [] };
    case EXPANDFAVOURITES:
      return { ...state, favourites: Array.from(new Set([...state.favourites, ...action.data])) };
    case UPDATEFAVOURITES: {
      let newFavourites = [...state.favourites];
      if (action.remove === true) {
        newFavourites = newFavourites.filter(id => id !== action.id);
      } else {
        newFavourites = [...newFavourites, action.id];
      }
      return { ...state, favourites: newFavourites };
    }
    case RESETCART:
      return { ...state, addToCart: [] };
    case EXPANDCART:
      return { ...state, addToCart: Array.from(new Set([...state.addToCart, ...action.data])) };
    case UPDATECART: {
      let newCart = [...state.addToCart];
      if (action.remove === true) {
        newCart = newCart.filter(id => id !== action.id);
      } else {
        newCart = [...newCart, action.id];
      }
      return { ...state, addToCart: newCart };
    }
    case UPDATESPORTSMENU:
      return { ...state, sportsMenu: action.payload };
    case SHOWAUTHENTICATOR:
      return { ...state, showAuthenticator: action.payload };
    case SHOWNOINTERNETMODAL:
      return { ...state, shownoInternetModal: action.payload };
    default:
      return state;
  }
}

// ── Inlined action creators from src/reducer/actions.js ──────────────────────
const setActiveScreen   = screen       => ({ type: UPDATEACTIVESCREEN, payload: screen });
const setSearchKeyWords = searchKey    => ({ type: GLOBALSEARCH, key: searchKey });
const setNetInfo        = connection   => ({ type: NETINFORMATION, internetConnection: connection });
const setActiveTab      = (tab, name)  => ({ type: ACTIVETABHEADER, tab, name });
const loadApp           = ()           => ({ type: LOADAPP });
const addToFavourite    = id           => ({ type: UPDATEFAVOURITES, id, remove: false });
const removeFromFavourite = id         => ({ type: UPDATEFAVOURITES, id, remove: true });
const expandFavourites  = data         => ({ type: EXPANDFAVOURITES, data });
const resetFavourites   = ()           => ({ type: RESETFAVOURITES });
const addCart           = id           => ({ type: UPDATECART, id, remove: false });
const removeFromCart    = id           => ({ type: UPDATECART, id, remove: true });
const expandCart        = data         => ({ type: EXPANDCART, data });
const resetCart         = ()           => ({ type: RESETCART });

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/reducer/appReducer.js
 * @source src/reducer/actiotypes.js
 * @symbol appReducer — initial state
 */
describe('appReducer initial state', () => {
  it('initialises spinner at 0', () => {
    const state = appReducer(undefined, { type: '@@INIT' });
    expect(state.spinner).toBe(0);
  });

  it('initialises appLoaded as false', () => {
    const state = appReducer(undefined, { type: '@@INIT' });
    expect(state.appLoaded).toBe(false);
  });

  it('initialises internetConnection as true', () => {
    const state = appReducer(undefined, { type: '@@INIT' });
    expect(state.internetConnection).toBe(true);
  });

  it('initialises favourites as an empty array', () => {
    const state = appReducer(undefined, { type: '@@INIT' });
    expect(state.favourites).toEqual([]);
  });

  it('initialises addToCart as an empty array', () => {
    const state = appReducer(undefined, { type: '@@INIT' });
    expect(state.addToCart).toEqual([]);
  });
});

/**
 * @source src/reducer/appReducer.js
 * @source src/reducer/actiotypes.js
 * @symbol appReducer — spinner behaviour
 */
describe('appReducer spinner counter', () => {
  it('INCREASESPINNERCOUNT increments spinner by 1', () => {
    const state = appReducer(undefined, { type: INCREASESPINNERCOUNT });
    expect(state.spinner).toBe(1);
  });

  it('DECREASESPINNERCOUNT decrements spinner by 1 from a positive value', () => {
    const loaded   = appReducer(undefined, { type: INCREASESPINNERCOUNT });
    const decreased = appReducer(loaded,   { type: DECREASESPINNERCOUNT });
    expect(decreased.spinner).toBe(0);
  });

  it('DECREASESPINNERCOUNT does not allow spinner to go below 0', () => {
    const state = appReducer(undefined, { type: DECREASESPINNERCOUNT });
    expect(state.spinner).toBe(0);
  });

  it('spinner can be incremented multiple times', () => {
    let state = appReducer(undefined, { type: INCREASESPINNERCOUNT });
    state     = appReducer(state,     { type: INCREASESPINNERCOUNT });
    state     = appReducer(state,     { type: INCREASESPINNERCOUNT });
    expect(state.spinner).toBe(3);
  });
});

/**
 * @source src/reducer/appReducer.js
 * @source src/reducer/actions.js
 * @symbol appReducer — navigation and screen tracking
 */
describe('appReducer active screen and navigation tracking', () => {
  it('UPDATEACTIVESCREEN stores the provided screen name', () => {
    const state = appReducer(undefined, setActiveScreen('homePage'));
    expect(state.activeScreen).toBe('homePage');
  });

  it('LOADAPP sets appLoaded to true', () => {
    const state = appReducer(undefined, loadApp());
    expect(state.appLoaded).toBe(true);
  });

  it('ACTIVETABHEADER updates activeTab and activeTabScreenName together', () => {
    const state = appReducer(undefined, setActiveTab(2, 'Sports'));
    expect(state.activeTab).toBe(2);
    expect(state.activeTabScreenName).toBe('Sports');
  });

  it('GLOBALSEARCH stores the search keyword', () => {
    const state = appReducer(undefined, setSearchKeyWords('boxing'));
    expect(state.searchKey).toBe('boxing');
  });

  it('NETINFORMATION sets internetConnection to false when offline', () => {
    const state = appReducer(undefined, setNetInfo(false));
    expect(state.internetConnection).toBe(false);
  });

  it('NETINFORMATION restores internetConnection to true when back online', () => {
    const offline = appReducer(undefined, setNetInfo(false));
    const online  = appReducer(offline,   setNetInfo(true));
    expect(online.internetConnection).toBe(true);
  });
});

/**
 * @source src/reducer/appReducer.js
 * @source src/reducer/actions.js
 * @symbol appReducer — favourites management
 */
describe('appReducer favourites management', () => {
  it('EXPANDFAVOURITES adds ids to the favourites array', () => {
    const state = appReducer(undefined, expandFavourites(['id1', 'id2']));
    expect(state.favourites).toContain('id1');
    expect(state.favourites).toContain('id2');
  });

  it('EXPANDFAVOURITES deduplicates ids already in the array', () => {
    const first  = appReducer(undefined, expandFavourites(['id1']));
    const second = appReducer(first,     expandFavourites(['id1', 'id2']));
    expect(second.favourites).toHaveLength(2);
  });

  it('UPDATEFAVOURITES with remove=false appends an id', () => {
    const state = appReducer(undefined, addToFavourite('matchId'));
    expect(state.favourites).toContain('matchId');
  });

  it('UPDATEFAVOURITES with remove=true removes the specified id', () => {
    const added   = appReducer(undefined, addToFavourite('matchId'));
    const removed = appReducer(added,     removeFromFavourite('matchId'));
    expect(removed.favourites).not.toContain('matchId');
  });

  it('RESETFAVOURITES empties the favourites array', () => {
    const loaded = appReducer(undefined, expandFavourites(['id1', 'id2']));
    const reset  = appReducer(loaded,    resetFavourites());
    expect(reset.favourites).toEqual([]);
  });
});

/**
 * @source src/reducer/appReducer.js
 * @source src/reducer/actions.js
 * @symbol appReducer — cart management
 */
describe('appReducer cart management', () => {
  it('EXPANDCART adds items to the cart array', () => {
    const state = appReducer(undefined, expandCart(['item1', 'item2']));
    expect(state.addToCart).toContain('item1');
  });

  it('UPDATECART with remove=false adds an item id to the cart', () => {
    const state = appReducer(undefined, addCart('ppv-001'));
    expect(state.addToCart).toContain('ppv-001');
  });

  it('UPDATECART with remove=true removes an item id from the cart', () => {
    const added   = appReducer(undefined, addCart('ppv-001'));
    const removed = appReducer(added,     removeFromCart('ppv-001'));
    expect(removed.addToCart).not.toContain('ppv-001');
  });

  it('RESETCART empties the addToCart array', () => {
    const loaded = appReducer(undefined, addCart('ppv-001'));
    const reset  = appReducer(loaded,    resetCart());
    expect(reset.addToCart).toEqual([]);
  });
});

/**
 * @source src/reducer/appReducer.js
 * @source src/reducer/actiotypes.js
 * @symbol appReducer — misc UI state
 */
describe('appReducer misc UI state', () => {
  it('UPDATESPORTSMENU toggles the sportsMenu flag', () => {
    const state = appReducer(undefined, { type: UPDATESPORTSMENU, payload: true });
    expect(state.sportsMenu).toBe(true);
  });

  it('SHOWAUTHENTICATOR stores the authenticator payload', () => {
    const state = appReducer(undefined, { type: SHOWAUTHENTICATOR, payload: 'qr-login' });
    expect(state.showAuthenticator).toBe('qr-login');
  });

  it('SHOWNOINTERNETMODAL sets shownoInternetModal to true', () => {
    const state = appReducer(undefined, { type: SHOWNOINTERNETMODAL, payload: true });
    expect(state.shownoInternetModal).toBe(true);
  });

  it('UPDATECOMPOSER stores the composer data in state', () => {
    const composer = { pages: [{ name: 'Home' }] };
    const state    = appReducer(undefined, { type: UPDATECOMPOSER, composer });
    expect(state.composer).toEqual(composer);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = appReducer(undefined, { type: '@@INIT' });
    const after  = appReducer(before,    { type: 'UNKNOWN_APP_ACTION' });
    expect(after).toEqual(before);
  });
});
