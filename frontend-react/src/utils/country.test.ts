import { describe, expect, it } from 'vitest';
import { countryCode, countryFlagUrl } from './country';

describe('country normalization', () => {
  it('accepts ISO codes, common aliases, and English country names', () => {
    expect(countryCode('jo')).toBe('JO');
    expect(countryCode('UK')).toBe('GB');
    expect(countryCode('usa')).toBe('US');
    expect(countryCode('Jordan')).toBe('JO');
  });

  it('builds flag URLs from canonical ISO alpha-2 codes', () => {
    expect(countryFlagUrl('UK')).toBe('/static/flags/gb.svg');
    expect(countryFlagUrl('USA')).toBe('/static/flags/us.svg');
  });
});
