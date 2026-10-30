from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage


class VercelBlobStorage(FileSystemStorage):
    """Use durable public Blob URLs in production and local files during dev."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL, **kwargs)

    @staticmethod
    def _is_blob_url(name):
        return isinstance(name, str) and name.startswith("https://")

    def _save(self, name, content):
        if not settings.USE_VERCEL_BLOB:
            return super()._save(name, content)

        from vercel.blob import sync as blob

        pathname = name.replace("\\", "/").lstrip("/")
        content_type = getattr(content, "content_type", None)
        if not content_type:
            import mimetypes
            content_type = mimetypes.guess_type(pathname)[0] or "application/octet-stream"
        result = blob.put_blob(
            pathname,
            content.read(),
            access="public",
            content_type=content_type,
            add_random_suffix=True,
        )
        return result.url

    def delete(self, name):
        if self._is_blob_url(name):
            from vercel.blob import sync as blob
            blob.delete_blob(name)
            return
        return super().delete(name)

    def exists(self, name):
        if self._is_blob_url(name):
            return False
        return super().exists(name)

    def url(self, name):
        if self._is_blob_url(name):
            return name
        return super().url(name)

    def path(self, name):
        if self._is_blob_url(name):
            raise NotImplementedError("Vercel Blob objects do not have a local filesystem path.")
        return super().path(name)

    def _open(self, name, mode="rb"):
        if self._is_blob_url(name):
            from vercel.blob import sync as blob
            result = blob.get_blob(name, access="public")
            filename = Path(urlsplit(name).path).name or "image"
            return ContentFile(result.body, name=filename)
        return super()._open(name, mode)
