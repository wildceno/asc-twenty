import { describe, expect, it } from 'vitest';

import { firsatTarihi, maliYil, secimAraligi, secimEtiketi, trGun, yilEtiketi } from 'src/lib/pano-veri';

describe('mali dönem', () => {
  it('takvim yılı (Ocak başlangıç)', () => {
    expect(secimAraligi({ tur: 'YIL', fy: 2026 }, 1)).toEqual(['2026-01-01', '2026-12-31']);
    expect(secimAraligi({ tur: 'CEYREK', fy: 2026, q: 4 }, 1)).toEqual(['2026-10-01', '2026-12-31']);
    expect(secimAraligi({ tur: 'CEYREK', fy: 2028, q: 1 }, 1)).toEqual(['2028-01-01', '2028-03-31']);
    expect(secimAraligi({ tur: 'AY', fy: 2028, q: 1, ay: 1 }, 1)).toEqual(['2028-02-01', '2028-02-29']);
    expect(secimEtiketi({ tur: 'CEYREK', fy: 2026, q: 4 }, 1)).toEqual({ ad: 'Q4 2026', aralik: '1 Eki 2026 – 31 Ara 2026' });
    expect(secimEtiketi({ tur: 'AY', fy: 2026, q: 4, ay: 10 }, 1).ad).toBe('Kasım 2026');
    expect(secimAraligi({ tur: 'TUMU' }, 1)).toBeNull();
  });
  it('Nisan başlangıçlı mali yıl', () => {
    expect(secimAraligi({ tur: 'YIL', fy: 2026 }, 4)).toEqual(['2026-04-01', '2027-03-31']);
    expect(secimAraligi({ tur: 'CEYREK', fy: 2026, q: 4 }, 4)).toEqual(['2027-01-01', '2027-03-31']);
    expect(maliYil('2027-02-15', 4)).toBe(2026);
    expect(maliYil('2027-04-01', 4)).toBe(2027);
    expect(yilEtiketi(2026, 4)).toBe('2026/27');
  });
  it('Türkiye saatiyle gün ve fırsat tarihi', () => {
    expect(trGun('2026-12-31T22:30:00.000Z')).toBe('2027-01-01');
    expect(trGun('2026-11-11')).toBe('2026-11-11');
    expect(firsatTarihi({ id: '1', name: 'a', stage: 'WON', closeDate: '2026-12-08T12:00:00.000Z', realCloseDate: '2026-11-11' })).toBe('2026-11-11');
    expect(firsatTarihi({ id: '2', name: 'b', stage: 'PIPELINE', closeDate: '2026-09-30T21:30:00.000Z' })).toBe('2026-10-01');
  });
});
