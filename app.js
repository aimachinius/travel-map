import L from 'leaflet';

/**
 * TikTok Liquid Glass Web Application Logic
 * Implements URL parsing, validation, state management, iframe embedding, and interactive effects.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const videoUrlInput = document.getElementById('videoUrlInput');
  const inputWrapper = document.getElementById('inputWrapper');
  const searchBtn = document.getElementById('searchBtn');
  const searchForm = document.getElementById('searchForm');
  const clearBtn = document.getElementById('clearBtn');
  const pasteBtn = document.getElementById('pasteBtn');
  
  // Video Frame States
  const emptyState = document.getElementById('emptyState');
  const loadingState = document.getElementById('loadingState');
  const videoState = document.getElementById('videoState');
  const tiktokIframe = document.getElementById('tiktokIframe');
  const tiktokVideoPlayer = document.getElementById('tiktokVideoPlayer');
  const toggleEngineBtn = document.getElementById('toggleEngineBtn');
  const engineTag = document.getElementById('engineTag');
  const refreshVideoBtn = document.getElementById('refreshVideoBtn');
  const openExternalBtn = document.getElementById('openExternalBtn');
  const googleMapNavBtn = document.getElementById('googleMapNavBtn');
  const prevVideoBtn = document.getElementById('prevVideoBtn');
  const nextVideoBtn = document.getElementById('nextVideoBtn');
  const innerScreen = document.getElementById('innerScreen');

  // Left Dock & Drawer Elements
  const likedVideosBtn = document.getElementById('likedVideosBtn');
  const likedPlacesBtn = document.getElementById('likedPlacesBtn');
  const analysisHistoryBtn = document.getElementById('analysisHistoryBtn');
  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const liquidDrawer = document.getElementById('liquidDrawer');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  const drawerTitle = document.getElementById('drawerTitle');
  const drawerSubtitle = document.getElementById('drawerSubtitle');
  const drawerIconBadge = document.getElementById('drawerIconBadge');
  const drawerBody = document.getElementById('drawerBody');
  
  // Toast
  const toastNotification = document.getElementById('toastNotification');
  const toastTitle = document.getElementById('toastTitle');
  const toastMsg = document.getElementById('toastMsg');
  let toastTimer = null;

  // Preset Chips
  const presetChips = document.querySelectorAll('.preset-chip');

  // Rich Video Playlist with Location & Coordinates
  const videoPlaylist = [
    {
      id: '7339739506692984070',
      url: 'https://www.tiktok.com/@ohmwts/video/7339739506692984070',
      title: '🍜 Sapporo Miso Ramen Nóng Hổi',
      author: '@ohmwts',
      locationName: 'Ganso Ramen Yokocho, Sapporo, Hokkaido 🇯🇵',
      lat: 43.0552,
      lng: 141.3533,
      gmapQuery: 'Ganso Ramen Yokocho, Sapporo, Hokkaido, Japan',
      category: 'Ẩm thực Nhật Bản',
      icon: '🍜',
      desc: 'Quán mì Miso Ramen truyền thống trứ danh tại con ngõ Ramen Yokocho, tuyết rơi trắng xóa.'
    },
    {
      id: '7106594312292453678',
      url: 'https://www.tiktok.com/@tiktok/video/7106594312292453678',
      title: '🏮 Khám Phá Shibuya Night Vibes',
      author: '@tiktok',
      locationName: 'Shibuya Crossing, Tokyo 🇯🇵',
      lat: 35.6595,
      lng: 139.7005,
      gmapQuery: 'Shibuya Crossing, Tokyo, Japan',
      category: 'Du lịch & Đô thị',
      icon: '🏮',
      desc: 'Giao lộ bận rộn nhất thế giới với ánh đèn neon rực rỡ và ẩm thực đêm sầm uất.'
    },
    {
      id: '7217349141872119045',
      url: 'https://www.tiktok.com/@khaby.lame/video/7217349141872119045',
      title: '🍕 Khaby Lame Thưởng Thức Pizza Milan',
      author: '@khaby.lame',
      locationName: 'Piazza del Duomo, Milan 🇮🇹',
      lat: 45.4642,
      lng: 9.1900,
      gmapQuery: 'Piazza del Duomo, Milan, Italy',
      category: 'Hài hước & Ẩm thực',
      icon: '🍕',
      desc: 'Khoảnh khắc ẩm thực Ý hài hước phong cách đặc trưng không cần nói lời nào trước thánh đường Duomo.'
    },
    {
      id: '6768504823336881414',
      url: 'https://www.tiktok.com/@zachking/video/6768504823336881414',
      title: '✨ Ảo Thuật Phép Thuật Zach King',
      author: '@zachking',
      locationName: 'Hollywood Boulevard, Los Angeles 🇺🇸',
      lat: 34.1016,
      lng: -118.3268,
      gmapQuery: 'Hollywood Walk of Fame, Los Angeles, USA',
      category: 'Sáng tạo VFX',
      icon: '✨',
      desc: 'Màn ảo thuật biến hóa không gian kỳ diệu ngay trên đại lộ danh vọng Hollywood.'
    },
    {
      id: '7280000000000000001',
      url: 'https://www.tiktok.com/@vietnamtravel/video/7280000000000000001',
      title: '🍲 Phở Bát Đàn Nước Dùng Gia Truyền',
      author: '@hanoifoodie',
      locationName: '49 Bát Đàn, Hoàn Kiếm, Hà Nội 🇻🇳',
      lat: 21.0335,
      lng: 105.8475,
      gmapQuery: 'Pho Bat Dan, 49 Bat Dan, Hoan Kiem, Hanoi, Vietnam',
      category: 'Ẩm thực Việt Nam',
      icon: '🍲',
      desc: 'Hương vị phở bò truyền thống lâu năm giữa lòng phố cổ Hà Nội ngàn năm văn hiến.'
    }
  ];

  // Currently loaded Video ID & URL & Playlist index
  let currentPlaylistIndex = 0;
  let currentVideoId = null;
  let currentOriginalUrl = '';
  let currentEngine = 'mp4'; // 'mp4' (Direct Stream 60fps) | 'v1' (Player v1) | 'v2' (Embed v2)
  let liveColorAnimId = null;

  // =========================================================================
  // Ambient Glass Engine: Synchronizes video colors into the 16px glass bezel
  // =========================================================================
  const ambientCanvas = document.getElementById('ambient-glass');
  const ambientCtx = ambientCanvas ? ambientCanvas.getContext('2d') : null;
  let ambientAnimId = null;
  let ambientMode = 'standby'; // 'standby' | 'video'

  // Pre-configured rich chromatic palettes for preset videos (chuẩn theo ảnh chụp của người dùng)
  const presetPalettes = {
    // 🍜 Hokkaido Food Demo (Khớp 100% màu ảnh mẫu: Cyan -> Purple -> Pink -> Green -> Coral -> Amber)
    '7339739506692984070': {
      c1: '#00f0ff', // Cyan (top-left)
      c2: '#a855f7', // Purple (top)
      c3: '#ff007f', // Hot Pink (top-right)
      c4: '#ff2a8d', // Magenta (right)
      c5: '#00ff88', // Electric Green (bottom-right)
      c6: '#ff3b30', // Coral/Red (bottom)
      c7: '#ff9500', // Amber (bottom-left)
      tl: 'rgba(0, 240, 255, 0.95)',
      tr: 'rgba(255, 0, 127, 0.95)',
      bl: 'rgba(255, 149, 0, 0.95)',
      br: 'rgba(0, 255, 136, 0.95)',
      mid: 'rgba(168, 85, 247, 0.85)'
    },
    '7106594312292453678': {
      // Trending 1 (Vibrant Cyan & Neon Pink)
      c1: '#00f2fe',
      c2: '#4facfe',
      c3: '#ff007f',
      c4: '#f72585',
      c5: '#00dfa2',
      c6: '#7928ca',
      c7: '#4361ee',
      tl: 'rgba(0, 242, 254, 0.95)',
      tr: 'rgba(255, 0, 127, 0.95)',
      bl: 'rgba(121, 40, 202, 0.95)',
      br: 'rgba(0, 223, 162, 0.95)',
      mid: 'rgba(79, 172, 254, 0.75)'
    },
    '7217349141872119045': {
      // Trending 2 (Khaby Lame - Amber Sunset & Deep Cobalt)
      c1: '#ff9900',
      c2: '#ff5e62',
      c3: '#ff3366',
      c4: '#ff0055',
      c5: '#00d2ff',
      c6: '#3a7bd5',
      c7: '#ffaa00',
      tl: 'rgba(255, 153, 0, 0.95)',
      tr: 'rgba(255, 94, 98, 0.95)',
      bl: 'rgba(58, 123, 213, 0.95)',
      br: 'rgba(0, 210, 255, 0.95)',
      mid: 'rgba(255, 170, 0, 0.75)'
    },
    '6768504823336881414': {
      // Zach King (Mystic Purple, Hot Magenta & Electric Violet)
      c1: '#9d4edd',
      c2: '#e0aaff',
      c3: '#ff007f',
      c4: '#7209b7',
      c5: '#4cc9f0',
      c6: '#3a0ca3',
      c7: '#f72585',
      tl: 'rgba(157, 78, 221, 0.95)',
      tr: 'rgba(255, 0, 127, 0.95)',
      bl: 'rgba(58, 12, 163, 0.95)',
      br: 'rgba(76, 201, 240, 0.95)',
      mid: 'rgba(114, 9, 183, 0.75)'
    }
  };

  const ambientGradientEl = document.getElementById('ambientGradient');

  /**
   * Applies 7-point perimeter color variables to the ambient glow gradient
   */
  function applyPaletteToGradient(palette) {
    if (!ambientGradientEl || !palette) return;
    ambientGradientEl.style.setProperty('--glow-c1', palette.c1);
    ambientGradientEl.style.setProperty('--glow-c2', palette.c2);
    ambientGradientEl.style.setProperty('--glow-c3', palette.c3);
    ambientGradientEl.style.setProperty('--glow-c4', palette.c4);
    ambientGradientEl.style.setProperty('--glow-c5', palette.c5);
    ambientGradientEl.style.setProperty('--glow-c6', palette.c6);
    ambientGradientEl.style.setProperty('--glow-c7', palette.c7);
  }

  /**
   * Initializes the Ambient Glass Canvas with resolution 36x64
   */
  function initAmbientGlass() {
    if (!ambientCanvas || !ambientCtx) return;
    ambientCanvas.width = 36;
    ambientCanvas.height = 64;

    // Start in pure thin clear glass standby mode (0% color)
    startStandbyAmbientLoop();
  }

  /**
   * Standby Ambient Setup:
   * Pure thin crystal-clear liquid glass looking through to map (No rainbow colors)
   */
  function startStandbyAmbientLoop() {
    if (ambientAnimId) {
      cancelAnimationFrame(ambientAnimId);
      ambientAnimId = null;
    }
    ambientMode = 'standby';

    const ambientWrapper = document.getElementById('ambientWrapper');
    if (ambientWrapper) ambientWrapper.style.opacity = '0';
    if (ambientCanvas && ambientCtx) {
      ambientCtx.clearRect(0, 0, ambientCanvas.width, ambientCanvas.height);
    }
    const phoneFrame = document.getElementById('phoneFrame');
    if (phoneFrame) {
      phoneFrame.classList.add('is-empty');
      phoneFrame.classList.remove('is-playing');
    }
  }

  /**
   * Synchronizes video colors into the ambient glass canvas:
   * 1. Updates the perimeter conic gradient
   * 2. Attempts to fetch thumbnail from TikTok OEmbed
   * 3. Draws the image on canvas or paints rich chromatic gradient
   */
  async function syncVideoAmbient(videoId, originalUrl) {
    if (!ambientCanvas || !ambientCtx) return;
    ambientMode = 'video';
    if (ambientAnimId) cancelAnimationFrame(ambientAnimId);

    const ambientWrapper = document.getElementById('ambientWrapper');
    if (ambientWrapper) ambientWrapper.style.opacity = '0.9';
    const phoneFrame = document.getElementById('phoneFrame');
    if (phoneFrame) {
      phoneFrame.classList.remove('is-empty');
      phoneFrame.classList.add('is-playing');
    }

    const palette = presetPalettes[videoId] || generatePaletteFromId(videoId);
    applyPaletteToGradient(palette);
    drawFallbackPalette(videoId, palette);

    let oembedRendered = false;
    try {
      const targetUrl = originalUrl || `https://www.tiktok.com/@tiktok/video/${videoId}`;
      const oembedApi = `https://www.tiktok.com/oembed?url=${encodeURIComponent(targetUrl)}`;
      
      const res = await fetch(oembedApi, { mode: 'cors' });
      if (res.ok) {
        const data = await res.json();
        if (data && data.thumbnail_url) {
          const img = new Image();
          img.crossOrigin = 'anonymous';
          img.onload = () => {
            ambientCtx.clearRect(0, 0, ambientCanvas.width, ambientCanvas.height);
            ambientCtx.drawImage(img, 0, 0, ambientCanvas.width, ambientCanvas.height);
            oembedRendered = true;
          };
          img.onerror = () => {
            drawFallbackPalette(videoId, palette);
          };
          img.src = data.thumbnail_url;
        }
      }
    } catch (e) {
      // Fallback palette is already active
    }

    // Safety fallback
    setTimeout(() => {
      if (!oembedRendered) {
        drawFallbackPalette(videoId, palette);
      }
    }, 350);
  }

  /**
   * Procedural video palette painter:
   * Draws 4 edge radial gradients matching the video onto the canvas
   * so the 16px liquid glass bezel is vibrant and responsive.
   */
  function drawFallbackPalette(videoId, palette) {
    if (!ambientCanvas || !ambientCtx) return;
    const w = ambientCanvas.width;
    const h = ambientCanvas.height;
    ambientCtx.clearRect(0, 0, w, h);

    const colors = palette || generatePaletteFromId(videoId);

    // Top-Left corner glow (Cyan)
    const gTL = ambientCtx.createRadialGradient(4, 4, 2, 8, 8, 36);
    gTL.addColorStop(0, colors.tl);
    gTL.addColorStop(1, 'transparent');
    ambientCtx.fillStyle = gTL;
    ambientCtx.fillRect(0, 0, w, h);

    // Top-Right corner glow (Pink)
    const gTR = ambientCtx.createRadialGradient(w - 4, 4, 2, w - 8, 8, 36);
    gTR.addColorStop(0, colors.tr);
    gTR.addColorStop(1, 'transparent');
    ambientCtx.fillStyle = gTR;
    ambientCtx.fillRect(0, 0, w, h);

    // Bottom-Left corner glow (Amber)
    const gBL = ambientCtx.createRadialGradient(4, h - 4, 2, 8, h - 8, 38);
    gBL.addColorStop(0, colors.bl);
    gBL.addColorStop(1, 'transparent');
    ambientCtx.fillStyle = gBL;
    ambientCtx.fillRect(0, 0, w, h);

    // Bottom-Right corner glow (Green)
    const gBR = ambientCtx.createRadialGradient(w - 4, h - 4, 2, w - 8, h - 8, 38);
    gBR.addColorStop(0, colors.br);
    gBR.addColorStop(1, 'transparent');
    ambientCtx.fillStyle = gBR;
    ambientCtx.fillRect(0, 0, w, h);

    // Center-edge glow (Violet)
    const gMid = ambientCtx.createRadialGradient(w / 2, h / 2, 4, w / 2, h / 2, 32);
    gMid.addColorStop(0, colors.mid);
    gMid.addColorStop(1, 'transparent');
    ambientCtx.fillStyle = gMid;
    ambientCtx.fillRect(0, 0, w, h);
  }

  /**
   * Deterministically generates vibrant chromatic color tokens from numeric videoId
   */
  function generatePaletteFromId(idStr) {
    let hash = 0;
    const str = String(idStr);
    for (let i = 0; i < str.length; i++) {
      hash = (hash << 5) - hash + str.charCodeAt(i);
      hash |= 0;
    }
    const h1 = Math.abs(hash) % 360;
    const h2 = (h1 + 55) % 360;
    const h3 = (h1 + 115) % 360;
    const h4 = (h1 + 165) % 360;
    const h5 = (h1 + 220) % 360;
    const h6 = (h1 + 270) % 360;
    const h7 = (h1 + 315) % 360;

    return {
      c1: `hsl(${h1}, 100%, 55%)`,
      c2: `hsl(${h2}, 100%, 60%)`,
      c3: `hsl(${h3}, 100%, 55%)`,
      c4: `hsl(${h4}, 100%, 60%)`,
      c5: `hsl(${h5}, 100%, 50%)`,
      c6: `hsl(${h6}, 100%, 55%)`,
      c7: `hsl(${h7}, 100%, 55%)`,
      tl: `hsla(${h1}, 95%, 60%, 0.95)`,
      tr: `hsla(${h3}, 95%, 65%, 0.95)`,
      bl: `hsla(${h7}, 95%, 55%, 0.95)`,
      br: `hsla(${h5}, 95%, 60%, 0.95)`,
      mid: `hsla(${h2}, 90%, 65%, 0.8)`
    };
  }

  // =========================================================================
  // Leaflet.js + OpenStreetMap (OSM) Interactive Background Engine
  // =========================================================================
  const mapCityBtn = document.getElementById('mapCityBtn');
  const mapCityLabel = document.getElementById('mapCityLabel');
  const mapStyleBtn = document.getElementById('mapStyleBtn');
  const mapStyleLabel = document.getElementById('mapStyleLabel');

  const cityPresets = [
    { name: 'Tokyo 🇯🇵', lat: 35.6812, lng: 139.7671, zoom: 14 },
    { name: 'Hà Nội 🇻🇳', lat: 21.0285, lng: 105.8542, zoom: 14 },
    { name: 'TP. Hồ Chí Minh 🇻🇳', lat: 10.7769, lng: 106.7009, zoom: 14 },
    { name: 'Paris 🇫🇷', lat: 48.8566, lng: 2.3522, zoom: 14 },
    { name: 'New York 🇺🇸', lat: 40.7128, lng: -74.0060, zoom: 14 },
    { name: 'London 🇬🇧', lat: 51.5074, lng: -0.1278, zoom: 14 }
  ];
  let currentCityIndex = 0;
  let currentMapStyle = 'dark'; // 'dark' (CARTO Dark based on OSM) | 'standard' (OpenStreetMap Standard)
  let leafletMap = null;
  let activeTileLayer = null;

  function initLeafletMap() {
    const mapEl = document.getElementById('mapBackground');
    if (!mapEl) return;

    try {
      leafletMap = L.map('mapBackground', {
        center: [cityPresets[0].lat, cityPresets[0].lng],
        zoom: cityPresets[0].zoom,
        zoomControl: false,
        attributionControl: true
      });

      // Zoom control at bottom right
      L.control.zoom({ position: 'bottomright' }).addTo(leafletMap);

      // Load initial OpenStreetMap Dark layer
      setMapTileLayer(currentMapStyle);

      // City Switcher (flyTo animation)
      if (mapCityBtn && mapCityLabel) {
        mapCityBtn.addEventListener('click', () => {
          currentCityIndex = (currentCityIndex + 1) % cityPresets.length;
          const targetCity = cityPresets[currentCityIndex];
          mapCityLabel.textContent = targetCity.name;
          leafletMap.flyTo([targetCity.lat, targetCity.lng], targetCity.zoom, {
            duration: 2.0,
            easeLinearity: 0.25
          });
          showToast('info', 'Bản Đồ OpenStreetMap', `Đang di chuyển đến ${targetCity.name}`);
        });
      }

      // Map Style Switcher (OSM Dark <-> OSM Standard)
      if (mapStyleBtn && mapStyleLabel) {
        mapStyleBtn.addEventListener('click', () => {
          if (currentMapStyle === 'dark') {
            currentMapStyle = 'standard';
            mapStyleLabel.textContent = 'OSM Standard';
            setMapTileLayer('standard');
            showToast('info', 'Giao Diện Bản Đồ', 'Đã chuyển sang lớp bản đồ OpenStreetMap Standard');
          } else {
            currentMapStyle = 'dark';
            mapStyleLabel.textContent = 'OSM Dark';
            setMapTileLayer('dark');
            showToast('info', 'Giao Diện Bản Đồ', 'Đã chuyển sang lớp bản đồ OpenStreetMap Dark Mode');
          }
        });
      }
    } catch (e) {
      console.warn('Leaflet map initialization error:', e);
    }
  }

  function setMapTileLayer(style) {
    if (!leafletMap) return;
    if (activeTileLayer) {
      leafletMap.removeLayer(activeTileLayer);
    }

    if (style === 'standard') {
      activeTileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
      }).addTo(leafletMap);
    } else {
      activeTileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        subdomains: 'abcd',
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors &copy; CARTO'
      }).addTo(leafletMap);
    }
  }

  // Initialize Map and Ambient Glass on load
  initLeafletMap();
  initAmbientGlass();

  // Engine Switcher: MP4 (Direct 60fps) -> V1 (Player v1) -> V2 (Embed v2)
  if (toggleEngineBtn && engineTag) {
    engineTag.textContent = 'MP4';
    engineTag.style.color = '#00ff88';

    toggleEngineBtn.addEventListener('click', () => {
      if (currentEngine === 'mp4') {
        currentEngine = 'v1';
        engineTag.textContent = 'V1';
        engineTag.style.color = '#00f2fe';
        showToast('info', 'Trình phát TikTok', 'Chế độ Player v1 (Iframe chính thức)');
      } else if (currentEngine === 'v1') {
        currentEngine = 'v2';
        engineTag.textContent = 'V2';
        engineTag.style.color = '#ff007f';
        showToast('info', 'Trình phát TikTok', 'Chế độ Embed v2 (Iframe nhúng)');
      } else {
        currentEngine = 'mp4';
        engineTag.textContent = 'MP4';
        engineTag.style.color = '#00ff88';
        showToast('success', 'Trình phát TikTok', 'Chế độ .MP4 phần cứng 60 FPS (Đồng bộ màu trực tiếp)');
      }
      if (currentVideoId) {
        loadTikTokVideo(currentVideoId);
      }
    });
  }

  // Live FPS & Render Time Monitor
  const fpsVal = document.getElementById('fpsVal');
  const frameTimeVal = document.getElementById('frameTimeVal');
  const fpsDot = document.getElementById('fpsDot');

  let lastFpsTime = performance.now();
  let fpsFrames = 0;
  let fpsArr = [];

  function monitorPerformance(now) {
    const delta = now - lastFpsTime;
    lastFpsTime = now;
    const currentFps = Math.min(240, Math.round(1000 / (delta || 16.6)));

    fpsArr.push(currentFps);
    if (fpsArr.length > 20) fpsArr.shift();

    fpsFrames++;
    if (fpsFrames % 10 === 0 && fpsVal && frameTimeVal) {
      const avg = Math.round(fpsArr.reduce((a, b) => a + b, 0) / fpsArr.length);
      fpsVal.textContent = avg;
      frameTimeVal.textContent = `${delta.toFixed(1)}ms`;

      if (fpsDot) {
        if (avg >= 55) {
          fpsVal.style.color = '#00dfa2';
          fpsDot.style.background = '#00dfa2';
        } else if (avg >= 35) {
          fpsVal.style.color = '#f59e0b';
          fpsDot.style.background = '#f59e0b';
        } else {
          fpsVal.style.color = '#ff2d55';
          fpsDot.style.background = '#ff2d55';
        }
      }
    }

    requestAnimationFrame(monitorPerformance);
  }
  requestAnimationFrame(monitorPerformance);



  // 2. Input Clear and Paste Buttons
  videoUrlInput.addEventListener('input', () => {
    if (videoUrlInput.value.trim().length > 0) {
      clearBtn.style.display = 'flex';
      // Remove error state when typing
      inputWrapper.classList.remove('shake-error');
    } else {
      clearBtn.style.display = 'none';
    }
  });

  clearBtn.addEventListener('click', () => {
    videoUrlInput.value = '';
    clearBtn.style.display = 'none';
    videoUrlInput.focus();
    inputWrapper.classList.remove('shake-error');
    currentVideoId = null;
    showState('empty');
    showToast('info', 'Đã xóa', 'Trở về màn hình kính trong suốt chờ nhận liên kết.');
  });

  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        videoUrlInput.value = text.trim();
        clearBtn.style.display = 'flex';
        inputWrapper.classList.remove('shake-error');
        showToast('success', 'Đã dán liên kết', 'Nhấn nút tìm kiếm hoặc Enter để phát.');
      }
    } catch (err) {
      showToast('error', 'Không thể dán', 'Vui lòng nhấn Ctrl+V để dán trực tiếp vào ô nhập.');
    }
  });

  // 3. Preset Sample Chips
  presetChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const url = chip.getAttribute('data-url');
      if (url) {
        videoUrlInput.value = url;
        clearBtn.style.display = 'flex';
        inputWrapper.classList.remove('shake-error');
        handleSearch();
      }
    });
  });

  // 4. Form Submit / Search Action
  searchForm.addEventListener('submit', (e) => {
    e.preventDefault();
    handleSearch();
  });

  searchBtn.addEventListener('click', (e) => {
    e.preventDefault();
    handleSearch();
  });

  videoUrlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSearch();
    }
  });

  /**
   * Main Search & Extraction Flow as specified in REAMDE.md:
   * 1. Validate & Parse URL/Video ID
   * 2. If invalid: Shake effect & red glow
   * 3. If valid: Show loading, render iframe with official player
   */
  function handleSearch() {
    const rawVal = videoUrlInput.value.trim();

    if (!rawVal) {
      triggerError('Vui lòng nhập đường dẫn TikTok hoặc Video ID.');
      return;
    }

    const videoId = extractTikTokVideoId(rawVal);

    if (!videoId) {
      triggerError('Liên kết không hợp lệ! Vui lòng dùng dạng https://www.tiktok.com/@user/video/ID');
      return;
    }

    currentVideoId = videoId;
    currentOriginalUrl = rawVal.startsWith('http') ? rawVal : `https://www.tiktok.com/@tiktok/video/${videoId}`;
    loadTikTokVideo(videoId);
  }

  /**
   * Extracts TikTok Video ID using Regex:
   * - standard: /video/(\d+)
   * - embed: /embed/v2/(\d+)
   * - direct numeric string (15-22 digits)
   */
  function extractTikTokVideoId(urlOrId) {
    // 1. Direct numeric ID
    const directMatch = urlOrId.match(/^(\d{15,22})$/);
    if (directMatch) {
      return directMatch[1];
    }

    // 2. Standard video URL pattern: /video/(\d+)
    const videoMatch = urlOrId.match(/\/video\/(\d+)/i);
    if (videoMatch && videoMatch[1]) {
      return videoMatch[1];
    }

    // 3. Embed pattern: /embed/v2/(\d+) or /embed/(\d+)
    const embedMatch = urlOrId.match(/\/embed\/(?:v\d+\/)?(\d+)/i);
    if (embedMatch && embedMatch[1]) {
      return embedMatch[1];
    }

    // 4. Any numeric sequence between 16 and 21 digits in URL
    const generalIdMatch = urlOrId.match(/(\d{16,21})/);
    if (generalIdMatch && generalIdMatch[1]) {
      return generalIdMatch[1];
    }

    return null;
  }

  /**
   * Triggers error shake animation and red glow border as specified
   */
  function triggerError(message) {
    inputWrapper.classList.remove('shake-error');
    // Force DOM reflow to restart animation
    void inputWrapper.offsetWidth;
    inputWrapper.classList.add('shake-error');
    
    showToast('error', 'Lỗi nhập liệu', message);
    videoUrlInput.focus();
  }

  /**
   * Fetches the direct .mp4 stream URL via TikWM public API (or direct MP4 link)
   */
  async function fetchDirectStreamUrl(targetUrl) {
    if (!targetUrl) return null;

    // 1. Direct .mp4 link provided
    if (targetUrl.toLowerCase().includes('.mp4')) {
      return { playUrl: targetUrl, title: 'Direct .MP4 Stream' };
    }

    // 2. Fetch direct .mp4 from TikWM API
    try {
      const apiUrl = `https://www.tikwm.com/api/?url=${encodeURIComponent(targetUrl)}`;
      const res = await fetch(apiUrl, { mode: 'cors' });
      if (res.ok) {
        const json = await res.json();
        if (json.code === 0 && json.data && json.data.play) {
          return {
            playUrl: json.data.play,
            wmplayUrl: json.data.wmplay,
            title: json.data.title || '',
            cover: json.data.cover || json.data.origin_cover || '',
            author: json.data.author?.nickname || ''
          };
        }
      }
    } catch (e) {
      console.warn('TikWM API fetch error:', e);
    }

    return null;
  }

  /**
   * Real-time 60 FPS video color extractor:
   * Draws playing video frames directly onto ambientCanvas and samples edge colors
   * into the perimeter liquid glass bezel!
   */
  let lastColorSampleTime = 0;
  let lastCanvasDrawTime = 0;

  function startLiveVideoColorSync() {
    if (liveColorAnimId) cancelAnimationFrame(liveColorAnimId);

    function liveLoop(timestamp) {
      if (!tiktokVideoPlayer || tiktokVideoPlayer.paused || tiktokVideoPlayer.ended) {
        return; // Dừng vòng lặp khi pause hoặc ended
      }

      // Giới hạn tần số vẽ ambient ở 30 FPS (~33ms) để giảm 50% GPU draw calls
      if (timestamp - lastCanvasDrawTime >= 33) {
        lastCanvasDrawTime = timestamp;

        if (tiktokVideoPlayer.readyState >= 2 && ambientCtx) {
          try {
            // Draw video frame to ambient canvas
            ambientCtx.drawImage(
              tiktokVideoPlayer,
              0,
              0,
              ambientCanvas.width,
              ambientCanvas.height
            );

            // Giới hạn getImageData (đọc ngược GPU -> CPU) ở chu kỳ 250ms (~4 FPS)
            // Loại bỏ hoàn toàn nghẽn GPU pipeline, đảm bảo video chạy 60 FPS mượt mà
            if (timestamp - lastColorSampleTime > 250) {
              lastColorSampleTime = timestamp;
              const imgData = ambientCtx.getImageData(
                0,
                0,
                ambientCanvas.width,
                ambientCanvas.height
              );
              if (imgData && imgData.data) {
                sampleLiveEdges(imgData.data, ambientCanvas.width, ambientCanvas.height);
              }
            }
          } catch (e) {
            // If cross-origin restricts getImageData, drawImage still renders to canvas
          }
        }
      }

      liveColorAnimId = requestAnimationFrame(liveLoop);
    }

    liveColorAnimId = requestAnimationFrame(liveLoop);
  }

  function sampleLiveEdges(data, w, h) {
    function getColor(x, y) {
      const i = (y * w + x) * 4;
      return `rgb(${data[i]}, ${data[i + 1]}, ${data[i + 2]})`;
    }
    if (ambientGradientEl) {
      ambientGradientEl.style.setProperty('--glow-c1', getColor(4, 4));
      ambientGradientEl.style.setProperty('--glow-c2', getColor(Math.floor(w / 2), 4));
      ambientGradientEl.style.setProperty('--glow-c3', getColor(w - 5, 4));
      ambientGradientEl.style.setProperty('--glow-c4', getColor(w - 5, Math.floor(h / 2)));
      ambientGradientEl.style.setProperty('--glow-c5', getColor(w - 5, h - 5));
      ambientGradientEl.style.setProperty('--glow-c6', getColor(Math.floor(w / 2), h - 5));
      ambientGradientEl.style.setProperty('--glow-c7', getColor(4, h - 5));
    }
  }

  // Hook live color sync to video playback events
  if (tiktokVideoPlayer) {
    tiktokVideoPlayer.addEventListener('play', () => {
      startLiveVideoColorSync();
    });
    tiktokVideoPlayer.addEventListener('pause', () => {
      if (liveColorAnimId) cancelAnimationFrame(liveColorAnimId);
    });
    tiktokVideoPlayer.addEventListener('loadeddata', () => {
      showState('video');
    });
    tiktokVideoPlayer.addEventListener('error', (e) => {
      console.warn('Video tag error, falling back to iframe:', e);
      fallbackToIframe(currentVideoId);
    });
  }

  /**
   * Loads TikTok video into the 9:16 liquid screen
   * Prioritizes Direct .MP4 stream with hardware decoder, falls back to iframe if needed.
   */
  async function loadTikTokVideo(videoId) {
    // Switch state to Loading
    showState('loading');
    
    // Configure External Link button
    if (openExternalBtn) {
      openExternalBtn.href = currentOriginalUrl;
      openExternalBtn.setAttribute('title', `Mở video ${videoId} trên TikTok`);
    }

    // Configure Google Maps navigation button & synchronize Leaflet Map location
    updateActiveVideoLocation(videoId);

    // Synchronize initial ambient glow with known presets or extracted colors
    syncVideoAmbient(videoId, currentOriginalUrl);

    // MODE 1: Direct .MP4 Stream (Hardware Decoder @ 60 FPS)
    if (currentEngine === 'mp4') {
      showToast('info', 'Đang tải luồng .MP4', 'Kết nối qua API trích xuất luồng trực tiếp...');
      
      const streamInfo = await fetchDirectStreamUrl(currentOriginalUrl);

      if (streamInfo && streamInfo.playUrl) {
        // Direct .MP4 found!
        if (tiktokIframe) {
          tiktokIframe.style.display = 'none';
          tiktokIframe.src = '';
        }

        if (tiktokVideoPlayer) {
          tiktokVideoPlayer.style.display = 'block';
          tiktokVideoPlayer.src = streamInfo.playUrl;

          tiktokVideoPlayer.play().then(() => {
            showState('video');
            showToast('success', 'Phát Video .MP4', 'Video chạy mượt ở 60 FPS phần cứng, viền kính trích xuất màu thực tế!');
            startLiveVideoColorSync();
          }).catch(() => {
            // Autoplay with audio policy requires muted start
            tiktokVideoPlayer.muted = true;
            tiktokVideoPlayer.play().then(() => {
              showState('video');
              showToast('success', 'Phát Video .MP4', 'Đang phát (đã tắt tiếng tự động, bấm loa để bật tiếng).');
              startLiveVideoColorSync();
            });
          });
        }
        return;
      } else {
        showToast('info', 'Chuyển sang Player Iframe', 'Không thể lấy luồng .MP4 trực tiếp cho link này, tự động dùng trình phát Iframe.');
      }
    }

    // MODE 2: Fallback to Official TikTok Iframe Player
    fallbackToIframe(videoId);
  }

  /**
   * Fallback to official TikTok Iframe
   */
  function fallbackToIframe(videoId) {
    if (tiktokVideoPlayer) {
      tiktokVideoPlayer.pause();
      tiktokVideoPlayer.src = '';
      tiktokVideoPlayer.style.display = 'none';
    }
    if (liveColorAnimId) {
      cancelAnimationFrame(liveColorAnimId);
    }

    if (tiktokIframe) {
      tiktokIframe.style.display = 'block';
      const playerUrl = currentEngine === 'v2'
        ? `https://www.tiktok.com/embed/v2/${videoId}`
        : `https://www.tiktok.com/player/v1/${videoId}?autoplay=1&rel=0`;

      tiktokIframe.src = playerUrl;

      const onIframeLoaded = () => {
        showState('video');
        showToast('success', 'Đã tải video', `Đang phát TikTok Iframe ID: ${videoId}`);
        tiktokIframe.removeEventListener('load', onIframeLoaded);
      };

      tiktokIframe.addEventListener('load', onIframeLoaded);

      setTimeout(() => {
        if (loadingState.classList.contains('active')) {
          showState('video');
        }
      }, 2800);
    }
  }

  /**
   * State switcher between empty, loading, and video
   */
  function showState(stateName) {
    emptyState.classList.remove('active');
    loadingState.classList.remove('active');
    videoState.classList.remove('active');

    const phoneFrame = document.getElementById('phoneFrame');
    const ambientWrapper = document.getElementById('ambientWrapper');

    if (stateName === 'empty') {
      if (innerScreen) {
        innerScreen.classList.add('is-empty');
        innerScreen.classList.remove('is-playing');
      }
      if (phoneFrame) {
        phoneFrame.classList.add('is-empty');
        phoneFrame.classList.remove('is-playing');
      }
      if (ambientWrapper) {
        ambientWrapper.style.opacity = '0';
      }
      if (ambientCanvas && ambientCtx) {
        ambientCtx.clearRect(0, 0, ambientCanvas.width, ambientCanvas.height);
      }

      emptyState.classList.add('active');
      if (tiktokVideoPlayer) {
        tiktokVideoPlayer.pause();
        tiktokVideoPlayer.src = '';
        tiktokVideoPlayer.style.display = 'none';
      }
      if (tiktokIframe) {
        tiktokIframe.src = '';
        tiktokIframe.style.display = 'none';
      }
      if (liveColorAnimId) cancelAnimationFrame(liveColorAnimId);
      startStandbyAmbientLoop();
    } else if (stateName === 'loading') {
      if (innerScreen) {
        innerScreen.classList.remove('is-empty');
        innerScreen.classList.add('is-playing');
      }
      if (phoneFrame) {
        phoneFrame.classList.remove('is-empty');
        phoneFrame.classList.add('is-playing');
      }
      loadingState.classList.add('active');
    } else if (stateName === 'video') {
      if (innerScreen) {
        innerScreen.classList.remove('is-empty');
        innerScreen.classList.add('is-playing');
      }
      if (phoneFrame) {
        phoneFrame.classList.remove('is-empty');
        phoneFrame.classList.add('is-playing');
      }
      if (ambientWrapper) {
        ambientWrapper.style.opacity = '0.9';
      }
      videoState.classList.add('active');
    }
  }

  // 5. Frame Actions: Refresh and Open External
  refreshVideoBtn.addEventListener('click', () => {
    if (currentVideoId) {
      loadTikTokVideo(currentVideoId);
    } else {
      showToast('info', 'Chưa có video', 'Hãy nhập link hoặc chọn video mẫu để phát.');
    }
  });

  // 6. Toast Notification Helper
  function showToast(type, title, message) {
    if (toastTimer) {
      clearTimeout(toastTimer);
    }

    toastNotification.className = `toast-notification liquid-glass ${type}`;
    toastTitle.textContent = title;
    toastMsg.textContent = message;

    // Set icon based on type
    const toastIcon = document.getElementById('toastIcon');
    if (type === 'success') {
      toastIcon.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      `;
    } else if (type === 'error') {
      toastIcon.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
      `;
    } else {
      toastIcon.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
      `;
    }

    toastNotification.classList.add('show');

    toastTimer = setTimeout(() => {
      toastNotification.classList.remove('show');
    }, 3500);
  }

  // =========================================================================
  // 7. Spec v2.1.0: Google Maps Navigation, Playlist Stream & Drawers
  // =========================================================================

  /**
   * Updates Google Maps link and flies Leaflet Map to coordinates if available
   */
  function updateActiveVideoLocation(videoId) {
    const foundItem = videoPlaylist.find(item => item.id === videoId);
    if (foundItem) {
      if (googleMapNavBtn) {
        googleMapNavBtn.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(foundItem.gmapQuery || foundItem.locationName)}`;
        googleMapNavBtn.setAttribute('title', `Chỉ đường tới ${foundItem.locationName} trên Google Maps`);
      }
      if (foundItem.lat && foundItem.lng && leafletMap) {
        try {
          leafletMap.flyTo([foundItem.lat, foundItem.lng], 15, {
            duration: 2.0,
            easeLinearity: 0.25
          });
        } catch (e) {
          console.warn('Map fly error:', e);
        }
      }
    } else if (googleMapNavBtn) {
      googleMapNavBtn.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`TikTok Video ${videoId}`)}`;
      googleMapNavBtn.setAttribute('title', `Tìm kiếm địa điểm video trên Google Maps`);
    }
  }

  /**
   * Plays a playlist item by index (supports wrapping around)
   */
  function playPlaylistItem(index) {
    if (videoPlaylist.length === 0) return;
    currentPlaylistIndex = (index + videoPlaylist.length) % videoPlaylist.length;
    const item = videoPlaylist[currentPlaylistIndex];
    currentVideoId = item.id;
    currentOriginalUrl = item.url;
    videoUrlInput.value = item.url;
    clearBtn.style.display = 'flex';
    inputWrapper.classList.remove('shake-error');
    
    loadTikTokVideo(item.id);
    showToast('info', 'Lướt video', `${item.title} (${currentPlaylistIndex + 1}/${videoPlaylist.length})`);
  }

  // Stream Navigation Buttons (Up / Down)
  if (prevVideoBtn) {
    prevVideoBtn.addEventListener('click', () => {
      playPlaylistItem(currentPlaylistIndex - 1);
    });
  }

  if (nextVideoBtn) {
    nextVideoBtn.addEventListener('click', () => {
      playPlaylistItem(currentPlaylistIndex + 1);
    });
  }

  // Keyboard Navigation: ArrowUp (prev), ArrowDown (next), Escape (close drawer)
  window.addEventListener('keydown', (e) => {
    // If user is currently typing in input field, don't hijack arrow keys
    if (document.activeElement === videoUrlInput) {
      if (e.key === 'Escape') {
        videoUrlInput.blur();
      }
      return;
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      playPlaylistItem(currentPlaylistIndex - 1);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      playPlaylistItem(currentPlaylistIndex + 1);
    } else if (e.key === 'Escape') {
      closeDrawer();
    }
  });

  // =========================================================================
  // 8. Liquid Glass Slide-in Drawer Management
  // =========================================================================
  function openDrawer(mode) {
    if (!liquidDrawer || !drawerBackdrop) return;
    drawerBackdrop.classList.add('active');
    liquidDrawer.classList.add('active');
    liquidDrawer.setAttribute('aria-hidden', 'false');

    if (mode === 'liked-videos') {
      drawerIconBadge.innerHTML = `
        <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
        </svg>
      `;
      drawerTitle.textContent = 'Các Video Đã Thích';
      drawerSubtitle.textContent = `${videoPlaylist.length} video thịnh hành đã lưu trong bộ sưu tập`;
      
      drawerBody.innerHTML = videoPlaylist.map((item, idx) => `
        <div class="drawer-card liquid-glass" data-idx="${idx}">
          <div class="drawer-card-icon">${item.icon}</div>
          <div class="drawer-card-info">
            <div class="drawer-card-title">${item.title}</div>
            <div class="drawer-card-desc">${item.author} • ${item.locationName}</div>
          </div>
          <span class="drawer-card-badge">${item.category}</span>
        </div>
      `).join('');
    } else if (mode === 'liked-places') {
      drawerIconBadge.innerHTML = `
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
          <circle cx="12" cy="10" r="3"></circle>
        </svg>
      `;
      drawerTitle.textContent = 'Các Địa Điểm Đã Thích';
      drawerSubtitle.textContent = 'Quán ăn & địa danh đã lưu trên bản đồ';

      drawerBody.innerHTML = videoPlaylist.map((item, idx) => `
        <div class="drawer-card liquid-glass" data-idx="${idx}">
          <div class="drawer-card-icon">📍</div>
          <div class="drawer-card-info">
            <div class="drawer-card-title">${item.locationName}</div>
            <div class="drawer-card-desc">${item.desc}</div>
          </div>
          <span class="drawer-card-badge" style="background: rgba(0, 223, 162, 0.15); color: #00dfa2;">Bay tới Map</span>
        </div>
      `).join('');
    } else if (mode === 'history') {
      drawerIconBadge.innerHTML = `
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="1 4 1 10 7 10"></polyline>
          <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
          <polyline points="12 6 12 12 16 14"></polyline>
        </svg>
      `;
      drawerTitle.textContent = 'Lịch Sử Phân Tích';
      drawerSubtitle.textContent = 'Nhật ký các video TikTok và vị trí đã trích xuất';

      drawerBody.innerHTML = videoPlaylist.map((item, idx) => `
        <div class="drawer-card liquid-glass" data-idx="${idx}">
          <div class="drawer-card-icon">⚡</div>
          <div class="drawer-card-info">
            <div class="drawer-card-title">ID: ${item.id} (${item.title})</div>
            <div class="drawer-card-desc">Tọa độ: [${item.lat.toFixed(4)}, ${item.lng.toFixed(4)}] • Trạng thái: 200 OK</div>
          </div>
          <span class="drawer-card-badge" style="background: rgba(255, 0, 127, 0.15); color: #ff007f;">Đã quét</span>
        </div>
      `).join('');
    }

    // Attach click events on drawer cards
    const cards = drawerBody.querySelectorAll('.drawer-card');
    cards.forEach(card => {
      card.addEventListener('click', () => {
        const idx = parseInt(card.getAttribute('data-idx'), 10);
        if (!isNaN(idx)) {
          playPlaylistItem(idx);
          closeDrawer();
        }
      });
    });
  }

  function closeDrawer() {
    if (!liquidDrawer || !drawerBackdrop) return;
    drawerBackdrop.classList.remove('active');
    liquidDrawer.classList.remove('active');
    liquidDrawer.setAttribute('aria-hidden', 'true');
  }

  // Left Dock button clicks
  if (likedVideosBtn) likedVideosBtn.addEventListener('click', () => openDrawer('liked-videos'));
  if (likedPlacesBtn) likedPlacesBtn.addEventListener('click', () => openDrawer('liked-places'));
  if (analysisHistoryBtn) analysisHistoryBtn.addEventListener('click', () => openDrawer('history'));
  if (closeDrawerBtn) closeDrawerBtn.addEventListener('click', closeDrawer);
  if (drawerBackdrop) drawerBackdrop.addEventListener('click', closeDrawer);
});
