import { defineField, FieldType, STANDARD_OBJECT } from 'twenty-sdk/define';

import { TAKIP_O_LAST } from 'src/constants/universal-identifiers';

// Fırsat takip alanı: hesap motoru yazar (arayüzde salt okunur), Takip iş akışı okur. Bkz. kararlar/2026-11-13-takip-kurallari.md
export default defineField({
  objectUniversalIdentifier: STANDARD_OBJECT.opportunity.universalIdentifier,
  universalIdentifier: TAKIP_O_LAST,
  type: FieldType.DATE_TIME,
  name: 'lastTouchAt',
  label: 'Son Temas',
  icon: 'IconMessages',
  isUIEditable: false,
});
