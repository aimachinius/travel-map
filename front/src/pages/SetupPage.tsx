export default function SetupPage() {
  return (
    <main className="setup-page">
      <div className="brand" aria-label="FoodMap">
        <span className="brand-mark" aria-hidden="true">f.</span>
        <span>FoodMap<span className="brand-dot">.</span></span>
      </div>
      <section className="setup-card" aria-labelledby="setup-title">
        <span className="eyebrow">FOOD REVIEW × BẢN ĐỒ</span>
        <h1 id="setup-title">Từ một chiếc video,<br />đến một địa điểm <em>ngon.</em></h1>
        <p className="intro">Không gian dành cho những khám phá ẩm thực của bạn.</p>
        <div className="setup-status">
          <span className="status-dot" aria-hidden="true" />
          <div>
            <h2>Nền tảng giao diện đã sẵn sàng</h2>
            <p>Bước 1 · Khởi tạo dự án và thiết lập giao diện chung.</p>
          </div>
        </div>
        <p className="setup-note">Đây là màn hình khởi tạo. Các trang tài khoản, phân tích video và bản đồ sẽ được xây dựng ở các bước tiếp theo.</p>
      </section>
      <footer>FoodMap · Đồ án ứng dụng bản đồ vào food review</footer>
    </main>
  )
}
