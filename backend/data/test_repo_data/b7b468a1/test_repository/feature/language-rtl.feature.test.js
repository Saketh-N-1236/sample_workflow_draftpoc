/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  FEATURE · Language RTL Support (Scenario 32)                       │
 * │  Category : feature (constant + utility + reducer)                  │
 * │  Tests    : 24                                                       │
 * │  Sources  :                                                          │
 * │    src/reducer/actiotypes.js    (RTL_LANGUAGES)                     │
 * │    src/helpers/utilities.js     (isRtlLanguage)                     │
 * │    src/reducer/languagereducer.js (isRTL field)                     │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     language-rtl-feature
 * @category  feature
 * @sources   src/reducer/actiotypes.js,
 *            src/helpers/utilities.js,
 *            src/reducer/languagereducer.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
/** @symbol LANGUAGE       @source src/reducer/actiotypes.js */
const LANGUAGE = 'LANGUAGE';

/** @symbol RTL_LANGUAGES  @source src/reducer/actiotypes.js */
const RTL_LANGUAGES = ['ar', 'he', 'fa', 'ur'];

// ── Inlined from src/helpers/utilities.js ────────────────────────────────────
/** @symbol isRtlLanguage  @source src/helpers/utilities.js */
const isRtlLanguage = code => {
  if (typeof code !== 'string') return false;
  return ['ar', 'he', 'fa', 'ur'].includes(code.toLowerCase());
};

// ── Inlined from src/reducer/languagereducer.js ──────────────────────────────
/** @symbol languagereducer  @source src/reducer/languagereducer.js */
const langInitialState = {
  selectlanguage: 'en',
  isRTL: false,
};

const languagereducer = (state = langInitialState, action) => {
  switch (action.type) {
    case LANGUAGE:
      return {
        ...state,
        selectlanguage: action.data,
        isRTL: RTL_LANGUAGES.includes(action.data),
      };
    default:
      return state;
  }
};

// ─────────────────────────────────────────────────────────────────────────────
// describe('RTL_LANGUAGES') — 7 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('RTL_LANGUAGES', () => {
  it('is an array', () => {
    expect(Array.isArray(RTL_LANGUAGES)).toBe(true);
  });

  it("contains 'ar' for Arabic", () => {
    expect(RTL_LANGUAGES).toContain('ar');
  });

  it("contains 'he' for Hebrew", () => {
    expect(RTL_LANGUAGES).toContain('he');
  });

  it("contains 'fa' for Farsi", () => {
    expect(RTL_LANGUAGES).toContain('fa');
  });

  it("contains 'ur' for Urdu", () => {
    expect(RTL_LANGUAGES).toContain('ur');
  });

  it('has exactly 4 entries', () => {
    expect(RTL_LANGUAGES).toHaveLength(4);
  });

  it("does not contain 'en', 'fr', or 'es'", () => {
    expect(RTL_LANGUAGES).not.toContain('en');
    expect(RTL_LANGUAGES).not.toContain('fr');
    expect(RTL_LANGUAGES).not.toContain('es');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// describe('isRtlLanguage') — 9 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('isRtlLanguage', () => {
  it("returns true for 'ar' (Arabic)", () => {
    expect(isRtlLanguage('ar')).toBe(true);
  });

  it("returns true for 'he' (Hebrew)", () => {
    expect(isRtlLanguage('he')).toBe(true);
  });

  it("returns true for 'fa' (Farsi)", () => {
    expect(isRtlLanguage('fa')).toBe(true);
  });

  it("returns true for 'ur' (Urdu)", () => {
    expect(isRtlLanguage('ur')).toBe(true);
  });

  it("returns true for uppercase 'AR' — check is case-insensitive", () => {
    expect(isRtlLanguage('AR')).toBe(true);
  });

  it("returns false for 'en' (English — LTR)", () => {
    expect(isRtlLanguage('en')).toBe(false);
  });

  it("returns false for 'fr' (French — LTR)", () => {
    expect(isRtlLanguage('fr')).toBe(false);
  });

  it("returns false for 'es' (Spanish — LTR)", () => {
    expect(isRtlLanguage('es')).toBe(false);
  });

  it('returns false for non-string inputs (null, undefined, number)', () => {
    expect(isRtlLanguage(null)).toBe(false);
    expect(isRtlLanguage(undefined)).toBe(false);
    expect(isRtlLanguage(42)).toBe(false);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// describe('languagereducer — isRTL') — 8 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('languagereducer — isRTL', () => {
  it("initialises isRTL as false (English is LTR by default)", () => {
    const state = languagereducer(undefined, { type: '@@INIT' });
    expect(state.isRTL).toBe(false);
  });

  it("LANGUAGE to 'ar' sets isRTL to true", () => {
    const state = languagereducer(undefined, { type: LANGUAGE, data: 'ar' });
    expect(state.isRTL).toBe(true);
  });

  it("LANGUAGE to 'he' sets isRTL to true", () => {
    const state = languagereducer(undefined, { type: LANGUAGE, data: 'he' });
    expect(state.isRTL).toBe(true);
  });

  it("LANGUAGE to 'fa' sets isRTL to true", () => {
    const state = languagereducer(undefined, { type: LANGUAGE, data: 'fa' });
    expect(state.isRTL).toBe(true);
  });

  it("LANGUAGE to 'ur' sets isRTL to true", () => {
    const state = languagereducer(undefined, { type: LANGUAGE, data: 'ur' });
    expect(state.isRTL).toBe(true);
  });

  it("LANGUAGE to 'en' sets isRTL to false", () => {
    const state = languagereducer(undefined, { type: LANGUAGE, data: 'en' });
    expect(state.isRTL).toBe(false);
  });

  it("LANGUAGE to 'fr' sets isRTL to false", () => {
    const state = languagereducer(undefined, { type: LANGUAGE, data: 'fr' });
    expect(state.isRTL).toBe(false);
  });

  it("switching from 'ar' to 'en' resets isRTL from true back to false", () => {
    const arabic  = languagereducer(undefined, { type: LANGUAGE, data: 'ar' });
    const english = languagereducer(arabic,    { type: LANGUAGE, data: 'en' });
    expect(english.isRTL).toBe(false);
  });
});
