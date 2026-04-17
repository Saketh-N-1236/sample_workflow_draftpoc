# 📦 iStream — Test Repository

> **Purpose:** A standalone, self-contained test suite designed to be paired with a git-diff–based test selection system. No application source imports are needed — all logic is inlined inside each test file.

---

## 📁 Folder Structure

```
test_repository/
├── jest.config.js                        ← Isolated Jest config (Node env, no React Native)
├── test-manifest.json                    ← Machine-readable map: test → source file + symbol
├── README.md                             ← This file
│
├── __setup__/
│   └── jest.setup.js                     ← Global mocks (localStorage, console)
│
├── standalone/                           ── 26 tests — pure, no cross-file deps
│   ├── regex.constants.test.js           ← 16 tests for all regex constants
│   └── utilities.pure.test.js            ← 10 tests for pure utility functions
│
├── cross-dependent/                      ── 26 tests — span 2+ source files
│   ├── auth-storage.cross.test.js        ← 14 tests: auth hooks ↔ constants ↔ storage
│   └── payment-state.cross.test.js       ← 12 tests: payment reducer ↔ actions ↔ storage
│
├── feature/                              ── 25 tests — full feature reducer flows
│   ├── user-profile.feature.test.js      ← 10 tests: userDetailsReducer + profileReducer
│   ├── favourites-watchlist.feature.test.js ← 8 tests: favouritesReducer + toastReducer
│   └── api-navigation.feature.test.js    ← 7 tests: API endpoints + API constants
│
└── scenarios/                            ── Simulated git diffs + expected selection outputs
    ├── scenario_A_email_regex_change.diff
    ├── scenario_A_expected_output.json
    ├── scenario_B_payment_reducer_new_action.diff
    ├── scenario_B_expected_output.json
    ├── scenario_C_user_details_reducer_change.diff
    └── scenario_C_expected_output.json
```

---

## 🧪 Test Categories

### 1. `standalone/` — 26 Tests
> **Definition:** Tests that cover a single symbol in a single source file. Zero cross-file dependencies. Ideal for catching pure logic regressions.

| File | Describe Block | What Is Tested | Source |
|---|---|---|---|
| `regex.constants.test.js` | `EMAIL_REGEX` | Accepts valid .com, rejects missing @, rejects .org | `src/types/constants.ts` |
| `regex.constants.test.js` | `PASSWORD_REGEX_CHANGE_PASSWORD` | Strong password, no uppercase, no special char, too long | `src/types/constants.ts` |
| `regex.constants.test.js` | `CARD_REGEX` | Digits+spaces pass, letters fail | `src/types/constants.ts` |
| `regex.constants.test.js` | `PHONE_REGEX` | 10-digit, +prefix, too short | `src/types/constants.ts` |
| `regex.constants.test.js` | `UNIQUE_USERNAME_REGEX` | Alphanumeric pass, digits-only fail | `src/types/constants.ts` |
| `regex.constants.test.js` | `CARD_NUMBER_REGEX` | 19-char spaced pass, <17 char fail | `src/types/constants.ts` |
| `utilities.pure.test.js` | `checkNull` | null → `''`, defined → value | `src/helpers/utilities.js` |
| `utilities.pure.test.js` | `checkArray` | null → `[]`, array → array | `src/helpers/utilities.js` |
| `utilities.pure.test.js` | `checkWhiteSpace` | space → true, no-space → false | `src/helpers/utilities.js` |
| `utilities.pure.test.js` | `getTimes` | 3661s → 1:01:01, <3600s → 0h | `src/helpers/utilities.js` |
| `utilities.pure.test.js` | `getProgressWidth` | 50/100 → 50%, 0 value → 0 | `src/helpers/utilities.js` |

---

### 2. `cross-dependent/` — 26 Tests
> **Definition:** Tests that verify behaviour which **crosses file boundaries** — e.g. an action creator from `actions.js` feeding into `paymentReducer.js`, or a utility function reading from `storage.ts`. Each test's `@source` tags list 2+ files.

| File | Describe Block | Files Crossed | Symbols Crossed |
|---|---|---|---|
| `auth-storage.cross.test.js` | `validateEmailOrUsername uses EMAIL_REGEX` | `signInFormHook.ts` + `constants.ts` | `validateEmailOrUsername`, `EMAIL_REGEX` |
| `auth-storage.cross.test.js` | `isUserLoggedIn reads storageKeys.token` | `utilities.js` + `storage.ts` | `isUserLoggedIn`, `storageKeys` |
| `auth-storage.cross.test.js` | `updateNewTokenDetails stores values under storageKeys` | `utilities.js` + `storage.ts` | `updateNewTokenDetails`, `storageKeys` |
| `auth-storage.cross.test.js` | `generateCardNumber output satisfies CARD_REGEX` | `utilities.js` + `constants.ts` | `generateCardNumber`, `CARD_REGEX` |
| `auth-storage.cross.test.js` | `capitalizeFirstLetter with checkWhiteSpace` | `utilities.js` (intra-file cross) | `capitalizeFirstLetter`, `checkWhiteSpace` |
| `payment-state.cross.test.js` | `updateUserCards action dispatched into paymentReducer` | `actions.js` + `paymentReducer.js` | `updateUserCards`, `paymentReducer` |
| `payment-state.cross.test.js` | `updatePaymentPlanDetails action and paymentReducer` | `actions.js` + `paymentReducer.js` | `updatePaymentPlanDetails`, `paymentReducer` |
| `payment-state.cross.test.js` | `paymentActions.CLEARCARDS resets payment state` | `paymentReducer.js` | `paymentActions`, `paymentReducer` |
| `payment-state.cross.test.js` | `storageKeys align with payment flow expectations` | `storage.ts` + `constants.ts` | `storageKeys` |
| `payment-state.cross.test.js` | `CARD_NUMBER_REGEX validates checkout flow input` | `constants.ts` + `paymentReducer.js` | `CARD_NUMBER_REGEX`, `paymentActions` |

---

### 3. `feature/` — 25 Tests
> **Definition:** Tests that exercise a complete feature as a black box. Each test covers the full lifecycle of a reducer or endpoint group — initial state, actions, edge cases, and unknown-action fallback.

| File | Describe Block | What Is Tested | Source |
|---|---|---|---|
| `user-profile.feature.test.js` | `userDetailsReducer` | Init, SUCCESS, UPDATEREFRESHEDTOKEN, ONAUTHENTICATE, SHOWLOGGEDOUTSHEET, unknown action | `src/reducer/userDetailsReducer.js` |
| `user-profile.feature.test.js` | `profileReducer` | Init, PROFILESDETAILS, SAVESELECTEDPROFILEDETAILS, unknown action | `src/reducer/profileReducer.js` |
| `favourites-watchlist.feature.test.js` | `favouritesReducer` | Init, UPDATEALLFAVOURITIESDETAILS, favouritesFetched flag, unknown action | `src/reducer/favouritesReducer.js` |
| `favourites-watchlist.feature.test.js` | `toastReducer` | Init null, TOAST stores message, reset to null, unknown action | `src/reducer/toastReducer.js` |
| `api-navigation.feature.test.js` | `endpoints.payment` | addCard, getAllCards, paymentsCheckout paths | `src/services/api/common/ApiEndPoints.js` |
| `api-navigation.feature.test.js` | `endpoints.favourites` | addCardtoFavourite, advertisement URL builder | `src/services/api/common/ApiEndPoints.js` |
| `api-navigation.feature.test.js` | `ApiConstants` | MAX_IMAGE_UPLOAD_SIZE = 10MB, TIMEOUT = 30s | `src/services/api/common/ApiConstants.js` |

---

## 🏃 Running the Tests

### Run all 77 tests
```bash
npx jest --config test_repository/jest.config.js --no-coverage
```

### Run a single category
```bash
# Standalone only
npx jest --config test_repository/jest.config.js --no-coverage test_repository/standalone/

# Cross-dependent only
npx jest --config test_repository/jest.config.js --no-coverage test_repository/cross-dependent/

# Feature only
npx jest --config test_repository/jest.config.js --no-coverage test_repository/feature/
```

### Run tests matching a specific symbol
```bash
# Run all tests that mention EMAIL_REGEX
npx jest --config test_repository/jest.config.js --no-coverage -t "EMAIL_REGEX"

# Run all payment reducer tests
npx jest --config test_repository/jest.config.js --no-coverage -t "paymentReducer"
```

### Run tests for a specific file
```bash
npx jest --config test_repository/jest.config.js --no-coverage test_repository/standalone/regex.constants.test.js
```

---

## 🗺️ Naming Convention

All tests use **functionality names** — not numeric IDs. The pattern is:

```
describe('symbolName')           ← exact symbol name from source code
  it('human-readable behaviour') ← what the symbol should do
```

**Example:**
```js
describe('EMAIL_REGEX', () => {
  it('accepts a valid .com email address', () => { ... });
  it('rejects an email address missing the @ symbol', () => { ... });
});
```

This means your test selection system can match a changed symbol directly to a `describe()` block label.

---

## 🤖 How the Test Selection System Uses This Repo

When a git diff arrives, the system follows this priority logic:

```
git diff changed symbol  →  lookup in test-manifest.json
                         ↓
        symbols[] match?  →  🔴 CRITICAL  (run first)
        sources[] match?  →  🟡 HIGH      (run second)
        no overlap?       →  ⏭  SKIP
        no test found?    →  🚨 GAP       (new test needed)
```

### `test-manifest.json` structure
```json
{
  "suite_key": {
    "file": "test_repository/path/to/test.js",
    "category": "standalone | cross-dependent | feature",
    "tests": [
      {
        "describe": "symbolName",
        "it": "human-readable behaviour",
        "sources": ["src/file/that/symbol/lives/in.ts"],
        "symbols": ["symbolName"]
      }
    ]
  },
  ...
}
```

---

## 📋 Scenario Validation

Three scenarios are provided in `scenarios/` to validate your test selection system:

| Scenario | Changed File | Changed Symbol | Expected CRITICAL | Coverage Gap? |
|---|---|---|---|---|
| **A** | `src/types/constants.ts` | `EMAIL_REGEX` | All `EMAIL_REGEX` describe blocks | ⚠️ `.org` test will fail (regex broadened) |
| **B** | `src/reducer/paymentReducer.js` | `paymentActions`, `RESETPAYMENT` | All `paymentReducer` + `paymentActions` describes | ✅ Gap: `RESETPAYMENT` has no test yet |
| **C** | `src/reducer/userDetailsReducer.js` | `userDetailsReducer`, `ONAUTHENTICATE` | All `userDetailsReducer` describes | ✅ Gap: `ONAUTHENTICATE` clears `profileToken` — no test yet |

Each scenario folder contains:
- `scenario_X_<name>.diff` — simulated git diff to feed into your system
- `scenario_X_expected_output.json` — expected CRITICAL / HIGH / SKIP / GAP output

---

## 🔢 Test Count Summary

| Category | Files | Tests |
|---|---|---|
| **standalone** | 2 | 26 |
| **cross-dependent** | 2 | 26 |
| **feature** | 3 | 25 |
| **Total** | **7** | **77** |

---

## 📌 Source Files Covered

| Source File | Symbols Under Test |
|---|---|
| `src/types/constants.ts` | `EMAIL_REGEX`, `PASSWORD_REGEX_CHANGE_PASSWORD`, `CARD_REGEX`, `PHONE_REGEX`, `UNIQUE_USERNAME_REGEX`, `CARD_NUMBER_REGEX` |
| `src/helpers/utilities.js` | `checkNull`, `checkArray`, `checkWhiteSpace`, `getTimes`, `getProgressWidth`, `isUserLoggedIn`, `generateCardNumber`, `capitalizeFirstLetter`, `updateNewTokenDetails` |
| `src/features/auth/hooks/signInFormHook.ts` | `validateEmailOrUsername` |
| `src/services/storage.ts` | `storageKeys`, `appStorage` |
| `src/reducer/paymentReducer.js` | `paymentActions`, `paymentReducer`, `paymentInitialState` |
| `src/reducer/actions.js` | `updateUserCards`, `updatePaymentPlanDetails` |
| `src/reducer/userDetailsReducer.js` | `userDetailsReducer` |
| `src/reducer/profileReducer.js` | `profileReducer` |
| `src/reducer/favouritesReducer.js` | `favouritesReducer`, `favouritesActions` |
| `src/reducer/toastReducer.js` | `toastReducer` |
| `src/reducer/actiotypes.js` | `SUCCESS`, `UPDATEREFRESHEDTOKEN`, `ONAUTHENTICATE`, `SHOWLOGGEDOUTSHEET`, `TOAST`, `PROFILESDETAILS`, `SAVESELECTEDPROFILEDETAILS` |
| `src/services/api/common/ApiEndPoints.js` | `endpoints` (payment, favourites, advertisement) |
| `src/services/api/common/ApiConstants.js` | `MAX_IMAGE_UPLOAD_SIZE`, `TIMEOUT` |
