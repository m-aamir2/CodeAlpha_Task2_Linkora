import { describe, expect, it } from 'vitest'
import { calculateCropRect } from './ImageCropper'

describe('calculateCropRect', () => {
  it('returns a square crop from a landscape image', () => {
    const crop = calculateCropRect(1600, 900, 400, 400, 1, { x: -155.5556, y: 0 })
    expect(crop.width / crop.height).toBeCloseTo(1)
    expect(crop.x).toBeCloseTo(350)
    expect(crop.y).toBeCloseTo(0)
  })

  it('preserves a portrait ratio and clamps a dragged crop inside the source', () => {
    const crop = calculateCropRect(1000, 800, 400, 500, 1.5, { x: 900, y: -900 })
    expect(crop.width / crop.height).toBeCloseTo(0.8)
    expect(crop.x).toBeGreaterThanOrEqual(0)
    expect(crop.y).toBeGreaterThanOrEqual(0)
    expect(crop.x + crop.width).toBeLessThanOrEqual(1000)
    expect(crop.y + crop.height).toBeLessThanOrEqual(800)
  })
})
