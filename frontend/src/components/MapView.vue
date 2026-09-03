<template>
  <div class="map-container">
    <div ref="mapContainer" class="amap-container"></div>

    <div class="map-controls">
      <el-button-group>
        <el-button size="small" @click="fitView">
          <el-icon><FullScreen /></el-icon>
          Fit View
        </el-button>
        <el-button size="small" @click="toggleRouteVisible">
          <el-icon><Guide /></el-icon>
          {{ routeVisible ? 'Hide' : 'Show' }} Route
        </el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { FullScreen, Guide } from '@element-plus/icons-vue'
import type { MapPoint, Location } from '@/types'

const AMAP_KEY = import.meta.env.VITE_AMAP_KEY || 'YOUR_AMAP_KEY'
const AMAP_SECURITY_CODE = import.meta.env.VITE_AMAP_SECURITY_CODE || ''

interface Props {
  points?: MapPoint[]
  center?: Location
}

const props = defineProps<Props>()

const mapContainer = ref<HTMLDivElement>()
const map = ref<any>(null)
const markers = ref<any[]>([])
const polyline = ref<any>(null)
const routeVisible = ref(true)
const amap = ref<any>(null)

let amapLoaderPromise: Promise<any> | null = null

const loadAMap = async () => {
  if (!amapLoaderPromise) {
    amapLoaderPromise = import('@amap/amap-jsapi-loader').then((mod) =>
      mod.default.load({
        key: AMAP_KEY,
        version: '2.0',
        plugins: [
          'AMap.Scale',
          'AMap.ToolBar',
          'AMap.Marker',
          'AMap.Polyline',
          'AMap.InfoWindow',
          'AMap.MarkerCluster'
        ]
      })
    )
  }

  return amapLoaderPromise
}

const pointsSignature = computed(() =>
  (props.points ?? [])
    .map((point) => {
      const lng = point.location?.lng ?? ''
      const lat = point.location?.lat ?? ''
      return [point.name, point.type, lng, lat].join(':')
    })
    .join('|')
)

const centerSignature = computed(() => {
  const lng = props.center?.lng
  const lat = props.center?.lat
  return lng != null && lat != null ? `${lng}:${lat}` : ''
})

const getActivityIcon = (type: string): string => {
  const iconMap: Record<string, string> = {
    attraction: 'A',
    dining: 'D',
    hotel: 'H',
    transport: 'T',
    other: 'P'
  }
  return iconMap[type] || 'P'
}

const getActivityColor = (type: string): string => {
  const colorMap: Record<string, string> = {
    attraction: '#4a90e2',
    dining: '#67c23a',
    hotel: '#f39c12',
    transport: '#95a5a6',
    other: '#909399'
  }
  return colorMap[type] || '#909399'
}

const getActivityTypeText = (type: string): string => {
  const typeMap: Record<string, string> = {
    attraction: 'Attraction',
    dining: 'Dining',
    hotel: 'Hotel',
    transport: 'Transport',
    other: 'Other'
  }
  return typeMap[type] || type
}

const clearMarkers = () => {
  if (!map.value) {
    markers.value = []
    polyline.value = null
    return
  }

  if (markers.value.length > 0) {
    map.value.remove(markers.value)
    markers.value = []
  }

  if (polyline.value) {
    map.value.remove(polyline.value)
    polyline.value = null
  }
}

const drawRoute = (points: [number, number][]) => {
  if (!map.value || !amap.value) {
    return
  }

  if (polyline.value) {
    map.value.remove(polyline.value)
  }

  polyline.value = new amap.value.Polyline({
    path: points,
    strokeColor: '#4a90e2',
    strokeWeight: 5,
    strokeOpacity: 0.8,
    lineJoin: 'round',
    lineCap: 'round',
    showDir: true,
    dirColor: '#fff',
    borderWeight: 1,
    isOutline: true,
    outlineColor: '#fff',
    strokeStyle: 'solid'
  })

  map.value.add(polyline.value)
}

const fitView = () => {
  if (map.value && markers.value.length > 0) {
    map.value.setFitView(markers.value, false, [50, 50, 50, 50], 13)
  }
}

const loadMarkers = () => {
  if (!map.value || !amap.value || !props.points?.length) {
    clearMarkers()
    return
  }

  clearMarkers()

  const pathPoints: [number, number][] = []
  const groups = new Map<string, MapPoint[]>()

  for (const point of props.points) {
    if (!point.location) {
      continue
    }

    const lng = Number(point.location.lng)
    const lat = Number(point.location.lat)

    if (
      Number.isNaN(lng) ||
      Number.isNaN(lat) ||
      lng < -180 || lng > 180 ||
      lat < -90 || lat > 90
    ) {
      console.warn('Skipping invalid map point', point.name, { lng, lat })
      continue
    }

    const key = `${lng.toFixed(6)},${lat.toFixed(6)}`
    const group = groups.get(key)
    if (group) {
      group.push(point)
    } else {
      groups.set(key, [point])
    }
  }

  let groupIndex = 0

  for (const [key, groupPoints] of groups.entries()) {
    groupIndex += 1

    const [lngStr, latStr] = key.split(',')
    const lng = Number(lngStr)
    const lat = Number(latStr)
    pathPoints.push([lng, lat])

    const firstPoint = groupPoints[0]
    const activityIcon = getActivityIcon(firstPoint.type)
    const activityColor = getActivityColor(firstPoint.type)

    const marker = new amap.value.Marker({
      position: [lng, lat],
      content: `
        <div class="custom-marker" style="--marker-color: ${activityColor}">
          <div class="marker-icon-wrapper">
            <div class="marker-icon">${activityIcon}</div>
            <div class="marker-number">${groupIndex}</div>
          </div>
        </div>
      `,
      anchor: 'center',
      offset: new amap.value.Pixel(0, 0),
      extData: {
        index: groupIndex,
        points: groupPoints
      }
    })

    const listHtml = groupPoints
      .map((point, index) => `
        <li>
          <strong>${index + 1}. ${point.name}</strong>
          <div>Type: ${getActivityTypeText(point.type)}</div>
          ${point.description ? `<div>${point.description}</div>` : ''}
          ${point.cost ? `<div>Cost: <strong>${point.cost}</strong></div>` : ''}
        </li>
      `)
      .join('')

    const infoWindow = new amap.value.InfoWindow({
      content: `
        <div class="info-window">
          <div class="info-header">
            <span class="info-icon">${activityIcon}</span>
            <h4>Stop ${groupIndex}</h4>
          </div>
          <div class="info-body">
            <ul class="info-list">
              ${listHtml}
            </ul>
          </div>
        </div>
      `,
      offset: new amap.value.Pixel(0, -10),
      autoMove: true
    })

    marker.on('click', () => {
      map.value?.clearInfoWindow()
      infoWindow.open(map.value, marker.getPosition())
    })

    marker.on('mouseover', () => marker.setTop(true))
    marker.on('mouseout', () => marker.setTop(false))

    markers.value.push(marker)
    map.value.add(marker)
  }

  if (pathPoints.length > 1 && routeVisible.value) {
    drawRoute(pathPoints)
  }

  if (pathPoints.length > 0) {
    fitView()
  }
}

const initMap = async () => {
  if (!mapContainer.value || map.value) {
    return
  }

  try {
    if (AMAP_SECURITY_CODE) {
      ;(window as any)._AMapSecurityConfig = {
        securityJsCode: AMAP_SECURITY_CODE
      }
    }

    amap.value = await loadAMap()

    const centerLng = Number(props.center?.lng)
    const centerLat = Number(props.center?.lat)
    const hasValidCenter = !Number.isNaN(centerLng) && !Number.isNaN(centerLat)

    map.value = new amap.value.Map(mapContainer.value, {
      zoom: 12,
      center: hasValidCenter ? [centerLng, centerLat] : [116.397428, 39.90923],
      viewMode: '2D',
      pitch: 0,
      resizeEnable: true,
      dragEnable: true,
      zoomEnable: true,
      doubleClickZoom: true,
      scrollWheel: true,
      touchZoom: true,
      animateEnable: true,
      jogEnable: true
    })

    map.value.addControl(new amap.value.Scale())
    map.value.addControl(new amap.value.ToolBar())
    loadMarkers()
  } catch (error: any) {
    console.error('Failed to initialize map:', error)
    ElMessage.error(error?.message ? `Map load failed: ${error.message}` : 'Map load failed')
  }
}

const toggleRouteVisible = () => {
  routeVisible.value = !routeVisible.value

  if (!polyline.value) {
    loadMarkers()
    return
  }

  if (routeVisible.value) {
    polyline.value.show()
  } else {
    polyline.value.hide()
  }
}

watch(pointsSignature, () => {
  if (map.value) {
    loadMarkers()
  }
})

watch(centerSignature, () => {
  if (!map.value || !props.center) {
    return
  }

  const centerLng = Number(props.center.lng)
  const centerLat = Number(props.center.lat)
  if (!Number.isNaN(centerLng) && !Number.isNaN(centerLat)) {
    map.value.setCenter([centerLng, centerLat])
  }
})

onMounted(() => {
  initMap()
})

onBeforeUnmount(() => {
  clearMarkers()
  map.value?.destroy?.()
  map.value = null
})

defineExpose({
  fitView,
  getMapInstance: () => map.value
})
</script>

<style scoped lang="scss">
.map-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 500px;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);

  .amap-container {
    width: 100%;
    flex: 1;
  }

  .map-controls {
    position: absolute;
    top: 16px;
    right: 16px;
    z-index: 10;
  }
}

:deep(.custom-marker) {
  position: relative;
  width: 48px;
  height: 48px;
  cursor: pointer;
  transition: all 0.3s ease;

  &:hover {
    transform: scale(1.2) translateY(-4px);
    filter: drop-shadow(0 6px 16px rgba(0, 0, 0, 0.4));
  }

  .marker-icon-wrapper {
    position: relative;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .marker-icon {
    width: 48px;
    height: 48px;
    background: var(--marker-color);
    border-radius: 50%;
    transform: none;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    border: 3px solid #fff;
    position: relative;

    &::before {
      content: '';
      position: absolute;
      width: 10px;
      height: 10px;
      background: rgba(255, 255, 255, 0.4);
      border-radius: 50%;
      top: 8px;
      right: 8px;
    }
  }

  .marker-number {
    position: absolute;
    top: -6px;
    right: -6px;
    width: 20px;
    height: 20px;
    background: rgba(0, 0, 0, 0.8);
    color: #fff;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: bold;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
    border: 2px solid #fff;
    z-index: 10;
    transform: none;
    line-height: 1;
  }
}

@keyframes pulse {
  0% {
    transform: translateX(-50%) scale(0.8);
    opacity: 0.8;
  }
  100% {
    transform: translateX(-50%) scale(2);
    opacity: 0;
  }
}

:deep(.info-window) {
  padding: 0;
  min-width: 240px;
  max-width: 320px;
  border-radius: 8px;
  overflow: hidden;

  .info-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;

    .info-icon {
      font-size: 24px;
    }

    h4 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      flex: 1;
    }
  }

  .info-body {
    padding: 12px 16px;

    p {
      margin: 6px 0;
      font-size: 13px;
      color: #606266;
      line-height: 1.6;

      &:first-child {
        margin-top: 0;
      }

      &:last-child {
        margin-bottom: 0;
      }
    }

    .info-label {
      color: #909399;
      font-weight: 500;
      margin-right: 4px;
    }

    .info-details {
      padding: 8px;
      background: #f5f7fa;
      border-radius: 4px;
      margin: 8px 0;
      font-size: 12px;
    }

    .info-cost {
      strong {
        color: #f56c6c;
        font-size: 16px;
      }
    }
  }
}

:deep(.amap-info-content) {
  padding: 0;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

:deep(.amap-info-sharp) {
  border-top-color: #667eea;
}
</style>
