import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createPortal } from 'react-dom'
import './CloudTransitionOverlay.css'

interface CloudTransitionOverlayProps {
  isActive: boolean
  onCovered?: () => void
  onRevealed?: () => void
  destinationName?: string
}

// 0,1 = soft thin clouds · 2,3 = big white clouds (thứ tự y nguyên như Mây phủ màn hình (1).html)
const CLOUD_SRCS = [
  '/cloud_image/cloud1.png?v=rgba2',
  '/cloud_image/cloud2.png?v=rgba2',
  '/cloud_image/cloud3.png?v=rgba2',
  '/cloud_image/cloud4.png?v=rgba2',
]

interface CloudItem {
  id: number
  l: number
  t: number
  w: number
  h: number
  srcIndex: number
  flip: boolean
  rot: number
  offX: number
  delaySec: string
}

// Preload hình ảnh mây để sẵn sàng tạo mây lập tức không có độ trễ
const preloadImgs: HTMLImageElement[] =
  typeof window !== 'undefined'
    ? CLOUD_SRCS.map((src) => {
        const img = new Image()
        img.src = src
        return img
      })
    : []

export default function CloudTransitionOverlay({
  isActive,
  onCovered,
  onRevealed,
  destinationName = 'Điểm hẹn ẩm thực',
}: CloudTransitionOverlayProps) {
  const navigate = useNavigate()
  const [clouds, setClouds] = useState<CloudItem[]>([])
  const [isCovered, setIsCovered] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  const onCoveredRef = useRef(onCovered)
  const onRevealedRef = useRef(onRevealed)

  useEffect(() => {
    onCoveredRef.current = onCovered
    onRevealedRef.current = onRevealed
  }, [onCovered, onRevealed])

  useEffect(() => {
    if (!isActive) return

    let cancelled = false
    const token = Date.now()

    // Đảm bảo ảnh đã tải xong rồi tính toán bố cục mây
    const decodePromises = preloadImgs.map((img) =>
      img.decode ? img.decode().catch(() => {}) : Promise.resolve(),
    )

    Promise.all(decodePromises).then(() => {
      if (cancelled) return

      const W = window.innerWidth
      const H = window.innerHeight
      // Kích thước chuẩn tương đối của mây theo độ phân giải màn hình
      const S = W < 700 ? W * 0.55 : W / (W < 1500 ? 3.8 : 5.2)
      const rnd = (a: number, b: number) => a + Math.random() * (b - a)

      const asp = (j: number) => {
        const img = preloadImgs[j]
        if (img && img.naturalWidth > 0) {
          return img.naturalHeight / img.naturalWidth
        }
        const fallbackRatios = [0.426, 0.507, 0.532, 0.514]
        return fallbackRatios[j] || 0.5
      }

      const rect = (cx: number, cy: number, w: number, i: number, soft: number) => {
        const h = w * asp(i)
        return {
          l: cx - w / 2,
          t: cy - h / 2,
          w,
          h,
          i,
          f: Math.random() < 0.5,
          a: Number(rnd(-soft, soft).toFixed(1)),
        }
      }

      // Canvas kích thước thu nhỏ (K = 8) để phát hiện và lấp đầy khoảng hở
      const K = 8
      const cv = document.createElement('canvas')
      cv.width = Math.ceil(W / K)
      cv.height = Math.ceil(H / K)
      const ctx = cv.getContext('2d')

      const paint = (r: { l: number; t: number; w: number; h: number; i: number; f: boolean; a: number }) => {
        if (!ctx) return
        ctx.save()
        ctx.translate((r.l + r.w / 2) / K, (r.t + r.h / 2) / K)
        ctx.rotate((r.a * Math.PI) / 180)
        if (r.f) ctx.scale(-1, 1)
        const img = preloadImgs[r.i]
        if (img) {
          ctx.drawImage(img, -r.w / 2 / K, -r.h / 2 / K, r.w / K, r.h / K)
        }
        ctx.restore()
      }

      // 1) Tạo các đám mây trắng lớn (cloud3, cloud4), rải ngẫu nhiên che diện rộng
      const bigs: ReturnType<typeof rect>[] = []
      // Tăng mật độ mây lớn che phủ rộng
      const target = Math.max(6, Math.round(((W * H) / (S * S * 0.72)) * 0.85) + 2)

      for (let t = 0; t < 600 && bigs.length < target; t++) {
        const cx = rnd(0.04, 0.96) * W
        const cy = rnd(0.04, 0.96) * H
        let type = Math.random() < 0.5 ? 2 : 3
        let near: (typeof bigs)[0] | null = null
        let nd = 1e9

        bigs.forEach((b) => {
          const d = Math.hypot(b.l + b.w / 2 - cx, b.t + b.h / 2 - cy)
          if (d < nd) {
            nd = d
            near = b
          }
        })

        if (near && nd < S * 1.9 && (near as (typeof bigs)[0]).i === type && Math.random() < 0.9) {
          type = type === 2 ? 3 : 2
        }

        const r = rect(cx, cy, S * rnd(1.05, 1.6), type, 4)
        const ok = bigs.every((b) => {
          const ax = r.w * 0.08,
            ay = r.h * 0.08,
            bx = b.w * 0.08,
            by = b.h * 0.08
          const ox = Math.min(r.l + r.w - ax, b.l + b.w - bx) - Math.max(r.l + ax, b.l + bx)
          const oy = Math.min(r.t + r.h - ay, b.t + b.h - by) - Math.max(r.t + ay, b.t + by)
          if (ox <= 0 || oy <= 0) return true
          return ox * oy < 0.22 * Math.min(r.w * r.h, b.w * b.h)
        })
        if (ok) bigs.push(r)
      }

      // Bổ sung thêm tối thiểu 1 mây loại 3 và 1 mây loại 4 theo đúng yêu cầu
      const extraBigTypes = [2, 3]
      extraBigTypes.forEach((t) => {
        const cx = rnd(0.12, 0.88) * W
        const cy = rnd(0.12, 0.88) * H
        const r = rect(cx, cy, S * rnd(1.15, 1.65), t, 4)
        bigs.push(r)
      })

      bigs.forEach(paint)

      // 2) Đặt mây xốp mỏng (cloud1, cloud2) lên bề mặt các đám mây lớn
      // Tăng số lượng mây mỏng theo yêu cầu để che kỹ bề mặt
      const overlays: ReturnType<typeof rect>[] = []
      bigs.forEach((b) => {
        const numOverlays = Math.random() < 0.8 ? 2 : 1
        for (let s = 0; s < numOverlays; s++) {
          const j = Math.random() < 0.5 ? 0 : 1
          const ow = b.w * rnd(1.05, 1.45)
          const mode = ['left', 'right', 'bottom', 'top', 'center'][Math.floor(Math.random() * 5)]
          const cxo =
            mode === 'left'
              ? b.l + b.w * rnd(0, 0.15)
              : mode === 'right'
                ? b.l + b.w * rnd(0.85, 1)
                : mode === 'center'
                  ? b.l + b.w * rnd(0.35, 0.65)
                  : b.l + b.w * rnd(0.2, 0.8)
          const cyo =
            mode === 'bottom'
              ? b.t + b.h * rnd(0.75, 0.95)
              : mode === 'top'
                ? b.t + b.h * rnd(0.05, 0.25)
                : mode === 'center'
                  ? b.t + b.h * rnd(0.35, 0.65)
                  : b.t + b.h * rnd(0.3, 0.7)
          const o = rect(cxo, cyo, ow, j, 5)
          overlays.push(o)
          paint(o)
        }
      })

      // 3) Quét và lấp đầy mọi khoảng hở bằng mây xốp mỏng ngẫu nhiên (cloud1, cloud2)
      const softs: ReturnType<typeof rect>[] = []
      if (ctx) {
        try {
          for (let it = 0; it < 260; it++) {
            const d = ctx.getImageData(0, 0, cv.width, cv.height).data
            const gaps: number[] = []
            // Ngưỡng alpha 210 để phát hiện cả những vùng bán trong suốt chưa đủ độ mờ che phủ
            for (let p = 3, k = 0; p < d.length; p += 4, k++) {
              if (d[p] < 210) gaps.push(k)
            }
            if (gaps.length < cv.width * cv.height * 0.003) break
            const g = gaps[Math.floor(Math.random() * gaps.length)]
            const s = rect(
              (g % cv.width) * K,
              Math.floor(g / cv.width) * K,
              S * rnd(1.1, 1.8),
              Math.random() < 0.5 ? 0 : 1,
              5,
            )
            softs.push(s)
            paint(s)
          }
        } catch {
          // Fallback nếu canvas bị hạn chế
        }
      }

      // Tối ưu tốc độ mây theo yêu cầu: chạy nhanh hơn (dur = 1.35s, MAXDELAY = 0.22s)
      const MAXDELAY = 0.22
      const allRects = [...softs, ...bigs, ...overlays]
      const items: CloudItem[] = allRects.map((r, idx) => {
        const onLeft = r.l + r.w / 2 < W / 2
        const off = onLeft ? -(r.l + r.w + 40) : W - r.l + 40
        return {
          id: token + idx,
          l: Math.round(r.l),
          t: Math.round(r.t),
          w: Math.round(r.w),
          h: Math.round(r.h),
          srcIndex: r.i,
          flip: r.f,
          rot: r.a,
          offX: Math.round(off),
          delaySec: (Math.random() * MAXDELAY).toFixed(2),
        }
      })

      setClouds(items)
      setIsMounted(true)
    })

    return () => {
      cancelled = true
    }
  }, [isActive])

  // Điều phối hiệu ứng: Kéo vào che kín -> Nhảy trang -> Mở ra 2 bên -> Kết thúc
  useEffect(() => {
    if (!isMounted || clouds.length === 0) return

    // 1. Kích hoạt hiệu ứng mây kéo vào từ 2 bên (sau 25ms để trình duyệt nạp xong style ban đầu)
    const coverTimer = setTimeout(() => {
      setIsCovered(true)
    }, 25)

    // 2. Khi mây đã phủ kín hoàn toàn màn hình (khoảng 1150ms): thực hiện chuyển trang
    const triggerCoveredTimer = setTimeout(() => {
      if (onCoveredRef.current) {
        onCoveredRef.current()
      }
    }, 1150)

    // 3. Mây giữ nguyên trạng thái che phủ bồng bềnh trong 400ms rồi bắt đầu tách ra 2 bên
    const uncoverTimer = setTimeout(() => {
      setIsCovered(false)
    }, 1550)

    // 3.5. Khi mây đang tan ra tầm 50% màn hình (~2200ms): phát sự kiện để các địa điểm nhảy lên
    const halfUncoverTimer = setTimeout(() => {
      window.dispatchEvent(new CustomEvent('cloud-uncover-halfway'))
    }, 2200)

    // 4. Mây đã lướt ra ngoài hẳn mép màn hình: giải phóng tài nguyên và kích hoạt onRevealed
    const finishTimer = setTimeout(() => {
      setIsMounted(false)
      setClouds([])
      if (onRevealedRef.current) {
        onRevealedRef.current()
      }
    }, 2950)

    return () => {
      clearTimeout(coverTimer)
      clearTimeout(triggerCoveredTimer)
      clearTimeout(uncoverTimer)
      clearTimeout(halfUncoverTimer)
      clearTimeout(finishTimer)
    }
  }, [isMounted, clouds.length])

  if (!isMounted || clouds.length === 0) return null

  // Sử dụng createPortal gắn trực tiếp lên document.body
  // Đảm bảo không bị ảnh hưởng bởi transform của dual-track-slider
  return createPortal(
    <div
      id="sky"
      className={`cloud-sky-overlay ${isCovered ? 'covered' : ''}`}
      aria-hidden="true"
      role="presentation"
    >
      {/* 0. Lớp sương mù khí quyển mượt mà kết hợp cùng các khối mây để che kín nền phía sau */}
      <div className="cloud-backdrop-layer" />

      {/* 1. Logo Food Spot ở góc trái trên cùng, luôn nổi lên trên tầng mây */}
      <div className="cloud-persistent-brand">
        <div className="cloud-persistent-brand-inner">
          <a
            href="/"
            onClick={(e) => {
              e.preventDefault()
              navigate('/')
            }}
            className="cloud-brand-link"
            aria-label="Food Spot — Về Trang chủ"
          >
            <img className="cloud-logo-img" src="/food-spot.svg" alt="Food Spot" />
          </a>
        </div>
      </div>

      {/* 2. Các khối mây thực thể di chuyển từ hai bên vào giữa */}
      {clouds.map((c) => (
        <div
          key={c.id}
          className={`cloud-node ${c.flip ? 'flip' : ''}`}
          style={
            {
              left: `${c.l}px`,
              top: `${c.t}px`,
              width: `${c.w}px`,
              height: `${c.h}px`,
              '--ox': `${c.offX}px`,
              '--rot': `${c.rot}deg`,
              transitionDelay: `${c.delaySec}s`,
            } as React.CSSProperties
          }
        >
          <img src={CLOUD_SRCS[c.srcIndex]} alt="" draggable={false} />
        </div>
      ))}

      {/* 3. Thẻ chuyến bay xuyên tầng mây hiện ra ở trung tâm khi mây bao phủ */}
      <div className="cloud-flight-badge">
        <div className="cloud-flight-icon">✈️</div>
        <div className="cloud-flight-text">
          <span>Đang bay xuyên tầng mây đến</span>
          <strong>{destinationName}</strong>
        </div>
      </div>
    </div>,
    document.body,
  )
}
