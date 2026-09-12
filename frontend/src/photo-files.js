const supportedPhotoTypes = new Set([
  'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif',
]);
const supportedPhotoExtensions = /\.(?:jpe?g|png|webp|heic|heif)$/i;

export function collectPhotoFiles(currentFiles, incomingFiles) {
  const incoming = Array.from(incomingFiles);
  const invalid = incoming.find(file => (
    !supportedPhotoTypes.has(file.type) && !supportedPhotoExtensions.test(file.name)
  ));
  if (invalid) {
    return { files: currentFiles, error: '请选择 JPG、PNG、WebP 或苹果照片格式。' };
  }
  return { files: [...currentFiles, ...incoming], error: null };
}
