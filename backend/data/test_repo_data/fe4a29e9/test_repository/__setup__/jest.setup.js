// Global localStorage mock — required because tests run in Node, not a browser
const localStorageMock = (() => {
  let store = {};
  return {
    getItem:    key         => store[key] !== undefined ? store[key] : null,
    setItem:    (key, val)  => { store[key] = String(val); },
    removeItem: key         => { delete store[key]; },
    clear:      ()          => { store = {}; },
  };
})();

Object.defineProperty(global, 'localStorage', { value: localStorageMock });

// Suppress noisy console output during test runs
beforeAll(() => {
  jest.spyOn(console, 'warn').mockImplementation(() => {});
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterAll(() => {
  console.warn.mockRestore();
  console.error.mockRestore();
});

// Clear localStorage between each test for isolation
beforeEach(() => {
  localStorage.clear();
});
