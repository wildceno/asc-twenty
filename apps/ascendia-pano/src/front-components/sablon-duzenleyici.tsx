import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';
import { copyToClipboard, useRecordId } from 'twenty-sdk/front-component';
import { RestApiClient } from 'twenty-client-sdk/rest';
import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';

import { SABLON_DUZENLEYICI_FC } from 'src/constants/universal-identifiers';
import { Kabuk, T } from 'src/lib/ui';

// Şablon düzenleyici (liste 15a; plan: kararlar/2026-11-13-teklif-modulu-plan.md, 15a kararları). Teklif Şablonu kayıt
// sayfasında "Şablon" sekmesi. Dosyayı belge servisi okur, bölümleri hesap motoru yazar; burada bölüm türü, otomatik
// içerik, kaldırılabilirlik ve varsayılan metin düzenlenir, şablon aktif / varsayılan yapılır. Yer tutucu sözlüğü motordan.
type YerTutucu = { ad: string; tur: 'crm' | 'otomatik' | 'doldurulacak' | 'akis' | 'duzen'; aciklama: string; bolumler: string[] };
// Motorla aynı (paketler/sablon.py): CRM'de tanımlanan içerik bölümü işareti ve sıra başlangıcı
const CRM_BOLUMU = 'CRM (içerik bölümü)';
const CRM_SIRA = 100;
type Sablon = {
  id: string; name?: string; status?: string | null; isDefault?: boolean | null; format?: string | null; readAt?: string | null;
  readWarnings?: string | null; placeholders?: YerTutucu[] | null; templateFile?: { label?: string }[] | null;
};
type Bolum = {
  id: string; name?: string; sortOrder?: number | null; sectionType?: string | null; autoContent?: string | null;
  removable?: boolean | null; defaultText?: string | null; sourceRef?: string | null; textPreview?: string | null;
  placeholders?: string[] | null;
};

const DURUM: Record<string, string> = { DRAFT: 'Taslak', ACTIVE: 'Aktif', PASSIVE: 'Pasif' };
const TUR: Record<string, string> = { FIXED: 'Sabit (şablondan)', FILL: 'Teklifte doldurulur', AUTO: 'Otomatik (tekliften)' };
const OTO: Record<string, string> = { LINE_TABLE: 'Kalem tablosu', PRODUCT_DESCRIPTIONS: 'Ürün açıklamaları' };
const YT_GRUP: [YerTutucu['tur'], string][] = [
  ['crm', 'CRM\'den dolar'], ['otomatik', 'Otomatik bölüm işaretleri'], ['akis', 'Akış şablonu (PowerPoint içerik slaytı)'], ['duzen', 'Düzen (boşluk, sayfa sonu)'], ['doldurulacak', 'Teklifte satışçı doldurur (tanınmayan)'],
];

const deger = (e: unknown) => {
  const x = e as { value?: string; checked?: boolean; target?: { value?: string; checked?: boolean }; detail?: { value?: string } };
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
const kart: CSSProperties = { border: `1px solid ${T.border}`, borderRadius: T.radius, padding: '8px 10px', background: T.bg };
const etiket: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 2, fontSize: 11, color: T.fg3 };

const SablonDuzenleyici = () => {
  const kayitId = useRecordId();
  const [s, setS] = useState<Sablon | null>(null);
  const [bolumler, setBolumler] = useState<Bolum[]>([]);
  const [taslak, setTaslak] = useState<Record<string, Partial<Bolum>>>({});
  const [hata, setHata] = useState<string | null>(null);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [yeni, setYeni] = useState({ ad: '', tur: 'FIXED', oto: 'LINE_TABLE' });
  const c = new RestApiClient();

  const yukle = async () => {
    if (!kayitId) return;
    try {
      const r = (await c.get(`/rest/quoteTemplates/${kayitId}`)) as { data: { quoteTemplate: Sablon } };
      setS(r.data.quoteTemplate);
      const b = (await c.get('/rest/templateSections', { query: { limit: 200, filter: `quoteTemplateId[eq]:${kayitId}` } })) as
        { data: { templateSections: Bolum[] } };
      setBolumler([...b.data.templateSections].sort((x, y) => (x.sortOrder ?? 0) - (y.sortOrder ?? 0)));
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  };
  const tazele = () => { [1500, 4000, 8000].forEach((ms) => setTimeout(yukle, ms)); };
  useEffect(() => { yukle(); }, [kayitId]);

  const isle = async (f: () => Promise<void>, basari: string) => {
    if (mesgul) return;
    setMesgul(true);
    setMesaj(null);
    try {
      await f();
      setMesaj(basari);
      tazele();
    } catch (e) {
      setMesaj(`Kaydedilemedi: ${e instanceof Error ? e.message : String(e)} (şablonu yalnız Super-user ve Admin düzenler)`);
    } finally {
      setMesgul(false);
    }
  };
  const alan = (b: Bolum, a: keyof Bolum) => (taslak[b.id] && a in taslak[b.id] ? taslak[b.id][a] : b[a]);
  const degistir = (id: string, a: keyof Bolum, v: unknown) => setTaslak({ ...taslak, [id]: { ...(taslak[id] ?? {}), [a]: v } });
  const kaydet = () => isle(async () => {
    for (const [id, d] of Object.entries(taslak)) {
      const g: Record<string, unknown> = { ...d };
      if (g.sectionType && g.sectionType !== 'AUTO') g.autoContent = null;
      await c.patch(`/rest/templateSections/${id}`, g);
    }
    setTaslak({});
  }, 'Bölümler kaydedildi.');
  const sablonGuncelle = (g: Record<string, unknown>, basari: string) => isle(async () => { await c.patch(`/rest/quoteTemplates/${kayitId}`, g); }, basari);

  if (hata) return <Kabuk><div style={{ color: T.red, fontSize: 13 }}>{hata}</div></Kabuk>;
  if (!s) return <Kabuk><div style={{ color: T.fg3, fontSize: 13 }}>Yükleniyor…</div></Kabuk>;
  const dosya = (s.templateFile ?? [])[0];
  const yt = s.placeholders ?? [];
  const akis = yt.some((y) => y.ad === 'icerik' && y.bolumler.length > 0);
  const dosyaBolumleri = bolumler.filter((b) => b.sourceRef !== CRM_BOLUMU);
  const icerikBolumleri = bolumler.filter((b) => b.sourceRef === CRM_BOLUMU);

  const bolumEkle = () => yeni.ad.trim() && isle(async () => {
    const sira = Math.max(CRM_SIRA, ...icerikBolumleri.map((b) => b.sortOrder ?? 0)) + 1;
    await c.post('/rest/templateSections', {
      quoteTemplateId: kayitId, name: yeni.ad.trim(), sortOrder: sira, sourceRef: CRM_BOLUMU, sectionType: yeni.tur,
      autoContent: yeni.tur === 'AUTO' ? yeni.oto : null, removable: yeni.tur !== 'AUTO' || yeni.oto !== 'LINE_TABLE',
    });
    setYeni({ ad: '', tur: 'FIXED', oto: 'LINE_TABLE' });
  }, 'Bölüm eklendi.');
  const tasi = (b: Bolum, yon: -1 | 1) => {
    const i = icerikBolumleri.findIndex((x) => x.id === b.id);
    const k = icerikBolumleri[i + yon];
    if (!k) return;
    isle(async () => {
      await c.patch(`/rest/templateSections/${b.id}`, { sortOrder: k.sortOrder });
      await c.patch(`/rest/templateSections/${k.id}`, { sortOrder: b.sortOrder });
    }, 'Sıra değişti.');
  };
  const bolumSil = (b: Bolum) => isle(async () => { await c.delete(`/rest/templateSections/${b.id}`); }, 'Bölüm silindi.');

  const bolumKarti = (b: Bolum, crm: boolean) => {
    const tur = (alan(b, 'sectionType') as string) ?? 'FIXED';
    const icerikSlayti = (b.placeholders ?? []).includes('icerik');
    return (
      <div key={b.id} style={kart}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ minWidth: 160, flex: '1 1 220px' }}>
            {crm
              ? <input style={{ ...giris, fontSize: 13, fontWeight: 500, width: '100%' }} value={(alan(b, 'name') as string) ?? ''}
                  onChange={(e) => degistir(b.id, 'name', deger(e))} />
              : <div style={{ fontSize: 13, fontWeight: 500 }}>{b.sortOrder}. {b.name}</div>}
            {!crm && <div style={{ fontSize: 11, color: T.fg3 }}>{b.sourceRef}{(b.placeholders ?? []).length ? ` · ${(b.placeholders ?? []).map((p) => `{{${p}}}`).join(' ')}` : ''}</div>}
            {!crm && b.textPreview && <div style={{ fontSize: 11, color: T.fg2, marginTop: 4 }}>{b.textPreview}</div>}
          </div>
          {crm && (
            <div style={{ display: 'flex', gap: 4 }}>
              <button style={dugme()} title="Yukarı" onClick={() => tasi(b, -1)}>↑</button>
              <button style={dugme()} title="Aşağı" onClick={() => tasi(b, 1)}>↓</button>
              <button style={dugme()} onClick={() => bolumSil(b)}>Sil</button>
            </div>
          )}
        </div>
        {icerikSlayti ? (
          <div style={{ fontSize: 12, color: T.fg2, marginTop: 6 }}>İçerik slaytı: aşağıdaki içerik bölümleri bu slayta yazılır ve gerektikçe çoğaltılır.</div>
        ) : (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, alignItems: 'flex-end' }}>
            <label style={{ ...etiket, width: 170 }}>Tür
              <select style={giris} value={tur} onChange={(e) => degistir(b.id, 'sectionType', deger(e))}>
                {Object.entries(TUR).map(([v, a]) => <option key={v} value={v}>{a}</option>)}</select>
            </label>
            {tur === 'AUTO' && (
              <label style={{ ...etiket, width: 150 }}>Otomatik içerik
                <select style={giris} value={(alan(b, 'autoContent') as string) ?? ''} onChange={(e) => degistir(b.id, 'autoContent', deger(e) || null)}>
                  <option value="">Seçin…</option>
                  {Object.entries(OTO).map(([v, a]) => <option key={v} value={v}>{a}</option>)}</select>
              </label>
            )}
            <label style={{ ...etiket, flexDirection: 'row', alignItems: 'center', gap: 6, fontSize: 12, color: T.fg }}>
              <input type="checkbox" checked={Boolean(alan(b, 'removable'))} onChange={(e) => degistir(b.id, 'removable', isaret(e))} />
              Teklifte kaldırılabilir
            </label>
          </div>
        )}
        {(tur === 'FILL' || (crm && tur === 'FIXED')) && (
          <label style={{ ...etiket, marginTop: 8 }}>{tur === 'FILL' ? 'Varsayılan metin (satışçı teklifte değiştirir)' : 'Metin'}
            <textarea style={{ ...giris, width: '100%', minHeight: crm ? 96 : 56, resize: 'vertical' }} value={(alan(b, 'defaultText') as string) ?? ''}
              onChange={(e) => degistir(b.id, 'defaultText', deger(e) || null)} />
          </label>
        )}
      </div>
    );
  };

  return (
    <Kabuk>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <span style={{ fontSize: 15, fontWeight: 600 }}>{s.name}</span>
        <span style={{ fontSize: 12, color: T.fg2 }}>
          {DURUM[s.status ?? 'DRAFT']}{s.isDefault ? ' · varsayılan' : ''}
          {s.format ? ` · ${s.format === 'DOCX' ? 'Word' : 'PowerPoint'}` : ''}
          {dosya ? ` · ${dosya.label ?? 'dosya'}` : ''}
          {s.readAt ? ` · okundu ${new Date(s.readAt).toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' })}` : ''}
        </span>
      </div>
      {s.readWarnings && <div style={{ fontSize: 12, color: T.red, marginBottom: 8 }}>{s.readWarnings}</div>}
      {!dosya && (
        <div style={{ ...kart, fontSize: 12, color: T.fg2, marginBottom: 12, lineHeight: 1.5 }}>
          <b>Şablon dosyası yükleyin:</b> Ana sayfa sekmesindeki <b>Şablon Dosyası</b> alanına .docx ya da .pptx dosyası yükleyin;
          birkaç saniye içinde bölümler burada görünür.<br />
          Bölümler: Word'de her <b>Başlık 1</b> yeni bölüm başlatır (öncesi ana kapak); PowerPoint'te her slayt bir bölümdür
          (ad = slayt başlığı; birkaç slaytı birleştirmek için slayt notuna <code>bölüm: Ad</code> yazın).
          Yer tutucular <code>{'{{ad}}'}</code> biçimindedir; kullanılabilir adlar aşağıda.
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center' }}>
        {s.status !== 'ACTIVE' && <button style={dugme(true)} onClick={() => sablonGuncelle({ status: 'ACTIVE' }, 'Şablon aktif.')}>Aktif yap</button>}
        {s.status === 'ACTIVE' && <button style={dugme()} onClick={() => sablonGuncelle({ status: 'DRAFT' }, 'Şablon taslağa alındı.')}>Taslağa al</button>}
        {s.status !== 'PASSIVE' && <button style={dugme()} onClick={() => sablonGuncelle({ status: 'PASSIVE', isDefault: false }, 'Şablon pasif.')}>Pasif yap</button>}
        {!s.isDefault && <button style={dugme()} onClick={() => sablonGuncelle({ isDefault: true }, 'Varsayılan şablon yapıldı.')}>Varsayılan yap</button>}
        {mesaj && <span style={{ fontSize: 12, color: T.fg2 }}>{mesaj}</span>}
      </div>

      {dosyaBolumleri.length > 0 && <div style={{ fontSize: 13, fontWeight: 600, margin: '4px 0 8px' }}>{akis ? 'Slaytlar' : 'Bölümler'}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 8 }}>
        {dosyaBolumleri.map((b) => bolumKarti(b, false))}
      </div>

      {akis && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>İçerik bölümleri</div>
          <div style={{ fontSize: 12, color: T.fg2, marginBottom: 8, lineHeight: 1.5 }}>
            Bu bölümler sırayla içerik slaytındaki <code>{'{{icerik}}'}</code> alanına yazılır; sığmazsa slayt çoğaltılır.
            Sabit bölümün metni burada yazılır; "teklifte doldurulur" bölümünü satışçı teklifin Belge sekmesinde yazar;
            otomatik bölüm kalem tablosu ya da ürün açıklamalarıdır. Metinde <code>{'{{musteri_adi}}'}</code> gibi yer tutucular kullanılabilir.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 8 }}>
            {icerikBolumleri.map((b) => bolumKarti(b, true))}
            {!icerikBolumleri.length && <div style={{ fontSize: 12, color: T.fg3 }}>Henüz içerik bölümü yok.</div>}
          </div>
          <div style={{ ...kart, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <label style={{ ...etiket, flex: '1 1 180px' }}>Yeni bölüm adı
              <input style={giris} value={yeni.ad} onChange={(e) => setYeni({ ...yeni, ad: deger(e) })} placeholder="ör. Hakkımızda" />
            </label>
            <label style={{ ...etiket, width: 170 }}>Tür
              <select style={giris} value={yeni.tur} onChange={(e) => setYeni({ ...yeni, tur: deger(e) })}>
                {Object.entries(TUR).map(([v, a]) => <option key={v} value={v}>{a}</option>)}</select>
            </label>
            {yeni.tur === 'AUTO' && (
              <label style={{ ...etiket, width: 150 }}>Otomatik içerik
                <select style={giris} value={yeni.oto} onChange={(e) => setYeni({ ...yeni, oto: deger(e) })}>
                  {Object.entries(OTO).map(([v, a]) => <option key={v} value={v}>{a}</option>)}</select>
              </label>
            )}
            <button style={dugme(true)} onClick={bolumEkle}>Ekle</button>
          </div>
        </div>
      )}
      {Object.keys(taslak).length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <button style={dugme(true)} onClick={kaydet}>Değişiklikleri kaydet</button>
          <button style={dugme()} onClick={() => setTaslak({})}>Vazgeç</button>
        </div>
      )}

      {yt.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Yer tutucular</div>
          {YT_GRUP.map(([g, baslik]) => {
            const l = yt.filter((y) => y.tur === g);
            if (!l.length) return null;
            return (
              <div key={g} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 12, color: T.fg2, marginBottom: 4 }}>{baslik}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {l.map((y) => (
                    <div key={y.ad} style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap', fontSize: 12 }}>
                      <button style={{ ...dugme(), padding: '1px 6px', fontFamily: 'monospace' }} title="Kopyala"
                        onClick={() => { copyToClipboard(`{{${y.ad}}}`); setMesaj(`{{${y.ad}}} kopyalandı.`); }}>{`{{${y.ad}}}`}</button>
                      <span style={{ color: T.fg2 }}>{y.aciklama}</span>
                      <span style={{ color: T.fg3, fontSize: 11 }}>{y.bolumler.length ? `kullanıldığı yer: ${y.bolumler.join(', ')}` : 'dosyada kullanılmıyor'}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: SABLON_DUZENLEYICI_FC,
  name: 'Şablon Düzenleyici',
  description: 'Teklif şablonunun bölümleri (tür, otomatik içerik, varsayılan metin), yer tutucu sözlüğü, aktif / varsayılan.',
  component: SablonDuzenleyici,
  widgetAvailability: { pageLayoutType: PageLayoutType.RECORD_PAGE },
});
