
import MainLayout from './MainLayout'
import './SavedVideos.css'

export default function SavedVideos() {
  return (
    <MainLayout pageTitle="Saved Videos">
      <section className="saved-videos-page">
        <div className="saved-videos-heading">
          <div>
            <span className="section-eyebrow">YOUR COLLECTION</span>
            <h2>Saved Videos</h2>
            <p>Những video review quán ăn bạn đã lưu.</p>
          </div>

          <span className="saved-videos-count">0 videos</span>
        </div>

        <div className="saved-videos-empty">
          <div className="saved-videos-icon">♡</div>
          <h3>Chưa có video nào</h3>
          <p>
            Khi tìm thấy video review hữu ích, bạn có thể lưu lại
            để xem sau.
          </p>
        </div>
      </section>
    </MainLayout>
  )
}
