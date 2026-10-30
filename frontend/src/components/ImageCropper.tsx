import { PointerEvent, useEffect, useRef, useState } from 'react'
import { Check, Crop, Move, RotateCcw, RotateCw, SkipForward, X, ZoomIn } from 'lucide-react'
import './ImageCropper.css'

type CropPosition = { x: number; y: number }
type CropRect = { x: number; y: number; width: number; height: number }
type Ratio = { label: string; value: number }
type PhotoFilter = { label: string; value: string }

const ratios: Ratio[] = [
  { label: 'Square', value: 1 },
  { label: 'Portrait', value: 4 / 5 },
  { label: 'Landscape', value: 16 / 9 },
]

const photoFilters: PhotoFilter[] = [
  { label: 'Original', value: '' },
  { label: 'Vivid', value: 'saturate(1.35) contrast(1.08)' },
  { label: 'Grayscale', value: 'grayscale(1)' },
  { label: 'Sepia', value: 'sepia(.85)' },
  { label: 'Vintage', value: 'sepia(.4) saturate(.82) contrast(.9)' },
  { label: 'Warm', value: 'sepia(.2) saturate(1.12)' },
  { label: 'Cool', value: 'hue-rotate(12deg) saturate(1.08)' },
  { label: 'Fade', value: 'brightness(1.06) contrast(.86) saturate(.88)' },
]

function clampPosition(position: CropPosition, scale: number, width: number, height: number, imageWidth: number, imageHeight: number): CropPosition {
  const drawnWidth = imageWidth * scale
  const drawnHeight = imageHeight * scale
  return {
    x: Math.min(0, Math.max(width - drawnWidth, position.x)),
    y: Math.min(0, Math.max(height - drawnHeight, position.y)),
  }
}

export function calculateCropRect(
  imageWidth: number,
  imageHeight: number,
  viewportWidth: number,
  viewportHeight: number,
  zoom: number,
  position: CropPosition,
): CropRect {
  const scale = Math.max(viewportWidth / imageWidth, viewportHeight / imageHeight) * zoom
  const width = Math.min(imageWidth, viewportWidth / scale)
  const height = Math.min(imageHeight, viewportHeight / scale)
  const x = Math.max(0, Math.min(imageWidth - width, -position.x / scale))
  const y = Math.max(0, Math.min(imageHeight - height, -position.y / scale))
  return { x, y, width, height }
}

function canvasBlob(canvas: HTMLCanvasElement, type: string): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('The photo could not be created. Please try another image.')), type, 0.92)
  })
}

function rotateImage(source: HTMLImageElement, degrees: number): { canvas: HTMLCanvasElement; sourceScale: number } {
  const sideways = degrees % 180 !== 0
  const sourceScale = Math.min(1, 4096 / source.naturalWidth, 4096 / source.naturalHeight)
  const canvas = document.createElement('canvas')
  canvas.width = Math.round((sideways ? source.naturalHeight : source.naturalWidth) * sourceScale)
  canvas.height = Math.round((sideways ? source.naturalWidth : source.naturalHeight) * sourceScale)
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Image editing is unavailable in this browser.')
  context.translate(canvas.width / 2, canvas.height / 2)
  context.rotate(degrees * Math.PI / 180)
  context.scale(sourceScale, sourceScale)
  context.drawImage(source, -source.naturalWidth / 2, -source.naturalHeight / 2)
  return { canvas, sourceScale }
}

export default function ImageCropper({
  file,
  index,
  total,
  onApply,
  onSkip,
  onClose,
}: {
  file: File
  index: number
  total: number
  onApply: (file: File) => void
  onSkip: () => void
  onClose: () => void
}) {
  const [source, setSource] = useState<HTMLImageElement | null>(null)
  const [ratio, setRatio] = useState(ratios[0].value)
  const [zoom, setZoom] = useState(1)
  const [position, setPosition] = useState<CropPosition>({ x: 0, y: 0 })
  const [viewport, setViewport] = useState({ width: 0, height: 0 })
  const [rotation, setRotation] = useState(0)
  const [filter, setFilter] = useState(photoFilters[0].value)
  const [brightness, setBrightness] = useState(100)
  const [contrast, setContrast] = useState(100)
  const [saturation, setSaturation] = useState(100)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const stageRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ pointerX: number; pointerY: number; x: number; y: number } | null>(null)

  useEffect(() => {
    setSource(null)
    setError('')
    setZoom(1)
    setPosition({ x: 0, y: 0 })
    setRatio(ratios[0].value)
    setRotation(0)
    setFilter(photoFilters[0].value)
    setBrightness(100)
    setContrast(100)
    setSaturation(100)
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => setSource(image)
    image.onerror = () => setError('This photo could not be opened. Choose a different image.')
    image.src = url
    return () => {
      URL.revokeObjectURL(url)
      image.onload = null
      image.onerror = null
    }
  }, [file])

  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    const measure = () => setViewport({ width: stage.clientWidth, height: stage.clientHeight })
    measure()
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measure)
      return () => window.removeEventListener('resize', measure)
    }
    const observer = new ResizeObserver(measure)
    observer.observe(stage)
    return () => observer.disconnect()
  }, [ratio])

  const sideways = rotation % 180 !== 0
  const imageWidth = source ? (sideways ? source.naturalHeight : source.naturalWidth) : 0
  const imageHeight = source ? (sideways ? source.naturalWidth : source.naturalHeight) : 0
  const fitScale = source && viewport.width && viewport.height
    ? Math.max(viewport.width / imageWidth, viewport.height / imageHeight)
    : 0
  const scale = fitScale * zoom
  const drawnWidth = source ? source.naturalWidth * scale : 0
  const drawnHeight = source ? source.naturalHeight * scale : 0
  const orientedDrawnWidth = imageWidth * scale
  const orientedDrawnHeight = imageHeight * scale
  const presetFilter = photoFilters.find(option => option.value === filter)?.value || ''
  const filterStyle = [
    `brightness(${brightness / 100})`,
    `contrast(${contrast / 100})`,
    `saturate(${saturation / 100})`,
    presetFilter,
  ].filter(Boolean).join(' ')

  useEffect(() => {
    if (!source || !viewport.width || !viewport.height || !scale) return
    setPosition(clampPosition({
      x: (viewport.width - orientedDrawnWidth) / 2,
      y: (viewport.height - orientedDrawnHeight) / 2,
    }, scale, viewport.width, viewport.height, imageWidth, imageHeight))
    // Recenter when the photo, frame size, or orientation changes.
  }, [source, rotation, viewport.width, viewport.height])

  const changeZoom = (nextZoom: number) => {
    if (!source || !viewport.width || !viewport.height || !fitScale) {
      setZoom(nextZoom)
      return
    }
    const focusX = (viewport.width / 2 - position.x) / scale
    const focusY = (viewport.height / 2 - position.y) / scale
    const nextScale = fitScale * nextZoom
    setPosition(clampPosition({
      x: viewport.width / 2 - focusX * nextScale,
      y: viewport.height / 2 - focusY * nextScale,
    }, nextScale, viewport.width, viewport.height, imageWidth, imageHeight))
    setZoom(nextZoom)
  }

  const startDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!source) return
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = { pointerX: event.clientX, pointerY: event.clientY, x: position.x, y: position.y }
  }
  const drag = (event: PointerEvent<HTMLDivElement>) => {
    const start = dragRef.current
    if (!start || !source) return
    setPosition(clampPosition({
      x: start.x + event.clientX - start.pointerX,
      y: start.y + event.clientY - start.pointerY,
    }, scale, viewport.width, viewport.height, imageWidth, imageHeight))
  }
  const stopDrag = () => { dragRef.current = null }

  const applyCrop = async () => {
    if (!source || !viewport.width || !viewport.height || busy) return
    setBusy(true)
    setError('')
    let applied = false
    try {
      const crop = calculateCropRect(imageWidth, imageHeight, viewport.width, viewport.height, zoom, position)
      const maxDimension = 1600
      const outputScale = Math.min(1, maxDimension / crop.width, maxDimension / crop.height)
      const canvas = document.createElement('canvas')
      canvas.width = Math.max(1, Math.round(crop.width * outputScale))
      canvas.height = Math.max(1, Math.round(crop.height * outputScale))
      const context = canvas.getContext('2d')
      if (!context) throw new Error('Image editing is unavailable in this browser.')
      const orientedSource = rotateImage(source, rotation)
      context.filter = filterStyle
      context.drawImage(orientedSource.canvas, crop.x * orientedSource.sourceScale, crop.y * orientedSource.sourceScale, crop.width * orientedSource.sourceScale, crop.height * orientedSource.sourceScale, 0, 0, canvas.width, canvas.height)
      const type = ['image/png', 'image/webp'].includes(file.type) ? file.type : 'image/jpeg'
      const blob = await canvasBlob(canvas, type)
      const extension = blob.type === 'image/png' ? 'png' : blob.type === 'image/webp' ? 'webp' : 'jpg'
      const baseName = file.name.replace(/\.[^.]+$/, '') || 'photo'
      const editedFile = new File([blob], `${baseName}-edited.${extension}`, { type: blob.type || type, lastModified: Date.now() })
      applied = true
      onApply(editedFile)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The photo could not be edited. Please try again.')
    } finally {
      if (!applied) setBusy(false)
    }
  }

  const currentRatio = ratios.find(option => option.value === ratio)?.value || 1
  const maxStageHeight = Math.min(480, window.innerHeight * 0.42)
  const stageWidth = Math.max(180, Math.min(560, window.innerWidth - 40, maxStageHeight * currentRatio))
  const adjustControls = [
    { label: 'Brightness', value: brightness, setValue: setBrightness },
    { label: 'Contrast', value: contrast, setValue: setContrast },
    { label: 'Saturation', value: saturation, setValue: setSaturation },
  ]

  return <div className="modal-backdrop crop-backdrop" onClick={event => event.target === event.currentTarget && onClose()}>
    <section className="modal-card crop-modal" role="dialog" aria-modal="true" aria-labelledby="crop-title">
      <header className="crop-header">
        <div><p className="eyebrow">PHOTO EDITOR · {index} OF {total}</p><h2 id="crop-title">Adjust your photo</h2><p>Choose a filter, crop, zoom, rotate, or fine-tune the image.</p></div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close photo editor"><X size={19}/></button>
      </header>
      <div className="crop-stage-wrap">
        <div
          ref={stageRef}
          className={`crop-stage ${source ? 'ready' : ''}`}
          style={{ aspectRatio: String(currentRatio), width: stageWidth }}
          onPointerDown={startDrag}
          onPointerMove={drag}
          onPointerUp={stopDrag}
          onPointerCancel={stopDrag}
          aria-label="Photo crop area; drag the photo to reposition it"
        >
          {source && <>
            <img
              className="crop-source"
              src={source.src}
              alt="Photo being edited"
              draggable={false}
              style={{
                width: drawnWidth,
                height: drawnHeight,
                left: position.x + (orientedDrawnWidth - drawnWidth) / 2,
                top: position.y + (orientedDrawnHeight - drawnHeight) / 2,
                transform: `rotate(${rotation}deg)`,
                filter: filterStyle,
              }}
            />
            <span className="crop-guides" aria-hidden="true"/>
          </>}
          {!source && !error && <span className="crop-loading">Loading photo…</span>}
          {error && <span className="crop-loading crop-error">{error}</span>}
        </div>
      </div>
      <div className="crop-filter-section">
        <div className="crop-section-label"><span>Filters</span><small>Live preview</small></div>
        <div className="crop-filter-list" aria-label="Photo filters">
          {photoFilters.map(option => <button type="button" key={option.label} className={`crop-filter ${filter === option.value ? 'active' : ''}`} onClick={() => setFilter(option.value)}>{option.label}</button>)}
        </div>
      </div>
      <div className="crop-adjustments">
        {adjustControls.map(control => <label className="crop-adjustment" key={control.label}>
          <span>{control.label}<small>{control.value}%</small></span>
          <input type="range" min="0" max="200" step="1" value={control.value} onChange={event => control.setValue(Number(event.target.value))} aria-label={control.label}/>
        </label>)}
      </div>
      <div className="crop-controls">
        <div className="crop-ratios" aria-label="Crop shape">
          <span><Crop size={15}/> Crop</span>
          {ratios.map(option => <button type="button" key={option.label} className={ratio === option.value ? 'active' : ''} onClick={() => setRatio(option.value)}>{option.label}</button>)}
        </div>
        <div className="crop-rotate">
          <span>Rotate</span>
          <button type="button" className="icon-button" onClick={() => setRotation(value => (value + 270) % 360)} aria-label="Rotate photo left"><RotateCcw size={16}/></button>
          <button type="button" className="icon-button" onClick={() => setRotation(value => (value + 90) % 360)} aria-label="Rotate photo right"><RotateCw size={16}/></button>
        </div>
      </div>
      <label className="crop-zoom"><span><ZoomIn size={16}/> Zoom</span><input type="range" min="1" max="3" step="0.01" value={zoom} onChange={event => changeZoom(Number(event.target.value))} aria-label="Zoom photo"/><small>{Math.round(zoom * 100)}%</small></label>
      {error && source && <p className="form-error crop-message" role="alert">{error}</p>}
      <footer className="crop-footer">
        <button type="button" className="button button-secondary button-sm" onClick={onSkip} disabled={busy}><SkipForward size={15}/> Skip photo</button>
        <span><Move size={14}/> Drag photo to position</span>
        <button type="button" className="button button-primary" onClick={applyCrop} disabled={!source || busy}><Check size={16}/>{busy ? 'Applying…' : 'Apply edits'}</button>
      </footer>
    </section>
  </div>
}
