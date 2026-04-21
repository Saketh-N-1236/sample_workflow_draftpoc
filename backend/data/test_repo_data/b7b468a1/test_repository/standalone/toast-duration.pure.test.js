/**
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │  STANDALONE · Toast Duration (Scenario 29)                          │
 * │  Category : standalone (pure logic, no cross-file dependencies)     │
 * │  Tests    : 15                                                       │
 * │  Sources  :                                                          │
 * │    src/reducer/actiotypes.js   (TOAST_DURATION)                     │
 * │    src/reducer/actions.js      (setToast)                           │
 * │    src/reducer/toastReducer.js (duration field)                     │
 * └─────────────────────────────────────────────────────────────────────┘
 *
 * @suite     toast-duration-pure
 * @category  standalone
 * @sources   src/reducer/actiotypes.js,
 *            src/reducer/actions.js,
 *            src/reducer/toastReducer.js
 */

// ── Inlined from src/reducer/actiotypes.js ───────────────────────────────────
/** @symbol TOAST          @source src/reducer/actiotypes.js */
const TOAST = 'TOAST';

/** @symbol TOAST_DURATION @source src/reducer/actiotypes.js */
const TOAST_DURATION = { SHORT: 2000, NORMAL: 3000, LONG: 5000 };

// ── Inlined from src/reducer/actions.js ──────────────────────────────────────
/** @symbol setToast  @source src/reducer/actions.js */
const setToast = (toast, toastType, duration = TOAST_DURATION.NORMAL) => ({
  type: TOAST,
  toast,
  toastType,
  duration,
});

// ── Inlined from src/reducer/toastReducer.js ─────────────────────────────────
/** @symbol toastReducer  @source src/reducer/toastReducer.js */
const initialState = {
  showToast:  null,
  toastType:  'warning',
  toastQueue: [],
  duration:   TOAST_DURATION.NORMAL,
};

const toastReducer = (state = initialState, action) => {
  switch (action.type) {
    case TOAST:
      return {
        ...state,
        showToast:  action.toast,
        toastType:  action.toastType ?? state.toastType,
        toastQueue: action.queue    ?? state.toastQueue,
        duration:   action.duration ?? state.duration,
      };
    case 'CLEARTOAST':
      return { ...state, showToast: null };
    default:
      return state;
  }
};

// ─────────────────────────────────────────────────────────────────────────────
// describe('TOAST_DURATION') — 5 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('TOAST_DURATION', () => {
  it('SHORT equals 2000 ms for quick confirmations', () => {
    expect(TOAST_DURATION.SHORT).toBe(2000);
  });

  it('NORMAL equals 3000 ms for regular informational messages', () => {
    expect(TOAST_DURATION.NORMAL).toBe(3000);
  });

  it('LONG equals 5000 ms for error messages that need more reading time', () => {
    expect(TOAST_DURATION.LONG).toBe(5000);
  });

  it('durations are in ascending order SHORT < NORMAL < LONG', () => {
    expect(TOAST_DURATION.SHORT).toBeLessThan(TOAST_DURATION.NORMAL);
    expect(TOAST_DURATION.NORMAL).toBeLessThan(TOAST_DURATION.LONG);
  });

  it('has exactly 3 keys (SHORT, NORMAL, LONG)', () => {
    expect(Object.keys(TOAST_DURATION)).toHaveLength(3);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// describe('setToast') — 5 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('setToast', () => {
  it('returns an action with type TOAST', () => {
    const action = setToast({ message: 'Saved' });
    expect(action.type).toBe(TOAST);
  });

  it('stores the toast message object in action.toast', () => {
    const msg = { message: 'Card added' };
    const action = setToast(msg);
    expect(action.toast).toBe(msg);
  });

  it('defaults duration to TOAST_DURATION.NORMAL (3000) when not provided', () => {
    const action = setToast({ message: 'Info' });
    expect(action.duration).toBe(TOAST_DURATION.NORMAL);
  });

  it('stores the provided duration when explicitly passed', () => {
    const action = setToast({ message: 'Error!' }, 'error', TOAST_DURATION.LONG);
    expect(action.duration).toBe(TOAST_DURATION.LONG);
  });

  it('stores the provided toastType in action.toastType', () => {
    const action = setToast({ message: 'Warning' }, 'warning', TOAST_DURATION.SHORT);
    expect(action.toastType).toBe('warning');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// describe('toastReducer — duration') — 5 tests
// ─────────────────────────────────────────────────────────────────────────────
describe('toastReducer — duration', () => {
  it('initialises duration to TOAST_DURATION.NORMAL (3000)', () => {
    const state = toastReducer(undefined, { type: '@@INIT' });
    expect(state.duration).toBe(TOAST_DURATION.NORMAL);
  });

  it('TOAST action stores action.duration in state', () => {
    const state = toastReducer(undefined, {
      type:     TOAST,
      toast:    { message: 'hello' },
      duration: TOAST_DURATION.SHORT,
    });
    expect(state.duration).toBe(TOAST_DURATION.SHORT);
  });

  it('TOAST action with LONG duration stores 5000', () => {
    const state = toastReducer(undefined, {
      type:     TOAST,
      toast:    { message: 'error' },
      duration: TOAST_DURATION.LONG,
    });
    expect(state.duration).toBe(5000);
  });

  it('TOAST action falls back to previous duration when none provided', () => {
    const withCustomDuration = toastReducer(undefined, {
      type:     TOAST,
      toast:    { message: 'first' },
      duration: TOAST_DURATION.LONG,
    });
    const withoutDuration = toastReducer(withCustomDuration, {
      type:  TOAST,
      toast: { message: 'second' },
    });
    expect(withoutDuration.duration).toBe(TOAST_DURATION.LONG);
  });

  it('CLEARTOAST does not reset duration', () => {
    const withLong = toastReducer(undefined, {
      type:     TOAST,
      toast:    { message: 'hi' },
      duration: TOAST_DURATION.LONG,
    });
    const cleared = toastReducer(withLong, { type: 'CLEARTOAST' });
    expect(cleared.duration).toBe(TOAST_DURATION.LONG);
  });
});
