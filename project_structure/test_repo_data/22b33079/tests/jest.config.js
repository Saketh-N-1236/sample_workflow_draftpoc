/**
 * tests/jest.config.js
 *
 * Standalone Jest configuration for the iStream test repository.
 * Runs in a plain Node environment — no React-Native bridge required.
 *
 * Usage:
 *   npx jest --config tests/jest.config.js
 *   npx jest --config tests/jest.config.js --verbose --no-coverage
 */
module.exports = {
  displayName:     'istream-tests',
  testEnvironment: 'node',
  rootDir:         '..',               // project root (fe-app/)
  testMatch:       ['<rootDir>/tests/**/*.test.js'],

  // Run the global setup file after the test env is initialised
  setupFilesAfterEnv: ['<rootDir>/tests/__setup__/jest.setup.js'],

  // Our test files are plain CommonJS — no JSX / TS / React-Native syntax.
  // Disabling the default babel-jest transform means Jest never tries to load
  // metro-react-native-babel-preset (which lives in node_modules, not npx cache).
  transform: {},

  moduleFileExtensions: ['js', 'json'],
};
