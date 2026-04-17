/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  STANDALONE · User Initials & Full Name Formatter (Scenario 31)     │
 * │  Category : standalone (pure functions, no external dependencies)   │
 * │  Tests    : 14                                                       │
 * │  Sources  :                                                          │
 * │    src/helpers/utilities.js  (getUserInitials, formatFullName)      │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     user-initials-pure
 * @category  standalone
 * @sources   src/helpers/utilities.js
 */

// ── Inlined from src/helpers/utilities.js ────────────────────────────────────

/** @symbol capitalizeFirstLetter  @source src/helpers/utilities.js */
function capitalizeFirstLetter(string) {
  const reWhiteSpace = /\s/;
  const checkWhiteSpace = s => reWhiteSpace.test(s);
  if (string && typeof string === 'string' && string.trim().length > 0) {
    if (checkWhiteSpace(string)) {
      return string
        .split(' ')
        .filter(w => w.length > 0)
        .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
        .join(' ');
    }
    return string.charAt(0).toUpperCase() + string.slice(1).toLowerCase();
  }
  return '';
}

/** @symbol getUserInitials  @source src/helpers/utilities.js */
function getUserInitials(firstName, lastName) {
  const first = typeof firstName === 'string' ? firstName.trim().charAt(0).toUpperCase() : '';
  const last  = typeof lastName  === 'string' ? lastName.trim().charAt(0).toUpperCase()  : '';
  return (first + last) || '--';
}

/** @symbol formatFullName  @source src/helpers/utilities.js */
function formatFullName(firstName, lastName) {
  const first = typeof firstName === 'string' ? firstName.trim() : '';
  const last  = typeof lastName  === 'string' ? lastName.trim()  : '';
  const combined = [first, last].filter(Boolean).join(' ');
  return capitalizeFirstLetter(combined);
}

// ─────────────────────────────────────────────────────────────────────────────
// describe('getUserInitials') — 7 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('getUserInitials', () => {
  it("returns two uppercase initials from first and last name: ('John', 'Doe') => 'JD'", () => {
    expect(getUserInitials('John', 'Doe')).toBe('JD');
  });

  it("returns only the first initial when lastName is empty: ('Alice', '') => 'A'", () => {
    expect(getUserInitials('Alice', '')).toBe('A');
  });

  it("returns only the second initial when firstName is empty: ('', 'Smith') => 'S'", () => {
    expect(getUserInitials('', 'Smith')).toBe('S');
  });

  it("returns '--' when both firstName and lastName are empty strings", () => {
    expect(getUserInitials('', '')).toBe('--');
  });

  it("returns '--' when both are null or undefined", () => {
    expect(getUserInitials(null, null)).toBe('--');
    expect(getUserInitials(undefined, undefined)).toBe('--');
  });

  it('trims leading and trailing whitespace before taking the initial', () => {
    expect(getUserInitials('  jane  ', '  doe  ')).toBe('JD');
  });

  it('uppercases the initial regardless of the input case', () => {
    expect(getUserInitials('john', 'doe')).toBe('JD');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// describe('formatFullName') — 7 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('formatFullName', () => {
  it("combines first and last name with a space and capitalises each word", () => {
    expect(formatFullName('john', 'doe')).toBe('John Doe');
  });

  it("returns only the first name when lastName is empty", () => {
    expect(formatFullName('alice', '')).toBe('Alice');
  });

  it("returns only the last name when firstName is empty", () => {
    expect(formatFullName('', 'smith')).toBe('Smith');
  });

  it("returns an empty string when both are empty or whitespace-only", () => {
    expect(formatFullName('', '')).toBe('');
    expect(formatFullName('   ', '   ')).toBe('');
  });

  it('trims extra whitespace from both parts before combining', () => {
    expect(formatFullName('  john  ', '  doe  ')).toBe('John Doe');
  });

  it('handles null and undefined gracefully by treating them as empty', () => {
    expect(formatFullName(null, null)).toBe('');
    expect(formatFullName(undefined, undefined)).toBe('');
  });

  it('does not add a trailing space when lastName is missing', () => {
    const result = formatFullName('Alice', '');
    expect(result).not.toMatch(/\s$/);
  });
});
