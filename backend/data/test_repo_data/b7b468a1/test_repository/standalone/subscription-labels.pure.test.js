/**
 * Scenario 36 — Subscription Plan Labels
 *
 * @scenario 36
 * @title Add "Most Popular" / "Best Value" badge labels to Monthly / Yearly subscription plan cards
 * @source src/screens/SubscriptionPlans/SubscriptionPlans.js
 *
 * What this tests:
 *   - PLAN_LABELS constant has the correct Monthly and Yearly values
 *   - getPlanLabel() returns correct label for each billing period
 *   - getPlanLabel() returns null for unknown billing periods
 *   - Both plan types have non-null labels (badges will always render)
 */

// ─── Inline source: SubscriptionPlans.js ───────────────────────────────────────
const PLAN_LABELS = {
  Monthly: 'Most Popular',
  Yearly: 'Best Value',
};

const getPlanLabel = billingPeriod => PLAN_LABELS[billingPeriod] ?? null;
// ───────────────────────────────────────────────────────────────────────────────

describe('PLAN_LABELS', () => {
  it('Monthly label is "Most Popular"', () => {
    expect(PLAN_LABELS.Monthly).toBe('Most Popular');
  });

  it('Yearly label is "Best Value"', () => {
    expect(PLAN_LABELS.Yearly).toBe('Best Value');
  });

  it('contains exactly two keys', () => {
    expect(Object.keys(PLAN_LABELS)).toHaveLength(2);
  });

  it('Monthly and Yearly labels are distinct strings', () => {
    expect(PLAN_LABELS.Monthly).not.toBe(PLAN_LABELS.Yearly);
  });

  it('both label strings are non-empty', () => {
    Object.values(PLAN_LABELS).forEach(label => {
      expect(label.length).toBeGreaterThan(0);
    });
  });
});

describe('getPlanLabel', () => {
  it('returns "Most Popular" for "Monthly"', () => {
    expect(getPlanLabel('Monthly')).toBe('Most Popular');
  });

  it('returns "Best Value" for "Yearly"', () => {
    expect(getPlanLabel('Yearly')).toBe('Best Value');
  });

  it('returns null for an unknown billing period', () => {
    expect(getPlanLabel('Weekly')).toBeNull();
  });

  it('returns null for undefined', () => {
    expect(getPlanLabel(undefined)).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(getPlanLabel('')).toBeNull();
  });

  it('is case-sensitive — "monthly" (lowercase) returns null', () => {
    expect(getPlanLabel('monthly')).toBeNull();
  });

  it('is case-sensitive — "yearly" (lowercase) returns null', () => {
    expect(getPlanLabel('yearly')).toBeNull();
  });

  it('Monthly plan has a truthy label so the badge always renders', () => {
    expect(getPlanLabel('Monthly')).toBeTruthy();
  });

  it('Yearly plan has a truthy label so the badge always renders', () => {
    expect(getPlanLabel('Yearly')).toBeTruthy();
  });
});
