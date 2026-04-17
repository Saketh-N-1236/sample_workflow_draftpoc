/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  STANDALONE · Pure Utility Functions                                │
 * │  Category : standalone (no cross-file dependencies)                 │
 * │  Tests    : 61                                                       │
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
const checkNull = str => (str != null ? str : '');

/** @symbol checkArray */
const checkArray = arr =>
  arr !== null && arr !== undefined && arr.length > 0 ? arr : [];

/** @symbol checkWhiteSpace */
const checkWhiteSpace = string => new RegExp(/\s/g).test(string ? string : '');

/** @symbol apiMessage */
const apiMessage = val =>
  val === null || val === '' || val === undefined
    ? 'Uh oh! Something went wrong, please try again later'
    : val;

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
    `${trailingZero(hours, 2)}:${trailingZero(minutes, 2)}:${trailingZero(seconds, 2)}`,
  ];
};

/** @symbol getProgressWidth */
const getProgressWidth = (value, max) => {
  if (!value || !max) return 0;
  return Math.min(100, (value / max) * 100);
};

/** @symbol timeConvert */
const timeConvert = n => {
  const hours    = n / 60;
  const rhours   = Math.floor(hours);
  const minutes  = (hours - rhours) * 60;
  const rminutes = Math.round(minutes);
  return `${rhours}h ${rminutes}min`;
};

/** @symbol getStreamingQuality */
const getStreamingQuality = bitrateBps => {
  if (!bitrateBps || bitrateBps <= 0) return 'unknown';
  if (bitrateBps < 500000)  return 'low';
  if (bitrateBps < 2000000) return 'medium';
  return 'high';
};

/** @symbol getTimestamp */
const getTimestamp = time => {
  if (!time) return 0;
  return new Date(time).getTime();
};

/** @symbol capitalizeFirstLetter */
const capitalizeFirstLetter = string => {
  if (string && typeof string === 'string' && string.trim().length > 0) {
    if (checkWhiteSpace(string)) {
      return string
        .split(' ')
        .filter(w => w.length > 0)
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(' ');
    }
    return string.charAt(0).toUpperCase() + string.slice(1);
  }
  return '';
};

/** @symbol generateCardNumber */
const generateCardNumber = (first, last, count) => {
  const fullNumber = `${first.slice(0, 4)}${'X'.repeat(count)}${last}`;
  return fullNumber.match(/.{1,4}/g).join(' ');
};

/** @symbol getScreenNumber */
const getScreenNumber = width => {
  let newScreennumber = 0;
  if (width > 480 && width <= 768)  newScreennumber = 1;
  else if (width > 768 && width <= 1024)  newScreennumber = 2;
  else if (width > 1024 && width <= 1200) newScreennumber = 3;
  else if (width > 1200) newScreennumber = 4;
  return newScreennumber;
};

/** @symbol nameCriteria */
const nameCriteria = text => {
  let formattedText = text;
  if (formattedText.length === 1) formattedText = formattedText.trim();
  const filteredText   = formattedText.replace(/[^a-zA-Z\s]/g, '');
  const capitalizedText = filteredText
    .split(' ')
    .map(word => (word.length > 0 ? word.charAt(0).toUpperCase() + word.slice(1) : ''))
    .join(' ');
  return capitalizedText.replace(/\s+/g, ' ');
};

/** @symbol usernameCriteria */
const usernameCriteria = text => {
  let formattedText = text.trim();
  const filteredText   = formattedText.replace(/[^a-zA-Z0-9. ]/g, '');
  const capitalizedText = filteredText.charAt(0).toUpperCase() + filteredText.slice(1);
  return capitalizedText.replace(/\s+/g, ' ');
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

  it('returns an empty string when the value is undefined', () => {
    expect(checkNull(undefined)).toBe('');
  });

  it('returns the original string value when it is defined and non-null', () => {
    expect(checkNull('hello')).toBe('hello');
  });

  it('returns 0 when given the number 0 because 0 is not null', () => {
    expect(checkNull(0)).toBe(0);
  });

  it('returns false when given boolean false because false is not null', () => {
    expect(checkNull(false)).toBe(false);
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

  it('returns an empty array when the input is undefined', () => {
    expect(checkArray(undefined)).toEqual([]);
  });

  it('returns an empty array when the input is an empty array', () => {
    expect(checkArray([])).toEqual([]);
  });

  it('returns the original array when it contains one or more items', () => {
    expect(checkArray([1, 2, 3])).toEqual([1, 2, 3]);
  });

  it('returns a single-element array unchanged', () => {
    expect(checkArray(['only'])).toEqual(['only']);
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

  it('returns false for a string with no whitespace characters', () => {
    expect(checkWhiteSpace('helloworld')).toBe(false);
  });

  it('returns true for a string that contains only a tab character', () => {
    expect(checkWhiteSpace('\t')).toBe(true);
  });

  it('returns true for a string that contains a newline character', () => {
    expect(checkWhiteSpace('line1\nline2')).toBe(true);
  });

  it('returns false for an empty string', () => {
    expect(checkWhiteSpace('')).toBe(false);
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol apiMessage
 */
describe('apiMessage', () => {
  it('returns the fallback message when the value is null', () => {
    expect(apiMessage(null)).toBe('Uh oh! Something went wrong, please try again later');
  });

  it('returns the fallback message when the value is an empty string', () => {
    expect(apiMessage('')).toBe('Uh oh! Something went wrong, please try again later');
  });

  it('returns the fallback message when the value is undefined', () => {
    expect(apiMessage(undefined)).toBe('Uh oh! Something went wrong, please try again later');
  });

  it('returns the original string when a valid non-empty message is provided', () => {
    expect(apiMessage('Invalid credentials')).toBe('Invalid credentials');
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol getTimes
 */
describe('getTimes', () => {
  it('correctly parses 3661 seconds into 1h 01m 01s with zero-padded formatting', () => {
    const [h, m, s, formatted] = getTimes(3661);
    expect(h).toBe(1);
    expect(m).toBe(1);
    expect(s).toBe(1);
    expect(formatted).toBe('01:01:01');
  });

  it('returns 0 hours when the duration is under 3600 seconds', () => {
    const [h] = getTimes(120);
    expect(h).toBe(0);
  });

  it('formats 0 seconds as 00:00:00', () => {
    const [h, m, s, formatted] = getTimes(0);
    expect(h).toBe(0);
    expect(m).toBe(0);
    expect(s).toBe(0);
    expect(formatted).toBe('00:00:00');
  });

  it('formats exactly 3600 seconds as 01:00:00', () => {
    const [h, m, s, formatted] = getTimes(3600);
    expect(h).toBe(1);
    expect(m).toBe(0);
    expect(s).toBe(0);
    expect(formatted).toBe('01:00:00');
  });

  it('zero-pads single-digit minutes in the formatted string', () => {
    const [, , , formatted] = getTimes(65);
    expect(formatted).toBe('00:01:05');
  });

  it('zero-pads single-digit seconds in the formatted string', () => {
    const [, , , formatted] = getTimes(61);
    expect(formatted).toBe('00:01:01');
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

  it('returns 0 when the value argument is falsy (0)', () => {
    expect(getProgressWidth(0, 100)).toBe(0);
  });

  it('returns 0 when max is falsy (0)', () => {
    expect(getProgressWidth(50, 0)).toBe(0);
  });

  it('clamps to 100 when value exceeds max', () => {
    expect(getProgressWidth(200, 100)).toBe(100);
  });

  it('returns exactly 100 when value equals max', () => {
    expect(getProgressWidth(100, 100)).toBe(100);
  });

  it('returns 0 when both value and max are undefined', () => {
    expect(getProgressWidth(undefined, undefined)).toBe(0);
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol timeConvert
 */
describe('timeConvert', () => {
  it('converts 90 minutes to 1h 30min', () => {
    expect(timeConvert(90)).toBe('1h 30min');
  });

  it('converts 60 minutes to 1h 0min', () => {
    expect(timeConvert(60)).toBe('1h 0min');
  });

  it('converts 45 minutes to 0h 45min', () => {
    expect(timeConvert(45)).toBe('0h 45min');
  });

  it('converts 0 minutes to 0h 0min', () => {
    expect(timeConvert(0)).toBe('0h 0min');
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol getStreamingQuality
 */
describe('getStreamingQuality', () => {
  it('returns unknown for null input', () => {
    expect(getStreamingQuality(null)).toBe('unknown');
  });

  it('returns unknown for 0 bitrate', () => {
    expect(getStreamingQuality(0)).toBe('unknown');
  });

  it('returns unknown for a negative bitrate', () => {
    expect(getStreamingQuality(-100)).toBe('unknown');
  });

  it('returns low for bitrate below 500 kbps (e.g. 400000)', () => {
    expect(getStreamingQuality(400000)).toBe('low');
  });

  it('returns medium for bitrate between 500 kbps and 2 Mbps (e.g. 1000000)', () => {
    expect(getStreamingQuality(1000000)).toBe('medium');
  });

  it('returns high for bitrate at or above 2 Mbps (e.g. 3000000)', () => {
    expect(getStreamingQuality(3000000)).toBe('high');
  });

  it('returns low for exactly 499999 bps (boundary below 500 kbps)', () => {
    expect(getStreamingQuality(499999)).toBe('low');
  });

  it('returns medium for exactly 500000 bps (lower boundary of medium)', () => {
    expect(getStreamingQuality(500000)).toBe('medium');
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol getTimestamp
 */
describe('getTimestamp', () => {
  it('returns 0 when the time argument is null', () => {
    expect(getTimestamp(null)).toBe(0);
  });

  it('returns 0 when the time argument is an empty string (falsy)', () => {
    expect(getTimestamp('')).toBe(0);
  });

  it('returns a positive integer timestamp for a valid ISO date string', () => {
    const ts = getTimestamp('2024-01-01T00:00:00Z');
    expect(typeof ts).toBe('number');
    expect(ts).toBeGreaterThan(0);
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol capitalizeFirstLetter
 */
describe('capitalizeFirstLetter', () => {
  it('capitalizes the first letter of each word in a multi-word string', () => {
    expect(capitalizeFirstLetter('john doe')).toBe('John Doe');
  });

  it('capitalizes a single word correctly', () => {
    expect(capitalizeFirstLetter('alice')).toBe('Alice');
  });

  it('returns an empty string when given an empty string', () => {
    expect(capitalizeFirstLetter('')).toBe('');
  });

  it('returns an empty string when given null', () => {
    expect(capitalizeFirstLetter(null)).toBe('');
  });

  it('returns an empty string for a whitespace-only string', () => {
    expect(capitalizeFirstLetter('   ')).toBe('');
  });

  it('collapses extra spaces and capitalizes each word', () => {
    const result = capitalizeFirstLetter('hello  world');
    expect(result).toBe('Hello World');
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol generateCardNumber
 */
describe('generateCardNumber', () => {
  it('preserves the first 4 digits and last 4 digits of the card', () => {
    const result = generateCardNumber('4111', '1111', 8);
    expect(result).toContain('4111');
    expect(result).toContain('1111');
  });

  it('masks middle digits with X characters', () => {
    const result = generateCardNumber('4111', '9999', 8);
    expect(result).toContain('XXXX');
  });

  it('produces space-separated groups of 4 characters', () => {
    const result = generateCardNumber('4111', '1111', 8);
    const groups = result.split(' ');
    groups.forEach(g => expect(g.length).toBe(4));
  });

  it('produces the correct masked representation for a 16-character card', () => {
    const result = generateCardNumber('5500', '4444', 8);
    expect(result).toBe('5500 XXXX XXXX 4444');
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol getScreenNumber
 */
describe('getScreenNumber', () => {
  it('returns 0 for viewport width at or below 480', () => {
    expect(getScreenNumber(480)).toBe(0);
  });

  it('returns 1 for viewport width between 481 and 768', () => {
    expect(getScreenNumber(600)).toBe(1);
  });

  it('returns 2 for viewport width between 769 and 1024', () => {
    expect(getScreenNumber(900)).toBe(2);
  });

  it('returns 3 for viewport width between 1025 and 1200', () => {
    expect(getScreenNumber(1100)).toBe(3);
  });

  it('returns 4 for viewport width above 1200', () => {
    expect(getScreenNumber(1440)).toBe(4);
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol nameCriteria
 */
describe('nameCriteria', () => {
  it('removes non-alphabetic characters from the name', () => {
    expect(nameCriteria('John123')).toBe('John');
  });

  it('capitalizes the first letter of each word', () => {
    expect(nameCriteria('john doe')).toBe('John Doe');
  });

  it('collapses multiple consecutive spaces into a single space', () => {
    const result = nameCriteria('john   doe');
    expect(result).toBe('John Doe');
  });

  it('trims leading whitespace when the text is a single character', () => {
    expect(nameCriteria(' ')).toBe('');
  });
});

/**
 * @source src/helpers/utilities.js
 * @symbol usernameCriteria
 */
describe('usernameCriteria', () => {
  it('trims leading and trailing spaces', () => {
    expect(usernameCriteria('  john  ')).toBe('John');
  });

  it('removes special characters other than letters, digits, dot and space', () => {
    expect(usernameCriteria('john@doe!')).toBe('Johndoe');
  });

  it('capitalizes the first character', () => {
    expect(usernameCriteria('alice99')).toBe('Alice99');
  });

  it('collapses multiple spaces into a single space', () => {
    const result = usernameCriteria('john   doe');
    expect(result).toBe('John doe');
  });
});
