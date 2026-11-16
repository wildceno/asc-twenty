import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';

import { ASAMA_DAGILIMI_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER } from 'src/constants/universal-identifiers';
import { usePano } from 'src/lib/hesap';
import { AsamaGrafigi, Kabuk } from 'src/lib/ui';

// Aşama Dağılımı: seçili aşamalarda toplam tutar ve fırsat adedi
const AsamaDagilimi = () => {
  const { hata, hesap } = usePano();
  if (!hesap) return <Kabuk hata={hata} yukleniyor />;
  return (
    <Kabuk donem={`${hesap.etiket.ad} · ${hesap.metrikEtiketi}`}>
      <AsamaGrafigi data={hesap.asamaDagilimi} currency={hesap.currency} />
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: ASAMA_DAGILIMI_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER,
  name: 'Aşama Dağılımı',
  description: 'Aşamaya göre toplam tutar ve fırsat adedi.',
  component: AsamaDagilimi,
  widgetAvailability: { pageLayoutType: PageLayoutType.DASHBOARD },
});
