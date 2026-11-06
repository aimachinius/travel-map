import { useEffect, useRef, useState } from 'react'

export interface FpsStatus {
  fps: number
  frameTime: string
  status: 'smooth' | 'medium' | 'low'
}

export function useFpsMonitor(): FpsStatus {
  const [data, setData] = useState<FpsStatus>({
    fps: 60,
    frameTime: '16.6ms',
    status: 'smooth',
  })

  const lastTimeRef = useRef<number>(0)
  const framesRef = useRef<number>(0)
  const fpsArrRef = useRef<number[]>([])

  useEffect(() => {
    let animId: number
    lastTimeRef.current = performance.now()

    const tick = (now: number) => {
      const delta = now - lastTimeRef.current
      lastTimeRef.current = now

      const instantFps = Math.min(240, Math.round(1000 / (delta || 16.6)))
      fpsArrRef.current.push(instantFps)
      if (fpsArrRef.current.length > 20) {
        fpsArrRef.current.shift()
      }

      framesRef.current++
      if (framesRef.current % 12 === 0) {
        const avg = Math.round(
          fpsArrRef.current.reduce((a, b) => a + b, 0) / (fpsArrRef.current.length || 1),
        )
        let status: 'smooth' | 'medium' | 'low' = 'smooth'
        if (avg < 30) status = 'low'
        else if (avg < 50) status = 'medium'

        setData({
          fps: avg,
          frameTime: `${delta.toFixed(1)}ms`,
          status,
        })
      }

      animId = requestAnimationFrame(tick)
    }

    animId = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(animId)
    }
  }, [])

  return data
}
