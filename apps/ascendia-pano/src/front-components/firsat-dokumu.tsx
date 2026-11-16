import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';

import { FIRSAT_DOKUMU_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER } from 'src/constants/universal-identifiers';
import { usePano } from 'src/lib/hesap';
import { type Deal, firsatTarihi, fmt, fullName, maliYil, METRIC_LABEL, pct, STAGE, STAGES, yilEtiketi } from 'src/lib/pano-veri';
import { Kabuk, T, tabloStil } from 'src/lib/ui';

// Fırsat Dökümü (eski Satış Panosu'nun yerine): Dönem › Kişi › Aşama gruplu tablo; Totals, Target, Achievement.
// Achievement = tablodaki toplam / hedef (aşama filtresine göre). Dönem sütunu fırsat tarihinin çeyreği.
const FirsatDokumu = () => {
  const { hata, hesap, sm } = usePano();
  if (!hesap) return <Kabuk hata={hata} yukleniyor />;
  const { th, td, grp } = tabloStil;

  const ceyrek = (d: Deal) => {
    const g = firsatTarihi(d);
    if (!g) return '—';
    const fy = maliYil(g, sm);
    const q = Math.floor(((Number(g.slice(5, 7)) - sm + 12) % 12) / 3) + 1;
    return `Q${q} ${yilEtiketi(fy, sm)}`;
  };
  // Çeyrekler kronolojik: mali yıl × 10 + çeyrek
  const ceyrekSira = (d: Deal) => {
    const g = firsatTarihi(d);
    if (!g) return 1e9;
    return maliYil(g, sm) * 10 + Math.floor(((Number(g.slice(5, 7)) - sm + 12) % 12) / 3) + 1;
  };
  const satirlar = [...hesap.suzulen].sort(
    (a, b) =>
      ceyrekSira(a) - ceyrekSira(b) ||
      fullName(a).localeCompare(fullName(b), 'tr') ||
      STAGES.findIndex((s) => s.value === a.stage) - STAGES.findIndex((s) => s.value === b.stage) ||
      hesap.val(b) - hesap.val(a),
  );
  const span = (i: number, key: (d: Deal) => string) => {
    if (i > 0 && key(satirlar[i - 1]) === key(satirlar[i])) return 0;
    let n = 1;
    while (i + n < satirlar.length && key(satirlar[i + n]) === key(satirlar[i])) n++;
    return n;
  };
  const kP = (d: Deal) => ceyrek(d);
  const kR = (d: Deal) => `${kP(d)}|${d.ownerId}`;
  const kS = (d: Deal) => `${kR(d)}|${d.stage}`;
  const ozet = { ...grp, fontWeight: 600, color: T.fg };
  const metrik = METRIC_LABEL[hesap.metric] ?? hesap.metric;

  return (
    <Kabuk donem={`${hesap.etiket.ad} · ${hesap.metrikEtiketi}`} sag={`${satirlar.length} fırsat`}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Dönem', 'Sahibi', 'Aşama', 'Müşteri', 'Fırsat', 'Kapanış', metrik].map((h, i) => (
              <th key={h} style={{ ...th, textAlign: i === 6 ? 'right' : 'left' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {satirlar.map((d, i) => (
            <tr key={d.id}>
              {span(i, kP) > 0 && <td rowSpan={span(i, kP)} style={grp}>{kP(d)}</td>}
              {span(i, kR) > 0 && <td rowSpan={span(i, kR)} style={grp}>{fullName(d)}</td>}
              {span(i, kS) > 0 && (
                <td rowSpan={span(i, kS)} style={grp}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: STAGE[d.stage]?.color ?? T.fgLight }} />
                    {STAGE[d.stage]?.label ?? d.stage}
                  </span>
                </td>
              )}
              <td style={{ ...td, color: T.fg2 }}>{d.company?.name ?? '—'}</td>
              <td style={td}>{d.name}</td>
              <td style={{ ...td, color: T.fg2 }}>{(firsatTarihi(d) ?? '—').split('-').reverse().join('.')}</td>
              <td style={{ ...td, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{fmt(hesap.val(d), hesap.currency)}</td>
            </tr>
          ))}
          <tr>
            <td colSpan={6} style={ozet}>Toplam</td>
            <td style={{ ...ozet, textAlign: 'right' }}>{fmt(hesap.toplam, hesap.currency)}</td>
          </tr>
          <tr>
            <td colSpan={6} style={ozet}>Hedef</td>
            <td style={{ ...ozet, textAlign: 'right' }}>{hesap.hedef ? fmt(hesap.hedef, hesap.currency) : '—'}</td>
          </tr>
          <tr>
            <td colSpan={6} style={ozet}>Toplam / Hedef</td>
            <td style={{ ...ozet, textAlign: 'right' }}>{pct(hesap.toplam, hesap.hedef)}</td>
          </tr>
        </tbody>
      </table>
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: FIRSAT_DOKUMU_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER,
  name: 'Fırsat Dökümü',
  description: 'Dönem › Kişi › Aşama gruplu fırsat tablosu; toplam, hedef ve hedefe oran.',
  component: FirsatDokumu,
  widgetAvailability: { pageLayoutType: PageLayoutType.DASHBOARD },
});
