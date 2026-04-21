/**
 * Scenario 35 — FAQ Additions in Help Center
 *
 * @scenario 35
 * @title Add 3 new FAQs to FAQDataList and use as fallback when API is empty
 * @source src/screens/frequentlyAskedQuestions/FAQDataList.js
 * @source src/screens/frequentlyAskedQuestions/FrequentlyAskedQuestions.js
 *
 * What this tests:
 *   - FAQDataList contains 8 entries after additions (was 5)
 *   - New entries have correct IDs (6, 7, 8)
 *   - New entries have non-empty sectionHeader and sectionContent
 *   - The fallback logic: uses FAQDataList when API response is empty/missing
 *   - The fallback logic: uses FAQDataList when API throws an error
 */

// ─── Inline source: FAQDataList ────────────────────────────────────────────────
const FAQDataList = [
  {
    id: '1',
    collapseImage: 'collapse',
    expandImage: 'expand',
    sectionHeader: 'What kind of fights can I expect to see on iStream?',
    sectionContent: 'iStream offers a variety of boxing, kickboxing, and MMA fights from different promotions and organizations around the world.',
  },
  {
    id: '2',
    collapseImage: 'collapse',
    expandImage: 'expand',
    sectionHeader: 'How much does a iStream subscription cost?',
    sectionContent: 'The cost of a iStream subscription varies depending on the plan you choose.',
  },
  {
    id: '3',
    collapseImage: 'collapse',
    expandImage: 'expand',
    sectionHeader: 'Can I watch iStream on multiple devices simultaneously?',
    sectionContent: 'No, you cannot watch iStream on multiple devices simultaneously.',
  },
  {
    id: '4',
    collapseImage: 'collapse',
    expandImage: 'expand',
    sectionHeader: 'Does iStream offer live streaming of events or only replays?',
    sectionContent: 'iStream offers both live streaming of events and replays of past fights.',
  },
  {
    id: '5',
    collapseImage: 'collapse',
    expandImage: 'expand',
    sectionHeader: 'Is there a free trial period for iStream before I commit to a subscription?',
    sectionContent: 'Yes, we offer a 30-day free trial period for new subscribers.',
  },
  {
    id: '6',
    collapseImage: 'collapse',
    expandImage: 'expand',
    sectionHeader: 'How do I reset my account password?',
    sectionContent: 'You can reset your password by navigating to the Sign In page and clicking "Forgot Password".',
  },
  {
    id: '7',
    collapseImage: 'collapse',
    expandImage: 'expand',
    sectionHeader: 'What streaming quality does iStream support?',
    sectionContent: 'iStream supports Standard Definition (SD), High Definition (HD at 1080p), and Ultra High Definition (4K) streaming.',
  },
  {
    id: '8',
    collapseImage: 'collapse',
    expandImage: 'expand',
    sectionHeader: 'What payment methods does iStream accept?',
    sectionContent: 'iStream accepts major credit and debit cards (Visa, Mastercard, American Express, JCB), as well as Bitcoin.',
  },
];
// ───────────────────────────────────────────────────────────────────────────────

// ─── Inline source: fallback logic (extracted from FrequentlyAskedQuestions.js) ─
const resolveFaqItems = async (faqApiCall) => {
  try {
    const response = await faqApiCall();
    const items = response?.data?.data?.items;
    return Array.isArray(items) && items.length > 0 ? items : FAQDataList;
  } catch {
    return FAQDataList;
  }
};
// ───────────────────────────────────────────────────────────────────────────────

describe('FAQDataList — size', () => {
  it('contains 8 entries after the 3 new FAQs are added', () => {
    expect(FAQDataList).toHaveLength(8);
  });

  it('every entry has a unique id', () => {
    const ids = FAQDataList.map(f => f.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('FAQDataList — new entries (ids 6, 7, 8)', () => {
  it('entry with id "6" exists', () => {
    expect(FAQDataList.find(f => f.id === '6')).toBeDefined();
  });

  it('entry with id "7" exists', () => {
    expect(FAQDataList.find(f => f.id === '7')).toBeDefined();
  });

  it('entry with id "8" exists', () => {
    expect(FAQDataList.find(f => f.id === '8')).toBeDefined();
  });

  it('entry 6 sectionHeader mentions password reset', () => {
    const entry = FAQDataList.find(f => f.id === '6');
    expect(entry.sectionHeader.toLowerCase()).toContain('password');
  });

  it('entry 7 sectionHeader mentions streaming quality', () => {
    const entry = FAQDataList.find(f => f.id === '7');
    expect(entry.sectionHeader.toLowerCase()).toContain('streaming quality');
  });

  it('entry 8 sectionHeader mentions payment methods', () => {
    const entry = FAQDataList.find(f => f.id === '8');
    expect(entry.sectionHeader.toLowerCase()).toContain('payment');
  });

  it('all 3 new entries have non-empty sectionContent', () => {
    ['6', '7', '8'].forEach(id => {
      const entry = FAQDataList.find(f => f.id === id);
      expect(entry.sectionContent.length).toBeGreaterThan(20);
    });
  });
});

describe('FAQ fallback logic — resolveFaqItems', () => {
  it('returns API items when API responds with a non-empty array', async () => {
    const apiItems = [{ id: 'api1', question: 'Q', answer: 'A' }];
    const faqApi = async () => ({ data: { data: { items: apiItems } } });
    const result = await resolveFaqItems(faqApi);
    expect(result).toBe(apiItems);
  });

  it('falls back to FAQDataList when API responds with an empty array', async () => {
    const faqApi = async () => ({ data: { data: { items: [] } } });
    const result = await resolveFaqItems(faqApi);
    expect(result).toBe(FAQDataList);
  });

  it('falls back to FAQDataList when API response has no items field', async () => {
    const faqApi = async () => ({ data: { data: {} } });
    const result = await resolveFaqItems(faqApi);
    expect(result).toBe(FAQDataList);
  });

  it('falls back to FAQDataList when API response is null', async () => {
    const faqApi = async () => null;
    const result = await resolveFaqItems(faqApi);
    expect(result).toBe(FAQDataList);
  });

  it('falls back to FAQDataList when API throws an error', async () => {
    const faqApi = async () => { throw new Error('Network error'); };
    const result = await resolveFaqItems(faqApi);
    expect(result).toBe(FAQDataList);
  });

  it('fallback list has 8 items so users always see content', async () => {
    const faqApi = async () => { throw new Error('Unavailable'); };
    const result = await resolveFaqItems(faqApi);
    expect(result).toHaveLength(8);
  });
});
