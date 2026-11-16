import { describe, expect, it, vi } from 'vitest';

vi.mock('twenty-sdk/front-component', () => ({ AppPath: {}, navigate: vi.fn(), useLocation: () => null }));

import { filtreCoz, filtreParametreleri, secimCoz, secimKodla } from 'src/lib/filtre';
import { DEFAULT_STAGES, type Secim } from 'src/lib/pano-veri';

describe('ortak filtre (adres)', () => {
  it('seçim kodla / çöz gidiş-dönüş', () => {
    const ornekler: Secim[] = [
      { tur: 'TUMU' },
      { tur: 'YIL', fy: 2026 },
      { tur: 'CEYREK', fy: 2026, q: 4 },
      { tur: 'AY', fy: 2026, q: 4, ay: 10 },
    ];
    for (const s of ornekler) expect(secimCoz(secimKodla(s))).toEqual(s);
    expect(secimCoz('2026-Q5')).toBeNull();
    expect(secimCoz('2026-A12')).toBeNull();
  });
  it('adres yoksa varsayılan', () => {
    expect(filtreCoz('')).toEqual({ secim: null, kisiler: null, asamalar: DEFAULT_STAGES, varsayilanMi: true });
  });
  it('yalnız ap_* değişir, diğer parametreler korunur', () => {
    const p = filtreParametreleri('?x=1&ap_kisi=a', { secim: { tur: 'CEYREK', fy: 2027, q: 1 }, kisiler: null, asamalar: ['WON'] });
    expect(p).toEqual({ x: '1', ap_donem: '2027-Q1', ap_asama: 'WON' });
    const f = filtreCoz('?' + new URLSearchParams(p).toString());
    expect(f.secim).toEqual({ tur: 'CEYREK', fy: 2027, q: 1 });
    expect(f.kisiler).toBeNull();
    expect(f.asamalar).toEqual(['WON']);
    expect(f.varsayilanMi).toBe(false);
  });
});
