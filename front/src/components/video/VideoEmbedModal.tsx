import './VideoEmbedModal.css'

interface VideoEmbedModalProps {
  video: {
    id: string
    platform: string
    platform_video_id: string
    video_url: string
    title: string | null
    author_name: string | null
  } | null
  onClose: () => void
}

export default function VideoEmbedModal({
  video,
  onClose,
}: VideoEmbedModalProps) {
  if (!video) return null

  let embedUrl = ''
  if (video.platform === 'youtube') {
    embedUrl = `https://www.youtube.com/embed/${video.platform_video_id}?autoplay=1`
  } else if (video.platform === 'tiktok') {
    embedUrl = `https://www.tiktok.com/embed/v2/${video.platform_video_id}`
  }

  return (
    <div className="video-modal-backdrop" onClick={onClose}>
      <div
        className="video-modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="video-modal-header">
          <div>
            <span className="video-modal-platform-badge">
              {video.platform.toUpperCase()}
            </span>
            <h3>{video.title || 'Video review ẩm thực'}</h3>
            {video.author_name && <p className="video-modal-author">bởi @{video.author_name}</p>}
          </div>

          <button
            type="button"
            className="video-modal-close"
            onClick={onClose}
            aria-label="Đóng video"
          >
            ✕
          </button>
        </div>

        <div className="video-modal-body">
          {embedUrl ? (
            <iframe
              src={embedUrl}
              title={video.title || 'Video player'}
              className="video-embed-iframe"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          ) : (
            <div className="video-embed-fallback">
              <p>Không thể nhúng trực tiếp trình phát này.</p>
              <a
                href={video.video_url}
                target="_blank"
                rel="noreferrer"
                className="video-modal-external-link"
              >
                Mở video trên {video.platform} →
              </a>
            </div>
          )}
        </div>

        <div className="video-modal-footer">
          <a
            href={video.video_url}
            target="_blank"
            rel="noreferrer"
            className="video-modal-open-btn"
          >
            Mở trên link gốc ↗
          </a>
        </div>
      </div>
    </div>
  )
}
