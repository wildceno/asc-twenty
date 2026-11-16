import { defineField, FieldType, STANDARD_OBJECT } from 'twenty-sdk/define';

import { TAKIP_O_DUE } from 'src/constants/universal-identifiers';

// Fırsat takip alanı: hesap motoru yazar (arayüzde salt okunur), Takip iş akışı okur. Bkz. kararlar/2026-11-13-takip-kurallari.md
export default defineField({
  objectUniversalIdentifier: STANDARD_OBJECT.opportunity.universalIdentifier,
  universalIdentifier: TAKIP_O_DUE,
  type: FieldType.DATE_TIME,
  name: 'followUpDueAt',
  label: 'Takip Tarihi',
  icon: 'IconCalendarDue',
  isUIEditable: false,
});
