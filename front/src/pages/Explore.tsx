
import { useState, type FormEvent } from 'react'
import ExploreMap from '../components/ExploreMap'
import MainLayout from './MainLayout'


export default function Explore() {
  const [videoUrl, setVideoUrl] = useState('')

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()

    if (!videoUrl.trim()) return

    alert(
      'Khung giao diện đã sẵn sàng. Chức năng phân tích video sẽ được tích hợp sau.',
    )
  }

  return (
    <MainLayout pageTitle="Explore Map">
      <form className="video-search" onSubmit={handleSubmit}>
        <span className="search-link-icon">↗</span>

        <input
          type="url"
          value={videoUrl}
          onChange={(e) => setVideoUrl(e.target.value)}
          placeholder="Dán link video TikTok hoặc YouTube Shorts..."
          aria-label="Link video review"
        />

        <button type="submit">
          Phân tích video <span>→</span>
        </button>
      </form>

      <section className="explore-workspace">
        <section className="map-panel">
          <ExploreMap />
        </section>

        <aside className="reviews-panel">
          <div className="reviews-heading">
            <div>
              <span className="section-eyebrow">PLACE REVIEWS</span>
              <h2>Video reviews</h2>
            </div>

            <span className="video-count">0 videos</span>
          </div>

          <div className="reviews-empty">
            <div className="empty-video-icon">▷</div>
            <h3>No place selected</h3>
            <p>
              Select a place on the map to see the review videos linked
              to that location.
            </p>
          </div>

          <div className="reviews-footer">
            <span className="source-dot" />
            <span>
              Videos stay linked to their original platforms.
            </span>
          </div>
        </aside>
      </section>
    </MainLayout>
  )
}
