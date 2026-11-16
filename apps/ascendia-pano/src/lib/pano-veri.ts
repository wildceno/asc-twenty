import { RestApiClient } from 'twenty-client-sdk/rest';

// Panoların ortak veri katmanı: aşamalar, metrik alanları, para okuma, sayfalı REST okuma.
// Veri, sayfaya bakan kişinin yetkisiyle okunur (RestApiClient oturumdaki kullanıcıyı kullanır).

export const STAGES: { value: string; label: string; color: string }[] = [
  { value: 'LEAD_GEN', label: 'Lead-Gen', color: '#9DB7F5' },
  { value: 'LEAD_IN_TOUCH', label: 'Lead-inTouch', color: '#7FD3C6' },
  { value: 'PIPELINE', label: 'Pipeline', color: '#6CB4EE' },
  { value: 'UPSIDE', label: 'Upside', color: '#B48EF0' },
  { value: 'COMMIT', label: 'Commit', color: '#F2A65A' },
  { value: 'AUDIT', label: 'Audit', color: '#F2CF5A' },
  { value: 'DELIVERY', label: 'Delivery', color: '#E9B949' },
  { value: 'INVOICE', label: 'Invoice', color: '#D9A33C' },
  { value: 'WON', label: 'Won', color: '#5CB85C' },
  { value: 'LOST', label: 'Lost', color: '#E06C6C' },
  { value: 'DISQUALIFIED', label: 'DSQ', color: '#B0B0B0' },
];
// Fırsat Kaynağı seçenekleri (metadata/01_temel_alanlar.py LEAD_SOURCES ile aynı)
export const KAYNAKLAR: { value: string; label: string; color: string }[] = [
  { value: 'CHANNEL', label: 'Kanal', color: '#6CB4EE' },
  { value: 'OUTBOUND', label: 'Outbound', color: '#F2A65A' },
  { value: 'INBOUND', label: 'Inbound', color: '#5CB85C' },
  { value: 'REFERRAL', label: 'Referans', color: '#B48EF0' },
  { value: 'EXISTING_CUSTOMER', label: 'Mevcut müşteri', color: '#7FD3C6' },
  { value: 'EVENT', label: 'Etkinlik', color: '#F2CF5A' },
];
export const KAZANILAN = new Set(['AUDIT', 'DELIVERY', 'INVOICE', 'WON']);
export const KAYBEDILEN = new Set(['LOST', 'DISQUALIFIED']);
export const LEAD_ASAMALARI = new Set(['LEAD_GEN', 'LEAD_IN_TOUCH']);

export const STAGE = Object.fromEntries(STAGES.map((s) => [s.value, s]));
export const CLOSED = new Set(['AUDIT', 'DELIVERY', 'INVOICE', 'WON', 'LOST', 'DISQUALIFIED']);
export const ACHIEVED = new Set(['AUDIT', 'DELIVERY', 'INVOICE', 'WON']);
export const DEFAULT_STAGES = STAGES.map((s) => s.value).filter((s) => s !== 'LOST' && s !== 'DISQUALIFIED');

export const METRIC_FIELD: Record<string, string> = {
  REVENUE: 'amountReporting',
  GROSS_PROFIT: 'grossProfitReporting',
  ARR: 'arrReporting',
  MRR: 'mrrReporting',
};
export const METRIC_LABEL: Record<string, string> = {
  REVENUE: 'Revenue',
  GROSS_PROFIT: 'Gross Profit',
  ARR: 'ARR',
  MRR: 'MRR',
};

export type Money = { amountMicros?: number | string | null; currencyCode?: string | null } | null;
export type Deal = {
  id: string;
  name: string;
  stage: string;
  closeDate?: string | null;
  realCloseDate?: string | null;
  reportingPeriodName?: string | null;
  inCurrentPeriod?: boolean | null;
  ownerId?: string | null;
  owner?: { name?: { firstName?: string; lastName?: string } } | null;
  company?: { name?: string } | null;
  leadSource?: string | null;
  channelPartnerId?: string | null;
  channelPartner?: { name?: string } | null;
  [key: string]: unknown;
};
export type TargetLine = {
  metric?: string;
  targetAmount?: Money;
  target?: {
    memberId?: string;
    targetRole?: string;
    period?: { name?: string; periodType?: string; startDate?: string; endDate?: string } | null;
  } | null;
};

export const money = (m: unknown): number => {
  const v = (m as Money)?.amountMicros;
  return v === null || v === undefined || v === '' ? 0 : Number(v) / 1e6;
};
export const fullName = (d: Deal) =>
  `${d.owner?.name?.firstName ?? ''} ${d.owner?.name?.lastName ?? ''}`.trim() || '—';
export const symbol = (cur: string) =>
  cur === 'USD' ? '$' : cur === 'EUR' ? '€' : cur === 'GBP' ? '£' : cur === 'TRY' ? '₺' : `${cur} `;
export const fmt = (n: number, cur: string) => `${symbol(cur)}${Math.round(n).toLocaleString('tr-TR')}`;
export const fmtShort = (n: number, cur: string) => {
  const a = Math.abs(n);
  const s = a >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : a >= 1e3 ? `${Math.round(n / 1e3)}K` : `${Math.round(n)}`;
  return `${symbol(cur)}${s}`;
};
export const pct = (a: number, b: number) => (b > 0 ? `%${Math.round((a / b) * 100)}` : '—');

export async function fetchAll<T>(client: RestApiClient, plural: string, query: Record<string, string | number>) {
  const out: T[] = [];
  let after: string | undefined;
  for (let i = 0; i < 50; i++) {
    const res = (await client.get(`/rest/${plural}`, {
      query: { limit: 60, ...query, ...(after ? { starting_after: after } : {}) },
    })) as { data: Record<string, T[]>; pageInfo?: { hasNextPage?: boolean; endCursor?: string } };
    out.push(...(res.data[plural] ?? []));
    if (!res.pageInfo?.hasNextPage || !res.pageInfo.endCursor) break;
    after = res.pageInfo.endCursor;
  }
  return out;
}

// ---------------- tarih ve mali dönem ----------------
// Motorla aynı kural: açık fırsatta beklenen kapanış (Türkiye saatiyle gün), kapanmışta gerçek kapanış.
const TR_GUN = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit' });
export const trGun = (iso?: string | null) => (iso ? (iso.length <= 10 ? iso : TR_GUN.format(new Date(iso))) : null);
export const firsatTarihi = (d: Deal) => (CLOSED.has(d.stage) ? trGun(d.realCloseDate) : trGun(d.closeDate));

export const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const AY_KISA = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];

// Seçim: tüm zamanlar, mali yıl, çeyrek (1–4) ya da ay (mali yıl içinde 0–11)
export type Secim =
  | { tur: 'TUMU' }
  | { tur: 'YIL'; fy: number }
  | { tur: 'CEYREK'; fy: number; q: number }
  | { tur: 'AY'; fy: number; q: number; ay: number };

const iso = (y: number, m0: number, d: number) => {
  const t = new Date(Date.UTC(y, m0, d));
  return t.toISOString().slice(0, 10);
};
// Mali yıl fy, başlangıç ayı sm (1–12); ofset ay sayısı kadar ileri
const ayBasi = (fy: number, sm: number, ofset: number) => iso(fy, sm - 1 + ofset, 1);
const ayBitis = (fy: number, sm: number, ofset: number) => iso(fy, sm - 1 + ofset + 1, 0);

export const maliYil = (gun: string, sm: number) => {
  const [y, m] = gun.split('-').map(Number);
  return m >= sm ? y : y - 1;
};
export const yilEtiketi = (fy: number, sm: number) => (sm === 1 ? `${fy}` : `${fy}/${String((fy + 1) % 100).padStart(2, '0')}`);

export function secimAraligi(s: Secim, sm: number): [string, string] | null {
  if (s.tur === 'TUMU') return null;
  if (s.tur === 'YIL') return [ayBasi(s.fy, sm, 0), ayBitis(s.fy, sm, 11)];
  if (s.tur === 'CEYREK') return [ayBasi(s.fy, sm, (s.q - 1) * 3), ayBitis(s.fy, sm, (s.q - 1) * 3 + 2)];
  return [ayBasi(s.fy, sm, s.ay), ayBitis(s.fy, sm, s.ay)];
}

const gunEtiketi = (g: string) => {
  const [y, m, d] = g.split('-').map(Number);
  return `${d} ${AY_KISA[m - 1]} ${y}`;
};
export const ayAdi = (fy: number, sm: number, ay: number) => {
  const [y, m] = ayBasi(fy, sm, ay).split('-').map(Number);
  return { kisa: AY_KISA[m - 1], uzun: `${AYLAR[m - 1]} ${y}` };
};

export function secimEtiketi(s: Secim, sm: number): { ad: string; aralik: string } {
  const r = secimAraligi(s, sm);
  const aralik = r ? `${gunEtiketi(r[0])} – ${gunEtiketi(r[1])}` : 'Tüm kayıtlar';
  if (s.tur === 'TUMU') return { ad: 'Tüm zamanlar', aralik };
  if (s.tur === 'YIL') return { ad: `${yilEtiketi(s.fy, sm)} tüm yıl`, aralik };
  if (s.tur === 'CEYREK') return { ad: `Q${s.q} ${yilEtiketi(s.fy, sm)}`, aralik };
  return { ad: ayAdi(s.fy, sm, s.ay).uzun, aralik };
}

export function bugununCeyregi(sm: number): Secim {
  const bugun = TR_GUN.format(new Date());
  const fy = maliYil(bugun, sm);
  const m = Number(bugun.slice(5, 7));
  const ofset = (m - sm + 12) % 12;
  return { tur: 'CEYREK', fy, q: Math.floor(ofset / 3) + 1 };
}

export type Donem = { id: string; name: string; periodType?: string; startDate?: string; endDate?: string };

export type PanoVerisi = {
  deals: Deal[];
  lines: TargetLine[];
  metric: string;
  currency: string;
  maliAy: number; // mali yıl başlangıç ayı (1–12)
  hedefTuru: string; // QUARTER | MONTH | YEAR
  // Dönüşüm oranları (%): motorun "Kullanılan Oran"ı (eşik altında manuel, üstünde geçmiş)
  oranlar: Record<string, { oran: number; kaynak: string }>;
  uyarilar: string[];
};

// Forecast (kullanıcı, 11 Kas 2026): total pipeline = Pipeline/Upside/Commit; tahmini = gerçekleşen + Σ(tutar × oran)
export const TOTAL_PIPELINE = ['PIPELINE', 'UPSIDE', 'COMMIT'];

const mesaj = (e: unknown) => (e instanceof Error ? e.message : typeof e === 'string' ? e : JSON.stringify(e));
// Yetki hatası beklenen durumdur (Satış/Support Yönetim'i göremez); diğer hatalar ekranda gösterilir.
const yetkiHatasi = (e: unknown) => /forbidden|permission|yetki|403/i.test(mesaj(e));

// Ayar ve hedefler Yönetim'de: yetkisi olmayan kullanıcıda okunamaz; o zaman varsayılan ve hedefsiz çalışır.
// REST derinliği en fazla 1 (v2.57.1: "Allowed values are 0, 1"): dönem adı ayrı sorguyla eşlenir.
export async function panoVerisiniYukle(): Promise<PanoVerisi> {
  const client = new RestApiClient();
  const uyarilar: string[] = [];
  let metric = 'REVENUE';
  let currency = 'USD';
  let maliAy = 1;
  let hedefTuru = 'QUARTER';
  let lines: TargetLine[] = [];
  const oranlar: PanoVerisi['oranlar'] = {};
  try {
    const s = (await client.get('/rest/crmSettings', { query: { limit: 1 } })) as {
      data: {
        crmSettings: { reportingMetric?: string; reportingCurrency?: string; fiscalYearStartMonth?: string; targetPeriodType?: string }[];
      };
    };
    const a = s.data.crmSettings[0];
    metric = a?.reportingMetric ?? metric;
    currency = a?.reportingCurrency ?? currency;
    maliAy = Number(a?.fiscalYearStartMonth?.slice(1)) || maliAy;
    hedefTuru = a?.targetPeriodType ?? hedefTuru;
  } catch (e) {
    if (!yetkiHatasi(e)) uyarilar.push(`Ayar okunamadı: ${mesaj(e)}`);
  }
  try {
    type HamSatir = Omit<TargetLine, 'target'> & {
      target?: { memberId?: string; targetRole?: string; periodId?: string } | null;
    };
    const [ham, donemler] = await Promise.all([
      fetchAll<HamSatir>(client, 'targetLines', { depth: 1 }),
      fetchAll<Donem>(client, 'reportingPeriods', { depth: 0 }),
    ]);
    const ad = new Map(donemler.map((p) => [p.id, p]));
    lines = ham.map((l) => ({
      ...l,
      target: l.target
        ? { ...l.target, period: l.target.periodId ? ad.get(l.target.periodId) ?? null : null }
        : null,
    }));
  } catch (e) {
    if (!yetkiHatasi(e)) uyarilar.push(`Hedefler okunamadı: ${mesaj(e)}`);
  }
  try {
    type Oran = { stage?: string; effectiveRate?: number | null; manualRate?: number | null; rateSource?: string | null };
    for (const r of await fetchAll<Oran>(client, 'forecastRates', { depth: 0 })) {
      const oran = r.effectiveRate ?? r.manualRate;
      if (r.stage && typeof oran === 'number') oranlar[r.stage] = { oran, kaynak: r.rateSource === 'HISTORY' ? 'geçmiş' : 'manuel' };
    }
  } catch (e) {
    if (!yetkiHatasi(e)) uyarilar.push(`Dönüşüm oranları okunamadı: ${mesaj(e)}`);
  }
  const deals = await fetchAll<Deal>(client, 'opportunities', { depth: 1 });
  return { deals, lines, metric, currency, maliAy, hedefTuru, oranlar, uyarilar };
}
