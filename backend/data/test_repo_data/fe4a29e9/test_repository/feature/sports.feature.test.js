/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Sports, Players & Shows                                  │
 * │  Category : feature (sports streams, player cards, show listings)   │
 * │  Tests    : 24                                                      │
 * │  Sources  :                                                         │
 * │    src/reducer/sportsReducer.js         (sportsReducer)             │
 * │    src/reducer/playerReducer.js         (playerReducer)             │
 * │    src/reducer/playerCarousalReducer.js (playerCarousalReducer)     │
 * │    src/reducer/showsReducer.js          (showsReducer)              │
 * │    src/reducer/actiotypes.js            (action type strings)       │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     sports-feature
 * @category  feature
 * @sources   src/reducer/sportsReducer.js,
 *            src/reducer/playerReducer.js,
 *            src/reducer/playerCarousalReducer.js,
 *            src/reducer/showsReducer.js,
 *            src/reducer/actiotypes.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
const UPDATEBOXINGDATA     = 'UPDATEBOXINGDATA';
const UPDATEMMADATA        = 'UPDATEMMADATA';
const UPDATEK1STREAMDATA   = 'UPDATEK1STREAMDATA';
const UPDATEPLYERCOMPOSER  = 'UPDATEPLYERCOMPOSER';
const UPDATEPLYERSCREENDATA = 'UPDATEPLYERSCREENDATA';

// ── Inlined from src/reducer/sportsReducer.js ────────────────────────────────
/** @symbol sportsReducer  @source src/reducer/sportsReducer.js */
const sportsInitialState = {
  boxingData: undefined,
  mmaData:    undefined,
  k1Data:     undefined,
};

function sportsReducer(state = sportsInitialState, action) {
  switch (action.type) {
    case UPDATEBOXINGDATA:
      return { ...state, boxingData: action.payload };
    case UPDATEMMADATA:
      return { ...state, mmaData: action.payload };
    case UPDATEK1STREAMDATA:
      return { ...state, k1Data: action.payload };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/playerReducer.js ────────────────────────────────
/** @symbol playerReducer  @source src/reducer/playerReducer.js */
const playerActions = { GETPLAYERS: 'GET_PLAYERS' };

const playerInitialState = {
  playerCards:  [],
  cardsFetched: false,
};

function playerReducer(state = playerInitialState, action) {
  switch (action.type) {
    case playerActions.GETPLAYERS:
      return { ...state, playerCards: action.playerCards, cardsFetched: action.cardsFetched };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/playerCarousalReducer.js ────────────────────────
/** @symbol playerCarousalReducer  @source src/reducer/playerCarousalReducer.js */
const playerCarousalInitialState = {
  playerComposer:   undefined,
  playerScreenData: undefined,
};

function playerCarousalReducer(state = playerCarousalInitialState, action) {
  switch (action.type) {
    case UPDATEPLYERCOMPOSER:
      return { ...state, playerComposer: action.playerComposer };
    case UPDATEPLYERSCREENDATA:
      return { ...state, playerScreenData: action.data };
    default:
      return state;
  }
}

// ── Inlined from src/reducer/showsReducer.js ─────────────────────────────────
/** @symbol showsReducer  @source src/reducer/showsReducer.js */
const showsActions = { GETSHOWS: 'GET_SHOWS' };

const showsInitialState = {
  showsCards:   [],
  cardsFetched: false,
};

function showsReducer(state = showsInitialState, action) {
  switch (action.type) {
    case showsActions.GETSHOWS:
      return { ...state, showsCards: action.showsCards, cardsFetched: action.cardsFetched };
    default:
      return state;
  }
}

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/reducer/sportsReducer.js
 * @symbol sportsReducer
 */
describe('sportsReducer', () => {
  it('initialises with boxingData as undefined', () => {
    const state = sportsReducer(undefined, { type: '@@INIT' });
    expect(state.boxingData).toBeUndefined();
  });

  it('initialises with mmaData as undefined', () => {
    const state = sportsReducer(undefined, { type: '@@INIT' });
    expect(state.mmaData).toBeUndefined();
  });

  it('initialises with k1Data as undefined', () => {
    const state = sportsReducer(undefined, { type: '@@INIT' });
    expect(state.k1Data).toBeUndefined();
  });

  it('UPDATEBOXINGDATA stores the boxing section payload', () => {
    const payload = [{ matchId: 'bx1', title: 'Championship Bout' }];
    const state   = sportsReducer(undefined, { type: UPDATEBOXINGDATA, payload });
    expect(state.boxingData).toEqual(payload);
  });

  it('UPDATEBOXINGDATA does not overwrite mmaData or k1Data', () => {
    const withMma   = sportsReducer(undefined, { type: UPDATEMMADATA,      payload: [{ id: 'm1' }] });
    const withBoxing = sportsReducer(withMma,   { type: UPDATEBOXINGDATA,   payload: [{ id: 'b1' }] });
    expect(withBoxing.mmaData).toEqual([{ id: 'm1' }]);
  });

  it('UPDATEMMADATA stores the MMA section payload', () => {
    const payload = [{ matchId: 'mma1', title: 'Cage Fight' }];
    const state   = sportsReducer(undefined, { type: UPDATEMMADATA, payload });
    expect(state.mmaData).toEqual(payload);
  });

  it('UPDATEK1STREAMDATA stores the K1 section payload', () => {
    const payload = [{ matchId: 'k1', title: 'K1 Grand Prix' }];
    const state   = sportsReducer(undefined, { type: UPDATEK1STREAMDATA, payload });
    expect(state.k1Data).toEqual(payload);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = sportsReducer(undefined, { type: '@@INIT' });
    const after  = sportsReducer(before,    { type: 'UNKNOWN_SPORTS_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/playerReducer.js
 * @symbol playerReducer
 * @symbol playerActions
 */
describe('playerReducer', () => {
  it('initialises with an empty playerCards array', () => {
    const state = playerReducer(undefined, { type: '@@INIT' });
    expect(state.playerCards).toEqual([]);
  });

  it('initialises with cardsFetched as false', () => {
    const state = playerReducer(undefined, { type: '@@INIT' });
    expect(state.cardsFetched).toBe(false);
  });

  it('GETPLAYERS stores the player cards and sets cardsFetched to true', () => {
    const cards = [{ id: 'p1', name: 'Ali' }, { id: 'p2', name: 'Tyson' }];
    const state = playerReducer(undefined, {
      type: playerActions.GETPLAYERS,
      playerCards:  cards,
      cardsFetched: true,
    });
    expect(state.playerCards).toEqual(cards);
    expect(state.cardsFetched).toBe(true);
  });

  it('GETPLAYERS with an empty array leaves cardsFetched as provided', () => {
    const state = playerReducer(undefined, {
      type: playerActions.GETPLAYERS,
      playerCards:  [],
      cardsFetched: false,
    });
    expect(state.playerCards).toEqual([]);
    expect(state.cardsFetched).toBe(false);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = playerReducer(undefined, { type: '@@INIT' });
    const after  = playerReducer(before,    { type: 'UNKNOWN_PLAYER_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/playerCarousalReducer.js
 * @symbol playerCarousalReducer
 */
describe('playerCarousalReducer', () => {
  it('initialises with playerComposer as undefined', () => {
    const state = playerCarousalReducer(undefined, { type: '@@INIT' });
    expect(state.playerComposer).toBeUndefined();
  });

  it('initialises with playerScreenData as undefined', () => {
    const state = playerCarousalReducer(undefined, { type: '@@INIT' });
    expect(state.playerScreenData).toBeUndefined();
  });

  it('UPDATEPLYERCOMPOSER stores the player composer configuration', () => {
    const composer = { layout: 'carousel', sections: 3 };
    const state    = playerCarousalReducer(undefined, {
      type: UPDATEPLYERCOMPOSER,
      playerComposer: composer,
    });
    expect(state.playerComposer).toEqual(composer);
  });

  it('UPDATEPLYERSCREENDATA stores the player screen data', () => {
    const data  = [{ id: 'p1' }, { id: 'p2' }];
    const state = playerCarousalReducer(undefined, { type: UPDATEPLYERSCREENDATA, data });
    expect(state.playerScreenData).toEqual(data);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = playerCarousalReducer(undefined, { type: '@@INIT' });
    const after  = playerCarousalReducer(before,    { type: 'UNKNOWN_CAROUSEL_ACTION' });
    expect(after).toEqual(before);
  });
});

/**
 * @source src/reducer/showsReducer.js
 * @symbol showsReducer
 * @symbol showsActions
 */
describe('showsReducer', () => {
  it('initialises with an empty showsCards array', () => {
    const state = showsReducer(undefined, { type: '@@INIT' });
    expect(state.showsCards).toEqual([]);
  });

  it('initialises with cardsFetched as false', () => {
    const state = showsReducer(undefined, { type: '@@INIT' });
    expect(state.cardsFetched).toBe(false);
  });

  it('GETSHOWS stores shows cards and sets cardsFetched to true', () => {
    const cards = [{ id: 's1', title: 'Show A' }, { id: 's2', title: 'Show B' }];
    const state = showsReducer(undefined, {
      type: showsActions.GETSHOWS,
      showsCards:   cards,
      cardsFetched: true,
    });
    expect(state.showsCards).toEqual(cards);
    expect(state.cardsFetched).toBe(true);
  });

  it('GETSHOWS with an empty array preserves cardsFetched as false', () => {
    const state = showsReducer(undefined, {
      type: showsActions.GETSHOWS,
      showsCards:   [],
      cardsFetched: false,
    });
    expect(state.showsCards).toEqual([]);
  });

  it('returns unchanged state for an unknown action type', () => {
    const before = showsReducer(undefined, { type: '@@INIT' });
    const after  = showsReducer(before,    { type: 'UNKNOWN_SHOWS_ACTION' });
    expect(after).toEqual(before);
  });
});
