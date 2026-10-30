import { ChangeEvent, FormEvent, useEffect, useRef, useState } from 'react'
import { ImagePlus, LoaderCircle, Pencil, Replace, Trash2, X } from 'lucide-react'
import { api, errorMessage } from '../services/api'
import { Post, PostImage } from '../types'
import ImageCropper from './ImageCropper'
import { uploadImageToBlob, usesDirectImageUploads } from '../services/blobUpload'
import './EditPostModal.css'

type CropJob = { file: File; replacesId?: number }
type EditedPhoto = { file: File; preview: string; replacesId?: number }

export default function EditPostModal({ post, onClose, onSave }: { post: Post; onClose: () => void; onSave: (post: Post) => void }) {
  const [content, setContent] = useState(post.content)
  const [removedIds, setRemovedIds] = useState<number[]>([])
  const [replaceAll, setReplaceAll] = useState(false)
  const [photos, setPhotos] = useState<EditedPhoto[]>([])
  const [cropQueue, setCropQueue] = useState<CropJob[]>([])
  const [cropIndex, setCropIndex] = useState(0)
  const [cropQueueIsReplacement, setCropQueueIsReplacement] = useState(false)
  const [loadingImageId, setLoadingImageId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const addInputRef = useRef<HTMLInputElement>(null)
  const replaceInputRef = useRef<HTMLInputElement>(null)
  const previewUrls = useRef<string[]>([])

  useEffect(() => () => previewUrls.current.forEach(URL.revokeObjectURL), [])

  const activeImages = post.images.filter(image => !replaceAll && !removedIds.includes(image.id))
  const remainingCount = (replaceAll ? 0 : activeImages.length) + photos.length

  const advanceCrop = () => {
    if (cropIndex + 1 >= cropQueue.length) {
      setCropQueue([])
      setCropIndex(0)
      setCropQueueIsReplacement(false)
    } else {
      setCropIndex(index => index + 1)
    }
  }

  const choosePhotos = (event: ChangeEvent<HTMLInputElement>, replacing = false) => {
    const incoming = Array.from(event.currentTarget.files || [])
    const eligible = incoming.filter(file => file.size <= 8 * 1024 * 1024)
    const capacity = replacing ? 6 : Math.max(0, 6 - remainingCount)
    const accepted = eligible.slice(0, capacity)
    if (incoming.some(file => file.size > 8 * 1024 * 1024)) setError('Each photo must be 8 MB or smaller.')
    else if (eligible.length > accepted.length) setError('A post can contain up to 6 photos.')
    else setError('')
    if (accepted.length) {
      if (replacing) {
        previewUrls.current.forEach(URL.revokeObjectURL)
        previewUrls.current = []
        setPhotos([])
        setRemovedIds([])
        setReplaceAll(true)
      }
      setCropQueue(accepted.map(file => ({ file })))
      setCropIndex(0)
      setCropQueueIsReplacement(replacing)
    }
    event.currentTarget.value = ''
  }

  const applyCrop = (file: File) => {
    const preview = URL.createObjectURL(file)
    previewUrls.current.push(preview)
    const job = cropQueue[cropIndex]
    setPhotos(current => [...current, { file, preview, replacesId: job?.replacesId }])
    if (job?.replacesId) setRemovedIds(current => current.includes(job.replacesId!) ? current : [...current, job.replacesId!])
    advanceCrop()
  }

  const skipCrop = () => {
    if (cropIndex + 1 >= cropQueue.length) {
      setCropQueue([])
      setCropIndex(0)
      setCropQueueIsReplacement(false)
    } else setCropIndex(index => index + 1)
  }

  const closeCropper = () => {
    setCropQueue([])
    setCropIndex(0)
    if (cropQueueIsReplacement && photos.length === 0) setReplaceAll(false)
    setCropQueueIsReplacement(false)
  }

  const removePhoto = (photo: EditedPhoto) => {
    URL.revokeObjectURL(photo.preview)
    previewUrls.current = previewUrls.current.filter(url => url !== photo.preview)
    setPhotos(current => current.filter(item => item !== photo))
    if (photo.replacesId) setRemovedIds(current => current.filter(id => id !== photo.replacesId))
  }

  const removeExisting = (image: PostImage) => {
    setRemovedIds(current => current.includes(image.id) ? current : [...current, image.id])
  }

  const keepCurrentPhotos = () => {
    if (post.images.length - removedIds.length + photos.length > 6) {
      setError('Remove some photos before keeping the current set. A post can contain up to 6 photos.')
      return
    }
    setReplaceAll(false)
  }

  const editExisting = async (image: PostImage) => {
    setLoadingImageId(image.id)
    setError('')
    try {
      const { data } = await api.get<Blob>(image.url, { responseType: 'blob' })
      const blob = data instanceof Blob ? data : new Blob([data])
      const path = new URL(image.url).pathname
      const extension = path.split('.').pop()?.toLowerCase() || 'jpg'
      const type = blob.type || (extension === 'png' ? 'image/png' : extension === 'webp' ? 'image/webp' : 'image/jpeg')
      const file = new File([blob], `post-${post.id}-photo-${image.id}.${extension}`, { type })
      setCropQueue([{ file, replacesId: image.id }])
      setCropIndex(0)
      setCropQueueIsReplacement(false)
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setLoadingImageId(null)
    }
  }

  const save = async (event: FormEvent) => {
    event.preventDefault()
    if (saving) return
    if (!content.trim() && remainingCount === 0) {
      setError('Add some text or at least one photo to your post.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const form = new FormData()
      form.append('content', content)
      form.append('replace_images', String(replaceAll))
      if (!replaceAll) removedIds.forEach(id => form.append('remove_image_ids', String(id)))
      if (usesDirectImageUploads) {
        const urls = await Promise.all(photos.map(photo => uploadImageToBlob(photo.file, post.author.id, 'posts')))
        urls.forEach(url => form.append('uploaded_image_urls', url))
      } else {
        photos.forEach(photo => form.append('uploaded_images', photo.file))
      }
      const { data } = await api.patch<Post>(`/posts/${post.id}/`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
      onSave(data)
      onClose()
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setSaving(false)
    }
  }

  const visibleCurrentImages = replaceAll ? [] : post.images.filter(image => !removedIds.includes(image.id))

  return <>
    <div className="modal-backdrop post-edit-backdrop" onClick={event => event.target === event.currentTarget && !saving && onClose()}>
      <form className="modal-card post-edit-modal" onSubmit={save}>
        <div className="modal-heading">
          <div><p className="eyebrow">YOUR POST</p><h2>Edit your post</h2></div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close post editor" disabled={saving}><X size={19}/></button>
        </div>
        <label className="post-edit-caption">Caption<textarea value={content} onChange={event => setContent(event.target.value)} maxLength={5000} placeholder="Write a caption…"/></label>
        <div className="post-edit-photo-heading"><strong>Photos</strong><small>{remainingCount}/6 photos</small></div>
        <div className="post-edit-photo-tools">
          <button type="button" className="button button-secondary button-sm" onClick={() => addInputRef.current?.click()}><ImagePlus size={15}/> Add photos</button>
          <button type="button" className="button button-secondary button-sm" onClick={() => replaceInputRef.current?.click()}><Replace size={15}/> Replace all photos</button>
          <input ref={addInputRef} className="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={event => choosePhotos(event)}/>
          <input ref={replaceInputRef} className="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={event => choosePhotos(event, true)}/>
        </div>
        {replaceAll&&<p className="post-edit-replace-note">Current photos will be replaced by the edited photos below. <button type="button" onClick={keepCurrentPhotos}>Keep current photos</button></p>}
        {visibleCurrentImages.length > 0 && <div className="post-edit-photo-grid">
          {visibleCurrentImages.map(image => <div className="post-edit-photo" key={image.id}>
            <img src={image.url} alt={image.alt_text || 'Current post photo'}/>
            <div><button type="button" onClick={() => editExisting(image)} disabled={loadingImageId !== null || saving} aria-label="Adjust current photo">{loadingImageId === image.id ? <LoaderCircle size={14} className="spin"/> : <Pencil size={14}/>} Adjust</button><button type="button" onClick={() => removeExisting(image)} disabled={saving} aria-label="Remove current photo"><Trash2 size={14}/> Remove</button></div>
          </div>)}
        </div>}
        {!visibleCurrentImages.length && !photos.length && <p className="post-edit-empty-photos">No photos selected. Add photos or save this as a text post.</p>}
        {photos.length > 0 && <div className="post-edit-photo-grid">
          {photos.map((photo, index) => <div className="post-edit-photo" key={photo.preview}>
            <img src={photo.preview} alt={`Edited post photo ${index + 1}`}/>
            <div><span>{photo.replacesId ? 'Adjusted' : 'Ready to upload'}</span><button type="button" onClick={() => removePhoto(photo)} disabled={saving} aria-label="Remove edited photo"><Trash2 size={14}/> Remove</button></div>
          </div>)}
        </div>}
        {error&&<p className="form-error" role="alert">{error}</p>}
        <div className="modal-footer"><button type="button" className="button button-secondary" onClick={onClose} disabled={saving}>Cancel</button><button type="submit" className="button button-primary" disabled={saving||loadingImageId!==null}>{saving?<LoaderCircle size={16} className="spin"/>:null}{saving?'Saving…':'Save changes'}</button></div>
      </form>
    </div>
    {cropQueue[cropIndex]&&<ImageCropper key={`${cropIndex}-${cropQueue[cropIndex].file.name}`} file={cropQueue[cropIndex].file} index={cropIndex+1} total={cropQueue.length} onApply={applyCrop} onSkip={skipCrop} onClose={closeCropper}/>}
  </>
}
