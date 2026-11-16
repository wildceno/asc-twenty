import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';
import { AppPath, navigate, useRecordId, useSelectedObjectMetadata } from 'twenty-sdk/front-component';
import { RestApiClient } from 'twenty-client-sdk/rest';
import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';

import { TEKLIF_EKRANI_FC } from 'src/constants/universal-identifiers';
import { Kabuk, Kpi, T } from 'src/lib/ui';

// Teklif ekranı (liste 14b; plan: kararlar/2026-11-13-teklif-modulu-plan.md). Teklif kayıt sayfasında "Teklif" sekmesi.
// Kalem ekleme (katalogdan / özel), düzenleme, silme, P&L özeti, durum düğmeleri, yeni sürüm. Hesapları hesap motoru
// (TEKLIF paketi) yapar: kayıttan sonra ekran birkaç kez yenilenir. Gönderilmiş teklif salt okunur.
type Para = { amountMicros?: number | string | null; currencyCode?: string | null } | null;
type Teklif = {
  id: string; name?: string; status?: string; version?: number; validUntil?: string | null; contractMonths?: number | null;
  opportunityId?: string; approverId?: string | null; approvedById?: string | null; systemWarning?: string | null;
  currencyBreakdown?: Record<string, { gelir: number; maliyet: number }> | null; revenueReporting?: Para; costReporting?: Para;
  channelShareReporting?: Para; grossProfitReporting?: Para; marginPercent?: number | null;
  sentAt?: string | null;
  inflationUsed?: { oranlar?: Record<string, number[]>; kaynak?: Record<string, string> } | null;
  channelShareRate?: number | null; channelShareBase?: string | null; channelShareScope?: string[] | null;
  priceEscalation?: string | null; priceEscalationRate?: number | null;
};
type Kalem = {
  id: string; name?: string; section?: string | null; sortOrder?: number | null; description?: string | null; quantity?: number | null;
  unit?: string | null; unitCost?: Para; unitPrice?: Para; listPrice?: Para; discountPercent?: number | null; billing?: string | null;
  months?: number | null; costType?: string | null; optionGroup?: string | null; isDefaultOption?: boolean | null;
  lineRevenue?: Para; lineCost?: Para; catalogItemId?: string | null; supplierId?: string | null;
};
type Katalog = { id: string; name?: string; unit?: string; listPrice?: Para; unitCost?: Para; billing?: string; active?: boolean };

const DURUM: Record<string, string> = {
  DRAFT: 'Taslak', PENDING_APPROVAL: 'Onay bekliyor', APPROVED: 'Onaylandı', SENT: 'Gönderildi', ACCEPTED: 'Kabul',
  REJECTED: 'Red', REVISED: 'Revize edildi',
};
const ODEME: Record<string, string> = { ONE_TIME: 'Tek seferlik', MONTHLY: 'Aylık', YEARLY: 'Yıllık' };
const MALIYET: Record<string, string> = { PERSONNEL: 'Personel', LICENSE: 'Lisans / Tedarikçi', SUBCONTRACT: 'Taşeron', OTHER: 'Diğer' };
const PB = ['TRY', 'USD', 'EUR', 'GBP'];
const ACIK = new Set(['DRAFT', 'PENDING_APPROVAL', 'APPROVED']);
const KOPYA_ALANLARI = ['name', 'section', 'sortOrder', 'description', 'quantity', 'unit', 'unitCost', 'unitPrice', 'listPrice',
  'discountPercent', 'billing', 'months', 'costType', 'optionGroup', 'isDefaultOption', 'catalogItemId', 'supplierId'] as const;

const tutar = (p: Para | undefined) => (p && p.amountMicros !== null && p.amountMicros !== undefined && p.amountMicros !== '' ? Number(p.amountMicros) / 1e6 : null);
const bicim = (n: number | null | undefined, pb?: string | null) =>
  n === null || n === undefined ? '—' : `${n.toLocaleString('tr-TR', { maximumFractionDigits: 2 })} ${pb ?? ''}`.trim();
const sayi = (s: string) => {
  const t = s.trim();
  if (!t) return null;
  const n = Number(t.includes(',') ? t.replace(/\./g, '').replace(',', '.') : t);
  return Number.isFinite(n) ? n : null;
};
const deger = (e: unknown) => {
  const x = e as { value?: string; target?: { value?: string }; detail?: { value?: string } };
  return x?.value ?? x?.target?.value ?? x?.detail?.value ?? '';
};
const para = (n: number | null, pb: string) => (n === null ? null : { amountMicros: Math.round(n * 1e6), currencyCode: pb });

const giris: CSSProperties = {
  border: `1px solid ${T.border}`, borderRadius: T.radiusSm, padding: '3px 6px', fontSize: 12, fontFamily: T.font,
  background: T.bg, color: T.fg, width: '100%', boxSizing: 'border-box',
};
const dugme = (vurgu?: boolean): CSSProperties => ({
  whiteSpace: 'nowrap',
  border: `1px solid ${vurgu ? T.blue : T.border}`, background: vurgu ? T.blue : T.bg, color: vurgu ? '#fff' : T.fg,
  borderRadius: T.radiusSm, padding: '4px 10px', fontSize: 12, fontFamily: T.font, cursor: 'pointer',
});

const TeklifEkrani = () => {
  const kayitId = useRecordId();
  const nesne = useSelectedObjectMetadata() as { nameSingular?: string } | null;
  const [t, setT] = useState<Teklif | null>(null);
  const [kalemler, setKalemler] = useState<Kalem[]>([]);
  const [katalog, setKatalog] = useState<Katalog[]>([]);
  const [taslak, setTaslak] = useState<Record<string, Record<string, string>>>({});
  const [hata, setHata] = useState<string | null>(null);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);   // çift tıklamayla iki kez işlem yapılmasın
  const [yeniKat, setYeniKat] = useState({ id: '', miktar: '1', bolum: '' });
  const [ozel, setOzel] = useState({ ad: '', miktar: '1', fiyat: '', fpb: 'USD', maliyet: '', mpb: 'USD', odeme: 'ONE_TIME', tur: 'OTHER', bolum: '' });
  const c = new RestApiClient();

  const yukle = async () => {
    if (!kayitId) return;
    try {
      const q = (await c.get(`/rest/quotes/${kayitId}`)) as { data: { quote: Teklif } };
      setT(q.data.quote);
      const l = (await c.get('/rest/quoteLines', { query: { limit: 200, filter: `quoteId[eq]:${kayitId}` } })) as { data: { quoteLines: Kalem[] } };
      setKalemler([...l.data.quoteLines].sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0)));
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  };
  const tazele = () => { [1500, 4000, 8000].forEach((ms) => setTimeout(yukle, ms)); };

  useEffect(() => {
    yukle();
    (async () => {
      try {
        const k = (await c.get('/rest/catalogItems', { query: { limit: 200 } })) as { data: { catalogItems: Katalog[] } };
        setKatalog(k.data.catalogItems.filter((x) => x.active !== false).sort((a, b) => (a.name ?? '').localeCompare(b.name ?? '', 'tr')));
      } catch { /* katalog okunamazsa yalnız özel kalem */ }
    })();
  }, [kayitId]);

  if (nesne?.nameSingular && nesne.nameSingular !== 'quote') return <Kabuk>Bu widget yalnız teklif sayfasında çalışır.</Kabuk>;
  if (!t) return <Kabuk hata={hata} yukleniyor={!hata} />;
  const acik = ACIK.has(t.status ?? 'DRAFT');
  const rap = t.revenueReporting?.currencyCode ?? 'USD';

  const yap = async (is: () => Promise<unknown>, tamam: string) => {
    if (mesgul) return;
    setMesgul(true);
    setMesaj('Kaydediliyor…');
    try { await is(); setMesaj(tamam); yukle(); tazele(); } catch (e) { setMesaj(`Hata: ${e instanceof Error ? e.message : String(e)}`); }
    finally { setMesgul(false); }
  };
  const alanDegis = (id: string, alan: string, v: string) => setTaslak((s) => ({ ...s, [id]: { ...(s[id] ?? {}), [alan]: v } }));
  const kaydet = () => yap(async () => {
    for (const [id, d] of Object.entries(taslak)) {
      const k = kalemler.find((x) => x.id === id);
      if (!k) continue;
      const y: Record<string, unknown> = {};
      if ('quantity' in d) y.quantity = sayi(d.quantity);
      if ('discountPercent' in d) y.discountPercent = sayi(d.discountPercent);
      if ('months' in d) y.months = sayi(d.months);
      if ('unitPrice' in d) y.unitPrice = para(sayi(d.unitPrice), k.unitPrice?.currencyCode ?? 'USD');
      if ('unitCost' in d) y.unitCost = para(sayi(d.unitCost), k.unitCost?.currencyCode ?? 'USD');
      if ('billing' in d) y.billing = d.billing;
      if ('section' in d) y.section = d.section || null;
      if (Object.keys(y).length) await c.patch(`/rest/quoteLines/${id}`, y);
    }
    setTaslak({});
  }, 'Kaydedildi; hesaplar birkaç saniye içinde güncellenir.');
  const sira = () => Math.max(0, ...kalemler.map((k) => k.sortOrder ?? 0)) + 1;
  const katalogEkle = () => yeniKat.id && yap(() => c.post('/rest/quoteLines', {
    quoteId: t.id, catalogItemId: yeniKat.id, quantity: sayi(yeniKat.miktar) ?? 1, sortOrder: sira(), section: yeniKat.bolum || null,
  }), 'Kalem eklendi.');
  const ozelEkle = () => ozel.ad && yap(() => c.post('/rest/quoteLines', {
    quoteId: t.id, name: ozel.ad, quantity: sayi(ozel.miktar) ?? 1, unitPrice: para(sayi(ozel.fiyat), ozel.fpb),
    unitCost: para(sayi(ozel.maliyet), ozel.mpb), billing: ozel.odeme, costType: ozel.tur, sortOrder: sira(), section: ozel.bolum || null,
  }), 'Özel kalem eklendi.');
  const sil = (id: string) => yap(() => c.delete(`/rest/quoteLines/${id}`), 'Kalem silindi.');
  const durum = (s: string) => yap(() => c.patch(`/rest/quotes/${t.id}`, { status: s }), `Durum: ${DURUM[s]}.`);
  const yeniSurum = () => yap(async () => {
    const yeni = (await c.post('/rest/quotes', {
      opportunityId: t.opportunityId, contractMonths: t.contractMonths, validUntil: t.validUntil, channelShareRate: t.channelShareRate,
      channelShareBase: t.channelShareBase, channelShareScope: t.channelShareScope, priceEscalation: t.priceEscalation,
      priceEscalationRate: t.priceEscalationRate,
    })) as { data: { createQuote: { id: string } } };
    for (const k of kalemler) {
      const kopya: Record<string, unknown> = { quoteId: yeni.data.createQuote.id };
      KOPYA_ALANLARI.forEach((a) => { if (k[a] !== null && k[a] !== undefined) kopya[a] = k[a]; });
      await c.post('/rest/quoteLines', kopya);
    }
    navigate(AppPath.RecordShowPage, { objectNameSingular: 'quote', objectRecordId: yeni.data.createQuote.id });
  }, 'Yeni sürüm oluşturuldu, açılıyor…');

  const bolumler = [...new Set(kalemler.map((k) => k.section || ''))];
  const deg = (k: Kalem, a: string, v: string) => taslak[k.id]?.[a] ?? v;
  const formul = (k: Kalem) => {
    const m = k.months ?? t.contractMonths;
    const f = bicim(tutar(k.unitPrice));
    const ind = k.discountPercent ? ` × (1 − %${k.discountPercent})` : '';
    if (k.billing === 'MONTHLY') return `${k.quantity ?? 0} × ${f}${ind} × ${m ?? 0} ay`;
    if (k.billing === 'YEARLY') return `${k.quantity ?? 0} × ${f}${ind} × ${m ?? 0}/12 yıl`;
    return `${k.quantity ?? 0} × ${f}${ind}`;
  };

  return (
    <Kabuk>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <span style={{ fontSize: 15, fontWeight: 600 }}>{t.name}</span>
        <span style={{ fontSize: 12, color: T.fg2 }}>Sürüm {t.version ?? '—'} · {DURUM[t.status ?? 'DRAFT']}
          {t.validUntil ? ` · geçerlilik ${t.validUntil.slice(0, 10).split('-').reverse().join('.')}` : ''}
          {t.contractMonths ? ` · ${t.contractMonths} ay` : ''}</span>
      </div>
      {t.systemWarning && <div style={{ fontSize: 12, color: T.red, marginBottom: 8 }}>{t.systemWarning}</div>}
      {t.approverId && !t.approvedById && <div style={{ fontSize: 12, color: T.fg2, marginBottom: 8 }}>Marj kuralı gereği onay gerekiyor; onaylayıcıya görev açılır.</div>}

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
        <Kpi label={`Gelir (${rap})`} value={bicim(tutar(t.revenueReporting))} />
        <Kpi label="Maliyet" value={bicim(tutar(t.costReporting))} />
        <Kpi label="Kanal payı" value={bicim(tutar(t.channelShareReporting))} />
        <Kpi label="Brüt kâr" value={bicim(tutar(t.grossProfitReporting))} />
        <Kpi label="Marj" value={t.marginPercent === null || t.marginPercent === undefined ? '—' : `%${t.marginPercent}`} accent={T.blue} />
      </div>
      {t.currencyBreakdown && Object.keys(t.currencyBreakdown).length > 1 && (
        <div style={{ fontSize: 12, color: T.fg2, marginBottom: 12 }}>
          Para birimine göre: {Object.entries(t.currencyBreakdown).map(([pb, v]) => `${pb} gelir ${bicim(v.gelir)} / maliyet ${bicim(v.maliyet)}`).join(' · ')}
        </div>
      )}

      {(t.contractMonths ?? 0) > 12 && (
        <div style={{ fontSize: 12, color: T.fg2, marginBottom: 12 }}>
          Enflasyon (yıllık, maliyete{t.priceEscalation === 'INFLATION' ? ' ve fiyata' : ''} yıl yıl uygulanır{t.sentAt ? '; gönderimde sabitlendi' : ''}):{' '}
          {Object.entries(t.inflationUsed?.oranlar ?? {}).length
            ? Object.entries(t.inflationUsed?.oranlar ?? {}).map(([pb, o]) =>
                `${pb} ${o.slice(0, Math.ceil((t.contractMonths ?? 0) / 12)).map((v) => `%${v.toLocaleString('tr-TR', { maximumFractionDigits: 1 })}`).join(' → ')}`).join(' · ')
            : 'öngörü yok'}
        </div>
      )}

      {/* Kalemler: her kalem bir kart; alanlar dar panelde alt satıra kayar (yan panelde yatay kaydırma olmasın) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 8 }}>
        {bolumler.map((b) => (
          <div key={`b-${b}`} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {b && <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{b}</div>}
            {kalemler.filter((k) => (k.section || '') === b).map((k) => (
              <div key={k.id} style={{ border: `1px solid ${T.border}`, borderRadius: T.radius, padding: '8px 10px', background: T.bg }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                  <div style={{ minWidth: 160, flex: '1 1 200px' }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{k.name}</div>
                    <div style={{ fontSize: 11, color: T.fg3 }}>
                      {[k.costType ? MALIYET[k.costType] : null, k.unit, k.optionGroup ? `seçenek ${k.optionGroup}${k.isDefaultOption ? ' (varsayılan)' : ''}` : null]
                        .filter(Boolean).join(' · ')}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    <div style={{ fontSize: 13 }}>Gelir {bicim(tutar(k.lineRevenue), k.lineRevenue?.currencyCode)}
                      <span style={{ color: T.fg3 }}> · Maliyet {bicim(tutar(k.lineCost), k.lineCost?.currencyCode)}</span></div>
                    <div style={{ fontSize: 11, color: T.fg3 }}>{formul(k)}</div>
                  </div>
                  {acik && <button style={dugme()} onClick={() => sil(k.id)}>Sil</button>}
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                  {[
                    ['Miktar', 'quantity', String(k.quantity ?? ''), 70, null],
                    ['Birim fiyat', 'unitPrice', String(tutar(k.unitPrice) ?? ''), 110,
                      `${k.unitPrice?.currencyCode ?? ''}${tutar(k.listPrice) ? ` · liste ${bicim(tutar(k.listPrice))}` : ''}`],
                    ['İndirim %', 'discountPercent', String(k.discountPercent ?? ''), 70, null],
                    ['Süre (ay)', 'months', String(k.months ?? ''), 70, k.months ? null : `teklif: ${t.contractMonths ?? '—'}`],
                    ['Birim maliyet', 'unitCost', String(tutar(k.unitCost) ?? ''), 110, k.unitCost?.currencyCode ?? ''],
                  ].map(([etiket, alan, v, gen, not]) => (
                    <label key={alan as string} style={{ display: 'flex', flexDirection: 'column', gap: 2, fontSize: 11, color: T.fg3, width: gen as number }}>
                      {etiket}
                      {acik
                        ? <input style={giris} value={deg(k, alan as string, v as string)} onChange={(e) => alanDegis(k.id, alan as string, deger(e))} />
                        : <span style={{ fontSize: 12, color: T.fg }}>{(v as string) || '—'}</span>}
                      {not && <span style={{ fontSize: 10 }}>{not as string}</span>}
                    </label>
                  ))}
                  <label style={{ display: 'flex', flexDirection: 'column', gap: 2, fontSize: 11, color: T.fg3, width: 120 }}>
                    Ödeme
                    {acik
                      ? <select style={giris} value={deg(k, 'billing', k.billing ?? 'ONE_TIME')} onChange={(e) => alanDegis(k.id, 'billing', deger(e))}>
                          {Object.entries(ODEME).map(([v, a]) => <option key={v} value={v}>{a}</option>)}</select>
                      : <span style={{ fontSize: 12, color: T.fg }}>{ODEME[k.billing ?? 'ONE_TIME']}</span>}
                  </label>
                </div>
              </div>
            ))}
          </div>
        ))}
        {!kalemler.length && <div style={{ fontSize: 13, color: T.fg3 }}>Henüz kalem yok.</div>}
      </div>
      {acik && Object.keys(taslak).length > 0 && <button style={dugme(true)} onClick={kaydet}>Değişiklikleri kaydet</button>}

      {acik && (
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 16 }}>
          <div style={{ flex: '1 1 280px', border: `1px solid ${T.border}`, borderRadius: T.radius, padding: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Katalogdan ekle</div>
            <select style={{ ...giris, marginBottom: 6 }} value={yeniKat.id} onChange={(e) => setYeniKat({ ...yeniKat, id: deger(e) })}>
              <option value="">Katalog kalemi seçin…</option>
              {katalog.map((k) => <option key={k.id} value={k.id}>{k.name}{k.unit ? ` (${k.unit})` : ''}</option>)}
            </select>
            <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
              <input style={giris} placeholder="Miktar" value={yeniKat.miktar} onChange={(e) => setYeniKat({ ...yeniKat, miktar: deger(e) })} />
              <input style={giris} placeholder="Bölüm (isteğe bağlı)" value={yeniKat.bolum} onChange={(e) => setYeniKat({ ...yeniKat, bolum: deger(e) })} />
            </div>
            <button style={dugme(true)} onClick={katalogEkle}>Ekle</button>
            {!katalog.length && <div style={{ fontSize: 11, color: T.fg3, marginTop: 6 }}>Katalog boş: Katalog menüsünden kalem ekleyin.</div>}
          </div>
          <div style={{ flex: '2 1 380px', border: `1px solid ${T.border}`, borderRadius: T.radius, padding: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Teklife özel kalem</div>
            <input style={{ ...giris, marginBottom: 6 }} placeholder="Ad" value={ozel.ad} onChange={(e) => setOzel({ ...ozel, ad: deger(e) })} />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginBottom: 6 }}>
              <input style={giris} placeholder="Miktar" value={ozel.miktar} onChange={(e) => setOzel({ ...ozel, miktar: deger(e) })} />
              <input style={giris} placeholder="Birim fiyat" value={ozel.fiyat} onChange={(e) => setOzel({ ...ozel, fiyat: deger(e) })} />
              <select style={giris} value={ozel.fpb} onChange={(e) => setOzel({ ...ozel, fpb: deger(e) })}>{PB.map((p) => <option key={p} value={p}>{p}</option>)}</select>
              <select style={giris} value={ozel.odeme} onChange={(e) => setOzel({ ...ozel, odeme: deger(e) })}>{Object.entries(ODEME).map(([v, a]) => <option key={v} value={v}>{a}</option>)}</select>
              <input style={giris} placeholder="Birim maliyet" value={ozel.maliyet} onChange={(e) => setOzel({ ...ozel, maliyet: deger(e) })} />
              <select style={giris} value={ozel.mpb} onChange={(e) => setOzel({ ...ozel, mpb: deger(e) })}>{PB.map((p) => <option key={p} value={p}>{p}</option>)}</select>
              <select style={giris} value={ozel.tur} onChange={(e) => setOzel({ ...ozel, tur: deger(e) })}>{Object.entries(MALIYET).map(([v, a]) => <option key={v} value={v}>{a}</option>)}</select>
              <input style={giris} placeholder="Bölüm" value={ozel.bolum} onChange={(e) => setOzel({ ...ozel, bolum: deger(e) })} />
            </div>
            <button style={dugme(true)} onClick={ozelEkle}>Ekle</button>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16, alignItems: 'center' }}>
        {(t.status === 'DRAFT' || t.status === 'APPROVED' || !t.status) && <button style={dugme(true)} onClick={() => durum('SENT')}>Gönderildi olarak işaretle</button>}
        {t.status === 'PENDING_APPROVAL' && <button style={dugme()} onClick={() => durum('APPROVED')}>Onayla (yetkiliyseniz)</button>}
        {t.status === 'SENT' && <><button style={dugme(true)} onClick={() => durum('ACCEPTED')}>Kabul edildi</button><button style={dugme()} onClick={() => durum('REJECTED')}>Reddedildi</button></>}
        <button style={dugme()} onClick={yeniSurum}>Yeni sürüm</button>
        {mesaj && <span style={{ fontSize: 12, color: T.fg2 }}>{mesaj}</span>}
      </div>
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: TEKLIF_EKRANI_FC,
  name: 'Teklif Ekranı',
  description: 'Teklif kalemleri (katalogdan / özel), P&L özeti, durum ve yeni sürüm; teklif kayıt sayfası için.',
  component: TeklifEkrani,
  widgetAvailability: { pageLayoutType: PageLayoutType.RECORD_PAGE },
});
