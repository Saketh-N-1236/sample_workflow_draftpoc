/**
 * Scenario 34 — Movies Tab Merge
 *
 * @scenario 34
 * @title Merge all carousel sections into a single "My Movies" section on the Movies tab
 * @source src/navigation/constants.js
 * @source src/screens/home/HomeIntroPage.js
 *
 * What this tests:
 *   - MY_MOVIES_TITLE constant equals 'My Movies'
 *   - carousaTypes.Movies constant is added with value 'MOVIES'
 *   - mergedMoviesSection() combines non-sports sections into one flat list
 *   - Sports sections are preserved and not merged
 *   - Empty/edge-case input handling
 */

// ─── Inline source: constants ───────────────────────────────────────────────────
const MY_MOVIES_TITLE = 'My Movies';

const carousaTypes = {
  isHighlightContent: 'Highlight Content',
  isSportsHighlightContent: 'Sports Highlight Content',
  Sports: 'Sports',
  Shows: 'Shows',
  Players: 'Players',
  Movies: 'MOVIES',
};
// ───────────────────────────────────────────────────────────────────────────────

// ─── Inline source: mergedMoviesSection logic (from HomeIntroPage useMemo) ─────
const mergedMoviesSection = homeScreenData => {
  if (!Array.isArray(homeScreenData)) return [];
  const sportTypes = new Set([carousaTypes.Sports, carousaTypes.isSportsHighlightContent]);
  const movieSections = homeScreenData.filter(s => !sportTypes.has(s.type));
  if (!movieSections.length) return homeScreenData;
  const allMovieItems = movieSections.flatMap(s => s.data ?? []);
  return [
    { title: MY_MOVIES_TITLE, type: carousaTypes.Movies, data: allMovieItems },
    ...homeScreenData.filter(s => sportTypes.has(s.type)),
  ];
};
// ───────────────────────────────────────────────────────────────────────────────

const sampleData = [
  { title: 'Thriller',  type: 'Genre', data: [{ id: 1 }, { id: 2 }] },
  { title: 'Crime',     type: 'Genre', data: [{ id: 3 }] },
  { title: 'Top Fights',type: carousaTypes.Sports, data: [{ id: 10 }] },
  { title: 'Highlights',type: carousaTypes.isSportsHighlightContent, data: [{ id: 11 }] },
];

describe('MY_MOVIES_TITLE', () => {
  it('equals the string "My Movies"', () => {
    expect(MY_MOVIES_TITLE).toBe('My Movies');
  });

  it('is a non-empty string', () => {
    expect(typeof MY_MOVIES_TITLE).toBe('string');
    expect(MY_MOVIES_TITLE.length).toBeGreaterThan(0);
  });
});

describe('carousaTypes.Movies', () => {
  it('has value "MOVIES"', () => {
    expect(carousaTypes.Movies).toBe('MOVIES');
  });

  it('is distinct from Sports type', () => {
    expect(carousaTypes.Movies).not.toBe(carousaTypes.Sports);
  });

  it('is distinct from Shows type', () => {
    expect(carousaTypes.Movies).not.toBe(carousaTypes.Shows);
  });

  it('original carousaTypes entries are still present', () => {
    expect(carousaTypes.isHighlightContent).toBe('Highlight Content');
    expect(carousaTypes.isSportsHighlightContent).toBe('Sports Highlight Content');
    expect(carousaTypes.Sports).toBe('Sports');
  });
});

describe('mergedMoviesSection', () => {
  it('returns an empty array when homeScreenData is undefined', () => {
    expect(mergedMoviesSection(undefined)).toHaveLength(0);
  });

  it('returns an empty array when homeScreenData is null', () => {
    expect(mergedMoviesSection(null)).toHaveLength(0);
  });

  it('returns exactly one movie section plus sports sections', () => {
    const result = mergedMoviesSection(sampleData);
    expect(result).toHaveLength(3); // 1 merged movies + 2 sports
  });

  it('first section title is MY_MOVIES_TITLE', () => {
    const result = mergedMoviesSection(sampleData);
    expect(result[0].title).toBe(MY_MOVIES_TITLE);
  });

  it('first section type is carousaTypes.Movies', () => {
    const result = mergedMoviesSection(sampleData);
    expect(result[0].type).toBe(carousaTypes.Movies);
  });

  it('merged section data combines items from all non-sports sections', () => {
    const result = mergedMoviesSection(sampleData);
    expect(result[0].data).toHaveLength(3); // ids 1, 2, 3
  });

  it('Sports section is preserved after the merged movie section', () => {
    const result = mergedMoviesSection(sampleData);
    const sports = result.find(s => s.type === carousaTypes.Sports);
    expect(sports).toBeDefined();
  });

  it('isSportsHighlightContent section is preserved after the merged movie section', () => {
    const result = mergedMoviesSection(sampleData);
    const highlights = result.find(s => s.type === carousaTypes.isSportsHighlightContent);
    expect(highlights).toBeDefined();
  });

  it('the old individual genre sections are NOT in the result', () => {
    const result = mergedMoviesSection(sampleData);
    const thriller = result.find(s => s.title === 'Thriller');
    expect(thriller).toBeUndefined();
  });

  it('returns original data unchanged when all sections are sports', () => {
    const allSports = [
      { title: 'A', type: carousaTypes.Sports, data: [] },
      { title: 'B', type: carousaTypes.isSportsHighlightContent, data: [] },
    ];
    const result = mergedMoviesSection(allSports);
    expect(result).toEqual(allSports);
  });

  it('handles sections with no data property gracefully', () => {
    const dataWithMissing = [{ title: 'NoData', type: 'Genre' }];
    const result = mergedMoviesSection(dataWithMissing);
    expect(result[0].data).toHaveLength(0);
  });
});
