import { handleUpload, type HandleUploadBody } from '@vercel/blob/client'
import { jwtVerify } from 'jose'

const imageTypes = ['image/jpeg', 'image/png', 'image/webp']
const maxImageSize = 8 * 1024 * 1024

export default async function handler(request: any, response: any) {
  response.setHeader('Cache-Control', 'no-store')
  if (request.method !== 'POST') {
    response.setHeader('Allow', 'POST')
    return response.status(405).json({ detail: 'Method not allowed.' })
  }

  const secret = process.env.SECRET_KEY
  const blobToken = process.env.BLOB_READ_WRITE_TOKEN
  if (!secret || !blobToken) {
    return response.status(503).json({ detail: 'Image uploads are not configured for this deployment.' })
  }

  try {
    const body = request.body as HandleUploadBody
    const result = await handleUpload({
      body,
      request,
      token: blobToken,
      onBeforeGenerateToken: async (pathname, clientPayload) => {
        const { accessToken } = JSON.parse(clientPayload || '{}') as { accessToken?: string }
        if (!accessToken) throw new Error('Authentication required.')

        const { payload } = await jwtVerify(accessToken, new TextEncoder().encode(secret), {
          algorithms: ['HS256'],
        })
        const userId = String(payload.user_id || '')
        const path = pathname.match(/^users\/(\d+)\/(posts|profiles)\/([a-zA-Z0-9._-]+)$/)
        if (payload.token_type !== 'access' || !/^\d+$/.test(userId) || !path || path[1] !== userId) {
          throw new Error('You are not allowed to upload this image.')
        }

        return {
          addRandomSuffix: true,
          allowedContentTypes: imageTypes,
          maximumSizeInBytes: maxImageSize,
        }
      },
      onUploadCompleted: async () => undefined,
    })
    return response.status(200).json(result)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Image upload failed.'
    const status = /auth|allowed/i.test(message) ? 401 : 400
    return response.status(status).json({ detail: message })
  }
}
