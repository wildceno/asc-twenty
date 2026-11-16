import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';

import { PANO_FILTRESI_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER } from 'src/constants/universal-identifiers';
import { usePano } from 'src/lib/hesap';
import { bugununCeyregi, STAGES } from 'src/lib/pano-veri';
import { Chip, DonemSecici, FiltreSatiri, Kabuk, T } from 'src/lib/ui';

// Pano Filtresi: dönem, kişi, aşama. Seçim adrese yazılır; sayfadaki tüm Ascendia widget'ları okur.
const PanoFiltresi = () => {
  const { hata, hesap, filtre, secim, sm, degistir, sifirla } = usePano();
  if (!hesap) return <Kabuk hata={hata} yukleniyor />;
  const bugun = bugununCeyregi(sm);
  const varsayilanFy = bugun.tur === 'CEYREK' ? bugun.fy : new Date().getFullYear();
  const kisiDegistir = (id: string) => {
    const n = new Set(hesap.aktifKisiler);
    n.has(id) ? n.delete(id) : n.add(id);
    degistir({ kisiler: n.size === hesap.tumKisiler.length ? null : [...n] });
  };
  const asamaDegistir = (v: string) => {
    const n = new Set(hesap.asamalar);
    n.has(v) ? n.delete(v) : n.add(v);
    degistir({ asamalar: STAGES.map((s) => s.value).filter((s) => n.has(s)) });
  };
  return (
    <Kabuk>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: T.fg }}>{hesap.etiket.ad}</span>
          <span style={{ fontSize: 12, color: T.fg3 }}>{hesap.etiket.aralik}</span>
          {!filtre.varsayilanMi && (
            <button
              onClick={() => sifirla()}
              style={{ marginLeft: 'auto', border: 'none', background: 'transparent', color: T.blue, fontSize: 12, cursor: 'pointer', fontFamily: T.font }}
            >
              Filtreyi sıfırla
            </button>
          )}
        </div>
        <FiltreSatiri label="Dönem">
          <DonemSecici secim={secim} setSecim={(s) => degistir({ secim: s })} sm={sm} varsayilanFy={varsayilanFy} />
        </FiltreSatiri>
        <FiltreSatiri label="Kişi">
          {hesap.tumKisiler.map(([id, name]) => (
            <Chip key={id} on={hesap.aktifKisiler.has(id)} label={name} onClick={() => kisiDegistir(id)} />
          ))}
        </FiltreSatiri>
        <FiltreSatiri label="Aşama">
          {STAGES.map((s) => (
            <Chip key={s.value} on={hesap.asamalar.has(s.value)} color={s.color} label={s.label} onClick={() => asamaDegistir(s.value)} />
          ))}
        </FiltreSatiri>
      </div>
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: PANO_FILTRESI_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER,
  name: 'Pano Filtresi',
  description: 'Dönem, kişi ve aşama filtresi; sayfadaki tüm Ascendia widget\'larına uygulanır.',
  component: PanoFiltresi,
  widgetAvailability: { pageLayoutType: PageLayoutType.DASHBOARD },
});
