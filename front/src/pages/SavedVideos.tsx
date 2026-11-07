/**
 * @deprecated LEGACY COMPONENT - ĐÃ NGƯNG SỬ DỤNG TRONG ROUTING CHÍNH
 * Chức năng "Video đã lưu" đã được thay thế bằng ngăn kéo kính thể lỏng (Liquid Drawer: Liked Videos)
 * trực tiếp trên trang /explore.
 * File này được giữ lại nhằm mục đích tham khảo mã nguồn cũ, không xóa.
 */

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
