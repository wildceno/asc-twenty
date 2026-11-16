import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';

import { SATIS_GOSTERGELERI_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER } from 'src/constants/universal-identifiers';
import { usePano } from 'src/lib/hesap';
import { fmt, pct } from 'src/lib/pano-veri';
import { Kabuk, Kpi, T } from 'src/lib/ui';

// Satış Göstergeleri: toplam, açık pipeline, gerçekleşen, hedef, gerçekleşme
const SatisGostergeleri = () => {
  const { hata, hesap } = usePano();
  if (!hesap) return <Kabuk hata={hata} yukleniyor />;
  const c = hesap.currency;
  const hedefNotu = hesap.hedef ? undefined : hesap.hedefGosterilir ? 'Hedef girilmemiş' : 'Aylık hedef yok';
  return (
    <Kabuk donem={hesap.etiket.ad} sag={hesap.metrikEtiketi}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Kpi label="Toplam" value={fmt(hesap.toplam, c)} sub={`${hesap.suzulen.length} fırsat`} />
        <Kpi label="Açık pipeline (Pipeline–Commit)" value={fmt(hesap.acik, c)} />
        <Kpi label="Gerçekleşen (Audit ve sonrası)" value={fmt(hesap.gerceklesen, c)} />
        <Kpi label="Hedef" value={hesap.hedef ? fmt(hesap.hedef, c) : '—'} sub={hedefNotu} />
        <Kpi label="Gerçekleşme" value={pct(hesap.gerceklesen, hesap.hedef)} accent={T.blue} />
      </div>
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: SATIS_GOSTERGELERI_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER,
  name: 'Satış Göstergeleri',
  description: 'Toplam, açık pipeline, gerçekleşen, hedef ve gerçekleşme yüzdesi.',
  component: SatisGostergeleri,
  widgetAvailability: { pageLayoutType: PageLayoutType.DASHBOARD },
});
