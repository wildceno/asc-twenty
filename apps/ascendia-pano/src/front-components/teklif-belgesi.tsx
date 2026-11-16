import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';
import { useRecordId } from 'twenty-sdk/front-component';
import { RestApiClient } from 'twenty-client-sdk/rest';
import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';

import { TEKLIF_BELGESI_FC } from 'src/constants/universal-identifiers';
import { Kabuk, T } from 'src/lib/ui';

// Teklif belgesi (liste 15b; plan: kararlar/2026-11-13-teklif-modulu-plan.md). Teklif kayıt sayfasında "Belge" sekmesi:
// şablon seçimi, kaldırılabilir bölümleri çıkarma, teklifte doldurulan alanlar, belge üretimi (Word / PowerPoint, PDF).
// Üretimi hesap motoru ve belge servisi yapar; ekran isteği yazar ve sonucu bekler. Gönderilmiş teklif salt okunur
// (belge yeniden üretilebilir).
type YerTutucu = { ad: string; tur: 'crm' | 'otomatik' | 'doldurulacak' };
type Sablon = { id: string; name?: string; status?: string | null; isDefault?: boolean | null; placeholders?: YerTutucu[] | null };
type Bolum = {
  id: string; name?: string; sortOrder?: number | null; sectionType?: string | null; removable?: boolean | null;
  defaultText?: string | null; placeholders?: string[] | null; sourceRef?: string | null;
};
// Motorla aynı (paketler/sablon.py): akış şablonunda CRM'de tanımlanan içerik bölümü
const CRM_BOLUMU = 'CRM (içerik bölümü)';
type Dosya = { label?: string; url?: string; extension?: string };
type Teklif = {
  id: string; name?: string; status?: string | null; quoteTemplateId?: string | null;
  documentSections?: { sira: number; ad?: string; dahil: boolean }[] | null; fillValues?: Record<string, string> | null;
  documentRequest?: string | null; documentStatus?: string | null; documents?: Dosya[] | null;
  opportunityId?: string | null; approverId?: string | null; approvedById?: string | null;
  signerId?: string | null; esignRequest?: string | null; esignStatus?: string | null; esignMessage?: string | null;
  esignSentAt?: string | null; esignCheckedAt?: string | null;
};

const ACIK = new Set(['DRAFT', 'PENDING_APPROVAL', 'APPROVED']);
const TUR: Record<string, string> = { FIXED: 'sabit', FILL: 'teklifte doldurulur', AUTO: 'tekliften otomatik' };
const BICIM: Record<string, string> = { BOTH: 'Word / PowerPoint + PDF', NATIVE: 'Word / PowerPoint', PDF: 'PDF' };

const deger = (e: unknown) => {
  const x = e as { value?: string; target?: { value?: string }; detail?: { value?: string } };
  return x?.value ?? x?.target?.value ?? x?.detail?.value ?? '';
};
const isaret = (e: unknown) => {
  const x = e as { checked?: boolean; target?: { checked?: boolean }; detail?: { checked?: boolean } };
  return Boolean(x?.checked ?? x?.target?.checked ?? x?.detail?.checked);
};
const giris: CSSProperties = {
  border: `1px solid ${T.border}`, borderRadius: T.radiusSm, padding: '3px 6px', fontSize: 12, fontFamily: T.font,
  background: T.bg, color: T.fg, boxSizing: 'border-box',
};
const dugme = (vurgu?: boolean): CSSProperties => ({
  whiteSpace: 'nowrap', border: `1px solid ${vurgu ? T.blue : T.border}`, background: vurgu ? T.blue : T.bg,
  color: vurgu ? '#fff' : T.fg, borderRadius: T.radiusSm, padding: '4px 10px', fontSize: 12, fontFamily: T.font, cursor: 'pointer',
});
type Kisi = { id: string; name?: { firstName?: string; lastName?: string }; emails?: { primaryEmail?: string } };
const IMZA_DURUM: Record<string, string> = {
  SENT: 'İmzaya gönderildi', DELIVERED: 'İmzalayan açtı', COMPLETED: 'İmzalandı', DECLINED: 'Reddedildi', VOIDED: 'İptal edildi', ERROR: 'Hata',
};
const kisiAdi = (k: Kisi) => [k.name?.firstName, k.name?.lastName].filter(Boolean).join(' ') || k.emails?.primaryEmail || '—';
const tarihSaat = (s?: string | null) => (s ? new Date(s).toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' }) : '');
const kart: CSSProperties = { border: `1px solid ${T.border}`, borderRadius: T.radius, padding: '8px 10px', background: T.bg };

const TeklifBelgesi = () => {
  const kayitId = useRecordId();
  const [t, setT] = useState<Teklif | null>(null);
  const [sablonlar, setSablonlar] = useState<Sablon[]>([]);
  const [bolumler, setBolumler] = useState<Bolum[]>([]);
  const [dahil, setDahil] = useState<Record<number, boolean>>({});
  const [alanlar, setAlanlar] = useState<Record<string, string>>({});
  const [degisti, setDegisti] = useState(false);
  const [bicim, setBicim] = useState('BOTH');
  const [hata, setHata] = useState<string | null>(null);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [kisiler, setKisiler] = useState<Kisi[]>([]);
  const c = new RestApiClient();

  const yukle = async (taslakKoru = false) => {
    if (!kayitId) return;
    try {
      const q = ((await c.get(`/rest/quotes/${kayitId}`)) as { data: { quote: Teklif } }).data.quote;
      setT(q);
      const s = ((await c.get('/rest/quoteTemplates', { query: { limit: 100 } })) as { data: { quoteTemplates: Sablon[] } }).data.quoteTemplates;
      setSablonlar(s.filter((x) => x.status === 'ACTIVE' || x.id === q.quoteTemplateId));
      // İmzalayacak kişi adayları: fırsatın şirketindeki kişiler; şirket yoksa ya da kişisi yoksa tüm kişiler
      let adaylar: Kisi[] = [];
      if (q.opportunityId) {
        const f = ((await c.get(`/rest/opportunities/${q.opportunityId}`)) as { data: { opportunity: { companyId?: string | null } } }).data.opportunity;
        if (f.companyId) {
          adaylar = ((await c.get('/rest/people', { query: { limit: 200, filter: `companyId[eq]:${f.companyId}` } })) as { data: { people: Kisi[] } }).data.people;
        }
      }
      if (!adaylar.length) adaylar = ((await c.get('/rest/people', { query: { limit: 200 } })) as { data: { people: Kisi[] } }).data.people;
      setKisiler([...adaylar].sort((x, y) => kisiAdi(x).localeCompare(kisiAdi(y), 'tr')));
      if (q.quoteTemplateId) {
        const b = ((await c.get('/rest/templateSections', { query: { limit: 200, filter: `quoteTemplateId[eq]:${q.quoteTemplateId}` } })) as
          { data: { templateSections: Bolum[] } }).data.templateSections;
        setBolumler([...b].sort((x, y) => (x.sortOrder ?? 0) - (y.sortOrder ?? 0)));
      } else setBolumler([]);
      if (!taslakKoru) {
        const d: Record<number, boolean> = {};
        (q.documentSections ?? []).forEach((x) => { d[x.sira] = x.dahil; });
        setDahil(d);
        setAlanlar({ ...(q.fillValues ?? {}) });
        setDegisti(false);
      }
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  };
  useEffect(() => { yukle(); }, [kayitId]);

  if (hata) return <Kabuk><div style={{ color: T.red, fontSize: 13 }}>{hata}</div></Kabuk>;
  if (!t) return <Kabuk><div style={{ color: T.fg3, fontSize: 13 }}>Yükleniyor…</div></Kabuk>;

  const acik = ACIK.has(t.status ?? 'DRAFT');
  const sablon = sablonlar.find((s) => s.id === t.quoteTemplateId);
  const tur: Record<string, string> = {};
  (sablon?.placeholders ?? []).forEach((y) => { tur[y.ad] = y.tur; });
  const doldurulacak = (b: Bolum) => (b.placeholders ?? []).filter((y) => tur[y] === 'doldurulacak');
  const varsayilan = (b: Bolum) => (doldurulacak(b).length === 1 && b.sectionType === 'FILL' ? b.defaultText ?? '' : '');
  const goruldu = new Set<string>();

  const kaydetVeri = () => ({
    documentSections: bolumler.map((b) => ({ sira: b.sortOrder ?? 0, ad: b.name, dahil: b.removable ? dahil[b.sortOrder ?? 0] !== false : true })),
    fillValues: alanlar,
  });
  const isle = async (f: () => Promise<void>, basari: string, bekle = [1500, 4000, 8000]) => {
    if (mesgul) return;
    setMesgul(true);
    setMesaj(null);
    try {
      await f();
      setMesaj(basari);
      bekle.forEach((ms) => setTimeout(() => yukle(), ms));
    } catch (e) {
      setMesaj(`İşlem yapılamadı: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setMesgul(false);
    }
  };
  const sablonSec = (id: string) => isle(async () => {
    await c.patch(`/rest/quotes/${kayitId}`, { quoteTemplateId: id || null, documentSections: null });
  }, 'Şablon değişti.', [800, 2500]);
  const kaydet = () => isle(async () => { await c.patch(`/rest/quotes/${kayitId}`, kaydetVeri()); }, 'Kaydedildi.');
  const uret = () => isle(async () => {
    await c.patch(`/rest/quotes/${kayitId}`, { ...(acik && degisti ? kaydetVeri() : {}), documentRequest: bicim });
  }, 'Belge hazırlanıyor… (PDF ile birlikte 10-30 saniye sürebilir)', [3000, 8000, 15000, 25000, 40000, 60000]);

  return (
    <Kabuk>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Şablon</span>
        <select style={{ ...giris, minWidth: 220 }} disabled={!acik} value={t.quoteTemplateId ?? ''} onChange={(e) => sablonSec(deger(e))}>
          <option value="">Şablon seçin…</option>
          {sablonlar.map((s) => <option key={s.id} value={s.id}>{s.name}{s.isDefault ? ' (varsayılan)' : ''}{s.status !== 'ACTIVE' ? ' — aktif değil' : ''}</option>)}
        </select>
        {!sablonlar.length && <span style={{ fontSize: 12, color: T.fg3 }}>Aktif şablon yok (Yönetim → Teklif Şablonları).</span>}
      </div>

      {bolumler.length > 0 && <div style={{ fontSize: 13, fontWeight: 600, margin: '4px 0 8px' }}>Bölümler</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 8 }}>
        {bolumler.map((b) => {
          const sira = b.sortOrder ?? 0;
          const icinde = b.removable ? dahil[sira] !== false : true;
          const crm = b.sourceRef === CRM_BOLUMU;
          const alanAdlari = crm ? (b.sectionType === 'FILL' ? [`bolum:${b.id}`] : [])
            : doldurulacak(b).filter((a) => { if (goruldu.has(a)) return false; goruldu.add(a); return true; });
          const icerikSlayti = (b.placeholders ?? []).includes('icerik');
          return (
            <div key={b.id} style={{ ...kart, opacity: icinde ? 1 : 0.55 }}>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
                <input type="checkbox" checked={icinde} disabled={!acik || !b.removable}
                  onChange={(e) => { setDahil({ ...dahil, [sira]: isaret(e) }); setDegisti(true); }} />
                <span style={{ fontWeight: 500 }}>{crm ? '' : `${sira}. `}{b.name}</span>
                <span style={{ fontSize: 11, color: T.fg3 }}>
                  {icerikSlayti ? 'içerik slaytı (aşağıdaki bölümler yazılır)' : `${crm ? 'içerik · ' : ''}${TUR[b.sectionType ?? 'FIXED']}`}{b.removable ? '' : ' · çıkarılamaz'}
                </span>
              </label>
              {icinde && alanAdlari.map((ad) => (
                <label key={ad} style={{ display: 'flex', flexDirection: 'column', gap: 2, fontSize: 11, color: T.fg3, marginTop: 8 }}>
                  {crm ? 'Metin' : `{{${ad}}}`}
                  <textarea style={{ ...giris, width: '100%', minHeight: crm ? 96 : 56, resize: 'vertical' }} disabled={!acik}
                    value={alanlar[ad] ?? (crm ? b.defaultText ?? '' : varsayilan(b))}
                    onChange={(e) => { setAlanlar({ ...alanlar, [ad]: deger(e) }); setDegisti(true); }} />
                </label>
              ))}
            </div>
          );
        })}
      </div>
      {acik && degisti && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <button style={dugme(true)} onClick={kaydet}>Değişiklikleri kaydet</button>
          <button style={dugme()} onClick={() => yukle()}>Vazgeç</button>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 12 }}>
        <select style={giris} value={bicim} onChange={(e) => setBicim(deger(e))}>
          {Object.entries(BICIM).map(([v, a]) => <option key={v} value={v}>{a}</option>)}
        </select>
        <button style={dugme(true)} disabled={!t.quoteTemplateId || Boolean(t.documentRequest)} onClick={uret}>
          {t.documentRequest ? 'Hazırlanıyor…' : 'Belge üret'}
        </button>
        {mesaj && <span style={{ fontSize: 12, color: T.fg2 }}>{mesaj}</span>}
      </div>
      {t.documentStatus && (
        <div style={{ fontSize: 12, color: t.documentStatus.startsWith('Üretilemedi') ? T.red : T.fg2, marginTop: 8 }}>{t.documentStatus}</div>
      )}
      {(t.documents ?? []).length > 0 && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
          {(t.documents ?? []).map((d) => (
            <a key={d.url ?? d.label} href={d.url} target="_blank" rel="noreferrer" style={{ fontSize: 13, color: T.blue }}>{d.label}</a>
          ))}
        </div>
      )}
      <div style={{ ...kart, marginTop: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>E-imza (DocuSign)</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: T.fg2 }}>İmzalayacak kişi</span>
          <select style={{ ...giris, minWidth: 220 }} disabled={Boolean(t.esignStatus && ['SENT', 'DELIVERED', 'COMPLETED'].includes(t.esignStatus))}
            value={t.signerId ?? ''} onChange={(e) => isle(async () => { await c.patch(`/rest/quotes/${kayitId}`, { signerId: deger(e) || null }); }, 'İmzalayacak kişi seçildi.', [800])}>
            <option value="">Seçin…</option>
            {kisiler.map((k) => <option key={k.id} value={k.id}>{kisiAdi(k)}{k.emails?.primaryEmail ? ` · ${k.emails.primaryEmail}` : ''}</option>)}
          </select>
          {!(t.esignStatus && ['SENT', 'DELIVERED', 'COMPLETED'].includes(t.esignStatus)) && (
            <button style={dugme(true)} disabled={!t.signerId || !(t.documents ?? []).some((d) => (d.label ?? '').toLowerCase().endsWith('.pdf')) || Boolean(t.esignRequest)}
              onClick={() => isle(async () => { await c.patch(`/rest/quotes/${kayitId}`, { esignRequest: 'SEND' }); }, 'DocuSign\'a gönderiliyor…', [3000, 8000, 15000])}>
              DocuSign ile imzaya gönder
            </button>
          )}
          {t.esignStatus && ['SENT', 'DELIVERED'].includes(t.esignStatus) && (
            <button style={dugme()} disabled={Boolean(t.esignRequest)}
              onClick={() => isle(async () => { await c.patch(`/rest/quotes/${kayitId}`, { esignRequest: 'CHECK' }); }, 'Durum soruluyor…', [3000, 8000, 15000])}>
              İmza durumunu şimdi kontrol et
            </button>
          )}
        </div>
        {(t.esignStatus || t.esignMessage) && (
          <div style={{ fontSize: 12, color: t.esignStatus === 'ERROR' || t.esignStatus === 'DECLINED' ? T.red : T.fg2, marginTop: 8 }}>
            {t.esignStatus ? `${IMZA_DURUM[t.esignStatus] ?? t.esignStatus}` : ''}
            {t.esignSentAt ? ` · gönderim ${tarihSaat(t.esignSentAt)}` : ''}
            {t.esignCheckedAt ? ` · son kontrol ${tarihSaat(t.esignCheckedAt)}` : ''}
            {t.esignMessage ? ` · ${t.esignMessage}` : ''}
          </div>
        )}
        <div style={{ fontSize: 11, color: T.fg3, marginTop: 6 }}>
          Son üretilen PDF gönderilir; şablonda {'{{imza}}'} varsa imza alanı oraya konur. İmza durumu 00:00, 08:00 ve 16:00'da kendiliğinden
          kontrol edilir; imzalanınca teklif Kabul olur ve imzalı PDF fırsatın Onaylanan Teklif alanına eklenir.
        </div>
      </div>
      {acik && (
        <div style={{ fontSize: 11, color: T.fg3, marginTop: 12 }}>
          Belgeyi müşteriye gönderdiğinizde Teklif sekmesinden "Gönderildi olarak işaretle"yi seçin: rakamlar fırsata yazılır.
        </div>
      )}
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: TEKLIF_BELGESI_FC,
  name: 'Teklif Belgesi',
  description: 'Teklif belgesi: şablon, bölüm seçimi, doldurulan alanlar, Word / PowerPoint ve PDF üretimi.',
  component: TeklifBelgesi,
  widgetAvailability: { pageLayoutType: PageLayoutType.RECORD_PAGE },
});
