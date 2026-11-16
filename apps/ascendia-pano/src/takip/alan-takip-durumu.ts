import { defineField, FieldType, STANDARD_OBJECT } from 'twenty-sdk/define';

import { TAKIP_O_STATUS } from 'src/constants/universal-identifiers';

// Fırsat takip alanı: hesap motoru yazar (arayüzde salt okunur), Takip iş akışı okur. Bkz. kararlar/2026-11-13-takip-kurallari.md
export default defineField({
  objectUniversalIdentifier: STANDARD_OBJECT.opportunity.universalIdentifier,
  universalIdentifier: TAKIP_O_STATUS,
  type: FieldType.SELECT,
  name: 'followUpStatus',
  label: 'Takip Durumu',
  icon: 'IconBellRinging',
  isUIEditable: false,
  options: [
    { value: 'INACTIVITY', label: 'Temassızlık', position: 0, color: 'red' },
    { value: 'MEETING', label: 'Planlı görüşme', position: 1, color: 'purple' },
  ],
});
