import { upload } from '@vercel/blob/client'

export const usesDirectImageUploads = import.meta.env.PROD || Boolean(import.meta.env.VITE_BLOB_UPLOAD_URL)

export async function uploadImageToBlob(
  file: File,
  userId: number,
  category: 'posts' | 'profiles',
): Promise<string> {
  const accessToken = localStorage.getItem('access')
  if (!accessToken) throw new Error('Please sign in again before uploading images.')
  if (file.size > 8 * 1024 * 1024) throw new Error('Images must be 8 MB or smaller.')

  const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_') || 'image'
  const extension = safeName.split('.').pop()?.toLowerCase()
  const fallbackType = extension === 'png' ? 'image/png' : extension === 'webp' ? 'image/webp' : ['jpg', 'jpeg'].includes(extension || '') ? 'image/jpeg' : ''
  const contentType = file.type || fallbackType
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(contentType)) {
    throw new Error('Choose a JPG, PNG, or WebP image.')
  }
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
