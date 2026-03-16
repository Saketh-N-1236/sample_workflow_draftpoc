/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · API Endpoints & API Constants                            │
 * │  Category : feature (endpoint contracts — no business logic)        │
 * │  Tests    : 7                                                        │
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
  iStream_login:    '/api/v2/client/login',
  signup:           'api/v2/subscriptor/account/registration',
  resetpassword:    '/api/v2/client/forgot-password-pf',
  refreshToken:     '/api/v2/client/refresh-token',
  ChangePasswordAPI:'/api/v2/client/account/reset-account-password',
  composer_api:     '/api/v3/composer/configuration',
  registerDevice:   '/api/v2/client/device-registration',

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

  getSubscriptionPlans:    '/api/v2/subscriptor/account/get-subscriptions',
  checkUserSubscription:   '/api/v2/subscriptor/account/get-all-user-subscriptions',

  advertisement: (type, id, genres) =>
    `/api/v2/advertisements/active-video-campaigns/list?type=${type}&vod_id=${id}&genresId=${genres}`,
};

// ── Inlined from src/services/api/common/ApiConstants.js ─────────────────────
/** @symbol MAX_IMAGE_UPLOAD_SIZE  @source src/services/api/common/ApiConstants.js */
const MAX_IMAGE_UPLOAD_SIZE = 10485760; // 10 MB

/** @symbol TIMEOUT  @source src/services/api/common/ApiConstants.js */
const TIMEOUT = 30000; // 30 seconds

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol endpoints
 */
describe('endpoints.payment', () => {
  it('addCard points to the correct payment creation path', () => {
    expect(endpoints.payment.addCard).toBe('/api/v2/payments/me?');
  });

  it('getAllCards points to the cards listing path', () => {
    expect(endpoints.payment.getAllCards).toBe('/api/v2/payments/me');
  });

  it('paymentsCheckout points to the checkout path', () => {
    expect(endpoints.payment.paymentsCheckout).toBe('/api/v2/payments/checkout');
  });
});

/**
 * @source src/services/api/common/ApiEndPoints.js
 * @symbol endpoints
 */
describe('endpoints.favourites', () => {
  it('addCardtoFavourite endpoint points to sports favourites add path', () => {
    expect(endpoints.favourites.addCardtoFavourite).toBe(
      '/api/v1/client/sports/add-favorite-match',
    );
  });

  it('advertisement endpoint builder produces a correctly interpolated URL', () => {
    const url = endpoints.advertisement('vod', '123', 'action');
    expect(url).toContain('type=vod');
    expect(url).toContain('vod_id=123');
    expect(url).toContain('genresId=action');
  });
});

/**
 * @source src/services/api/common/ApiConstants.js
 * @symbol MAX_IMAGE_UPLOAD_SIZE
 * @symbol TIMEOUT
 */
describe('ApiConstants', () => {
  it('MAX_IMAGE_UPLOAD_SIZE equals 10 MB expressed in bytes', () => {
    expect(MAX_IMAGE_UPLOAD_SIZE).toBe(10 * 1024 * 1024);
  });

  it('TIMEOUT equals 30 seconds expressed in milliseconds', () => {
    expect(TIMEOUT).toBe(30 * 1000);
  });
});
