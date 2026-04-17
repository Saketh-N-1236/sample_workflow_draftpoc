/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Search Unification (Scenario 28)                         │
 * │  Category : feature (unified search endpoint + UI config)           │
 * │  Tests    : 18                                                       │
 * │  Sources  :                                                          │
 * │    src/services/api/common/ApiEndPoints.js  (unifiedSearchApi)      │
 * │    src/services/api/common/homescreen/homescreen.js (unifiedSearchAPI) │
 * │    src/components/carousel/SearchResults/Component.js (getSeaarchResults) │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     search-unification-feature
 * @category  feature
 * @sources   src/services/api/common/ApiEndPoints.js,
 *            src/services/api/common/homescreen/homescreen.js,
 *            src/components/carousel/SearchResults/Component.js
 */

// ── Inlined from src/services/api/common/ApiEndPoints.js ─────────────────────
/** @symbol unifiedSearchApi  @source src/services/api/common/ApiEndPoints.js */
const endpoints = {
  Movies:         '/api/v3/movie/searchcontent/home?types=0&',
  TVShowsSearch:  '/api/v3/movie/searchcontent/home?types=2&page=1&limit=2&titleSearch=',
  unifiedSearchApi: '/api/v3/movie/searchcontent/home?types=0,2&',
  matchesApi:     '/api/v1/client/sports/search/match?',
};

// ── Mock ApiClient ────────────────────────────────────────────────────────────
const ApiClient = { get: jest.fn() };

// ── Inlined from src/services/api/common/homescreen/homescreen.js ────────────
/** @symbol unifiedSearchAPI  @source src/services/api/common/homescreen/homescreen.js */
const unifiedSearchAPI = key => {
  try {
    const response = ApiClient.get(endpoints.unifiedSearchApi + key);
    return response;
  } catch (error) {
    throw new Error(error.message);
  }
};

// ── Inlined from src/components/carousel/SearchResults/Component.js ──────────
/** @symbol getSeaarchResults  @source src/components/carousel/SearchResults/Component.js */
const buildApiCallling = search => {
  const titles = {
    allResults: 'All Results',
    Sports:     'Sports',
  };
  return [
    {
      title:           titles.allResults,
      apiEndPoint:     `titleSearch=${search}&pageNo=0&pageSize=15`,
      searchAPI:       unifiedSearchAPI,
      callPagination:  true,
      showPagination:  true,
    },
    {
      title:           titles.Sports,
      apiEndPoint:     `title=${search}&pageNo=0&pageSize=10`,
      callPagination:  true,
      showPagination:  true,
    },
  ];
};

// ─────────────────────────────────────────────────────────────────────────────
// describe('unifiedSearchApi') — 5 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('unifiedSearchApi', () => {
  it('contains types=0,2 to cover both movies and TV shows in one request', () => {
    expect(endpoints.unifiedSearchApi).toContain('types=0,2');
  });

  it('uses the /searchcontent/home path shared with the old separate endpoints', () => {
    expect(endpoints.unifiedSearchApi).toContain('/searchcontent/home');
  });

  it('is distinct from the old Movies endpoint which only had types=0', () => {
    expect(endpoints.unifiedSearchApi).not.toBe(endpoints.Movies);
  });

  it('is distinct from the old TVShowsSearch endpoint which only had types=2', () => {
    expect(endpoints.unifiedSearchApi).not.toBe(endpoints.TVShowsSearch);
  });

  it('ends with & so a query key can be appended directly without extra punctuation', () => {
    expect(endpoints.unifiedSearchApi.endsWith('&')).toBe(true);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// describe('unifiedSearchAPI') — 5 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('unifiedSearchAPI', () => {
  beforeEach(() => {
    ApiClient.get.mockReset();
  });

  it('calls ApiClient.get exactly once per invocation', () => {
    ApiClient.get.mockReturnValue({ data: {} });
    unifiedSearchAPI('titleSearch=batman&pageNo=0&pageSize=15');
    expect(ApiClient.get).toHaveBeenCalledTimes(1);
  });

  it('appends the search key directly after the unifiedSearchApi base URL', () => {
    ApiClient.get.mockReturnValue({ data: {} });
    unifiedSearchAPI('titleSearch=spiderman');
    expect(ApiClient.get).toHaveBeenCalledWith(
      endpoints.unifiedSearchApi + 'titleSearch=spiderman',
    );
  });

  it('returns the response object provided by ApiClient.get', () => {
    const mockResponse = { data: { data: { items: [{ id: 1 }] } } };
    ApiClient.get.mockReturnValue(mockResponse);
    const result = unifiedSearchAPI('titleSearch=test');
    expect(result).toBe(mockResponse);
  });

  it('throws when ApiClient.get throws', () => {
    ApiClient.get.mockImplementation(() => {
      throw new Error('network error');
    });
    expect(() => unifiedSearchAPI('key')).toThrow('network error');
  });

  it('the URL forwarded to ApiClient.get contains types=0,2', () => {
    ApiClient.get.mockReturnValue({});
    unifiedSearchAPI('x');
    const calledUrl = ApiClient.get.mock.calls[0][0];
    expect(calledUrl).toContain('types=0,2');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// describe('getSeaarchResults — unified search') — 8 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('getSeaarchResults — unified search', () => {
  it('apiCallling array has exactly 2 entries after the merge (All Results + Sports)', () => {
    expect(buildApiCallling('batman')).toHaveLength(2);
  });

  it('first entry title is "All Results"', () => {
    expect(buildApiCallling('batman')[0].title).toBe('All Results');
  });

  it('first entry searchAPI is unifiedSearchAPI', () => {
    expect(buildApiCallling('batman')[0].searchAPI).toBe(unifiedSearchAPI);
  });

  it('first entry apiEndPoint includes pageSize=15 (increased from the old 8)', () => {
    expect(buildApiCallling('batman')[0].apiEndPoint).toContain('pageSize=15');
  });

  it('first entry apiEndPoint includes the search term', () => {
    expect(buildApiCallling('inception')[0].apiEndPoint).toContain('inception');
  });

  it('second entry title is "Sports" and is unchanged from the original', () => {
    expect(buildApiCallling('batman')[1].title).toBe('Sports');
  });

  it('neither entry has the old "Movies" title', () => {
    const titles = buildApiCallling('test').map(e => e.title);
    expect(titles).not.toContain('Movies');
  });

  it('neither entry has the old "TV Shows" title', () => {
    const titles = buildApiCallling('test').map(e => e.title);
    expect(titles).not.toContain('TV Shows');
  });
});
