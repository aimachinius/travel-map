import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ChromaticPalette, EngineType, VideoPlaylistItem } from './types'
import { PRESET_PALETTES, generatePaletteFromId } from './mockData'
import { useAuth } from '../../services/useAuth'
import { savedApi } from '../../services/api'

interface LiquidVideoPlayerProps {
  currentVideo: VideoPlaylistItem | null
  isActive?: boolean
  engine?: EngineType
  onToggleEngine?: () => void
  onRefresh: () => void
  onPrevVideo: () => void
  onNextVideo: () => void
  playlist?: VideoPlaylistItem[]
  currentIndex?: number
  isRoutingActive?: boolean
  onToggleRouting?: () => void
}

// Bộ nhớ đệm thumbnail oEmbed để tránh lặp lại request mạng
const oembedThumbnailCache = new Map<string, string>()

export default function LiquidVideoPlayer({
  currentVideo,
  isActive = true,
  engine: _engine,
  onToggleEngine: _onToggleEngine,
  onRefresh,
  onPrevVideo,
  onNextVideo,
  playlist = [],
  currentIndex = 0,
  isRoutingActive = false,
  onToggleRouting,
}: LiquidVideoPlayerProps) {
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [isPlaying, setIsPlaying] = useState<boolean>(true)
  const isPlayingRef = useRef<boolean>(true)
  const volumeSetVideosRef = useRef<Set<string>>(new Set())

  // Trạng thái âm thanh:
  // - Khi ở Trang chủ (isActive = false): TẮT TIẾNG (Muted = true), không phát âm thanh khi chưa vào bản đồ
  // - Khi vào Bản đồ Review (isActive = true): TỰ ĐỘNG BẬT TIẾNG (Muted = false), không bắt người dùng bật thủ công
  const [isMuted, setIsMuted] = useState<boolean>(() => !isActive)
  const isMutedRef = useRef<boolean>(!isActive)
  const prevIsActiveRef = useRef<boolean>(isActive)

  useEffect(() => {
    isMutedRef.current = isMuted
  }, [isMuted])

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const iframeRefs = useRef<Record<string, HTMLIFrameElement | null>>({})
  const userWatchedTimesRef = useRef<Record<string, number>>({})

  // Điều phối tải trước so le (Staggered Preload):
  // Khi videoId thay đổi: canPreloadNext tự động là false ngay trong render cycle (tránh cascading render).
  // Sau 250ms (khi main thread rảnh): activePreloadId được cập nhật -> canPreloadNext = true -> tải ngầm video kế tiếp.
  const [activePreloadId, setActivePreloadId] = useState<string | null>(null)

  const videoId = currentVideo?.id || ''
  const canPreloadNext = Boolean(videoId && activePreloadId === videoId)

  const { user, token } = useAuth()
  const [isSaved, setIsSaved] = useState<boolean>(Boolean(currentVideo?.isSaved))

  useEffect(() => {
    setIsSaved(Boolean(currentVideo?.isSaved))
  }, [currentVideo?.id, currentVideo?.isSaved])

  const handleToggleSave = async () => {
    if (!token || !user) {
      alert('Vui lòng đăng nhập để lưu quán ăn này vào bộ sưu tập của bạn!')
      return
    }

    try {
      if (isSaved) {
        if (currentVideo?.placeId) await savedApi.unsavePlace(currentVideo.placeId)
        if (currentVideo?.videoId) await savedApi.unsaveVideo(currentVideo.videoId)
        setIsSaved(false)
      } else {
        if (currentVideo?.placeId) await savedApi.savePlace(currentVideo.placeId)
        if (currentVideo?.videoId) await savedApi.saveVideo(currentVideo.videoId)
        setIsSaved(true)
      }
    } catch (err) {
      console.warn('Lỗi khi lưu/bỏ lưu:', err)
    }
  }

  const playerState: 'empty' | 'loading' | 'video' = !currentVideo
    ? 'empty'
    : isLoading
      ? 'loading'
      : 'video'

  // Kích hoạt hẹn giờ tải so le 250ms mỗi khi chuyển sang video mới
  useEffect(() => {
    const timer = setTimeout(() => {
      setActivePreloadId(videoId)
    }, 250)
    return () => clearTimeout(timer)
  }, [videoId])

  // =========================================================================
  // CỬA SỔ TRƯỢT 3 PHẦN TỬ SO LE (STAGGERED SLIDING WINDOW TRI-BUFFER)
  // - [Prev] (nếu có): Đã xem, tạm dừng, giữ trong cache để lướt ngược lại mượt mà.
  // - [Current]: Đang phát, loa 75%, ưu tiên toàn bộ tài nguyên CPU/Network.
  // - [Next] (sau 250ms): Tải ngầm và ĐÓNG BĂNG tại 00:00 (không chạy trước).
  // - Các video xa hơn: Hoàn toàn không mount -> RAM luôn ổn định dưới 150MB.
  // =========================================================================
  const slidingWindow = useMemo(() => {
    if (!playlist || playlist.length === 0) {
      return currentVideo ? [{ item: currentVideo, role: 'current' as const }] : []
    }
    const len = playlist.length
    const curIdx =
      currentIndex >= 0 && currentIndex < len
        ? currentIndex
        : playlist.findIndex((p) => p.id === videoId)

    if (curIdx === -1) {
      return currentVideo ? [{ item: currentVideo, role: 'current' as const }] : []
    }

    const currentItem = playlist[curIdx]
    const list: { item: VideoPlaylistItem; role: 'current' | 'next' | 'prev' }[] = [
      { item: currentItem, role: 'current' },
    ]

    // Preload video tiếp theo (Next) sau nhịp nghỉ so le 250ms
    if (len > 1 && canPreloadNext) {
      const nextIdx = (curIdx + 1) % len
      list.push({ item: playlist[nextIdx], role: 'next' })
    }

    // Giữ video trước đó (Prev) trong bộ đệm để lướt ngược lại tức thì
    if (len > 2) {
      const prevIdx = (curIdx - 1 + len) % len
      const nextIdx = (curIdx + 1) % len
      if (prevIdx !== nextIdx) {
        list.push({ item: playlist[prevIdx], role: 'prev' })
      }
    }

    return list
  }, [playlist, currentIndex, videoId, currentVideo, canPreloadNext])

  // Gửi lệnh điều khiển postMessage tới từng frame TikTok (changeVolume chuẩn API TikTok 0-100)
  const sendPlayerCommand = useCallback(
    (
      targetId: string,
      type: 'play' | 'pause' | 'mute' | 'unMute' | 'seekTo' | 'changeVolume',
      value?: unknown,
    ) => {
      const frame = iframeRefs.current[targetId]
      if (frame && frame.contentWindow) {
        frame.contentWindow.postMessage(
          {
            'x-tiktok-player': true,
            type,
            ...(value !== undefined ? { value } : {}),
          },
          '*',
        )
      }
    },
    [],
  )

  // Lắng nghe tín hiệu postMessage từ TikTok iframe (onPlayerReady, onCurrentTime, onStateChange)
  useEffect(() => {
    const handleWindowMessage = (e: MessageEvent) => {
      if (e.data && typeof e.data === 'object' && e.data['x-tiktok-player']) {
        if (e.data.type === 'onCurrentTime' && typeof e.data.value === 'number') {
          // CHỈ LƯU TIẾN TRÌNH CHO VIDEO ĐANG THỰC SỰ XEM (isCurrent)
          if (videoId) {
            userWatchedTimesRef.current[videoId] = e.data.value
          }
        }
        if (e.data.type === 'onStateChange' && typeof e.data.value === 'number') {
          if (e.data.value === 1) {
            setIsPlaying(true)
            isPlayingRef.current = true
          } else if (e.data.value === 2 || e.data.value === 0) {
            setIsPlaying(false)
            isPlayingRef.current = false
          }
        }
        if (e.data.type === 'onPlayerReady') {
          // Định danh chính xác iframe phát tín hiệu ready bằng e.source
          const matchedEntry = slidingWindow.find(
            (w) => iframeRefs.current[w.item.id]?.contentWindow === e.source,
          )
          const readyId = matchedEntry ? matchedEntry.item.id : videoId
          const isReadyCurrent = readyId === videoId

          // Nếu chưa ở trang Khám phá (đang ở Trang chủ): TUYỆT ĐỐI KHÔNG PHÁT VÀ KHÔNG BẬT ÂM THANH
          if (!isActive) {
            sendPlayerCommand(readyId, 'pause')
            sendPlayerCommand(readyId, 'mute')
            return
          }

          if (isReadyCurrent) {
            setIsLoading(false)
            sendPlayerCommand(readyId, 'play')
            if (!isMutedRef.current) {
              sendPlayerCommand(readyId, 'unMute')
              if (!volumeSetVideosRef.current.has(readyId)) {
                sendPlayerCommand(readyId, 'changeVolume', 75)
                volumeSetVideosRef.current.add(readyId)
              }
            } else {
              sendPlayerCommand(readyId, 'mute')
            }
          } else {
            // Video tiếp theo hoặc trước đó nạp xong trong buffer ngầm:
            // ĐÓNG BĂNG NGAY LẬP TỨC TẠI 00:00 (pause, mute, seekTo 0)
            sendPlayerCommand(readyId, 'pause')
            sendPlayerCommand(readyId, 'mute')
            sendPlayerCommand(readyId, 'seekTo', 0)
          }
        }
      }
    }
    window.addEventListener('message', handleWindowMessage)
    return () => window.removeEventListener('message', handleWindowMessage)
  }, [isActive, videoId, slidingWindow, sendPlayerCommand])

  // Người dùng chủ động bật / tắt âm thanh qua nút bấm hoặc cử chỉ
  const handleToggleMute = useCallback(() => {
    if (!videoId) return
    setIsMuted((prev) => {
      const next = !prev
      if (!next) {
        sendPlayerCommand(videoId, 'unMute')
        sendPlayerCommand(videoId, 'changeVolume', 75)
        volumeSetVideosRef.current.add(videoId)
      } else {
        sendPlayerCommand(videoId, 'mute')
      }
      return next
    })
  }, [videoId, sendPlayerCommand])

  // Lắng nghe khi isActive thay đổi:
  // - Bước vào Bản đồ Review (isActive = true): Tự động bật tiếng (Unmute) và set volume 75
  // - Quay về Trang chủ (isActive = false): Tắt tiếng & ngắt âm hoàn toàn
  useEffect(() => {
    if (isActive && !prevIsActiveRef.current) {
      setIsMuted(false)
      isMutedRef.current = false
      if (videoId) {
        sendPlayerCommand(videoId, 'unMute')
        sendPlayerCommand(videoId, 'changeVolume', 75)
        volumeSetVideosRef.current.add(videoId)
      }
    } else if (!isActive && prevIsActiveRef.current) {
      setIsMuted(true)
      isMutedRef.current = true
    }
    prevIsActiveRef.current = isActive
  }, [isActive, videoId, sendPlayerCommand])

  // Điều phối âm thanh và trạng thái phát:
  // - Khi isActive = false (về Trang chủ): Dừng và ngắt âm toàn bộ các iframe
  // - Khi isActive = true: Phát video hiện tại (giữ mute theo isMuted), đóng băng video phụ
  useEffect(() => {
    if (!isActive) {
      slidingWindow.forEach(({ item }) => {
        sendPlayerCommand(item.id, 'pause')
        sendPlayerCommand(item.id, 'mute')
      })
      isPlayingRef.current = false
    } else if (videoId) {
      slidingWindow.forEach(({ item, role }) => {
        if (role === 'current') {
          sendPlayerCommand(item.id, 'play')
          if (!isMutedRef.current) {
            sendPlayerCommand(item.id, 'unMute')
            if (!volumeSetVideosRef.current.has(item.id)) {
              sendPlayerCommand(item.id, 'changeVolume', 75)
              volumeSetVideosRef.current.add(item.id)
            }
          } else {
            sendPlayerCommand(item.id, 'mute')
          }
          const savedTime = userWatchedTimesRef.current[item.id]
          if (savedTime && savedTime > 1) {
            sendPlayerCommand(item.id, 'seekTo', savedTime)
          } else {
            sendPlayerCommand(item.id, 'seekTo', 0)
          }
        } else {
          // Video khác trong buffer ngầm: Đóng băng chặt chẽ tại 00:00
          sendPlayerCommand(item.id, 'pause')
          sendPlayerCommand(item.id, 'mute')
          sendPlayerCommand(item.id, 'seekTo', 0)
        }
      })
      isPlayingRef.current = true
    }
  }, [isActive, videoId, slidingWindow, sendPlayerCommand])

  // =========================================================================
  // XỬ LÝ CỬ CHỈ LƯỚT VÀ CUỘN (LƯỚT TỚI ĐÂU - CHẠY TỚI ĐÓ)
  // =========================================================================
  const isWheelingRef = useRef(false)
  const pointerStartY = useRef<number | null>(null)
  const pointerStartTime = useRef<number>(0)
  const hasMoved = useRef<boolean>(false)

  // Ghi nhớ xem người dùng đã thực hiện thao tác lướt lần nào chưa
  // Khi vừa vào Page review: hiện gợi ý; sau khi lướt lần đầu tiên: ẩn vĩnh viễn
  const [hasSwiped, setHasSwiped] = useState<boolean>(() => {
    return typeof window !== 'undefined' && sessionStorage.getItem('has_swiped_video') === 'true'
  })

  const markSwiped = useCallback(() => {
    setHasSwiped((prev) => {
      if (!prev) {
        try {
          sessionStorage.setItem('has_swiped_video', 'true')
        } catch {
          // ignore
        }
        return true
      }
      return prev
    })
  }, [])

  // Theo dõi nếu videoId thay đổi từ video ban đầu -> tự động đánh dấu đã lướt
  const initialVideoIdRef = useRef<string | null>(videoId)
  useEffect(() => {
    if (initialVideoIdRef.current && videoId && videoId !== initialVideoIdRef.current) {
      markSwiped()
    }
  }, [videoId, markSwiped])

  // 1. Cuộn con lăn chuột (Mouse Wheel) để lướt video tức thì
  const handleWheel = (e: React.WheelEvent) => {
    e.stopPropagation()
    if (isWheelingRef.current) return

    if (Math.abs(e.deltaY) > 20) {
      isWheelingRef.current = true
      markSwiped()
      if (e.deltaY > 0) {
        onNextVideo()
      } else {
        onPrevVideo()
      }
      setTimeout(() => {
        isWheelingRef.current = false
      }, 250)
    }
  }

  // 2. Chạm vuốt ngón tay (Touch Swipe) & Kéo chuột (Mouse Drag)
  const handlePointerDown = (e: React.PointerEvent) => {
    pointerStartY.current = e.clientY
    pointerStartTime.current = Date.now()
    hasMoved.current = false
  }

  const handlePointerMove = (e: React.PointerEvent) => {
    if (pointerStartY.current === null) return
    if (Math.abs(e.clientY - pointerStartY.current) > 10) {
      hasMoved.current = true
    }
  }

  const handlePointerUp = (e: React.PointerEvent) => {
    if (pointerStartY.current === null) return
    const diffY = pointerStartY.current - e.clientY
    const elapsed = Date.now() - pointerStartTime.current

    if (Math.abs(diffY) > 35) {
      markSwiped()
      // Vuốt lên -> Sang video tiếp theo (Next)
      if (diffY > 0) {
        onNextVideo()
      } else {
        // Vuốt xuống -> Sang video trước (Prev)
        onPrevVideo()
      }
    } else if (!hasMoved.current && elapsed < 400) {
      // Cú Click / Tap ngắn vào video: Toggle Play / Pause chuẩn phong cách TikTok
      if (videoId) {
        if (isPlayingRef.current) {
          sendPlayerCommand(videoId, 'pause')
          setIsPlaying(false)
          isPlayingRef.current = false
        } else {
          sendPlayerCommand(videoId, 'play')
          sendPlayerCommand(videoId, 'unMute')
          if (!volumeSetVideosRef.current.has(videoId)) {
            sendPlayerCommand(videoId, 'changeVolume', 75)
            volumeSetVideosRef.current.add(videoId)
          }
          setIsPlaying(true)
          isPlayingRef.current = true
        }
      }
    }

    pointerStartY.current = null
    hasMoved.current = false
  }

  const palette: ChromaticPalette = videoId
    ? PRESET_PALETTES[videoId] || generatePaletteFromId(videoId)
    : {
        c1: '#00f0ff',
        c2: '#a855f7',
        c3: '#ff007f',
        c4: '#ff2a8d',
        c5: '#00ff88',
        c6: '#ff3b30',
        c7: '#ff9500',
      }

  const [, setOembedVersion] = useState<number>(0)
  const currentPoster = useMemo(() => {
    if (!currentVideo) return null
    const targetUrl = currentVideo.url || `https://www.tiktok.com/@tiktok/video/${currentVideo.id}`
    return oembedThumbnailCache.get(targetUrl) || null
  }, [currentVideo])

  // Quản lý trạng thái chuyển đổi Video, Ambient Canvas và Instant Poster Shell
  useEffect(() => {
    if (!currentVideo) return

    const targetUrl = currentVideo.url || `https://www.tiktok.com/@tiktok/video/${currentVideo.id}`
    const cachedThumb = oembedThumbnailCache.get(targetUrl)

    const canvas = canvasRef.current
    if (canvas) {
      const ctx = canvas.getContext('2d')
      if (ctx) {
        if (cachedThumb) {
          const img = new Image()
          img.onload = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height)
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
          }
          img.src = cachedThumb
        } else {
          const oembedApi = `https://www.tiktok.com/oembed?url=${encodeURIComponent(targetUrl)}`
          fetch(oembedApi)
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => {
              if (data?.thumbnail_url) {
                oembedThumbnailCache.set(targetUrl, data.thumbnail_url)
                setOembedVersion((v) => v + 1)
                const img = new Image()
                img.onload = () => {
                  ctx.clearRect(0, 0, canvas.width, canvas.height)
                  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
                }
                img.src = data.thumbnail_url
              }
            })
            .catch(() => {})
        }
      }
    }
  }, [currentVideo])

  // Tải trước ảnh Poster (Thumbnail) ngầm cho video tiếp theo để khi lướt là có hình ngay (0ms)
  useEffect(() => {
    slidingWindow.forEach(({ item }) => {
      const targetUrl = item.url || `https://www.tiktok.com/@tiktok/video/${item.id}`
      if (!oembedThumbnailCache.has(targetUrl)) {
        const oembedApi = `https://www.tiktok.com/oembed?url=${encodeURIComponent(targetUrl)}`
        fetch(oembedApi)
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data?.thumbnail_url) {
              oembedThumbnailCache.set(targetUrl, data.thumbnail_url)
            }
          })
          .catch(() => {})
      }
    })
  }, [slidingWindow])

  const gmapsUrl = currentVideo
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
        currentVideo.gmapQuery || currentVideo.locationName,
      )}`
    : '#'

  const tiktokUrl = currentVideo?.url || '#'

  return (
    <section className="video-display-area" aria-label="Khung hiển thị Video TikTok">
      {/* Khung viền Liquid Glass Bezel */}
      <div
        className={`liquid-glass-bezel ${playerState === 'empty' ? 'is-empty' : 'is-playing'}`}
        id="phoneFrame"
      >
        {/* Lớp 1: Ambient Glow */}
        <div
          className="ambient-glow-wrapper"
          style={{ opacity: playerState === 'empty' ? 0 : 0.95 }}
        >
          <div
            className="ambient-glow-gradient"
            style={
              {
                '--glow-c1': palette.c1,
                '--glow-c2': palette.c2,
                '--glow-c3': palette.c3,
                '--glow-c4': palette.c4,
                '--glow-c5': palette.c5,
                '--glow-c6': palette.c6,
                '--glow-c7': palette.c7,
              } as Record<string, string>
            }
          />
          <canvas ref={canvasRef} className="ambient-canvas" width="36" height="64" />
        </div>

        {/* Lớp 2: Glass Surface Overlay + Notch */}
        <div className="glass-surface-overlay">
          <div className="device-notch">
            <div className="speaker-grill" />
            <div className="lens-dot" />
          </div>
        </div>

        {/* Lớp 3: Video Screen */}
        <div className={`video-screen ${playerState === 'empty' ? 'is-empty' : 'is-playing'}`}>
          {/* State 1: Empty (Kính trong suốt nhìn xuống map) */}
          <div className={`screen-state empty-state ${playerState === 'empty' ? 'active' : ''}`} />

          {/* State 2: Loading Shimmer */}
          <div className={`screen-state loading-state ${playerState === 'loading' ? 'active' : ''}`}>
            <div className="liquid-spinner">
              <div className="spinner-ring ring-outer" />
              <div className="spinner-ring ring-inner" />
            </div>
            <p className="loading-label">Đang nạp video TikTok...</p>
          </div>

          {/* State 3: Active Video & Staggered Sliding Tri-Buffer */}
          <div className={`screen-state video-state ${playerState === 'video' ? 'active' : ''}`}>
            {/* Lớp Instant Poster Shell: Ngay khi lướt sang (0ms), poster sắc nét hiện diện ngay */}
            {currentPoster && (
              <div
                className="tiktok-instant-poster-shell"
                style={{
                  position: 'absolute',
                  inset: 0,
                  backgroundImage: `url(${currentPoster})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                  zIndex: 0,
                  filter: 'brightness(0.92)',
                  pointerEvents: 'none',
                  transition: 'opacity 0.25s ease',
                }}
              />
            )}

            {/* 
              HỆ THỐNG CỬA SỔ TRƯỢT 3 PHẦN TỬ SO LE (STAGGERED SLIDING WINDOW TRI-BUFFER):
              - CHỈ MOUNT KHI isActive = true (khi ở trang Khám phá / xem review).
              - Khi ở Trang chủ (isActive = false): Tuyệt đối KHÔNG mount iframe -> 0% CPU, 0% âm thanh chạy ngầm!
              - Tại mọi thời điểm chỉ duy trì tối đa 2 đến 3 thẻ iframe (Prev, Current, Next).
              - Ban đầu vào Explore: Chỉ nạp 1 video duy nhất -> 100% tài nguyên cho Video 0 -> 0% lag!
              - Sau 250ms: Bắt đầu tải ngầm Video Next và ĐÓNG BĂNG tại 00:00 (không chạy trước).
              - Mặc định khởi tạo ở chế độ TẮT TIẾNG (Muted), chỉ bật tiếng khi người dùng chủ động chọn.
            */}
            {isActive &&
              slidingWindow.map(({ item, role }) => {
                const isCurrent = role === 'current'
                return (
                  <iframe
                    key={item.id}
                    ref={(el) => {
                      if (el) {
                        iframeRefs.current[item.id] = el
                      } else {
                        delete iframeRefs.current[item.id]
                      }
                    }}
                    src={`https://www.tiktok.com/player/v1/${item.id}?embed_from=webapp_share&music_info=0&description=0&autoplay=1&muted=${isCurrent && !isMuted ? 0 : 1}&rel=0&loop=1`}
                    title={isCurrent ? currentVideo?.title || 'TikTok Video Player' : `Buffered Video ${item.id}`}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    sandbox="allow-scripts allow-same-origin allow-forms"
                    loading={isCurrent ? 'eager' : 'lazy'}
                    onLoad={() => {
                      if (!isActive) {
                        sendPlayerCommand(item.id, 'pause')
                        sendPlayerCommand(item.id, 'mute')
                        return
                      }

                      if (isCurrent) {
                        setIsLoading(false)
                        sendPlayerCommand(item.id, 'play')
                        if (!isMutedRef.current) {
                          sendPlayerCommand(item.id, 'unMute')
                          if (!volumeSetVideosRef.current.has(item.id)) {
                            sendPlayerCommand(item.id, 'changeVolume', 75)
                            volumeSetVideosRef.current.add(item.id)
                          }
                        } else {
                          sendPlayerCommand(item.id, 'mute')
                        }
                        const savedTime = userWatchedTimesRef.current[item.id]
                        if (savedTime && savedTime > 1) {
                          sendPlayerCommand(item.id, 'seekTo', savedTime)
                        } else {
                          sendPlayerCommand(item.id, 'seekTo', 0)
                        }
                      } else {
                        // Video Next hoặc Prev nạp ngầm trong buffer:
                        // ĐÓNG BĂNG NGAY LẬP TỨC TẠI 00:00 (Tạm dừng, tắt tiếng, tua về 0)
                        sendPlayerCommand(item.id, 'pause')
                        sendPlayerCommand(item.id, 'mute')
                        sendPlayerCommand(item.id, 'seekTo', 0)
                      }
                    }}
                    className={`tiktok-sliding-frame ${isCurrent ? 'is-active' : 'is-cached'}`}
                    style={{
                      position: 'absolute',
                      inset: 0,
                      width: '100%',
                      height: '100%',
                      border: 'none',
                      opacity: isCurrent ? 1 : 0,
                      pointerEvents: isCurrent ? 'auto' : 'none',
                      zIndex: isCurrent ? 2 : 1,
                      transition: 'opacity 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
                    }}
                  />
                )
              })}

            {/* Biểu tượng Pause ở giữa màn hình khi tạm dừng (chuẩn TikTok) */}
            {!isPlaying && playerState === 'video' && (
              <div className="tiktok-center-pause-indicator" aria-hidden="true">
                <div className="pause-icon-circle">
                  <svg viewBox="0 0 24 24" width="40" height="40" fill="white">
                    <polygon points="6 4 20 12 6 20 6 4" />
                  </svg>
                </div>
              </div>
            )}

            {/* Màn che khi người dùng đang ở Trang chủ (tắt tương tác & tối ưu hiển thị) */}
            {!isActive && (
              <div className="inactive-poster-overlay">
                <div className="inactive-play-hint">
                  <svg viewBox="0 0 24 24" width="32" height="32" fill="white">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                </div>
              </div>
            )}

            {/* Lớp cảm ứng lướt TikTok thông minh (Click để Pause/Play, Kéo/Cuộn để lướt) */}
            <div
              className="tiktok-gesture-surface"
              onWheel={handleWheel}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onPointerCancel={handlePointerUp}
              aria-label="Khu vực điều khiển và lướt video TikTok"
            />

            {/* Gợi ý cử chỉ lướt tinh tế (chỉ hiện khi mới vào, lướt 1 phát là ẩn vĩnh viễn) */}
            {!hasSwiped && (
              <div className="tiktok-swipe-hint">
                <span>⇅ Cuộn chuột hoặc vuốt để lướt</span>
              </div>
            )}

            {/* Lá chắn chặn click Tim, Bình luận, Share (chỉ xem số liệu, không thể click nhảy app) */}
            <div
              className="tiktok-actions-shield"
              title="Số liệu tương tác (chỉ xem)"
              aria-hidden="true"
            />

            {/* Lá chắn chặn click Avatar và Logo TikTok góc trên */}
            <div
              className="tiktok-top-shield"
              title="Thông tin tác giả (chỉ xem)"
              aria-hidden="true"
            />

            {/* Lá chắn góc dưới: Không chặn click để nút Cài đặt (⚙) hoạt động trơn tru */}
            <div className="fullscreen-blocker-shield" aria-hidden="true" />

            {/* Nút bật âm thanh nhanh trên video khi đang tắt tiếng */}
            {isMuted && playerState === 'video' && isActive && (
              <button
                type="button"
                className="tiktok-mute-badge"
                onClick={handleToggleMute}
                aria-label="Bật âm thanh"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="13"
                  height="13"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="white" />
                  <line x1="22" y1="9" x2="16" y2="15" />
                  <line x1="16" y1="9" x2="22" y2="15" />
                </svg>
                <span>Nhấn để bật tiếng</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Right Action Dock (Gắn trực tiếp document.body qua createPortal để chạm sát tường phải 100%, đối xứng với cụm 3 nút trái) */}
      {isActive &&
        typeof document !== 'undefined' &&
        createPortal(
          <div className="frame-floating-controls" aria-label="Cụm phím tác vụ phải">
            {/* Toggle Âm thanh (Bật / Tắt tiếng) */}
            <button
              type="button"
              className={`frame-action-btn liquid-glass ${!isMuted ? 'is-sound-on' : ''}`}
              onClick={handleToggleMute}
              aria-label={isMuted ? 'Bật âm thanh' : 'Tắt âm thanh'}
            >
              {isMuted ? (
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  <line x1="23" y1="9" x2="17" y2="15" />
                  <line x1="17" y1="9" x2="23" y2="15" />
                </svg>
              ) : (
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
                </svg>
              )}
              <span className="dock-tooltip right-side">{isMuted ? 'Bật âm thanh' : 'Tắt âm thanh'}</span>
            </button>

            {/* Refresh video */}
            <button
              type="button"
              className="frame-action-btn liquid-glass"
              onClick={() => {
                setIsLoading(true)
                onRefresh()
              }}
              aria-label="Tải lại"
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
              </svg>
              <span className="dock-tooltip right-side">Tải lại video</span>
            </button>

            {/* Nút Bật/Tắt Chỉ đường OSRM trên bản đồ */}
            <button
              type="button"
              className={`frame-action-btn liquid-glass ${isRoutingActive ? 'is-routing-active' : ''}`}
              onClick={onToggleRouting}
              aria-label="Chỉ đường"
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <polygon
                  points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"
                  fill="currentColor"
                  fillOpacity="0.25"
                />
              </svg>
              <span className="dock-tooltip right-side">
                {isRoutingActive ? 'Đang chỉ đường (Bấm để tắt)' : '🧭 Chỉ đường đến quán'}
              </span>
            </button>

            {/* Nút Lưu quán / Bỏ lưu */}
            <button
              type="button"
              className={`frame-action-btn liquid-glass ${isSaved ? 'is-saved' : ''}`}
              onClick={handleToggleSave}
              aria-label={isSaved ? 'Bỏ lưu quán' : 'Lưu quán yêu thích'}
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill={isSaved ? '#ff007f' : 'none'}
                stroke={isSaved ? '#ff007f' : 'currentColor'}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
              </svg>
              <span className="dock-tooltip right-side">
                {isSaved ? 'Đã lưu (Bấm để bỏ lưu)' : '❤️ Lưu quán này'}
              </span>
            </button>

            {/* Mở Google Maps định vị quán */}
            <a
              href={gmapsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="frame-action-btn liquid-glass"
              aria-label="Google Maps"
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
              <span className="dock-tooltip right-side">Mở Google Maps</span>
            </a>

            {/* Mở link TikTok trực tiếp */}
            <a
              href={tiktokUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="frame-action-btn liquid-glass"
              aria-label="TikTok"
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polygon points="3 11 22 2 13 21 11 13 3 11" />
              </svg>
              <span className="dock-tooltip right-side">Mở TikTok</span>
            </a>

            {/* Divider */}
            <div className="stream-nav-divider" />

            {/* Prev Video */}
            <button
              type="button"
              className="frame-action-btn liquid-glass"
              onClick={() => {
                markSwiped()
                onPrevVideo()
              }}
              aria-label="Video trước"
            >
              <svg
                viewBox="0 0 24 24"
                width="16"
                height="16"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="18 15 12 9 6 15" />
              </svg>
              <span className="dock-tooltip right-side">Video trước (↑)</span>
            </button>

            {/* Next Video */}
            <button
              type="button"
              className="frame-action-btn liquid-glass"
              onClick={() => {
                markSwiped()
                onNextVideo()
              }}
              aria-label="Video tiếp"
            >
              <svg
                viewBox="0 0 24 24"
                width="16"
                height="16"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
              <span className="dock-tooltip right-side">Video tiếp (↓)</span>
            </button>
          </div>,
          document.body,
        )}
    </section>
  )
}
