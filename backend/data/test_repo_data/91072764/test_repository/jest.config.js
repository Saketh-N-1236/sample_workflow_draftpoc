module.exports = {
  preset: null,
  testEnvironment: 'node',
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
  testMatch: [
    '<rootDir>/standalone/**/*.test.js',
    '<rootDir>/cross-dependent/**/*.test.js',
    '<rootDir>/feature/**/*.test.js',
  ],
  setupFilesAfterEnv: ['<rootDir>/__setup__/jest.setup.js'],
  transform: {},
};
