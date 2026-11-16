import { defineObject, FieldType } from 'twenty-sdk/define';

import { TAKIP_F_DAYS, TAKIP_F_NAME, TAKIP_F_STAGE, TAKIP_OBJ } from 'src/constants/universal-identifiers';

// Takip Kuralları (Yönetim): her açık aşama için "kaç gün temas yoksa görev açılsın". Boş = kural kapalı.
// Organizasyon değiştirir (kullanıcı, 13 Kas 2026). Kayıtları metadata/15_takip.py tohumlar.
export default defineObject({
  universalIdentifier: TAKIP_OBJ,
  nameSingular: 'followUpRule',
  namePlural: 'followUpRules',
  labelSingular: 'Takip Kuralı',
  labelPlural: 'Takip Kuralları',
  description: 'Aşama bazında temassız gün eşiği; süre dolunca sorumluya takip görevi açılır. Boş = kapalı.',
  icon: 'IconBellRinging',
  labelIdentifierFieldMetadataUniversalIdentifier: TAKIP_F_NAME,
  fields: [
    { universalIdentifier: TAKIP_F_NAME, type: FieldType.TEXT, name: 'name', label: 'Ad', icon: 'IconTag' },
    {
      universalIdentifier: TAKIP_F_STAGE,
      type: FieldType.SELECT,
      name: 'stage',
      label: 'Aşama',
      icon: 'IconProgress',
      options: [
        { value: 'LEAD_GEN', label: 'Lead-Gen', position: 0, color: 'sky' },
        { value: 'LEAD_IN_TOUCH', label: 'Lead-inTouch', position: 1, color: 'turquoise' },
        { value: 'PIPELINE', label: 'Pipeline', position: 2, color: 'blue' },
        { value: 'UPSIDE', label: 'Upside', position: 3, color: 'purple' },
        { value: 'COMMIT', label: 'Commit', position: 4, color: 'orange' },
      ],
    },
    { universalIdentifier: TAKIP_F_DAYS, type: FieldType.NUMBER, name: 'days', label: 'Temassız Gün Eşiği', icon: 'IconClock' },
  ],
});
