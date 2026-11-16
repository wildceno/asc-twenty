import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';
import { AppPath, navigate } from 'twenty-sdk/front-component';

import { BUYUK_FIRSATLAR_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER } from 'src/constants/universal-identifiers';
import { usePano } from 'src/lib/hesap';
import { firsatTarihi, fmt, fullName, METRIC_LABEL, STAGE } from 'src/lib/pano-veri';
import { Bos, Kabuk, T, tabloStil } from 'src/lib/ui';

// Büyük Fırsatlar: seçime uyan en büyük 10 fırsat; satıra tıklayınca fırsat açılır
const BuyukFirsatlar = () => {
  const { hata, hesap } = usePano();
  if (!hesap) return <Kabuk hata={hata} yukleniyor />;
  const { th, td } = tabloStil;
  const ilk = [...hesap.suzulen].sort((a, b) => hesap.val(b) - hesap.val(a)).slice(0, 10);
  if (!ilk.length) return <Kabuk donem={hesap.etiket.ad}><Bos /></Kabuk>;
  return (
    <Kabuk donem={hesap.etiket.ad} sag={`${ilk.length} / ${hesap.suzulen.length} fırsat`}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Fırsat', 'Müşteri', 'Sahibi', 'Aşama', 'Kapanış', METRIC_LABEL[hesap.metric] ?? hesap.metric].map((h, i) => (
              <th key={h} style={{ ...th, textAlign: i === 5 ? 'right' : 'left' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ilk.map((d) => (
            <tr
              key={d.id}
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(AppPath.RecordShowPage, { objectNameSingular: 'opportunity', objectRecordId: d.id })}
            >
              <td style={td}>{d.name}</td>
              <td style={{ ...td, color: T.fg2 }}>{d.company?.name ?? '—'}</td>
              <td style={{ ...td, color: T.fg2 }}>{fullName(d)}</td>
              <td style={td}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: STAGE[d.stage]?.color ?? T.fgLight }} />
                  {STAGE[d.stage]?.label ?? d.stage}
                </span>
              </td>
              <td style={{ ...td, color: T.fg2 }}>{(firsatTarihi(d) ?? '—').split('-').reverse().join('.')}</td>
              <td style={{ ...td, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{fmt(hesap.val(d), hesap.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: BUYUK_FIRSATLAR_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER,
  name: 'Büyük Fırsatlar',
  description: 'Seçime uyan en büyük 10 fırsat.',
  component: BuyukFirsatlar,
  widgetAvailability: { pageLayoutType: PageLayoutType.DASHBOARD },
});
