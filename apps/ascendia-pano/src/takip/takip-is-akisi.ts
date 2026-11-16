import { defineWorkflow, STANDARD_OBJECT } from 'twenty-sdk/define';

import {
  TAKIP_O_STATUS,
  TAKIP_WF,
  TAKIP_WF_CLEAR,
  TAKIP_WF_FIND,
  TAKIP_WF_ITER,
  TAKIP_WF_TARGET,
  TAKIP_WF_TASK,
  TAKIP_WF_TRIG,
} from 'src/constants/universal-identifiers';

// Takip görevleri (kullanıcı, 13 Kas 2026; kararlar/2026-11-13-takip-kurallari.md).
// Hesap motoru her fırsat için Takip Durumu / Tarihi / Görevi / Sorumlusu'nu hesaplar (temassızlık ya da planlı
// görüşme). Bu iş akışı saatte bir Takip Durumu dolu fırsatları bulur; her biri için sorumluya görev açar, görevi
// fırsata bağlar ve Takip Durumu'nu temizler. Açık görev olduğu için motor aynı fırsatı yeniden işaretlemez.
const OPP = STANDARD_OBJECT.opportunity.universalIdentifier;
const kalem = `{{${TAKIP_WF_ITER}.currentItem`;

export default defineWorkflow({
  universalIdentifier: TAKIP_WF,
  name: 'Takip görevleri (Ascendia)',
  version: {
    trigger: {
      universalIdentifier: TAKIP_WF_TRIG,
      type: 'CRON',
      name: 'Saatte bir',
      settings: { type: 'HOURS', schedule: { hour: 1, minute: 10 } },
      nextStepIds: [TAKIP_WF_FIND],
    },
    steps: [
      {
        universalIdentifier: TAKIP_WF_FIND,
        name: 'Takip bekleyen fırsatlar',
        type: 'FIND_RECORDS',
        nextStepIds: [TAKIP_WF_ITER],
        input: {
          objectUniversalIdentifier: OPP,
          limit: 200,
          filter: {
            recordFilterGroups: [{ id: 'g', logicalOperator: 'AND' }],
            recordFilters: [
              { id: 'f', operand: 'IS_NOT_EMPTY', value: '', recordFilterGroupId: 'g', fieldMetadataUniversalIdentifier: TAKIP_O_STATUS },
            ],
          },
        },
      },
      {
        universalIdentifier: TAKIP_WF_ITER,
        name: 'Her fırsat için',
        type: 'ITERATOR',
        nextStepIds: [],
        input: { items: `{{${TAKIP_WF_FIND}.all}}`, initialLoopStepIds: [TAKIP_WF_TASK], shouldContinueOnIterationFailure: true },
      },
      {
        universalIdentifier: TAKIP_WF_TASK,
        name: 'Görev aç',
        type: 'CREATE_RECORD',
        nextStepIds: [TAKIP_WF_TARGET],
        input: {
          objectUniversalIdentifier: STANDARD_OBJECT.task.universalIdentifier,
          objectRecord: {
            title: `${kalem}.followUpTitle}}`,
            assigneeId: `${kalem}.followUpAssigneeId}}`,
            dueAt: `${kalem}.followUpDueAt}}`,
            status: 'TODO',
          },
        },
      },
      {
        universalIdentifier: TAKIP_WF_TARGET,
        name: 'Görevi fırsata bağla',
        type: 'CREATE_RECORD',
        nextStepIds: [TAKIP_WF_CLEAR],
        input: {
          objectUniversalIdentifier: STANDARD_OBJECT.taskTarget.universalIdentifier,
          objectRecord: { taskId: `{{${TAKIP_WF_TASK}.id}}`, targetOpportunityId: `${kalem}.id}}` },
        },
      },
      {
        universalIdentifier: TAKIP_WF_CLEAR,
        name: 'Takip durumunu temizle',
        type: 'UPDATE_RECORD',
        nextStepIds: [TAKIP_WF_ITER],
        input: {
          objectUniversalIdentifier: OPP,
          objectRecordId: `${kalem}.id}}`,
          objectRecord: { followUpStatus: null },
          fieldsToUpdate: ['followUpStatus'],
        },
      },
    ],
  },
});
