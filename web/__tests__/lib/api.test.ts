import { describe, it, expect } from 'vitest'
import { getTier, getTierColor, getScoreColor } from '@/lib/api'

describe('getTier', () => {
  it('returns "Untrusted" for score 0', () => {
    expect(getTier(0)).toBe('Untrusted')
  })

  it('returns "Untrusted" for score 349', () => {
    expect(getTier(349)).toBe('Untrusted')
  })

  it('returns "Poor" for score 350', () => {
    expect(getTier(350)).toBe('Poor')
  })

  it('returns "Poor" for score 549', () => {
    expect(getTier(549)).toBe('Poor')
  })

  it('returns "Fair" for score 550', () => {
    expect(getTier(550)).toBe('Fair')
  })

  it('returns "Fair" for score 699', () => {
    expect(getTier(699)).toBe('Fair')
  })

  it('returns "Good" for score 700', () => {
    expect(getTier(700)).toBe('Good')
  })

  it('returns "Good" for score 849', () => {
    expect(getTier(849)).toBe('Good')
  })

  it('returns "Excellent" for score 850', () => {
    expect(getTier(850)).toBe('Excellent')
  })

  it('returns "Excellent" for score 1000', () => {
    expect(getTier(1000)).toBe('Excellent')
  })
})

describe('getTierColor', () => {
  it('returns #10b981 for "Excellent"', () => {
    expect(getTierColor('Excellent')).toBe('#10b981')
  })

  it('returns #22c55e for "Good"', () => {
    expect(getTierColor('Good')).toBe('#22c55e')
  })

  it('returns #f59e0b for "Fair"', () => {
    expect(getTierColor('Fair')).toBe('#f59e0b')
  })

  it('returns #ef4444 for "Poor"', () => {
    expect(getTierColor('Poor')).toBe('#ef4444')
  })

  it('returns #6b7280 for "Untrusted"', () => {
    expect(getTierColor('Untrusted')).toBe('#6b7280')
  })

  it('is case-insensitive', () => {
    expect(getTierColor('excellent')).toBe('#10b981')
    expect(getTierColor('GOOD')).toBe('#22c55e')
  })

  it('returns default color for unknown tier', () => {
    expect(getTierColor('unknown')).toBe('#6b7280')
  })
})

describe('getScoreColor', () => {
  it('returns Excellent color for score 900', () => {
    expect(getScoreColor(900)).toBe('#10b981')
  })

  it('returns Good color for score 750', () => {
    expect(getScoreColor(750)).toBe('#22c55e')
  })

  it('returns Fair color for score 600', () => {
    expect(getScoreColor(600)).toBe('#f59e0b')
  })

  it('returns Poor color for score 400', () => {
    expect(getScoreColor(400)).toBe('#ef4444')
  })

  it('returns Untrusted color for score 100', () => {
    expect(getScoreColor(100)).toBe('#6b7280')
  })
})
