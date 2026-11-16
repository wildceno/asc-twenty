import { useEffect, useMemo, useState } from 'react';

import { useOrtakFiltre } from 'src/lib/filtre';
import {
  ACHIEVED,
  bugununCeyregi,
  type Deal,
  firsatTarihi,
  fullName,
  METRIC_FIELD,
  METRIC_LABEL,
  money,
  type PanoVerisi,
  panoVerisiniYukle,
  type Secim,
  secimAraligi,
  secimEtiketi,
  STAGES,
  TOTAL_PIPELINE,
} from 'src/lib/pano-veri';

// Tüm widget'ların ortak hesabı: veri bir kez yüklenir, ortak filtre uygulanır, türetilmiş değerler döner.
// Kurallar (kullanıcı, 11–13 Kas 2026): fırsat tarihi = açıkta beklenen kapanış, kapanmışta gerçek kapanış
// (TR saati); gerçekleşen = Audit/Delivery/Invoice/Won; açık pipeline = Pipeline/Upside/Commit;
// hedef = hedef türündeki dönemlerden seçili aralıkta kalanlar (yıl = çeyrekler toplamı), aya bölünmez.

export type KisiSatiri = {
  id: string;
  name: string;
  byStage: { value: string; label: string; color: string; amount: number; count: number }[];
  total: number;
  achieved: number;
  forecast: number; // Σ(Pipeline/Upside/Commit tutarı × oran)
  target: number;
};

export function usePano() {
  const [veri, setVeri] = useState<PanoVerisi | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const { filtre, degistir, sifirla } = useOrtakFiltre();

  useEffect(() => {
    panoVerisiniYukle()
      .then(setVeri)
      .catch((e) => setHata(e instanceof Error ? e.message : String(e)));
  }, []);

  const sm = veri?.maliAy ?? 1;
  const secim: Secim = filtre.secim ?? bugununCeyregi(sm);

  const hesap = useMemo(() => {
    if (!veri) return null;
    const { deals, lines, metric, currency, hedefTuru, oranlar } = veri;
    const oranOf = (stage: string) => (TOTAL_PIPELINE.includes(stage) ? (oranlar[stage]?.oran ?? 0) / 100 : 0);
    const field = METRIC_FIELD[metric] ?? 'amountReporting';
    const val = (d: Deal) => money(d[field]);
    const aralik = secimAraligi(secim, sm);
    const aralikta = (g?: string | null) => !aralik || (!!g && g >= aralik[0] && g <= aralik[1]);
    const hedefGosterilir = !(secim.tur === 'AY' && hedefTuru !== 'MONTH');

    const kisiMap = new Map<string, string>();
    deals.forEach((d) => d.ownerId && kisiMap.set(d.ownerId, fullName(d)));
    const tumKisiler = [...kisiMap.entries()].sort((a, b) => a[1].localeCompare(b[1], 'tr'));
    const aktifKisiler = new Set(filtre.kisiler ?? tumKisiler.map(([id]) => id));
    const asamalar = new Set(filtre.asamalar);

    // Dönem + kişi süzmesi (aşama hariç): kazanma oranı gibi Lost/DSQ'yu da görmesi gereken widget'lar için
    const donemKisi = deals.filter((d) => aralikta(firsatTarihi(d)) && !!d.ownerId && aktifKisiler.has(d.ownerId));
    const suzulen = donemKisi.filter((d) => asamalar.has(d.stage));

    const hedefi = (memberId: string) =>
      hedefGosterilir
        ? lines
            .filter(
              (l) =>
                l.metric === metric &&
                l.target?.memberId === memberId &&
                (l.target?.targetRole ?? 'PERSONAL') === 'PERSONAL' &&
                l.target?.period?.periodType === hedefTuru &&
                aralikta(l.target?.period?.startDate) &&
                aralikta(l.target?.period?.endDate),
            )
            .reduce((s, l) => s + money(l.targetAmount), 0)
        : 0;

    const kisiSatirlari: KisiSatiri[] = tumKisiler
      .filter(([id]) => aktifKisiler.has(id))
      .map(([id, name]) => {
        const benim = suzulen.filter((d) => d.ownerId === id);
        const byStage = STAGES.map((s) => {
          const ds = benim.filter((d) => d.stage === s.value);
          return { ...s, amount: ds.reduce((t, d) => t + val(d), 0), count: ds.length };
        });
        return {
          id,
          name,
          byStage,
          total: byStage.reduce((t, s) => t + s.amount, 0),
          achieved: benim.filter((d) => ACHIEVED.has(d.stage)).reduce((t, d) => t + val(d), 0),
          forecast: benim.reduce((t, d) => t + val(d) * oranOf(d.stage), 0),
          target: hedefi(id),
        };
      })
      .sort((a, b) => b.total - a.total);

    const asamaDagilimi = STAGES.filter((s) => asamalar.has(s.value)).map((s) => {
      const ds = suzulen.filter((d) => d.stage === s.value);
      return { ...s, amount: ds.reduce((t, d) => t + val(d), 0), count: ds.length };
    });

    return {
      metric,
      currency,
      hedefTuru,
      field,
      val,
      etiket: secimEtiketi(secim, sm),
      metrikEtiketi: `${METRIC_LABEL[metric] ?? metric} (${currency})`,
      hedefGosterilir,
      tumKisiler,
      aktifKisiler,
      asamalar,
      suzulen,
      donemKisi,
      kisiSatirlari,
      asamaDagilimi,
      toplam: kisiSatirlari.reduce((t, r) => t + r.total, 0),
      hedef: kisiSatirlari.reduce((t, r) => t + r.target, 0),
      gerceklesen: suzulen.filter((d) => ACHIEVED.has(d.stage)).reduce((t, d) => t + val(d), 0),
      oranlar,
      forecast: kisiSatirlari.reduce((t, r) => t + r.forecast, 0),
      acik: suzulen.filter((d) => ['PIPELINE', 'UPSIDE', 'COMMIT'].includes(d.stage)).reduce((t, d) => t + val(d), 0),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [veri, sm, JSON.stringify(secim), JSON.stringify(filtre.kisiler), filtre.asamalar.join(',')]);

  return { veri, hata, hesap, filtre, secim, sm, degistir, sifirla };
}
