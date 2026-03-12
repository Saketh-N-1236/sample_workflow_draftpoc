/**
 * tests/__setup__/jest.setup.js
 *
 * Global Jest setup file for the iStream test repository.
 * Runs once before every test suite.
 *
 * What it does
 * ────────────
 *  1. Provides an in-memory localStorage mock so that tests that exercise
 *     appStorage (storage.ts) do not throw "localStorage is not defined"
 *     errors in the Node / Jest environment.
 *
 *  2. Silences expected console.error / console.warn noise that React
 *     and third-party libraries emit during testing.
 *
 *  3. Restores all mocks after each test to prevent cross-test pollution.
 */

// ─── 1. In-memory localStorage mock ─────────────────────────────────────────
class LocalStorageMock {
  constructor() {
    this.store = {};
  }
  clear()           { this.store = {}; }
  getItem(key)      { return Object.prototype.hasOwnProperty.call(this.store, key) ? this.store[key] : null; }
  setItem(key, val) { this.store[key] = String(val); }
  removeItem(key)   { delete this.store[key]; }
  get length()      { return Object.keys(this.store).length; }
  key(n)            { return Object.keys(this.store)[n] || null; }
}

Object.defineProperty(global, 'localStorage', {
  value:    new LocalStorageMock(),
  writable: true,
});

// ─── 2. Suppress expected noise ──────────────────────────────────────────────
const originalError = console.error.bind(console);
const originalWarn  = console.warn.bind(console);

beforeAll(() => {
  console.error = (...args) => {
    // Suppress React act() warnings in pure-logic tests
    if (typeof args[0] === 'string' && args[0].includes('act(')) return;
    originalError(...args);
  };
  console.warn = (...args) => {
    if (typeof args[0] === 'string' && args[0].includes('deprecated')) return;
    originalWarn(...args);
  };
});

afterAll(() => {
  console.error = originalError;
  console.warn  = originalWarn;
});

// ─── 3. Restore mocks after each test ────────────────────────────────────────
afterEach(() => {
  jest.restoreAllMocks();
  localStorage.clear();
});
