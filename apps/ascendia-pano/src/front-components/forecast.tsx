import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';

import { FORECAST_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER } from 'src/constants/universal-identifiers';
import { type KisiSatiri, usePano } from 'src/lib/hesap';
import { fmt, fmtShort, pct, STAGE, TOTAL_PIPELINE } from 'src/lib/pano-veri';
import { Bos, Kabuk, Kpi, Lejant, T, tabloStil, YatayGrafik } from 'src/lib/ui';

// Forecast (kullanıcı, 11 Kas 2026): Pipeline/Upside/Commit × aşama dönüşüm oranı = ağırlıklı forecast;
// tahmini kapanış = gerçekleşen (Audit ve sonrası) + forecast; hedefle karşılaştırılır. 2 haftalık forecast toplantısı için.
const GERCEKLESEN_RENK = '#5CB85C';
const FORECAST_RENK = '#6CB4EE';

const Forecast = () => {
  const { hata, hesap } = usePano();
  if (!hesap) return <Kabuk hata={hata} yukleniyor />;
  const c = hesap.currency;
  const rows = hesap.kisiSatirlari.filter((r) => r.achieved + r.forecast + r.target > 0 || r.byStage.some((s) => TOTAL_PIPELINE.includes(s.value) && s.amount > 0));
  const tahmini = hesap.gerceklesen + hesap.forecast;
  const tutar = (r: KisiSatiri, asama: string) => r.byStage.find((s) => s.value === asama)?.amount ?? 0;
  const oranYazi = ['COMMIT', 'UPSIDE', 'PIPELINE']
    .map((a) => `${STAGE[a]?.label} %${hesap.oranlar[a]?.oran ?? '—'}${hesap.oranlar[a] ? ` (${hesap.oranlar[a].kaynak})` : ''}`)
    .join(' · ');
  const { th, td } = tabloStil;
  const sag = { ...td, textAlign: 'right' as const, fontVariantNumeric: 'tabular-nums' as const };
  const toplam = { ...sag, fontWeight: 600, background: T.bg2 };
  const kolonlar = ['Kişi', 'Commit', 'Upside', 'Pipeline', 'Gerçekleşen', 'Forecast', 'Tahmini', 'Hedef', 'Tahmini / Hedef', 'Hedefe kalan'];
  const kalan = (tah: number, hed: number) => (hed > 0 ? fmt(Math.max(0, hed - tah), c) : '—');
  const toplamTutar = (a: string) => rows.reduce((t, r) => t + tutar(r, a), 0);

  return (
    <Kabuk donem={`${hesap.etiket.ad} · ${hesap.metrikEtiketi}`} sag={`Oranlar: ${oranYazi}`}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
        <Kpi label="Gerçekleşen (Audit ve sonrası)" value={fmt(hesap.gerceklesen, c)} />
        <Kpi label="Ağırlıklı forecast" value={fmt(hesap.forecast, c)} />
        <Kpi label="Tahmini kapanış" value={fmt(tahmini, c)} sub="Gerçekleşen + forecast" />
        <Kpi label="Hedef" value={hesap.hedef ? fmt(hesap.hedef, c) : '—'} />
        <Kpi label="Tahmini / Hedef" value={pct(tahmini, hesap.hedef)} accent={T.blue} />
      </div>
      {!rows.length ? (
        <Bos />
      ) : (
        <>
          <YatayGrafik
            currency={c}
            rows={rows.map((r) => ({
              id: r.id,
              name: r.name,
              dilimler: [
                { key: 'g', amount: r.achieved, color: GERCEKLESEN_RENK },
                { key: 'f', amount: r.forecast, color: FORECAST_RENK, opacity: 0.75 },
              ],
              hedef: r.target,
              etiket: `${fmtShort(r.achieved + r.forecast, c)}${r.target > 0 ? ` · ${pct(r.achieved + r.forecast, r.target)}` : ''}`,
            }))}
          />
          <Lejant
            ogeler={[
              { ad: 'Gerçekleşen', renk: GERCEKLESEN_RENK },
              { ad: 'Ağırlıklı forecast', renk: FORECAST_RENK, opacity: 0.75 },
              { ad: 'Hedef', renk: 'var(--t-color-red, #e5484d)', cizgi: true },
            ]}
          />
          <div style={{ height: 12 }} />
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>{kolonlar.map((k, i) => <th key={k} style={{ ...th, textAlign: i === 0 ? 'left' : 'right' }}>{k}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const tah = r.achieved + r.forecast;
                return (
                  <tr key={r.id}>
                    <td style={td}>{r.name}</td>
                    <td style={sag}>{fmt(tutar(r, 'COMMIT'), c)}</td>
                    <td style={sag}>{fmt(tutar(r, 'UPSIDE'), c)}</td>
                    <td style={sag}>{fmt(tutar(r, 'PIPELINE'), c)}</td>
                    <td style={sag}>{fmt(r.achieved, c)}</td>
                    <td style={sag}>{fmt(r.forecast, c)}</td>
                    <td style={{ ...sag, fontWeight: 600 }}>{fmt(tah, c)}</td>
                    <td style={sag}>{r.target ? fmt(r.target, c) : '—'}</td>
                    <td style={sag}>{pct(tah, r.target)}</td>
                    <td style={sag}>{kalan(tah, r.target)}</td>
                  </tr>
                );
              })}
              <tr>
                <td style={{ ...toplam, textAlign: 'left' }}>Toplam</td>
                <td style={toplam}>{fmt(toplamTutar('COMMIT'), c)}</td>
                <td style={toplam}>{fmt(toplamTutar('UPSIDE'), c)}</td>
                <td style={toplam}>{fmt(toplamTutar('PIPELINE'), c)}</td>
                <td style={toplam}>{fmt(hesap.gerceklesen, c)}</td>
                <td style={toplam}>{fmt(hesap.forecast, c)}</td>
                <td style={toplam}>{fmt(tahmini, c)}</td>
                <td style={toplam}>{hesap.hedef ? fmt(hesap.hedef, c) : '—'}</td>
                <td style={toplam}>{pct(tahmini, hesap.hedef)}</td>
                <td style={toplam}>{kalan(tahmini, hesap.hedef)}</td>
              </tr>
            </tbody>
          </table>
        </>
      )}
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: FORECAST_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER,
  name: 'Forecast',
  description: 'Commit / Upside / Pipeline, ağırlıklı forecast, tahmini kapanış ve hedefe kalan; forecast toplantısı için.',
  component: Forecast,
  widgetAvailability: { pageLayoutType: PageLayoutType.DASHBOARD },
});
