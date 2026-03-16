/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  STANDALONE · Pure Utility Functions                                │
 * │  Category : standalone (no cross-file dependencies)                 │
 * │  Tests    : 10                                                       │
 * │  Source   : src/helpers/utilities.js                                │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     utilities-pure
 * @category  standalone
 * @source    src/helpers/utilities.js
 *
 * Only pure, side-effect-free functions are tested here.
 * All logic is inlined — no application imports required.
 */

// ── Inlined from src/helpers/utilities.js ────────────────────────────────────

/** @symbol checkNull */
const checkNull = str => (str !== null && str !== undefined ? str : '');

/** @symbol checkArray */
const checkArray = arr =>
  arr !== null && arr !== undefined && arr.length > 0 ? arr : [];

/** @symbol checkWhiteSpace */
const checkWhiteSpace = string =>
  new RegExp(/\s/g).test(string ? string : '');

/** @symbol getTimes */
const trailingZero = (value, count) => String(value).padStart(count, '0');
const getTimes = time => {
  const hours   = parseInt(time / 3600);
  let   seconds = time - hours * 3600;
  const minutes = parseInt(seconds / 60);
  seconds       = parseInt(seconds - minutes * 60);
  return [
    hours,
    minutes,
    seconds,
    `${hours}:${trailingZero(minutes, 2)}:${trailingZero(seconds, 2)}`,
  ];
};

/** @symbol getProgressWidth */
const getProgressWidth = (value, max) => {
  if (!value || !max) return 0;
  return (value / max) * 100;
};

/** @symbol timeConvert */
const timeConvert = n => {
  const hours    = n / 60;
  const rhours   = Math.floor(hours);
  const minutes  = (hours - rhours) * 60;
  const rminutes = Math.round(minutes);
  return `${rhours}h ${rminutes}min`;
};

// ─────────────────────────────────────────────────────────────────────────────

/**
 * @source src/helpers/utilities.js
 * @symbol checkNull
 */
describe('checkNull', () => {
  it('returns an empty string when the value is null', () => {
    expect(checkNull(null)).toBe('');
  });

  it('returns the original value when it is defined and non-null', () => {
    expect(checkNull('hello')).toBe('hello');
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol checkArray
 */
describe('checkArray', () => {
  it('returns an empty array when the input is null', () => {
    expect(checkArray(null)).toEqual([]);
  });

  it('returns the original array when it contains items', () => {
    expect(checkArray([1, 2, 3])).toEqual([1, 2, 3]);
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol checkWhiteSpace
 */
describe('checkWhiteSpace', () => {
  it('returns true for a string that contains a space', () => {
    expect(checkWhiteSpace('hello world')).toBe(true);
  });

  it('returns false for a string with no whitespace', () => {
    expect(checkWhiteSpace('helloworld')).toBe(false);
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol getTimes
 */
describe('getTimes', () => {
  it('correctly parses 3661 seconds into 1h 01m 01s', () => {
    const [h, m, s, formatted] = getTimes(3661);
    expect(h).toBe(1);
    expect(m).toBe(1);
    expect(s).toBe(1);
    expect(formatted).toBe('1:01:01');
  });

  it('returns 0 hours when the duration is under 3600 seconds', () => {
    const [h] = getTimes(120);
    expect(h).toBe(0);
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol getProgressWidth
 */
describe('getProgressWidth', () => {
  it('calculates 50% when value is half of max', () => {
    expect(getProgressWidth(50, 100)).toBe(50);
  });

  it('returns 0 when the value argument is missing or falsy', () => {
    expect(getProgressWidth(0, 100)).toBe(0);
  });
});
