# Test Repository

This test repository contains test scripts organized by feature sets.

## Structure

### Authentication Feature Set (25 tests)
Located in: `authentication/`

This feature set contains tests for authentication and authorization functionality. The tests are organized with varying levels of connection to the core authentication feature:

**Strongly Connected Tests (Core Authentication):**
- LoginServiceTest - Core login operations
- TokenValidationTest - JWT/access token validation
- SessionManagementTest - User session management
- LogoutServiceTest - Logout functionality
- LoginControllerTest - REST API endpoints
- PasswordEncryptionTest - Password security
- IpLocationValidationTest - IP-based security
- MultiFactorAuthTest - MFA implementation
- AccountLockoutTest - Account security
- TwoFactorAuthTest - 2FA implementation
- PasswordPolicyTest - Password policy enforcement
- JwtTokenServiceTest - JWT token management
- LoginRequestValidationTest - Request validation
- LoginResponseTest - Response formatting

**Loosely Connected Tests (Extended Features):**
- PasswordResetTest - Password recovery flow
- EmailVerificationTest - Email verification for registration
- OAuthIntegrationTest - Third-party OAuth authentication
- RememberMeTest - Persistent login sessions
- RoleBasedAccessTest - RBAC authorization
- AuditLogTest - Security audit logging
- ApiKeyAuthTest - API key authentication
- DeviceFingerprintingTest - Device recognition
- BiometricAuthTest - Biometric authentication
- SocialLoginTest - Social media login integration
- UserRegistrationTest - User registration process

### Payment/Billing Feature Set (75 tests)
Located in: `payment/`

This feature set contains tests for payment processing and billing functionality. These tests are completely unrelated to the authentication feature set and focus on:

- Payment Processing (credit/debit cards, authorization, capture)
- Invoice Generation and Management
- Subscription Management and Billing
- Refund Processing
- Payment Gateway Integration
- Billing Cycles and Recurring Payments
- Tax Calculation
- Payment Security and Compliance
- Transaction History and Reporting
- Payment Methods Management
- Chargeback and Dispute Handling
- Coupon and Discount Management
- Payment Notifications
- Account Balance Management
- Payment Retry Logic
- Reconciliation and Settlement
- Multi-currency Support
- Payment Analytics and Metrics
- API Endpoints
- Performance, Load, and Scalability Testing
- Resilience and Concurrency Testing
- Data Migration and Archival
- And many more payment-related components

## Test File Structure

Each test file includes:
- Package declaration appropriate to the feature set
- JUnit 5 test annotations
- Component description comment explaining what component the test serves
- Test method placeholders with descriptive names

## Usage

These test files serve as a structured test repository for:
- Test organization and management
- Component documentation
- Test coverage analysis
- Feature set isolation
- Test repository balance demonstration
