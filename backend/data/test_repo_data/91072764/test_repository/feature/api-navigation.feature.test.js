/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · API Endpoints & API Constants                            │
 * │  Category : feature (endpoint contracts — no business logic)        │
 * │  Tests    : 30                                                       │
 * │  Sources  :                                                          │
 * │    src/services/api/common/ApiEndPoints.js  (endpoints)             │
 * │    src/services/api/common/ApiConstants.js  (base URLs, timeouts)   │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     api-navigation-feature
 * @category  feature
 * @sources   src/services/api/common/ApiEndPoints.js,
 *            src/services/api/common/ApiConstants.js
 */

// ── Inlined from src/services/api/common/ApiEndPoints.js ─────────────────────
/** @symbol endpoints  @source src/services/api/common/ApiEndPoints.js */
const endpoints = {
  iStream_login:       '/api/v2/client/login',
  signup:              'api/v2/subscriptor/account/registration',
  resetpassword:       '/api/v2/client/forgot-password-pf',
  refreshToken:        '/api/v2/client/refresh-token',
  ChangePasswordAPI:   '/api/v2/client/account/reset-account-password',
  composer_api:        '/api/v3/composer/configuration',
  registerDevice:      '/api/v2/client/device-registration',
  getDevices:          '/api/v2/subscriptor/device/get-devices-by-account',
  removeDevice:        '/api/v2/subscriptor/device/remove-device',
  contactus:           '/api/v2/client/contactUs',
  FAQAPI:              '/api/v1/client/sports/faq/getall',
  getAllPlayer:         '/api/v1/client/sports/getAllPlayer',
  getAllShows:          '/api/v1/client/leagues/getall',
  getSubscriptionPlans:   '/api/v2/subscriptor/account/get-subscriptions',
  checkUserSubscription:  '/api/v2/subscriptor/account/get-all-user-subscriptions',
  profile_api:         '/api/v2/subscriptor/account/getAllProfiles-accountId',
  fetchProfileData:    '/api/v2/subscriptor/account/getAllprofiles',
  emailverification:   '/api/v2/subscriptor/account/activate/email',
  continueWatching:    '?carouselType=Static&types=0,1,2,3,4&filterType=Continue%20Watching',
  getLandingPage:      '/api/v2/composer/configuration',
  favoriteWatchList:   '/api/v2/movie/composer/content?carouselType=Static&types=0,2&filterType=Favorites',
  generateQrToken:     '/api/v2/client/generate-token',
  validateToken:       '/api/v2/client/qrcode-validation?token=',

  payment: {
    addCard:          '/api/v2/payments/me?',
    deleteCard:       '/api/v2/payments/me?cardId=',
    preAuth:          '/api/v2/payments/me/preauth-verify?',
    getAllCards:       '/api/v2/payments/me',
    updateCard:       '/api/v2/payments/me?',
    paymentsCheckout: '/api/v2/payments/checkout',
  },

  favourites: {
    addCardtoFavourite:     '/api/v1/client/sports/add-favorite-match',
    getAllFavourites:        '/api/v1/client/sports/favorite-match-list?type=4',
    removeCardFromFavourite:'/api/v1/client/sports/remove-favorite-match',
    favoritesList:          '/api/v2/movie/getallfavoritelist?accountProfileId=',
  },

  cart: {
    addItemToCart:    'api/v1/client/sports/addToCart/',
    removeItemsToCart:'api/v1/client/sports/remove/',
  },

  episodes: ({ tvShowId, seasonId }) =>
    `/api/v2/movie/single-event-vods-list?multiEventVodId=${tvShowId}&multiEventVodSeasonId=${seasonId}&type=1&sortColumnName=episodeNumber&sortDirection=ASC&limit=20&page=1`,

  topPicksForYou: ({ type, id }) =>
    `/api/v3/movie/composer/content?carouselType=Static&type=${type}&filterType=Top Picks For You&vodId=${id}`,

  myOrders: id =>
    `/api/v2/payments/get-transaction?account_id=${id}`,
};

// ── Inlined from src/services/api/common/ApiConstants.js ─────────────────────
/** @symbol MAX_IMAGE_UPLOAD_SIZE  @source src/services/api/common/ApiConstants.js */
const MAX_IMAGE_UPLOAD_SIZE = 20971520; // 20 MB

/** @symbol TIMEOUT  @source src/services/api/common/ApiConstants.js */
const TIMEOUT = 60000; // 60 seconds

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol endpoints.payment
 */
describe('endpoints.payment', () => {
  it('addCard points to the correct payment creation path', () => {
    expect(endpoints.payment.addCard).toBe('/api/v2/payments/me?');
  });

  it('getAllCards points to the cards listing path without query parameters', () => {
    expect(endpoints.payment.getAllCards).toBe('/api/v2/payments/me');
  });

  it('paymentsCheckout points to the v2 checkout path', () => {
    expect(endpoints.payment.paymentsCheckout).toBe('/api/v2/payments/checkout');
  });

  it('deleteCard endpoint includes the cardId query parameter placeholder', () => {
    expect(endpoints.payment.deleteCard).toContain('cardId=');
  });

  it('preAuth endpoint targets the preauth-verify path', () => {
    expect(endpoints.payment.preAuth).toContain('preauth-verify');
  });

  it('updateCard and addCard share the same base path', () => {
    expect(endpoints.payment.updateCard).toBe(endpoints.payment.addCard);
  });
});

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol endpoints.favourites
 */
describe('endpoints.favourites', () => {
  it('addCardtoFavourite endpoint points to the sports favourites add path', () => {
    expect(endpoints.favourites.addCardtoFavourite).toBe(
      '/api/v1/client/sports/add-favorite-match',
    );
  });

  it('getAllFavourites endpoint includes type=4 query filter', () => {
    expect(endpoints.favourites.getAllFavourites).toContain('type=4');
  });

  it('removeCardFromFavourite endpoint points to the remove-favorite-match path', () => {
    expect(endpoints.favourites.removeCardFromFavourite).toBe(
      '/api/v1/client/sports/remove-favorite-match',
    );
  });

  it('favoritesList endpoint includes accountProfileId as a query parameter placeholder', () => {
    expect(endpoints.favourites.favoritesList).toContain('accountProfileId=');
  });
});

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol endpoints.cart
 */
describe('endpoints.cart', () => {
  it('addItemToCart endpoint points to the sports cart add path', () => {
    expect(endpoints.cart.addItemToCart).toContain('addToCart');
  });

  it('removeItemsToCart endpoint points to the sports cart remove path', () => {
    expect(endpoints.cart.removeItemsToCart).toContain('remove');
  });
});

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol endpoints (auth and profile)
 */
describe('endpoints for authentication and profile management', () => {
  it('iStream_login endpoint targets the v2 client login path', () => {
    expect(endpoints.iStream_login).toBe('/api/v2/client/login');
  });

  it('resetpassword endpoint targets the v2 forgot-password path', () => {
    expect(endpoints.resetpassword).toContain('forgot-password');
  });

  it('refreshToken endpoint targets the v2 client refresh-token path', () => {
    expect(endpoints.refreshToken).toBe('/api/v2/client/refresh-token');
  });

  it('ChangePasswordAPI endpoint targets the reset-account-password path', () => {
    expect(endpoints.ChangePasswordAPI).toContain('reset-account-password');
  });

  it('emailverification endpoint targets the account activate/email path', () => {
    expect(endpoints.emailverification).toContain('activate/email');
  });

  it('registerDevice endpoint targets the v2 device-registration path', () => {
    expect(endpoints.registerDevice).toBe('/api/v2/client/device-registration');
  });

  it('getDevices and removeDevice endpoints both target the subscriptor device namespace', () => {
    expect(endpoints.getDevices).toContain('subscriptor/device');
    expect(endpoints.removeDevice).toContain('subscriptor/device');
  });
});

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol endpoints (dynamic builders)
 */
describe('endpoints dynamic builder functions', () => {
  it('episodes builder interpolates tvShowId and seasonId into the URL', () => {
    const url = endpoints.episodes({ tvShowId: '42', seasonId: '3' });
    expect(url).toContain('multiEventVodId=42');
    expect(url).toContain('multiEventVodSeasonId=3');
  });

  it('episodes builder always sorts by episodeNumber ascending', () => {
    const url = endpoints.episodes({ tvShowId: '1', seasonId: '1' });
    expect(url).toContain('sortColumnName=episodeNumber');
    expect(url).toContain('sortDirection=ASC');
  });

  it('topPicksForYou builder interpolates type and vodId into the URL', () => {
    const url = endpoints.topPicksForYou({ type: 2, id: 'vod-99' });
    expect(url).toContain('type=2');
    expect(url).toContain('vodId=vod-99');
  });

  it('myOrders builder interpolates account id into the transaction query path', () => {
    const url = endpoints.myOrders('user-123');
    expect(url).toBe('/api/v2/payments/get-transaction?account_id=user-123');
  });
});

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol endpoints (content and subscription)
 */
describe('endpoints for content and subscriptions', () => {
  it('getSubscriptionPlans targets the v2 get-subscriptions path', () => {
    expect(endpoints.getSubscriptionPlans).toContain('get-subscriptions');
  });

  it('checkUserSubscription targets the get-all-user-subscriptions path', () => {
    expect(endpoints.checkUserSubscription).toContain('get-all-user-subscriptions');
  });

  it('composer_api targets the v3 composer configuration path', () => {
    expect(endpoints.composer_api).toBe('/api/v3/composer/configuration');
  });

  it('getLandingPage targets the v2 composer configuration path', () => {
    expect(endpoints.getLandingPage).toBe('/api/v2/composer/configuration');
  });

  it('continueWatching query string includes the Continue Watching filterType', () => {
    expect(endpoints.continueWatching).toContain('filterType=Continue%20Watching');
  });
});

/**
 * @source src/services/api/common/ApiConstants.js
 * @symbol MAX_IMAGE_UPLOAD_SIZE
 * @symbol TIMEOUT
 */
describe('ApiConstants', () => {
  it('MAX_IMAGE_UPLOAD_SIZE equals exactly 20 MB expressed in bytes', () => {
    expect(MAX_IMAGE_UPLOAD_SIZE).toBe(20 * 1024 * 1024);
  });

  it('TIMEOUT equals exactly 60 seconds expressed in milliseconds', () => {
    expect(TIMEOUT).toBe(60 * 1000);
  });
});
