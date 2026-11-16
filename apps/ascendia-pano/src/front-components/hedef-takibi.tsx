import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';
import { useState } from 'react';

import { HEDEF_TAKIBI_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER } from 'src/constants/universal-identifiers';
import { usePano } from 'src/lib/hesap';
import { fmt } from 'src/lib/pano-veri';
import { Kabuk, KisiGrafigi } from 'src/lib/ui';

// Hedef Takibi: kişi bazında aşamalar üst üste, kırmızı çizgi hedef, yanında hedefin yüzdesi
const HedefTakibi = () => {
  const { hata, hesap } = usePano();
  const [hover, setHover] = useState<string | null>(null);
  if (!hesap) return <Kabuk hata={hata} yukleniyor />;
  const ipucu = (() => {
    if (!hover) return null;
    const [rid, sv] = hover.split('|');
    const r = hesap.kisiSatirlari.find((x) => x.id === rid);
    const s = r?.byStage.find((x) => x.value === sv);
    return r && s ? `${r.name} · ${s.label}: ${fmt(s.amount, hesap.currency)} (${s.count} fırsat)` : null;
  })();
  return (
    <Kabuk donem={`${hesap.etiket.ad} · ${hesap.metrikEtiketi}`} sag={ipucu ?? 'Kırmızı çizgi: hedef'}>
      <KisiGrafigi rows={hesap.kisiSatirlari} currency={hesap.currency} hover={hover} setHover={setHover} />
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: HEDEF_TAKIBI_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER,
  name: 'Hedef Takibi',
  description: 'Kişi bazında pipeline (aşamalar üst üste), hedef çizgisi ve hedefin yüzdesi.',
  component: HedefTakibi,
  widgetAvailability: { pageLayoutType: PageLayoutType.DASHBOARD },
});
