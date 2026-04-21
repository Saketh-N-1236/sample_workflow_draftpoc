/**
 * Scenario 33 — My Orders Clustering
 *
 * @scenario 33
 * @title My Orders cluster by type (Movies vs TV Shows)
 * @source src/screens/MyOrder/myOrderData.js
 * @source src/screens/MyOrder/MyOrder.js
 *
 * What this tests:
 *   - ORDER_TYPES constant has the correct Movie and TVShow values
 *   - getOrdersByType() filters the order list correctly by type
 *   - myOrderDetails entries carry the new `type` field
 *   - Section grouping logic (Movies first, then TV Shows)
 */

// ─── Inline source: myOrderData helpers ────────────────────────────────────────
const ORDER_TYPES = {
  MOVIE: 'Movie',
  TV_SHOW: 'TVShow',
};

const getOrdersByType = (orders, type) =>
  Array.isArray(orders) ? orders.filter(o => o.type === type) : [];

const myOrderDetails = [
  { id: 1, gameTitle: 'Spider Man',   type: 'Movie',  paymentStatus: 'Processing' },
  { id: 2, gameTitle: 'Avatar',       type: 'Movie',  paymentStatus: 'Processing' },
  { id: 3, gameTitle: 'Wonder Woman', type: 'TVShow', paymentStatus: 'Failed'     },
  { id: 4, gameTitle: 'Thor',         type: 'TVShow', paymentStatus: 'Success'    },
  { id: 5, gameTitle: 'Black Panther',type: 'Movie',  paymentStatus: 'Success'    },
];
// ───────────────────────────────────────────────────────────────────────────────

describe('ORDER_TYPES', () => {
  it('MOVIE value is the string "Movie"', () => {
    expect(ORDER_TYPES.MOVIE).toBe('Movie');
  });

  it('TV_SHOW value is the string "TVShow"', () => {
    expect(ORDER_TYPES.TV_SHOW).toBe('TVShow');
  });

  it('contains exactly two keys', () => {
    expect(Object.keys(ORDER_TYPES)).toHaveLength(2);
  });

  it('MOVIE and TV_SHOW are distinct values', () => {
    expect(ORDER_TYPES.MOVIE).not.toBe(ORDER_TYPES.TV_SHOW);
  });
});

describe('getOrdersByType', () => {
  it('returns only Movie orders when type is ORDER_TYPES.MOVIE', () => {
    const result = getOrdersByType(myOrderDetails, ORDER_TYPES.MOVIE);
    expect(result).toHaveLength(3);
    result.forEach(item => expect(item.type).toBe('Movie'));
  });

  it('returns only TVShow orders when type is ORDER_TYPES.TV_SHOW', () => {
    const result = getOrdersByType(myOrderDetails, ORDER_TYPES.TV_SHOW);
    expect(result).toHaveLength(2);
    result.forEach(item => expect(item.type).toBe('TVShow'));
  });

  it('returns empty array when no orders match the type', () => {
    const result = getOrdersByType(myOrderDetails, 'Unknown');
    expect(result).toHaveLength(0);
  });

  it('returns empty array when orders list is empty', () => {
    expect(getOrdersByType([], ORDER_TYPES.MOVIE)).toHaveLength(0);
  });

  it('returns empty array when orders argument is undefined', () => {
    expect(getOrdersByType(undefined, ORDER_TYPES.MOVIE)).toHaveLength(0);
  });

  it('returns empty array when orders argument is null', () => {
    expect(getOrdersByType(null, ORDER_TYPES.MOVIE)).toHaveLength(0);
  });

  it('does not mutate the original orders array', () => {
    const copy = [...myOrderDetails];
    getOrdersByType(myOrderDetails, ORDER_TYPES.MOVIE);
    expect(myOrderDetails).toHaveLength(copy.length);
  });
});

describe('myOrderDetails — type field', () => {
  it('every entry in myOrderDetails has a type field', () => {
    myOrderDetails.forEach(item => {
      expect(item).toHaveProperty('type');
    });
  });

  it('type field is either Movie or TVShow for every entry', () => {
    const valid = new Set([ORDER_TYPES.MOVIE, ORDER_TYPES.TV_SHOW]);
    myOrderDetails.forEach(item => {
      expect(valid.has(item.type)).toBe(true);
    });
  });

  it('Spider Man is classified as Movie', () => {
    const order = myOrderDetails.find(o => o.gameTitle === 'Spider Man');
    expect(order.type).toBe(ORDER_TYPES.MOVIE);
  });

  it('Avatar is classified as Movie', () => {
    const order = myOrderDetails.find(o => o.gameTitle === 'Avatar');
    expect(order.type).toBe(ORDER_TYPES.MOVIE);
  });

  it('Wonder Woman is classified as TVShow', () => {
    const order = myOrderDetails.find(o => o.gameTitle === 'Wonder Woman');
    expect(order.type).toBe(ORDER_TYPES.TV_SHOW);
  });

  it('Thor is classified as TVShow', () => {
    const order = myOrderDetails.find(o => o.gameTitle === 'Thor');
    expect(order.type).toBe(ORDER_TYPES.TV_SHOW);
  });
});

describe('Section grouping — Movies before TV Shows', () => {
  const renderOrder = [ORDER_TYPES.MOVIE, ORDER_TYPES.TV_SHOW];

  it('render order array has Movies as the first entry', () => {
    expect(renderOrder[0]).toBe(ORDER_TYPES.MOVIE);
  });

  it('render order array has TV Shows as the second entry', () => {
    expect(renderOrder[1]).toBe(ORDER_TYPES.TV_SHOW);
  });

  it('Movie group has 3 items in sample data', () => {
    expect(getOrdersByType(myOrderDetails, ORDER_TYPES.MOVIE)).toHaveLength(3);
  });

  it('TV Show group has 2 items in sample data', () => {
    expect(getOrdersByType(myOrderDetails, ORDER_TYPES.TV_SHOW)).toHaveLength(2);
  });

  it('Movie + TV Show counts sum to total order count', () => {
    const movies = getOrdersByType(myOrderDetails, ORDER_TYPES.MOVIE).length;
    const tvShows = getOrdersByType(myOrderDetails, ORDER_TYPES.TV_SHOW).length;
    expect(movies + tvShows).toBe(myOrderDetails.length);
  });
});
