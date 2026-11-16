import { defineFrontComponent, PageLayoutType } from 'twenty-sdk/define';
import { RestApiClient } from 'twenty-client-sdk/rest';
import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';

import { SAGLIK_FC } from 'src/constants/universal-identifiers';
import { Kabuk, T, tabloStil } from 'src/lib/ui';

// Sistem Durumu (liste 7): hesap motoru, kur, yedek, takip iş akışı ve açık alarmlar. Motor 5 dakikada bir yazar;
// kalp atışı 15 dakikayı geçerse widget motorun durduğunu kendisi gösterir. Yalnız Admin / Super-user görür.
type Durum = {
  lastHeartbeatAt?: string | null;
  motorStartedAt?: string | null;
  lastRateDate?: string | null;
  lastBackupAt?: string | null;
  lastWorkflowRunAt?: string | null;
  lastWorkflowStatus?: string | null;
  errors24h?: number | null;
  lastError?: string | null;
  lastErrorAt?: string | null;
  portalStatus?: string | null;
};
type Alarm = { id: string; name: string; severity?: string; firstSeenAt?: string; repeatCount?: number; alarmStatus?: string };

const YESIL = 'var(--t-color-green, #30a46c)';
const TURUNCU = 'var(--t-color-orange, #f76b15)';
const dk = (iso?: string | null) => (iso ? (Date.now() - Date.parse(iso)) / 60000 : Infinity);
const once = (iso?: string | null) => {
  const m = dk(iso);
  if (!Number.isFinite(m)) return 'kayıt yok';
  if (m < 1) return 'az önce';
  if (m < 60) return `${Math.round(m)} dk önce`;
  if (m < 48 * 60) return `${Math.round(m / 60)} saat önce`;
  return `${Math.round(m / 1440)} gün önce`;
};
const trGun = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul' });

const Isik = ({ renk }: { renk: string }) => (
  <span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 5, background: renk, marginRight: 8 }} />
);

const SistemDurumu = () => {
  const [d, setD] = useState<Durum | null>(null);
  const [alarmlar, setAlarmlar] = useState<Alarm[]>([]);
  const [hata, setHata] = useState<string | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);

  useEffect(() => {
    const c = new RestApiClient();
    (async () => {
      try {
        const s = (await c.get('/rest/systemStatuses', { query: { limit: 1 } })) as { data: { systemStatuses: Durum[] } };
        setD(s.data.systemStatuses[0] ?? {});
        const a = (await c.get('/rest/systemAlarms', { query: { limit: 60 } })) as { data: { systemAlarms: Alarm[] } };
        setAlarmlar(a.data.systemAlarms.filter((x) => x.alarmStatus === 'OPEN'));
      } catch (e) {
        const m = e instanceof Error ? e.message : String(e);
        setHata(/forbidden|permission|403/i.test(m) ? 'Bu widget yalnız yöneticiler içindir.' : m);
      } finally {
        setYukleniyor(false);
      }
    })();
  }, []);

  if (yukleniyor || hata || !d) return <Kabuk hata={hata && !hata.startsWith('Bu widget') ? hata : null} yukleniyor={yukleniyor}>{hata}</Kabuk>;

  const bugun = trGun.format(new Date());
  const motorDurdu = dk(d.lastHeartbeatAt) > 15;
  const satirlar: { ad: string; deger: string; renk: string; not?: string }[] = [
    {
      ad: 'Hesap motoru',
      deger: motorDurdu ? `Yanıt vermiyor (son kalp atışı ${once(d.lastHeartbeatAt)})` : `Çalışıyor · son kalp atışı ${once(d.lastHeartbeatAt)}`,
      renk: motorDurdu ? T.red : YESIL,
      not: d.motorStartedAt ? `başlangıç ${once(d.motorStartedAt)}` : undefined,
    },
    {
      ad: 'Döviz kuru',
      deger: d.lastRateDate ? `Son kur ${d.lastRateDate.split('-').reverse().join('.')}` : 'Kur yok',
      renk: d.lastRateDate === bugun ? YESIL : TURUNCU,
      not: d.lastRateDate === bugun ? undefined : 'bugünün kuru 16:05 sonrası gelir; hafta sonu ve tatilde yayımlanmaz',
    },
    {
      ad: 'Yedek',
      deger: d.lastBackupAt ? `Son yedek ${once(d.lastBackupAt)}` : 'Yedek kaydı yok',
      renk: dk(d.lastBackupAt) > 26 * 60 ? T.red : YESIL,
    },
    {
      ad: 'Takip iş akışı',
      deger: d.lastWorkflowRunAt ? `${d.lastWorkflowStatus ?? '—'} · ${once(d.lastWorkflowRunAt)}` : 'Henüz çalışmadı',
      renk: d.lastWorkflowStatus === 'FAILED' ? TURUNCU : YESIL,
    },
    {
      ad: 'Hatalar (24 saat)',
      deger: `${d.errors24h ?? 0}`,
      renk: (d.errors24h ?? 0) > 0 ? TURUNCU : YESIL,
      not: d.lastError ? `son: ${once(d.lastErrorAt)} · ${d.lastError.slice(0, 140)}` : undefined,
    },
    { ad: 'Destek portalı', deger: d.portalStatus ?? '—', renk: (d.portalStatus ?? '').startsWith('son gönderim') ? YESIL : T.fgLight },
  ];
  const { th, td } = tabloStil;
  const seviyeRenk = (s?: string) => (s === 'KRITIK' ? T.red : s === 'UYARI' ? TURUNCU : T.fgLight);
  const ozet: CSSProperties = { fontSize: 13, fontWeight: 600, marginBottom: 8, color: motorDurdu || alarmlar.some((a) => a.severity === 'KRITIK') ? T.red : alarmlar.length ? TURUNCU : YESIL };

  return (
    <Kabuk>
      <div style={ozet}>
        {motorDurdu ? 'Hesap motoru yanıt vermiyor' : alarmlar.length ? `${alarmlar.length} açık alarm` : 'Her şey yolunda'}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 12 }}>
        <tbody>
          {satirlar.map((s) => (
            <tr key={s.ad}>
              <td style={{ ...td, width: 150, color: T.fg2 }}><Isik renk={s.renk} />{s.ad}</td>
              <td style={td}>
                {s.deger}
                {s.not && <div style={{ fontSize: 11, color: T.fg3, marginTop: 2 }}>{s.not}</div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {alarmlar.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>{['Açık alarm', 'Ne zamandan beri', 'Tekrar'].map((h, i) => <th key={h} style={{ ...th, textAlign: i === 2 ? 'right' : 'left' }}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {alarmlar.map((a) => (
              <tr key={a.id}>
                <td style={td}><Isik renk={seviyeRenk(a.severity)} />{a.name}</td>
                <td style={{ ...td, color: T.fg2 }}>{once(a.firstSeenAt)}</td>
                <td style={{ ...td, textAlign: 'right' }}>{a.repeatCount ?? 1}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Kabuk>
  );
};

export default defineFrontComponent({
  universalIdentifier: SAGLIK_FC,
  name: 'Sistem Durumu',
  description: 'Hesap motoru, döviz kuru, yedek, takip iş akışı ve açık sistem alarmları (yöneticiler için).',
  component: SistemDurumu,
  widgetAvailability: { pageLayoutType: PageLayoutType.DASHBOARD },
});
