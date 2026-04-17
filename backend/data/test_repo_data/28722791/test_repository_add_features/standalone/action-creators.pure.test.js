/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  STANDALONE · Action Creators                                       │
 * │  Category : standalone (pure functions — no side effects)           │
 * │  Tests    : 40                                                      │
 * │  Sources  :                                                         │
 * │    src/reducer/actions.js   (all action creator functions)          │
 * │    src/reducer/actiotypes.js (action type string constants)         │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     action-creators-standalone
 * @category  standalone
 * @sources   src/reducer/actions.js,
 *            src/reducer/actiotypes.js
 */

// ── Inlined action type constants from src/reducer/actiotypes.js ─────────────
const SCREENSIZE              = 'SCREENSIZE';
const SCREENDIMENTIONS        = 'SCREENDIMENTIONS';
const SIGNINDATA              = 'SIGNINDATA';
const SUCCESS                 = 'SUCCESS';
const SIGNUPDATA              = 'SIGNUPDATA';
const SIGNUPSUCCESS           = 'SIGNUPSUCCESS';
const COMPOSERDATA            = 'COMPOSERDATA';
const TOAST                   = 'TOAST';
const UPDATEACTIVESCREEN      = 'UPDATEACTIVESCREEN';
const GLOBALSEARCH            = 'GLOBALSEARCH';
const SECTIONLIST             = 'SECTIONLIST';
const SHOWSIGNUPMODAL         = 'SHOWSIGNUPMODAL';
const UPDATE_BUY_SUBSCRIPTION_PLAN = 'UPDATE_BUY_SUBSCRIPTION_PLAN';
const UPDATEHOMESCREENCOMPOSER = 'UPDATEHOMESCREENCOMPOSER';
const UPDATEHOMESCREENDATA    = 'UPDATEHOMESCREENDATA';
const UPDATEFAVOURITES        = 'UPDATEFAVOURITES';
const EXPANDFAVOURITES        = 'EXPANDFAVOURITES';
const RESETFAVOURITES         = 'RESETFAVOURITES';
const UPDATEBOXINGDATA        = 'UPDATEBOXINGDATA';
const UPDATEMMADATA           = 'UPDATEMMADATA';
const UPDATEK1STREAMDATA      = 'UPDATEK1STREAMDATA';
const UPDATECART              = 'UPDATECART';
const EXPANDCART              = 'EXPANDCART';
const RESETCART               = 'RESETCART';
const BANNERCAROUSALS         = 'BANNERCAROUSALS';
const ACTIVETABHEADER         = 'ACTIVETABHEADER';
const HOMESCREENSPINNER       = 'HOMESCREENSPINNER';
const STREAMEDMOVIEINFO       = 'STREAMEDMOVIEINFO';
const STREAMEDEPISODEINFO     = 'STREAMEDEPISODEINFO';
const STREAMSEASONINFO        = 'STREAMSEASONINFO';
const STREAMINGVIDEOURL       = 'STREAMINGVIDEOURL';
const SETACTIVEEPISODEINDEX   = 'SETACTIVEEPISODEINDEX';
const SETACTIVESEASONINDEX    = 'SETACTIVESEASONINDEX';
const UPCOMINGEPISODES        = 'UPCOMINGEPISODES';
const VIDEOBUFFERING          = 'VIDEOBUFFERING';
const STREAMEDSUBTITLES       = 'STREAMEDSUBTITLES';
const ACTIVESUBTITLE          = 'ACTIVESUBTITLE';
const PROFILESDETAILS         = 'PROFILESDETAILS';
const LOGINUSERNAME           = 'LOGINUSERNAME';
const LOGINSUCCESS            = 'LOGINSUCCESS';
const GETADDEDWATCHLIST       = 'GETADDEDWATCHLIST';
const REMOVEALLWATCHLIST      = 'REMOVEALLWATCHLIST';
const ADD_TO_WISHLIST         = 'ADD_TO_WISHLIST';
const REMOVE_FROM_WISHLIST    = 'REMOVE_FROM_WISHLIST';
const CLEAR_WISHLIST          = 'CLEAR_WISHLIST';
const SHOWAUTHENTICATOR       = 'SHOWAUTHENTICATOR';
const VIDEODETAILS            = 'VIDEODETAILS';
const PIPSTATUS               = 'PIPSTATUS';
const PIPIDSTATUS             = 'PIPIDSTATUS';
const LANGUAGE                = 'LANGUAGE';
const UPDATE_SHIMMER          = 'UPDATE_SHIMMER';
const SPORTSACTIVETAB         = 'SPORTSACTIVETAB';
const WS_ONRECEIVECONTINUEWATCHING = 'WS_ONRECEIVECONTINUEWATCHING';
const SHOWNOINTERNETMODAL     = 'SHOWNOINTERNETMODAL';
const SHOWLOGGEDOUTSHEET      = 'SHOWLOGGEDOUTSHEET';
const UPDATEREFRESHEDTOKEN    = 'REFRESH_TOKEN_UPDATE';
const SEARCHDATA              = 'SEARCHDATA';
const CLEAR_SEARCH_DATA       = 'CLEAR_SEARCH_DATA';
const SAVESELECTEDPROFILEDETAILS = 'SAVESELECTEDPROFILEDETAILS';
const SET_VIDEO_PLAYER_STATE  = 'SET_VIDEO_PLAYER_STATE';
const VIDEO_PLAYED_UPTO       = 'VIDEO_PLAYED_UPTO';
const NETINFORMATION          = 'NETINFORMATION';
const ONAUTHENTICATE          = 'ONAUTHENTICATE';
const LOADAPP                 = 'LOADAPP';
const STATICPROFILEIMAGE      = 'STATICPROFILE';
const UPDATESPORTSMENU        = 'UPDATESPORTSMENU';

// ── paymentActions and playerActions / showsActions / favouritesActions ───────
const UPDATEPAYMENTPLANDETAILS = 'UPDATE_PAYMENT_PLAN_DETAILS';
const UPDATEALLCARDDETAILS     = 'UPDATE_STORED_USER_ALL_CARD_DETAILS';
const UPDATEALLFAVOURITIESDETAILS = 'UPDATE_STORED_USER_ALL_FAVOURITIES_DETAILS';
const GETPLAYERS               = 'GET_PLAYERS';
const GETSHOWS                 = 'GET_SHOWS';

// ── Inlined action creators from src/reducer/actions.js ──────────────────────

const setActiveTab = (tab, name)           => ({ type: ACTIVETABHEADER, tab, name });
const setActiveSubTitles = title           => ({ type: ACTIVESUBTITLE, title });
const onAuth = ()                          => ({ type: ONAUTHENTICATE });
const loadApp = ()                         => ({ type: LOADAPP });
const setActiveSportsCarousal = sportActiveTab => ({ type: SPORTSACTIVETAB, sportActiveTab });
const setActiveEpisode = activeIndex       => ({ type: SETACTIVEEPISODEINDEX, activeIndex });
const setAvailableSubTitles = subTitlesArr => ({ type: STREAMEDSUBTITLES, subTitlesArr });
const nextPlaybackEpisodes = upcomingEpisodes => ({ type: UPCOMINGEPISODES, upcomingEpisodes });
const setActiveSeason = ID                 => ({ type: SETACTIVESEASONINDEX, ID });
const setScreenSize = screensizenumber     => ({ type: SCREENSIZE, screensizenumber });
const currentStreamedDetails = (movie, id) => ({ type: STREAMEDMOVIEINFO, movie, id });
const currentStreamedEpisodeDetails = episode => ({ type: STREAMEDEPISODEINFO, episode });
const currentStreamedSeasonDetails = season   => ({ type: STREAMSEASONINFO, season });
const setBuffering = onBuffer              => ({ type: VIDEOBUFFERING, onBuffer });
const streamingVideoUrl = videoURL         => ({ type: STREAMINGVIDEOURL, videoURL });
const paginationSpinner = bool             => ({ type: HOMESCREENSPINNER, bool });
const setFocussedCarousal = (focussedStream, hoveredtitle) => ({ type: BANNERCAROUSALS, focussedStream, hoveredtitle });
const setNetInfo = internetConnection      => ({ type: NETINFORMATION, internetConnection });
const setScreenDimentions = (width, height) => ({ type: SCREENDIMENTIONS, width, height });
const setSearchData = data                 => ({ type: SEARCHDATA, data });
const setSignIn = data                     => ({ type: SIGNINDATA, data });
const setUserDetailsSuccess = data         => ({ type: SUCCESS, data });
const setUserLoginDetailsSuccess = data    => ({ type: LOGINSUCCESS, data });
const setUserLoginUserName = data          => ({ type: LOGINUSERNAME, data });
const setComposer = data                   => ({ type: COMPOSERDATA, data });
const setSignUp = data                     => ({ type: SIGNUPDATA, data });
const setRegisterModal = showRegister      => ({ type: SHOWSIGNUPMODAL, showRegister });
const setSignUpSuccess = isAuthenticated   => ({ type: SIGNUPSUCCESS, isAuthenticated });
const setToast = toast                     => ({ type: TOAST, toast });
const setActiveScreen = screen             => ({ type: UPDATEACTIVESCREEN, payload: screen });
const setSearchKeyWords = searchKey        => ({ type: GLOBALSEARCH, key: searchKey });
const updateProfilesDetails = data         => ({ type: PROFILESDETAILS, data });
const setSectionList = (title, data)       => ({ type: SECTIONLIST, title, data });
const updateBuySubscriptionPlan = subscriptionDetails => ({ type: UPDATE_BUY_SUBSCRIPTION_PLAN, subscriptionDetails });
const updateUserCards = (userCards, cardsFetched = false) => ({
  type: UPDATEALLCARDDETAILS,
  userCards,
  cardsFetched,
  normalisedCards: Array.isArray(userCards)
    ? userCards.map(c => ({ ...c, last4: String(c?.last4 ?? '') }))
    : [],
});
const updateUserFavourites = (userFavourites, favouritesFetched = false) => ({
  type: UPDATEALLFAVOURITIESDETAILS,
  userFavourites,
  favouritesFetched,
});
const getplayer = (playerCards, cardsFetched = false) => ({ type: GETPLAYERS, playerCards, cardsFetched });
const getShows  = (showsCards,  cardsFetched = false) => ({ type: GETSHOWS,   showsCards,  cardsFetched });
const updateHomeScreenComposer = homeComposer => ({ type: UPDATEHOMESCREENCOMPOSER, homeComposer });
const updateHomeScreenData = ({ bannerData, data }) => ({ type: UPDATEHOMESCREENDATA, bannerData, data });
const setLanguage = data                   => ({ type: LANGUAGE, data });
const addToFavourite = id                  => ({ type: UPDATEFAVOURITES, id, remove: false });
const removeFromFavourite = id             => ({ type: UPDATEFAVOURITES, id, remove: true });
const expandFavourites = data              => ({ type: EXPANDFAVOURITES, data });
const resetFavourites = ()                 => ({ type: RESETFAVOURITES });
const setSportsMenu = payload              => ({ type: UPDATESPORTSMENU, payload });
const setSportsBoxingData = payload        => ({ type: UPDATEBOXINGDATA, payload });
const setSportsMMAData = payload           => ({ type: UPDATEMMADATA, payload });
const setContinueWatchingData = cw_data    => ({ type: WS_ONRECEIVECONTINUEWATCHING, cw_data });
const setSportsk1StreamData = payload      => ({ type: UPDATEK1STREAMDATA, payload });
const addCart = id                         => ({ type: UPDATECART, id, remove: false });
const removeFromCart = id                  => ({ type: UPDATECART, id, remove: true });
const addToWishlist = movieId              => ({ type: ADD_TO_WISHLIST,      payload: movieId });
const clearWishlist = ()                   => ({ type: CLEAR_WISHLIST });
const removeFromWishlist = movieId         => ({ type: REMOVE_FROM_WISHLIST, payload: movieId });
const videoData = data                     => ({ type: VIDEODETAILS, data });
const setPipvideoStatus = data             => ({ type: PIPSTATUS, data });
const setPipvideoIdStatus = videoId        => ({ type: PIPIDSTATUS, videoId });
const getAddedWatchList = payload          => ({ type: GETADDEDWATCHLIST, payload });
const removeAllWatchList = ()              => ({ type: REMOVEALLWATCHLIST });
const expandCart = data                    => ({ type: EXPANDCART, data });
const resetCart = ()                       => ({ type: RESETCART });
const setShowAuthenticator = show          => ({ type: SHOWAUTHENTICATOR, payload: show });
const updatePaymentPlanDetails = (payload, billingCycle = 'monthly') => ({
  type: UPDATEPAYMENTPLANDETAILS,
  payload,
  billingCycle,
});
const setShowInternetModal = payload       => ({ type: SHOWNOINTERNETMODAL, payload });
const setShowLoggedOutSheet = payload      => ({ type: SHOWLOGGEDOUTSHEET, payload });
const updateRefreshedToken = payload       => ({ type: UPDATEREFRESHEDTOKEN, payload });
const setStaticImageIndex = payload        => ({ type: STATICPROFILEIMAGE, payload });
const clearSearchData = ()                 => ({ type: CLEAR_SEARCH_DATA });
const saveSelectedProfileDetails = data    => ({ type: SAVESELECTEDPROFILEDETAILS, data });
const setVideoPlayerState = data           => ({ type: SET_VIDEO_PLAYER_STATE, data });
const setVideoPlayedUpto = data            => ({ type: VIDEO_PLAYED_UPTO, data });
const updateShimmer = value                => ({ type: UPDATE_SHIMMER, payload: value });

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/reducer/actions.js
 * @symbol All exported action creator functions
 */
describe('action creators — navigation and screen management', () => {
  it('setActiveTab returns ACTIVETABHEADER with tab and name', () => {
    const action = setActiveTab('sports', 'Boxing');
    expect(action.type).toBe(ACTIVETABHEADER);
    expect(action.tab).toBe('sports');
    expect(action.name).toBe('Boxing');
  });

  it('setActiveScreen returns UPDATEACTIVESCREEN with a payload', () => {
    const action = setActiveScreen('HomeScreen');
    expect(action.type).toBe(UPDATEACTIVESCREEN);
    expect(action.payload).toBe('HomeScreen');
  });

  it('setScreenSize returns SCREENSIZE with the screennumber', () => {
    const action = setScreenSize(0);
    expect(action.type).toBe(SCREENSIZE);
    expect(action.screensizenumber).toBe(0);
  });

  it('setScreenDimentions returns SCREENDIMENTIONS with width and height', () => {
    const action = setScreenDimentions(1920, 1080);
    expect(action.type).toBe(SCREENDIMENTIONS);
    expect(action.width).toBe(1920);
    expect(action.height).toBe(1080);
  });

  it('loadApp returns LOADAPP type', () => {
    expect(loadApp().type).toBe(LOADAPP);
  });

  it('onAuth returns ONAUTHENTICATE type', () => {
    expect(onAuth().type).toBe(ONAUTHENTICATE);
  });
});

describe('action creators — search and home screen', () => {
  it('setSearchData returns SEARCHDATA with data array', () => {
    const data   = [{ id: 1, title: 'Match' }];
    const action = setSearchData(data);
    expect(action.type).toBe(SEARCHDATA);
    expect(action.data).toEqual(data);
  });

  it('clearSearchData returns CLEAR_SEARCH_DATA type', () => {
    expect(clearSearchData().type).toBe(CLEAR_SEARCH_DATA);
  });

  it('setSearchKeyWords returns GLOBALSEARCH with key', () => {
    const action = setSearchKeyWords('boxing');
    expect(action.type).toBe(GLOBALSEARCH);
    expect(action.key).toBe('boxing');
  });

  it('updateHomeScreenComposer returns UPDATEHOMESCREENCOMPOSER with homeComposer', () => {
    const homeComposer = { sections: 4 };
    const action = updateHomeScreenComposer(homeComposer);
    expect(action.type).toBe(UPDATEHOMESCREENCOMPOSER);
    expect(action.homeComposer).toEqual(homeComposer);
  });

  it('paginationSpinner returns HOMESCREENSPINNER with bool', () => {
    const action = paginationSpinner(true);
    expect(action.type).toBe(HOMESCREENSPINNER);
    expect(action.bool).toBe(true);
  });

  it('setFocussedCarousal returns BANNERCAROUSALS with stream and title', () => {
    const action = setFocussedCarousal({ id: 's1' }, 'Top Pick');
    expect(action.type).toBe(BANNERCAROUSALS);
    expect(action.hoveredtitle).toBe('Top Pick');
  });
});

describe('action creators — authentication and user profile', () => {
  it('setUserDetailsSuccess returns SUCCESS with user data', () => {
    const data   = { userId: 'u1', name: 'John' };
    const action = setUserDetailsSuccess(data);
    expect(action.type).toBe(SUCCESS);
    expect(action.data).toEqual(data);
  });

  it('setUserLoginDetailsSuccess returns LOGINSUCCESS with login data', () => {
    const data   = { token: 'tok-abc', userId: 'u1' };
    const action = setUserLoginDetailsSuccess(data);
    expect(action.type).toBe(LOGINSUCCESS);
    expect(action.data).toEqual(data);
  });

  it('setUserLoginUserName returns LOGINUSERNAME with the username string', () => {
    const action = setUserLoginUserName('john_doe');
    expect(action.type).toBe(LOGINUSERNAME);
    expect(action.data).toBe('john_doe');
  });

  it('updateProfilesDetails returns PROFILESDETAILS with profile data', () => {
    const data   = [{ profileId: 'p1', name: 'Kids' }];
    const action = updateProfilesDetails(data);
    expect(action.type).toBe(PROFILESDETAILS);
    expect(action.data).toEqual(data);
  });

  it('saveSelectedProfileDetails returns SAVESELECTEDPROFILEDETAILS with data', () => {
    const data   = { profileId: 'p2', name: 'Adult' };
    const action = saveSelectedProfileDetails(data);
    expect(action.type).toBe(SAVESELECTEDPROFILEDETAILS);
    expect(action.data).toEqual(data);
  });

  it('setShowAuthenticator returns SHOWAUTHENTICATOR with payload', () => {
    const action = setShowAuthenticator(true);
    expect(action.type).toBe(SHOWAUTHENTICATOR);
    expect(action.payload).toBe(true);
  });

  it('setStaticImageIndex returns STATICPROFILE with payload', () => {
    const action = setStaticImageIndex(3);
    expect(action.type).toBe(STATICPROFILEIMAGE);
    expect(action.payload).toBe(3);
  });
});

describe('action creators — wishlist and favourites', () => {
  it('addToWishlist returns ADD_TO_WISHLIST with movieId as payload', () => {
    const action = addToWishlist([42]);
    expect(action.type).toBe(ADD_TO_WISHLIST);
    expect(action.payload).toEqual([42]);
  });

  it('removeFromWishlist returns REMOVE_FROM_WISHLIST with movieId as payload', () => {
    const action = removeFromWishlist(42);
    expect(action.type).toBe(REMOVE_FROM_WISHLIST);
    expect(action.payload).toBe(42);
  });

  it('clearWishlist returns CLEAR_WISHLIST type', () => {
    expect(clearWishlist().type).toBe(CLEAR_WISHLIST);
  });

  it('getAddedWatchList returns GETADDEDWATCHLIST with payload', () => {
    const payload = [{ id: 'm1' }];
    const action  = getAddedWatchList(payload);
    expect(action.type).toBe(GETADDEDWATCHLIST);
    expect(action.payload).toEqual(payload);
  });

  it('removeAllWatchList returns REMOVEALLWATCHLIST type', () => {
    expect(removeAllWatchList().type).toBe(REMOVEALLWATCHLIST);
  });

  it('expandFavourites returns EXPANDFAVOURITES with data', () => {
    const data   = [{ id: 'f1' }];
    const action = expandFavourites(data);
    expect(action.type).toBe(EXPANDFAVOURITES);
    expect(action.data).toEqual(data);
  });

  it('resetFavourites returns RESETFAVOURITES type', () => {
    expect(resetFavourites().type).toBe(RESETFAVOURITES);
  });

  it('addToFavourite returns UPDATEFAVOURITES with remove: false', () => {
    const action = addToFavourite('match-1');
    expect(action.type).toBe(UPDATEFAVOURITES);
    expect(action.remove).toBe(false);
    expect(action.id).toBe('match-1');
  });

  it('removeFromFavourite returns UPDATEFAVOURITES with remove: true', () => {
    const action = removeFromFavourite('match-1');
    expect(action.type).toBe(UPDATEFAVOURITES);
    expect(action.remove).toBe(true);
  });
});

describe('action creators — sports', () => {
  it('setSportsBoxingData returns UPDATEBOXINGDATA with payload', () => {
    const payload = [{ id: 'bx1' }];
    const action  = setSportsBoxingData(payload);
    expect(action.type).toBe(UPDATEBOXINGDATA);
    expect(action.payload).toEqual(payload);
  });

  it('setSportsMMAData returns UPDATEMMADATA with payload', () => {
    const payload = [{ id: 'mma1' }];
    const action  = setSportsMMAData(payload);
    expect(action.type).toBe(UPDATEMMADATA);
    expect(action.payload).toEqual(payload);
  });

  it('setSportsk1StreamData returns UPDATEK1STREAMDATA with payload', () => {
    const payload = [{ id: 'k1' }];
    const action  = setSportsk1StreamData(payload);
    expect(action.type).toBe(UPDATEK1STREAMDATA);
    expect(action.payload).toEqual(payload);
  });
});

describe('action creators — video player and streaming', () => {
  it('currentStreamedDetails returns STREAMEDMOVIEINFO with movie and id', () => {
    const movie  = { title: 'Fight Night' };
    const action = currentStreamedDetails(movie, 'movie-1');
    expect(action.type).toBe(STREAMEDMOVIEINFO);
    expect(action.movie).toEqual(movie);
    expect(action.id).toBe('movie-1');
  });

  it('currentStreamedEpisodeDetails returns STREAMEDEPISODEINFO with episode', () => {
    const episode = [{ ep: 1 }, { ep: 2 }];
    const action  = currentStreamedEpisodeDetails(episode);
    expect(action.type).toBe(STREAMEDEPISODEINFO);
    expect(action.episode).toEqual(episode);
  });

  it('currentStreamedSeasonDetails returns STREAMSEASONINFO with season', () => {
    const season = [{ season: 1 }];
    const action = currentStreamedSeasonDetails(season);
    expect(action.type).toBe(STREAMSEASONINFO);
    expect(action.season).toEqual(season);
  });

  it('streamingVideoUrl returns STREAMINGVIDEOURL with videoURL', () => {
    const action = streamingVideoUrl('https://cdn.example.com/v1.m3u8');
    expect(action.type).toBe(STREAMINGVIDEOURL);
    expect(action.videoURL).toBe('https://cdn.example.com/v1.m3u8');
  });

  it('setBuffering returns VIDEOBUFFERING with onBuffer flag', () => {
    const action = setBuffering(true);
    expect(action.type).toBe(VIDEOBUFFERING);
    expect(action.onBuffer).toBe(true);
  });

  it('setVideoPlayerState returns SET_VIDEO_PLAYER_STATE with data', () => {
    const action = setVideoPlayerState(true);
    expect(action.type).toBe(SET_VIDEO_PLAYER_STATE);
    expect(action.data).toBe(true);
  });

  it('setVideoPlayedUpto returns VIDEO_PLAYED_UPTO with progress seconds', () => {
    const action = setVideoPlayedUpto(450);
    expect(action.type).toBe(VIDEO_PLAYED_UPTO);
    expect(action.data).toBe(450);
  });

  it('videoData returns VIDEODETAILS with data', () => {
    const data   = { id: 'v1', url: 'https://cdn.example.com/v1.mp4' };
    const action = videoData(data);
    expect(action.type).toBe(VIDEODETAILS);
    expect(action.data).toEqual(data);
  });

  it('setPipvideoStatus returns PIPSTATUS with pip state', () => {
    const action = setPipvideoStatus(true);
    expect(action.type).toBe(PIPSTATUS);
    expect(action.data).toBe(true);
  });

  it('setPipvideoIdStatus returns PIPIDSTATUS with videoId', () => {
    const action = setPipvideoIdStatus('vid-77');
    expect(action.type).toBe(PIPIDSTATUS);
    expect(action.videoId).toBe('vid-77');
  });
});

describe('action creators — payment and subscription', () => {
  it('updateBuySubscriptionPlan returns UPDATE_BUY_SUBSCRIPTION_PLAN with subscriptionDetails', () => {
    const plan   = { planId: 'premium', price: 9.99 };
    const action = updateBuySubscriptionPlan(plan);
    expect(action.type).toBe(UPDATE_BUY_SUBSCRIPTION_PLAN);
    expect(action.subscriptionDetails).toEqual(plan);
  });

  it('updatePaymentPlanDetails defaults billingCycle to monthly', () => {
    const action = updatePaymentPlanDetails({ planId: 'standard' });
    expect(action.billingCycle).toBe('monthly');
  });

  it('updatePaymentPlanDetails accepts a custom billingCycle', () => {
    const action = updatePaymentPlanDetails({ planId: 'premium' }, 'yearly');
    expect(action.billingCycle).toBe('yearly');
  });

  it('updateShimmer returns UPDATE_SHIMMER with the payload value', () => {
    const action = updateShimmer(true);
    expect(action.type).toBe(UPDATE_SHIMMER);
    expect(action.payload).toBe(true);
  });
});

describe('action creators — notifications and UI modals', () => {
  it('setShowInternetModal returns SHOWNOINTERNETMODAL with payload', () => {
    const action = setShowInternetModal(true);
    expect(action.type).toBe(SHOWNOINTERNETMODAL);
    expect(action.payload).toBe(true);
  });

  it('setShowLoggedOutSheet returns SHOWLOGGEDOUTSHEET with payload', () => {
    const action = setShowLoggedOutSheet({ reason: 'session_expired' });
    expect(action.type).toBe(SHOWLOGGEDOUTSHEET);
    expect(action.payload).toEqual({ reason: 'session_expired' });
  });

  it('setRegisterModal returns SHOWSIGNUPMODAL with showRegister', () => {
    const action = setRegisterModal(true);
    expect(action.type).toBe(SHOWSIGNUPMODAL);
    expect(action.showRegister).toBe(true);
  });

  it('setNetInfo returns NETINFORMATION with internetConnection', () => {
    const action = setNetInfo(false);
    expect(action.type).toBe(NETINFORMATION);
    expect(action.internetConnection).toBe(false);
  });

  it('setLanguage returns LANGUAGE with language code', () => {
    const action = setLanguage('fr');
    expect(action.type).toBe(LANGUAGE);
    expect(action.data).toBe('fr');
  });
});
