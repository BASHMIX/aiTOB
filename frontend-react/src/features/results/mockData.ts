import type { StandingEntrySnapshot } from '@/scene/types';
import { PLAYER_IMAGE_PLACEHOLDER } from '@/utils/overlayAssets';

function createMockEntry(
  ordinal: number,
  placement: number,
  entrantId: string,
  entrantName: string,
  prefix: string | null,
  displayName: string,
  country: string | null,
  avatarUrl: string | null,
  characterName: string | null,
  characterImageUrl: string | null,
  isTied: boolean = false,
): StandingEntrySnapshot {
  return {
    ordinal,
    placement,
    entrant_id: entrantId,
    entrant_name: entrantName,
    is_tied: isTied,
    presentation: {
      display_name: { value: displayName, source: 'provider_snapshot' },
      prefix: { value: prefix, source: 'provider_snapshot' },
      country: { value: country, source: 'provider_snapshot' },
      avatar_url: { value: avatarUrl, source: 'provider_snapshot' },
      character: {
        value: {
          id: characterName ? characterName.toLowerCase().replace(/\s+/g, '_') : null,
          name: characterName,
          image_url: characterImageUrl,
        },
        source: 'provider_snapshot',
      },
    },
  };
}

export const MOCK_NORMAL_STANDINGS: StandingEntrySnapshot[] = [
  createMockEntry(1, 1, 'ent-1', 'Knee', 'DRX', 'Knee', 'KR', PLAYER_IMAGE_PLACEHOLDER, 'Feng', PLAYER_IMAGE_PLACEHOLDER),
  createMockEntry(2, 2, 'ent-2', 'Arslan Ash', 'Twisted Minds', 'Arslan Ash', 'PK', PLAYER_IMAGE_PLACEHOLDER, 'Nina', PLAYER_IMAGE_PLACEHOLDER),
  createMockEntry(3, 3, 'ent-3', 'Atif Butt', 'Falcons', 'Atif', 'PK', PLAYER_IMAGE_PLACEHOLDER, 'Dragunov', PLAYER_IMAGE_PLACEHOLDER),
  createMockEntry(4, 4, 'ent-4', 'Ulsan', 'KDF', 'Ulsan', 'KR', PLAYER_IMAGE_PLACEHOLDER, 'Dragunov', PLAYER_IMAGE_PLACEHOLDER),
  createMockEntry(5, 5, 'ent-5', 'CBM', 'KDF', 'CherryBerryMango', 'KR', PLAYER_IMAGE_PLACEHOLDER, 'Jin', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(6, 5, 'ent-6', 'Rangchu', 'VARREL', 'Rangchu', 'KR', PLAYER_IMAGE_PLACEHOLDER, 'Panda', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(7, 7, 'ent-7', 'Mulgold', 'DRX', 'Mulgold', 'KR', PLAYER_IMAGE_PLACEHOLDER, 'Claudio', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(8, 7, 'ent-8', 'Keisuke', 'VIZ', 'Keisuke', 'JP', PLAYER_IMAGE_PLACEHOLDER, 'Kazuya', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(9, 9, 'ent-9', 'Chikurin', 'THY', 'Chikurin', 'JP', PLAYER_IMAGE_PLACEHOLDER, 'Lili', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(10, 9, 'ent-10', 'LowHigh', 'DRX', 'LowHigh', 'KR', PLAYER_IMAGE_PLACEHOLDER, 'Shaheen', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(11, 9, 'ent-11', 'JoKa', 'PAR', 'JoKa', 'GB', PLAYER_IMAGE_PLACEHOLDER, 'Feng', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(12, 9, 'ent-12', 'AK', 'FATE', 'AK', 'PH', PLAYER_IMAGE_PLACEHOLDER, 'Law', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(13, 13, 'ent-13', 'Book', 'TALON', 'Book', 'TH', PLAYER_IMAGE_PLACEHOLDER, 'Jin', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(14, 13, 'ent-14', 'Shadow 20z', 'RB', 'Shadow 20z', 'US', PLAYER_IMAGE_PLACEHOLDER, 'Zafina', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(15, 13, 'ent-15', 'Farzeen', 'TM', 'Farzeen', 'PK', PLAYER_IMAGE_PLACEHOLDER, 'Victor', PLAYER_IMAGE_PLACEHOLDER, true),
  createMockEntry(16, 13, 'ent-16', 'Nobi', 'YAMASA', 'Nobi', 'JP', PLAYER_IMAGE_PLACEHOLDER, 'Dragunov', PLAYER_IMAGE_PLACEHOLDER, true),
];

export const MOCK_LONG_NAMES_STANDINGS: StandingEntrySnapshot[] = [
  createMockEntry(
    1,
    1,
    'ent-l1',
    'SuperUltraMegaLongPlayerGamerTagExtremeEdition',
    'INTERNATIONAL ESPORTS CHAMPIONSHIP TEAM 2026',
    'SuperUltraMegaLongPlayerGamerTagExtremeEdition',
    'GLOBAL',
    PLAYER_IMAGE_PLACEHOLDER,
    'Yoshimitsu The Mechanical Space Ninja Clan Leader',
    PLAYER_IMAGE_PLACEHOLDER,
  ),
  createMockEntry(
    2,
    2,
    'ent-l2',
    'TheUnstoppableForceMeetingTheImmovableObjectHere',
    'VERY LONG SPONSOR AND GUILD PREFIX',
    'TheUnstoppableForceMeetingTheImmovableObjectHere',
    'UNITED_KINGDOM',
    PLAYER_IMAGE_PLACEHOLDER,
    'King The Legendary Armor Lucha Wrestler',
    PLAYER_IMAGE_PLACEHOLDER,
  ),
  createMockEntry(3, 3, 'ent-l3', 'Alexandros Konstantinos Papadopoulos', 'HELLAS', 'Alexandros Konstantinos Papadopoulos', 'GR', null, 'Reina', null),
  createMockEntry(4, 4, 'ent-l4', 'Wolfeschlegelsteinhausenbergerdorff', 'EU', 'Wolfeschlegelsteinhausenbergerdorff', 'DE', null, 'Victor', null),
  createMockEntry(5, 5, 'ent-l5', 'PlayerFiveWithExtraordinaryNameLength', 'TAG', 'PlayerFiveWithExtraordinaryNameLength', 'FR', null, 'Lili', null, true),
  createMockEntry(6, 5, 'ent-l6', 'PlayerSixWithExtraordinaryNameLength', 'TAG', 'PlayerSixWithExtraordinaryNameLength', 'IT', null, 'Azucena', null, true),
  createMockEntry(7, 7, 'ent-l7', 'PlayerSevenWithExtraordinaryNameLength', 'TAG', 'PlayerSevenWithExtraordinaryNameLength', 'ES', null, 'Leo', null, true),
  createMockEntry(8, 7, 'ent-l8', 'PlayerEightWithExtraordinaryNameLength', 'TAG', 'PlayerEightWithExtraordinaryNameLength', 'BR', null, 'Eddy', null, true),
];

export const MOCK_MISSING_MEDIA_STANDINGS: StandingEntrySnapshot[] = [
  createMockEntry(1, 1, 'ent-m1', 'GhostWinner', null, 'GhostWinner', null, null, null, null),
  createMockEntry(2, 2, 'ent-m2', 'NoArtRunnerUp', null, 'NoArtRunnerUp', null, null, 'Kazuya', null),
  createMockEntry(3, 3, 'ent-m3', 'MysteryThird', 'TAG', 'MysteryThird', 'US', null, null, null),
  createMockEntry(4, 4, 'ent-m4', 'PlayerFour', null, 'PlayerFour', null, null, null, null),
  createMockEntry(5, 5, 'ent-m5', 'PlayerFive', null, 'PlayerFive', null, null, null, null, true),
  createMockEntry(6, 5, 'ent-m6', 'PlayerSix', null, 'PlayerSix', null, null, null, null, true),
  createMockEntry(7, 7, 'ent-m7', 'PlayerSeven', null, 'PlayerSeven', null, null, null, null, true),
  createMockEntry(8, 7, 'ent-m8', 'PlayerEight', null, 'PlayerEight', null, null, null, null, true),
];

export const MOCK_RTL_STANDINGS: StandingEntrySnapshot[] = [
  createMockEntry(1, 1, 'ent-r1', 'بطل الشرق الأوسط', 'صقور الشرق', 'بطل الشرق الأوسط', 'SA', PLAYER_IMAGE_PLACEHOLDER, 'شاهين', PLAYER_IMAGE_PLACEHOLDER),
  createMockEntry(2, 2, 'ent-r2', 'فارس الظلام', 'فرسان الخليج', 'فارس الظلام', 'AE', PLAYER_IMAGE_PLACEHOLDER, 'جين', PLAYER_IMAGE_PLACEHOLDER),
  createMockEntry(3, 3, 'ent-r3', 'نجم الرياض', 'فالكونز', 'نجم الرياض', 'SA', PLAYER_IMAGE_PLACEHOLDER, 'دراغونوف', PLAYER_IMAGE_PLACEHOLDER),
  createMockEntry(4, 4, 'ent-r4', 'سيف العدالة', null, 'سيف العدالة', 'KW', PLAYER_IMAGE_PLACEHOLDER, 'كازويا', PLAYER_IMAGE_PLACEHOLDER),
  createMockEntry(5, 5, 'ent-r5', 'صقر قريش', 'تحدي', 'صقر قريش', 'QA', null, 'لارس', null, true),
  createMockEntry(6, 5, 'ent-r6', 'أسد الرافدين', null, 'أسد الرافدين', 'IQ', null, 'كينغ', null, true),
  createMockEntry(7, 7, 'ent-r7', 'أمير البحار', null, 'أمير البحار', 'BH', null, 'براين', null, true),
  createMockEntry(8, 7, 'ent-r8', 'نسر الأطلس', 'مغرب إسبورتس', 'نسر الأطلس', 'MA', null, 'هواورانغ', null, true),
];

export const MOCK_TIED_STANDINGS: StandingEntrySnapshot[] = [
  createMockEntry(1, 1, 'ent-t1', 'Knee', 'DRX', 'Knee', 'KR', null, 'Feng', null, false),
  createMockEntry(2, 2, 'ent-t2', 'Arslan', 'TM', 'Arslan', 'PK', null, 'Nina', null, false),
  createMockEntry(3, 3, 'ent-t3', 'Atif', 'FLC', 'Atif', 'PK', null, 'Dragunov', null, true),
  createMockEntry(4, 3, 'ent-t4', 'Ulsan', 'KDF', 'Ulsan', 'KR', null, 'Azucena', null, true),
  createMockEntry(5, 5, 'ent-t5', 'CBM', 'KDF', 'CBM', 'KR', null, 'Jin', null, true),
  createMockEntry(6, 5, 'ent-t6', 'Rangchu', 'VRL', 'Rangchu', 'KR', null, 'Panda', null, true),
  createMockEntry(7, 7, 'ent-t7', 'Mulgold', 'DRX', 'Mulgold', 'KR', null, 'Claudio', null, true),
  createMockEntry(8, 7, 'ent-t8', 'Keisuke', 'VIZ', 'Keisuke', 'JP', null, 'Kazuya', null, true),
  // 9th entrant tied at 7th / overflow scenario:
  createMockEntry(9, 7, 'ent-t9', 'Chikurin', 'THY', 'Chikurin', 'JP', null, 'Lili', null, true),
];

export const MOCK_DATASETS: Record<string, StandingEntrySnapshot[]> = {
  normal: MOCK_NORMAL_STANDINGS,
  long_names: MOCK_LONG_NAMES_STANDINGS,
  missing_media: MOCK_MISSING_MEDIA_STANDINGS,
  rtl: MOCK_RTL_STANDINGS,
  tied_placements: MOCK_TIED_STANDINGS,
};
