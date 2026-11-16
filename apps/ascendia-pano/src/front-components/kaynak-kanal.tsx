import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';

import { KAYNAK_KANAL_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER } from 'src/constants/universal-identifiers';
import { usePano } from 'src/lib/hesap';
import { type Deal, fmt, fmtShort, KAYBEDILEN, KAYNAKLAR, KAZANILAN, LEAD_ASAMALARI, TOTAL_PIPELINE } from 'src/lib/pano-veri';
import { Bos, Kabuk, Lejant, T, tabloStil, YatayGrafik } from 'src/lib/ui';

// Kaynak ve Kanal: Fırsat Kaynağı'na ve kanal ortağına göre lead, açık pipeline, gerçekleşen, kaybedilen,
// kazanma oranı (adet: kazanılan ÷ (kazanılan + kaybedilen)). Dönem ve kişi filtresi uygulanır; aşama filtresi
// uygulanmaz, çünkü kazanma oranı Lost/DSQ fırsatlarını da görmelidir.
const GERCEKLESEN_RENK = '#5CB85C';
const ACIK_RENK = '#6CB4EE';

type Grup = { id: string; ad: string; renk?: string; firsatlar: Deal[] };
type Ozet = { adet: number; lead: number; acik: number; gerceklesen: number; kazanilan: number; kaybedilen: number };

const KaynakKanal = () => {
  const { hata, hesap } = usePano();
  if (!hesap) return <Kabuk hata={hata} yukleniyor />;
  const c = hesap.currency;
  const val = hesap.val;

  const ozet = (ds: Deal[]): Ozet => ({
    adet: ds.length,
    lead: ds.filter((d) => LEAD_ASAMALARI.has(d.stage)).length,
    acik: ds.filter((d) => TOTAL_PIPELINE.includes(d.stage)).reduce((t, d) => t + val(d), 0),
    gerceklesen: ds.filter((d) => KAZANILAN.has(d.stage)).reduce((t, d) => t + val(d), 0),
    kazanilan: ds.filter((d) => KAZANILAN.has(d.stage)).length,
    kaybedilen: ds.filter((d) => KAYBEDILEN.has(d.stage)).length,
  });
  const oran = (o: Ozet) => (o.kazanilan + o.kaybedilen > 0 ? `%${Math.round((o.kazanilan / (o.kazanilan + o.kaybedilen)) * 100)}` : '—');

  const tum = hesap.donemKisi;
  const kaynaklar: Grup[] = [
    ...KAYNAKLAR.map((k) => ({ id: k.value, ad: k.label, renk: k.color, firsatlar: tum.filter((d) => d.leadSource === k.value) })),
    { id: '_bos', ad: 'Belirtilmemiş', renk: T.fgLight, firsatlar: tum.filter((d) => !d.leadSource) },
  ].filter((g) => g.firsatlar.length > 0);

  const kanal = tum.filter((d) => d.leadSource === 'CHANNEL');
  const ortakMap = new Map<string, Grup>();
  kanal.forEach((d) => {
    const id = d.channelPartnerId ?? '_bos';
    const ad = d.channelPartner?.name ?? 'Ortak belirtilmemiş';
    if (!ortakMap.has(id)) ortakMap.set(id, { id, ad, firsatlar: [] });
    ortakMap.get(id)!.firsatlar.push(d);
  });
  const ortaklar = [...ortakMap.values()].sort(
    (a, b) => ozet(b.firsatlar).gerceklesen + ozet(b.firsatlar).acik - (ozet(a.firsatlar).gerceklesen + ozet(a.firsatlar).acik),
  );

  const { th, td } = tabloStil;
  const sag = { ...td, textAlign: 'right' as const, fontVariantNumeric: 'tabular-nums' as const };
  const kolonlar = ['Fırsat', 'Lead', 'Açık pipeline', 'Gerçekleşen', 'Kazanılan', 'Kaybedilen', 'Kazanma oranı'];
  const Tablo = ({ gruplar, ilk }: { gruplar: Grup[]; ilk: string }) => {
    const t = ozet(gruplar.flatMap((g) => g.firsatlar));
    const top = { ...sag, fontWeight: 600, background: T.bg2 };
    return (
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>{[ilk, ...kolonlar].map((k, i) => <th key={k} style={{ ...th, textAlign: i === 0 ? 'left' : 'right' }}>{k}</th>)}</tr>
        </thead>
        <tbody>
          {gruplar.map((g) => {
            const o = ozet(g.firsatlar);
            return (
              <tr key={g.id}>
                <td style={td}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    {g.renk && <span style={{ width: 8, height: 8, borderRadius: 2, background: g.renk }} />}
                    {g.ad}
                  </span>
                </td>
                <td style={sag}>{o.adet}</td>
                <td style={sag}>{o.lead}</td>
                <td style={sag}>{fmt(o.acik, c)}</td>
                <td style={sag}>{fmt(o.gerceklesen, c)}</td>
                <td style={sag}>{o.kazanilan}</td>
                <td style={sag}>{o.kaybedilen}</td>
                <td style={sag}>{oran(o)}</td>
              </tr>
            );
          })}
          <tr>
            <td style={{ ...top, textAlign: 'left' }}>Toplam</td>
            <td style={top}>{t.adet}</td>
            <td style={top}>{t.lead}</td>
            <td style={top}>{fmt(t.acik, c)}</td>
            <td style={top}>{fmt(t.gerceklesen, c)}</td>
            <td style={top}>{t.kazanilan}</td>
            <td style={top}>{t.kaybedilen}</td>
            <td style={top}>{oran(t)}</td>
          </tr>
        </tbody>
      </table>
    );
  };
  const baslik = (s: string) => <div style={{ fontSize: 13, fontWeight: 600, color: T.fg, margin: '16px 0 8px' }}>{s}</div>;

  if (!tum.length) return <Kabuk donem={hesap.etiket.ad}><Bos /></Kabuk>;
  return (
    <Kabuk donem={`${hesap.etiket.ad} · ${hesap.metrikEtiketi}`} sag="Aşama filtresi bu widget'ta uygulanmaz">
      {baslik('Fırsat kaynağına göre')}
      <YatayGrafik
        currency={c}
        rows={kaynaklar.map((g) => {
          const o = ozet(g.firsatlar);
          return {
            id: g.id,
            name: g.ad,
            dilimler: [
              { key: 'g', amount: o.gerceklesen, color: GERCEKLESEN_RENK },
              { key: 'a', amount: o.acik, color: ACIK_RENK, opacity: 0.75 },
            ],
            hedef: 0,
            etiket: `${fmtShort(o.gerceklesen + o.acik, c)} · ${o.adet} fırsat`,
          };
        })}
      />
      <Lejant
        ogeler={[
          { ad: 'Gerçekleşen', renk: GERCEKLESEN_RENK },
          { ad: 'Açık pipeline (Pipeline–Commit)', renk: ACIK_RENK, opacity: 0.75 },
        ]}
      />
      <div style={{ height: 10 }} />
      <Tablo gruplar={kaynaklar} ilk="Kaynak" />
      {baslik('Kanal ortaklarına göre')}
      {ortaklar.length ? <Tablo gruplar={ortaklar} ilk="Kanal ortağı" /> : <Bos mesaj="Bu seçimde kanal kaynaklı fırsat yok." />}
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: KAYNAK_KANAL_FRONT_COMPONENT_UNIVERSAL_IDENTIFIER,
  name: 'Kaynak ve Kanal',
  description: 'Fırsat kaynağına ve kanal ortağına göre lead, pipeline, gerçekleşen ve kazanma oranı.',
  component: KaynakKanal,
  widgetAvailability: { pageLayoutType: PageLayoutType.DASHBOARD },
});
