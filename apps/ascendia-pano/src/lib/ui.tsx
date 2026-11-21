import { scaleLinear } from 'd3-scale';
import type { CSSProperties, ReactNode } from 'react';

import type { KisiSatiri } from 'src/lib/hesap';
import { ayAdi, fmt, fmtShort, pct, type Secim, yilEtiketi } from 'src/lib/pano-veri';

// Ortak görünüm: Twenty'nin tema değişkenleri (--t-*); açık/koyu tema Twenty'den gelir.
// Grafikler SVG + d3-scale (sandbox'ta canvas ve DOM ölçümü yok).

export const T = {
  font: 'var(--t-font-family, Inter, -apple-system, sans-serif)',
  fg: 'var(--t-font-color-primary, #333)',
  fg2: 'var(--t-font-color-secondary, #666)',
  fg3: 'var(--t-font-color-tertiary, #999)',
  fgLight: 'var(--t-font-color-light, #b3b3b3)',
  bg: 'var(--t-background-primary, #fff)',
  bg2: 'var(--t-background-secondary, #fcfcfc)',
  border: 'var(--t-border-color-medium, #ebebeb)',
  borderLight: 'var(--t-border-color-light, #f1f1f1)',
  blue: 'var(--t-color-blue, #1961ed)',
  red: 'var(--t-color-red, #e5484d)',
  radius: 'var(--t-border-radius-md, 8px)',
  radiusSm: 'var(--t-border-radius-sm, 4px)',
};

// Widget kabuğu: Twenty widget çerçevesinin içini doldurur; üstte hangi dönemin gösterildiği yazar.
export const Kabuk = ({
  hata,
  yukleniyor,
  donem,
  sag,
  children,
}: {
  hata?: string | null;
  yukleniyor?: boolean;
  donem?: string;
  sag?: ReactNode;
  children?: ReactNode;
}) => (
  <div style={{ fontFamily: T.font, color: T.fg, height: '100%', overflow: 'auto', padding: '4px 12px 12px', boxSizing: 'border-box' }}>
    {hata ? (
      <div style={{ fontSize: 13, color: T.red }}>Veri alınamadı: {hata}</div>
    ) : yukleniyor ? (
      <div style={{ fontSize: 13, color: T.fg3 }}>Yükleniyor…</div>
    ) : (
      <>
        {(donem || sag) && (
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12, color: T.fg3, marginBottom: 8 }}>
            <span>{donem}</span>
            <span>{sag}</span>
          </div>
        )}
        {children}
      </>
    )}
  </div>
);

export const Bos = ({ mesaj = 'Seçime uyan fırsat yok.' }: { mesaj?: string }) => (
  <div style={{ fontSize: 13, color: T.fg3, padding: '24px 0', textAlign: 'center' }}>{mesaj}</div>
);

export const Chip = ({ on, label, color, onClick }: { on: boolean; label: string; color?: string; onClick: () => void }) => (
  <button
    onClick={onClick}
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      border: `1px solid ${on ? T.border : 'transparent'}`,
      background: on ? T.bg : 'transparent',
      color: on ? T.fg : T.fg3,
      borderRadius: T.radiusSm,
      padding: '3px 8px',
      fontSize: 12,
      fontFamily: T.font,
      cursor: 'pointer',
    }}
  >
    {color && <span style={{ width: 8, height: 8, borderRadius: 2, background: on ? color : T.fgLight }} />}
    {label}
  </button>
);

export const FiltreSatiri = ({ label, children }: { label: string; children: ReactNode }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
    <span style={{ fontSize: 12, color: T.fg3, width: 56 }}>{label}</span>
    {children}
  </div>
);

export const Kpi = ({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) => (
  <div style={{ flex: '1 1 150px', background: T.bg, border: `1px solid ${T.border}`, borderRadius: T.radius, padding: '10px 14px' }}>
    <div style={{ fontSize: 12, color: T.fg3, marginBottom: 6 }}>{label}</div>
    <div style={{ fontSize: 22, fontWeight: 600, color: accent ?? T.fg, letterSpacing: -0.3 }}>{value}</div>
    {sub && <div style={{ fontSize: 12, color: T.fg2, marginTop: 4 }}>{sub}</div>}
  </div>
);

// Dönem seçici: ‹ yıl ›, Tüm yıl / Q1–Q4, seçili çeyreğin ayları, Tüm zamanlar
export const DonemSecici = ({
  secim,
  setSecim,
  sm,
  varsayilanFy,
}: {
  secim: Secim;
  setSecim: (s: Secim) => void;
  sm: number;
  varsayilanFy: number;
}) => {
  const fy = secim.tur === 'TUMU' ? varsayilanFy : secim.fy;
  const q = secim.tur === 'CEYREK' || secim.tur === 'AY' ? secim.q : null;
  const ok = (yon: number) => setSecim(secim.tur === 'TUMU' ? { tur: 'YIL', fy: fy + yon } : { ...secim, fy: secim.fy + yon });
  const okStil: CSSProperties = {
    border: `1px solid ${T.border}`,
    background: T.bg,
    color: T.fg2,
    borderRadius: T.radiusSm,
    width: 24,
    height: 24,
    cursor: 'pointer',
    fontFamily: T.font,
    fontSize: 13,
    lineHeight: '20px',
    padding: 0,
  };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
      <button style={okStil} onClick={() => ok(-1)}>‹</button>
      <span style={{ fontSize: 13, fontWeight: 600, minWidth: 48, textAlign: 'center', color: secim.tur === 'TUMU' ? T.fg3 : T.fg }}>
        {yilEtiketi(fy, sm)}
      </span>
      <button style={okStil} onClick={() => ok(1)}>›</button>
      <span style={{ width: 8 }} />
      <Chip on={secim.tur === 'YIL'} label="Tüm yıl" onClick={() => setSecim({ tur: 'YIL', fy })} />
      {[1, 2, 3, 4].map((n) => (
        <Chip key={n} on={q === n} label={`Q${n}`} onClick={() => setSecim({ tur: 'CEYREK', fy, q: n })} />
      ))}
      {q !== null && (
        <>
          <span style={{ width: 1, height: 16, background: T.border, margin: '0 6px' }} />
          {[0, 1, 2].map((i) => {
            const ay = (q - 1) * 3 + i;
            const secili = secim.tur === 'AY' && secim.ay === ay;
            return (
              <Chip
                key={ay}
                on={secili}
                label={ayAdi(fy, sm, ay).kisa}
                onClick={() => setSecim(secili ? { tur: 'CEYREK', fy, q } : { tur: 'AY', fy, q, ay })}
              />
            );
          })}
        </>
      )}
      <span style={{ width: 8 }} />
      <Chip on={secim.tur === 'TUMU'} label="Tüm zamanlar" onClick={() => setSecim({ tur: 'TUMU' })} />
    </div>
  );
};

// Grafikler HTML ile çizilir: uzunluklar yüzde, yazılar sabit piksel. Widget hangi genişlikte olursa olsun
// yazı boyutu Twenty'nin geri kalanıyla aynı kalır (SVG viewBox ölçeklenince yazılar büyüyordu, 13 Kas).
const ETIKET_GENISLIK = 120;
const yuzde = (n: number) => `${n}%`;

export type Dilim = { key: string; amount: number; color: string; opacity?: number };
export type YatayCubukSatiri = { id: string; name: string; dilimler: Dilim[]; hedef: number; etiket: string };

// Yatay çubuklar: üst üste dilimler, kırmızı hedef çizgisi, sağda etiket; altta eksen
export const YatayGrafik = ({
  rows,
  currency,
  hover,
  setHover,
}: {
  rows: YatayCubukSatiri[];
  currency: string;
  hover?: string | null;
  setHover?: (s: string | null) => void;
}) => {
  const max = Math.max(1, ...rows.map((r) => Math.max(r.dilimler.reduce((t, d) => t + d.amount, 0), r.hedef)));
  // Sağda etiket için %20 boşluk
  const x = scaleLinear().domain([0, max]).nice().range([0, 80]);
  const ticks = x.ticks(5).filter((t) => max < 5 || Number.isInteger(t));
  const izgara = (
    <div style={{ position: 'absolute', left: ETIKET_GENISLIK, right: 0, top: 0, bottom: 0, pointerEvents: 'none' }}>
      {ticks.map((t) => (
        <div key={t} style={{ position: 'absolute', left: yuzde(x(t)), top: 0, bottom: 0, borderLeft: `1px solid ${T.borderLight}` }} />
      ))}
    </div>
  );
  return (
    <div style={{ fontFamily: T.font }}>
      <div style={{ position: 'relative' }}>
        {izgara}
        {rows.map((r) => {
          let acc = 0;
          const son = Math.max(r.dilimler.reduce((t, d) => t + d.amount, 0), r.hedef);
          return (
            <div key={r.id} style={{ display: 'flex', alignItems: 'center', height: 34, position: 'relative' }}>
              <div
                style={{
                  width: ETIKET_GENISLIK - 10, paddingRight: 10, textAlign: 'right', fontSize: 13, color: T.fg,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flexShrink: 0,
                }}
              >
                {r.name}
              </div>
              <div style={{ position: 'relative', flex: 1, height: 20 }}>
                {r.dilimler.filter((d) => d.amount > 0).map((d) => {
                  const sol = x(acc);
                  acc += d.amount;
                  const k = `${r.id}|${d.key}`;
                  return (
                    <div
                      key={k}
                      onMouseEnter={setHover ? () => setHover(k) : undefined}
                      onMouseLeave={setHover ? () => setHover(null) : undefined}
                      style={{
                        position: 'absolute', left: yuzde(sol), width: `calc(${yuzde(x(acc) - sol)} - 1px)`, top: 0, bottom: 0,
                        background: d.color, borderRadius: 2,
                        opacity: (d.opacity ?? 1) * (hover && hover !== k ? 0.45 : 1),
                      }}
                    />
                  );
                })}
                {r.hedef > 0 && (
                  <div style={{ position: 'absolute', left: yuzde(x(r.hedef)), top: -5, bottom: -5, width: 2, background: T.red }} />
                )}
                <div
                  style={{
                    position: 'absolute', left: `calc(${yuzde(x(son))} + 8px)`, top: 0, bottom: 0, display: 'flex',
                    alignItems: 'center', fontSize: 12, color: T.fg2, whiteSpace: 'nowrap',
                  }}
                >
                  {r.etiket}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ position: 'relative', height: 18, marginLeft: ETIKET_GENISLIK }}>
        {ticks.map((t) => (
          <span
            key={t}
            style={{ position: 'absolute', left: yuzde(x(t)), transform: 'translateX(-50%)', fontSize: 11, color: T.fg3, whiteSpace: 'nowrap' }}
          >
            {fmtShort(t, currency)}
          </span>
        ))}
      </div>
    </div>
  );
};

export const Lejant = ({ ogeler }: { ogeler: { ad: string; renk: string; cizgi?: boolean; opacity?: number }[] }) => (
  <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 11, color: T.fg2, margin: `6px 0 0 ${ETIKET_GENISLIK}px` }}>
    {ogeler.map((o) => (
      <span key={o.ad} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <span style={{ display: 'inline-block', width: o.cizgi ? 2 : 10, height: 10, background: o.renk, opacity: o.opacity ?? 1, borderRadius: o.cizgi ? 0 : 2 }} />
        {o.ad}
      </span>
    ))}
  </div>
);

// Kişi bazında aşamalar üst üste, hedef çizgisi ve hedefin yüzdesi
export const KisiGrafigi = ({
  rows,
  currency,
  hover,
  setHover,
}: {
  rows: KisiSatiri[];
  currency: string;
  hover: string | null;
  setHover: (s: string | null) => void;
}) => {
  if (!rows.some((r) => r.total > 0 || r.target > 0)) return <Bos />;
  return (
    <YatayGrafik
      currency={currency}
      hover={hover}
      setHover={setHover}
      rows={rows.map((r) => ({
        id: r.id,
        name: r.name,
        dilimler: r.byStage.map((s) => ({ key: s.value, amount: s.amount, color: s.color })),
        hedef: r.target,
        etiket: `${fmtShort(r.total, currency)}${r.target > 0 ? ` · ${pct(r.total, r.target)}` : ''}`,
      }))}
    />
  );
};

// Aşamaya göre toplam (sütun) ve adet; aşama adları 45° çapraz (kullanıcı, 13 Kas)
export const AsamaGrafigi = ({
  data,
  currency,
}: {
  data: { value: string; label: string; color: string; amount: number; count: number }[];
  currency: string;
}) => {
  if (!data.some((d) => d.count > 0)) return <Bos />;
  const max = Math.max(1, ...data.map((d) => d.amount));
  // Üstte değer etiketi için %12 boşluk
  const y = scaleLinear().domain([0, max]).nice().range([0, 88]);
  const ticks = y.ticks(4).filter((t) => max < 5 || Number.isInteger(t));
  const SOL = 48;
  // Sütun alanı widget'ın kalan yüksekliğini alır (Kabuk başlığı ~28 px), eğik aşama adları (78 px) kutuda kalır
  // (16 Kas: küçük widget'ta adlar kesiliyordu; sabit 190 px yerine esnek, en az 100 px)
  return (
    <div style={{ fontFamily: T.font, height: 'calc(100% - 28px)', minHeight: 178, display: 'flex', flexDirection: 'column' }}>
      <div style={{ position: 'relative', flex: 1, minHeight: 100, marginLeft: SOL }}>
        {ticks.map((t) => (
          <div key={t} style={{ position: 'absolute', left: 0, right: 0, bottom: yuzde(y(t)), borderTop: `1px solid ${T.borderLight}` }}>
            <span style={{ position: 'absolute', right: '100%', marginRight: 6, transform: 'translateY(-50%)', fontSize: 11, color: T.fg3, whiteSpace: 'nowrap' }}>
              {fmtShort(t, currency)}
            </span>
          </div>
        ))}
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'flex-end', gap: '3%', padding: '0 1%' }}>
          {data.map((d) => (
            <div key={d.value} style={{ flex: 1, height: '100%', position: 'relative' }}>
              <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: yuzde(y(d.amount)), background: d.color, borderRadius: '3px 3px 0 0' }} />
              {d.amount > 0 && (
                <div style={{ position: 'absolute', left: 0, right: 0, bottom: `calc(${yuzde(y(d.amount))} + 4px)`, textAlign: 'center', fontSize: 11, color: T.fg2, whiteSpace: 'nowrap' }}>
                  {fmtShort(d.amount, currency)}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', gap: '3%', padding: '0 1%', marginLeft: SOL, height: 78, flexShrink: 0 }}>
        {data.map((d) => (
          <div key={d.value} style={{ flex: 1, position: 'relative' }}>
            <div
              style={{
                position: 'absolute', right: '50%', top: 6, transform: 'rotate(-45deg)', transformOrigin: 'top right',
                fontSize: 12, color: T.fg, whiteSpace: 'nowrap',
              }}
            >
              {d.label} <span style={{ color: T.fg3 }}>({d.count})</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const tabloStil = {
  th: { textAlign: 'left', fontWeight: 500, fontSize: 12, color: T.fg3, padding: '8px', borderBottom: `1px solid ${T.border}` } as CSSProperties,
  td: { fontSize: 13, padding: '7px 8px', borderBottom: `1px solid ${T.borderLight}`, color: T.fg } as CSSProperties,
  grp: { fontSize: 13, padding: '7px 8px', borderBottom: `1px solid ${T.borderLight}`, color: T.fg2, background: T.bg2, verticalAlign: 'top' } as CSSProperties,
};

export const tutar = fmt;
