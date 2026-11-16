import { AppPath, navigate, useLocation } from 'twenty-sdk/front-component';

import { DEFAULT_STAGES, type Secim } from 'src/lib/pano-veri';

// Ortak filtre: sayfanın adresinde (sorgu parametreleri) tutulur. Pano Filtresi widget'ı yazar, diğer
// widget'lar okur. Her widget ayrı sandbox'ta çalıştığı için ortak durumun tek yeri adres çubuğu;
// sayfa yenilenince korunur, bağlantıyla paylaşılabilir. Filtre widget'ı yoksa varsayılanlar geçerli.
// Parametreler: ap_donem (tumu | 2026 | 2026-Q4 | 2026-A10), ap_kisi (id,id), ap_asama (PIPELINE,UPSIDE)

export type Filtre = {
  secim: Secim | null; // null: varsayılan (içinde bulunulan çeyrek)
  kisiler: string[] | null; // null: herkes
  asamalar: string[]; // seçili aşamalar
  varsayilanMi: boolean; // adreste hiç filtre yok
};

export function secimKodla(s: Secim): string {
  if (s.tur === 'TUMU') return 'tumu';
  if (s.tur === 'YIL') return `${s.fy}`;
  if (s.tur === 'CEYREK') return `${s.fy}-Q${s.q}`;
  return `${s.fy}-A${s.ay}`;
}

export function secimCoz(k: string | null): Secim | null {
  if (!k) return null;
  if (k === 'tumu') return { tur: 'TUMU' };
  let m = /^(\d{4})$/.exec(k);
  if (m) return { tur: 'YIL', fy: Number(m[1]) };
  m = /^(\d{4})-Q([1-4])$/.exec(k);
  if (m) return { tur: 'CEYREK', fy: Number(m[1]), q: Number(m[2]) };
  m = /^(\d{4})-A(\d{1,2})$/.exec(k);
  if (m && Number(m[2]) < 12) {
    const ay = Number(m[2]);
    return { tur: 'AY', fy: Number(m[1]), q: Math.floor(ay / 3) + 1, ay };
  }
  return null;
}

export function filtreCoz(search: string): Filtre {
  const p = new URLSearchParams(search);
  const kisi = p.get('ap_kisi');
  const asama = p.get('ap_asama');
  return {
    secim: secimCoz(p.get('ap_donem')),
    kisiler: kisi === null ? null : kisi.split(',').filter(Boolean),
    asamalar: asama === null ? DEFAULT_STAGES : asama.split(',').filter(Boolean),
    varsayilanMi: !p.has('ap_donem') && kisi === null && asama === null,
  };
}

// Adresteki diğer parametreler korunur; yalnız ap_* değişir.
export function filtreParametreleri(search: string, f: Partial<Omit<Filtre, 'varsayilanMi'>>): Record<string, string> {
  const p = new URLSearchParams(search);
  if (f.secim !== undefined) f.secim ? p.set('ap_donem', secimKodla(f.secim)) : p.delete('ap_donem');
  if (f.kisiler !== undefined) f.kisiler === null ? p.delete('ap_kisi') : p.set('ap_kisi', f.kisiler.join(','));
  if (f.asamalar !== undefined) p.set('ap_asama', f.asamalar.join(','));
  return Object.fromEntries(p.entries());
}

// Bulunulan sayfaya (Dashboard kaydı ya da bağımsız sayfa) aynı yolla, yeni sorgu parametreleriyle gidilir.
async function adreseYaz(pathname: string, sorgu: Record<string, string>) {
  const kayit = /^\/object\/([^/]+)\/([^/?#]+)/.exec(pathname);
  if (kayit) {
    await navigate(AppPath.RecordShowPage, { objectNameSingular: kayit[1], objectRecordId: kayit[2] }, sorgu, { replace: true });
    return true;
  }
  const sayfa = /^\/page\/([^/?#]+)/.exec(pathname);
  if (sayfa) {
    await navigate(AppPath.PageLayoutPage, { pageLayoutId: sayfa[1] }, sorgu, { replace: true });
    return true;
  }
  return false;
}

export function useOrtakFiltre() {
  const loc = useLocation();
  const search = loc?.search ?? '';
  const filtre = filtreCoz(search);
  const degistir = (f: Partial<Omit<Filtre, 'varsayilanMi'>>) =>
    adreseYaz(loc?.pathname ?? '', filtreParametreleri(search, f));
  const sifirla = () =>
    adreseYaz(
      loc?.pathname ?? '',
      Object.fromEntries([...new URLSearchParams(search).entries()].filter(([k]) => !k.startsWith('ap_'))),
    );
  return { filtre, degistir, sifirla };
}
