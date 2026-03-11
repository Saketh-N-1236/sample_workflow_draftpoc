# Test Repository

Comprehensive test suite for the Engineering Tutor AI Chatbot project.

## 📁 Structure

```
tests/
├── jest.config.js              # Jest configuration
├── setupTests.js               # Global test setup
├── README.md                   # This file
├── utils/                      # Test utilities
│   ├── testHelpers.js         # Common helper functions
│   └── testDatabase.js        # Database utilities
├── fixtures/                   # Test data fixtures
│   └── testData.js            # Sample test data
├── unit/                       # Unit tests
│   └── services/              # Service unit tests
│       ├── chatService.test.js
│       └── geminiService.test.js
├── integration/                # Integration tests
│   └── routes/                # Route integration tests
│       ├── auth.test.js
│       ├── chat.test.js
│       └── files.test.js
└── e2e/                        # End-to-end tests
    └── chatFlow.test.js
```

## 🚀 Getting Started

### Prerequisites

- Node.js (v18+)
- MongoDB (for integration and E2E tests)
- All project dependencies installed

### Installation

1. Install test dependencies (if not already installed):
```bash
cd server
npm install
```

2. Set up test environment variables:
Create a `.env` file in the `server` directory with:
```env
NODE_ENV=test
MONGO_URI=mongodb://localhost:27017/chatbot_test_db
JWT_SECRET=test-secret-key-for-jwt
GEMINI_API_KEY=your-test-api-key (optional for unit tests)
```

## 🧪 Running Tests

### Run All Tests
```bash
cd tests
npm test
```

Or from the server directory:
```bash
cd server
npm test
```

### Run Specific Test Suites

**Unit Tests Only:**
```bash
npm test -- unit
```

**Integration Tests Only:**
```bash
npm test -- integration
```

**E2E Tests Only:**
```bash
npm test -- e2e
```

**Specific Test File:**
```bash
npm test -- auth.test.js
```

### Run Tests in Watch Mode
```bash
npm test -- --watch
```

### Run Tests with Coverage
```bash
npm test -- --coverage
```

## 📝 Writing Tests

### Unit Tests

Unit tests are located in `tests/unit/` and test individual functions and services in isolation.

Example:
```javascript
describe('Service Name', () => {
  test('should do something', () => {
    // Test implementation
  });
});
```

### Integration Tests

Integration tests are located in `tests/integration/` and test API routes with mocked dependencies.

Example:
```javascript
describe('Route Name', () => {
  test('should handle request', async () => {
    const response = await request(app)
      .get('/api/endpoint')
      .expect(200);
  });
});
```

### E2E Tests

E2E tests are located in `tests/e2e/` and test complete user flows with a real database.

Example:
```javascript
describe('User Flow', () => {
  test('should complete full flow', async () => {
    // Complete flow test
  });
});
```

## 🛠️ Test Utilities

### testHelpers.js

Common helper functions:
- `generateTestToken(userId, username)` - Generate JWT token for testing
- `createMockUser(overrides)` - Create mock user object
- `createMockSession(overrides)` - Create mock session object
- `createMockRequest(overrides)` - Create mock Express request
- `createMockResponse()` - Create mock Express response

### testDatabase.js

Database utilities:
- `connectTestDB()` - Connect to test database
- `disconnectTestDB()` - Disconnect from test database
- `clearTestDatabase()` - Clear all collections
- `dropTestDatabase()` - Drop test database

### testData.js

Test fixtures with sample data for:
- Users
- Sessions
- Messages
- Queries
- Files
- API Keys

## 📊 Test Coverage

Generate coverage reports:
```bash
npm test -- --coverage
```

Coverage reports will be generated in `tests/coverage/`.

## 🔧 Configuration

### Jest Configuration

The Jest configuration is in `jest.config.js`. Key settings:
- Test environment: Node.js
- Test timeout: 30 seconds
- Coverage collection from `server/` directory
- Setup file: `setupTests.js`

### Environment Variables

Test-specific environment variables:
- `NODE_ENV=test` - Sets test environment
- `MONGO_URI` - Test database connection string
- `JWT_SECRET` - Secret for JWT token generation

## 🐛 Debugging Tests

### Run Tests in Debug Mode
```bash
node --inspect-brk node_modules/.bin/jest --runInBand
```

### View Test Output
Add `console.log()` statements or use Jest's built-in debugging:
```javascript
test('debug test', () => {
  console.log('Debug information');
  // Test code
});
```

## 📋 Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Cleanup**: Always clean up test data after tests
3. **Mocking**: Mock external services and APIs in unit tests
4. **Fixtures**: Use test fixtures for consistent test data
5. **Descriptive Names**: Use clear, descriptive test names
6. **Arrange-Act-Assert**: Follow AAA pattern in tests

## 🚨 Common Issues

### MongoDB Connection Issues
- Ensure MongoDB is running
- Check `MONGO_URI` in `.env` file
- Verify database permissions

### Authentication Errors
- Ensure `JWT_SECRET` is set in `.env`
- Check token generation in test helpers

### Timeout Errors
- Increase timeout in `jest.config.js` if needed
- Check for hanging promises or unclosed connections

## 📚 Additional Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [Supertest Documentation](https://github.com/visionmedia/supertest)
- [Testing Best Practices](https://github.com/goldbergyoni/javascript-testing-best-practices)

## 🤝 Contributing

When adding new features:
1. Write tests first (TDD approach)
2. Ensure all tests pass
3. Maintain or improve test coverage
4. Update this README if adding new test utilities

## 📄 License

Same as the main project.
