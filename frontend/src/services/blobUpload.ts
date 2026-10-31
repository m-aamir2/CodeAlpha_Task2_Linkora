import { upload } from '@vercel/blob/client'

export const usesDirectImageUploads = import.meta.env.PROD || Boolean(import.meta.env.VITE_BLOB_UPLOAD_URL)

export type MediaUploadCategory = 'posts' | 'profiles' | 'stories' | 'reels' | 'reel-thumbnails'

export async function uploadMediaToBlob(
  file: File,
  userId: number,
  category: MediaUploadCategory,
): Promise<string> {
  const accessToken = localStorage.getItem('access')
  if (!accessToken) throw new Error('Please sign in again before uploading media.')
  const video = file.type.startsWith('video/') || /\.(mp4|webm)$/i.test(file.name)
  const maxSize = video ? 100 * 1024 * 1024 : 8 * 1024 * 1024
  if (file.size > maxSize) throw new Error(video ? 'Videos must be 100 MB or smaller.' : 'Images must be 8 MB or smaller.')

  const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_') || 'image'
  const extension = safeName.split('.').pop()?.toLowerCase()
  const fallbackType = extension === 'png' ? 'image/png' : extension === 'webp' ? 'image/webp' : ['jpg', 'jpeg'].includes(extension || '') ? 'image/jpeg' : ''
  const mediaFallback = extension === 'mp4' ? 'video/mp4' : extension === 'webm' ? 'video/webm' : ''
  const contentType = file.type || fallbackType || mediaFallback
  const imageTypes = ['image/jpeg', 'image/png', 'image/webp']
  const videoTypes = ['video/mp4', 'video/webm']
  const allowed = category === 'reels' ? videoTypes : category === 'stories' ? [...imageTypes, ...videoTypes] : imageTypes
  if (!allowed.includes(contentType)) throw new Error(category === 'reels' ? 'Choose an MP4 or WebM video.' : 'Choose a JPG, PNG, WebP, MP4, or WebM file.')
  const handleUploadUrl = import.meta.env.PROD ? '/api/blob-upload' : import.meta.env.VITE_BLOB_UPLOAD_URL || '/api/blob-upload'
  const blob = await upload(`users/${userId}/${category}/${safeName}`, file, {
    access: 'public',
    contentType,
    handleUploadUrl,
    clientPayload: JSON.stringify({ accessToken }),
    multipart: file.size > 5 * 1024 * 1024,
  })
  return blob.url
}

export async function uploadImageToBlob(file: File, userId: number, category: 'posts' | 'profiles'): Promise<string> {
  return uploadMediaToBlob(file, userId, category)
}
