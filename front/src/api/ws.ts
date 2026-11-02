import { API_BASE_URL } from './client'
import type { AnalysisUpdatedEvent } from '../types/ws'

export type WebSocketListener = (event: AnalysisUpdatedEvent) => void

class WebSocketManager {
  private socket: WebSocket | null = null
  private listeners: Set<WebSocketListener> = new Set()
  private reconnectTimeout: number | null = null
  private reconnectInterval = 2000
  private pingInterval: number | null = null

  connect(token?: string) {
    const activeToken = token || localStorage.getItem('foodspot_access_token')
    if (!activeToken) {
      this.disconnect()
      return
    }

    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING)
    ) {
      return
    }

    const wsProtocol = API_BASE_URL.startsWith('https') ? 'wss' : 'ws'
    const host = API_BASE_URL.replace(/^https?:\/\//, '')
    const wsUrl = `${wsProtocol}://${host}/api/v1/ws?token=${encodeURIComponent(
      activeToken,
    )}`

    try {
      this.socket = new WebSocket(wsUrl)

      this.socket.onopen = () => {
        console.log('[WebSocket] Connected to Food Spot realtime service')
        this.reconnectInterval = 2000

        // Ping keep-alive every 25s
        if (this.pingInterval) clearInterval(this.pingInterval)
        this.pingInterval = window.setInterval(() => {
          if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send('ping')
          }
        }, 25000)
      }

      this.socket.onmessage = (event) => {
        if (event.data === 'pong') return
        try {
          const parsed = JSON.parse(event.data) as AnalysisUpdatedEvent
          if (parsed && parsed.event === 'ANALYSIS_UPDATED') {
            this.notifyListeners(parsed)
          }
        } catch (err) {
          console.warn('[WebSocket] Error parsing message:', err)
        }
      }

      this.socket.onclose = () => {
        console.log('[WebSocket] Connection closed. Retrying...')
        this.cleanup()
        this.scheduleReconnect()
      }

      this.socket.onerror = (err) => {
        console.warn('[WebSocket] Socket encountered error:', err)
        this.socket?.close()
      }
    } catch (e) {
      console.warn('[WebSocket] Connect error:', e)
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout)
    this.reconnectTimeout = window.setTimeout(() => {
      this.reconnectInterval = Math.min(this.reconnectInterval * 1.5, 30000)
      this.connect()
    }, this.reconnectInterval)
  }

  private cleanup() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  disconnect() {
    this.cleanup()
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
    if (this.socket) {
      this.socket.onclose = null
      this.socket.close()
      this.socket = null
    }
  }

  subscribe(listener: WebSocketListener): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  private notifyListeners(event: AnalysisUpdatedEvent) {
    this.listeners.forEach((listener) => {
      try {
        listener(event)
      } catch (e) {
        console.error('[WebSocket] Error in listener:', e)
      }
    })
  }
}

export const wsManager = new WebSocketManager()
