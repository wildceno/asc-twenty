import { defineObject, FieldType } from 'twenty-sdk/define';

import {
  SAGLIK_S_BACKUP,
  SAGLIK_S_ERR24,
  SAGLIK_S_HB,
  SAGLIK_S_LASTERR,
  SAGLIK_S_LASTERRAT,
  SAGLIK_S_NAME,
  SAGLIK_S_OBJ,
  SAGLIK_S_PORTAL,
  SAGLIK_S_RATE,
  SAGLIK_S_START,
  SAGLIK_S_WFAT,
  SAGLIK_S_WFST,
} from 'src/constants/universal-identifiers';

// Sistem Durumu (Yönetim): tek kayıt. Hesap motoru 5 dakikada bir yazar; yedek betiği son yedeği yazar.
// Sistem Durumu widget'ı kalp atışı gecikirse motorun durduğunu buradan anlar.
export default defineObject({
  universalIdentifier: SAGLIK_S_OBJ,
  nameSingular: 'systemStatus',
  namePlural: 'systemStatuses',
  labelSingular: 'Sistem Durumu',
  labelPlural: 'Sistem Durumu',
  description: 'Hesap motoru, kur, yedek ve iş akışının son durumu (sistem yazar).',
  icon: 'IconHeartbeat',
  labelIdentifierFieldMetadataUniversalIdentifier: SAGLIK_S_NAME,
  fields: [
    { universalIdentifier: SAGLIK_S_NAME, type: FieldType.TEXT, name: 'name', label: 'Ad', icon: 'IconTag' },
    { universalIdentifier: SAGLIK_S_HB, type: FieldType.DATE_TIME, name: 'lastHeartbeatAt', label: 'Son Kalp Atışı', icon: 'IconHeartbeat', isUIEditable: false },
    { universalIdentifier: SAGLIK_S_START, type: FieldType.DATE_TIME, name: 'motorStartedAt', label: 'Motor Başlangıcı', icon: 'IconPlayerPlay', isUIEditable: false },
    { universalIdentifier: SAGLIK_S_RATE, type: FieldType.DATE, name: 'lastRateDate', label: 'Son Kur Tarihi', icon: 'IconCurrencyDollar', isUIEditable: false },
    { universalIdentifier: SAGLIK_S_BACKUP, type: FieldType.DATE_TIME, name: 'lastBackupAt', label: 'Son Yedek', icon: 'IconDatabase', isUIEditable: false },
    { universalIdentifier: SAGLIK_S_WFAT, type: FieldType.DATE_TIME, name: 'lastWorkflowRunAt', label: 'İş Akışı Son Çalışma', icon: 'IconSettingsAutomation', isUIEditable: false },
    { universalIdentifier: SAGLIK_S_WFST, type: FieldType.TEXT, name: 'lastWorkflowStatus', label: 'İş Akışı Durumu', icon: 'IconCheck', isUIEditable: false },
    { universalIdentifier: SAGLIK_S_ERR24, type: FieldType.NUMBER, name: 'errors24h', label: 'Hata (24 saat)', icon: 'IconAlertTriangle', isUIEditable: false },
    { universalIdentifier: SAGLIK_S_LASTERR, type: FieldType.TEXT, name: 'lastError', label: 'Son Hata', icon: 'IconBug', isUIEditable: false },
    { universalIdentifier: SAGLIK_S_LASTERRAT, type: FieldType.DATE_TIME, name: 'lastErrorAt', label: 'Son Hata Zamanı', icon: 'IconClock', isUIEditable: false },
    { universalIdentifier: SAGLIK_S_PORTAL, type: FieldType.TEXT, name: 'portalStatus', label: 'Portal Bağlantısı', icon: 'IconPlugConnected', isUIEditable: false },
  ],
});
