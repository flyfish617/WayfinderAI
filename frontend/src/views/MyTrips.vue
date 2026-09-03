<template>
  <div class="my-trips-container">
    <div class="background-decoration">
      <div class="decoration-circle circle-1"></div>
      <div class="decoration-circle circle-2"></div>
      <div class="decoration-circle circle-3"></div>
    </div>

    <div class="header-section">
      <h1>我的行程</h1>
      <p>查看、编辑和管理已经生成的行程</p>
    </div>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>

    <div v-else-if="tripsList.length > 0" class="trips-content">
      <el-row :gutter="24">
        <el-col
          v-for="(trip, index) in tripsList"
          :key="trip.id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
        >
          <el-card class="trip-card" shadow="hover" @click="viewTrip(index)">
            <div class="trip-card-header">
              <div class="trip-destination">
                <span class="destination-icon">旅行</span>
                <h3>{{ trip.trip_title || '未命名行程' }}</h3>
              </div>
              <div class="trip-badge">第 {{ index + 1 }} 个</div>
            </div>

            <div class="trip-info">
              <div class="info-item">
                <el-icon><Calendar /></el-icon>
                <span>{{ getTripSummary(trip) }}</span>
              </div>
              <div class="info-item">
                <el-icon><Wallet /></el-icon>
                <span>预算 {{ getBudgetLabel(trip) }}</span>
              </div>
              <div class="info-item">
                <el-icon><Clock /></el-icon>
                <span>{{ formatDate(trip.created_at) }}</span>
              </div>
            </div>

            <div class="trip-preview">
              <div class="preview-tags">
                <el-tag
                  v-for="day in trip.days.slice(0, 3)"
                  :key="`${trip.id}-${day.day}`"
                  size="small"
                  type="info"
                >
                  Day {{ day.day }}: {{ day.theme || '未命名主题' }}
                </el-tag>
                <el-tag v-if="trip.days.length > 3" size="small" type="info">
                  +{{ trip.days.length - 3 }}
                </el-tag>
              </div>
            </div>

            <div class="trip-actions">
              <el-button type="primary" size="small" @click.stop="viewTrip(index)">
                <el-icon><View /></el-icon>
                查看
              </el-button>
              <el-button type="success" size="small" @click.stop="editTrip(index)">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button type="danger" size="small" @click.stop="deleteTrip(index)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-empty v-else description="暂无行程记录" class="empty-state">
      <p class="empty-caption">先去首页生成一份新行程，或者稍后再试一次。</p>
      <div class="empty-actions">
        <el-button type="primary" @click="createNewTrip">
          <el-icon><Plus /></el-icon>
          开始规划
        </el-button>
        <el-button @click="loadTrips">重新加载</el-button>
      </div>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Calendar, Wallet, Clock, View, Edit, Delete, Plus } from '@element-plus/icons-vue'
import type { TripListItem } from '@/types'
import { tripApi } from '@/services/api'
import { useTripStore } from '@/stores/trip'

const router = useRouter()
const tripStore = useTripStore()
const loading = ref(false)

const tripsList = computed<TripListItem[]>(() => tripStore.tripsCache)

const formatDate = (dateString: string) => {
  if (!dateString) return '未知时间'

  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) {
    return '未知时间'
  }

  const diffMs = Date.now() - date.getTime()
  const hours = Math.floor(diffMs / (1000 * 60 * 60))

  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours} 小时前`

  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} 天前`

  return date.toLocaleDateString('zh-CN')
}

const getTripSummary = (trip: TripListItem) => {
  const dayCount = Array.isArray(trip.days) ? trip.days.length : 0
  if (dayCount <= 0) return '暂无日程'
  return `${dayCount} 天 ${Math.max(dayCount - 1, 0)} 晚`
}

const getBudgetLabel = (trip: TripListItem) => {
  const total = trip.total_budget?.total
  return typeof total === 'number' ? `￥${total}` : '待补充'
}

const loadTrips = async () => {
  loading.value = true

  try {
    const trips = await tripApi.getTripsList()
    tripStore.setTripsCache(trips)
  } catch (error) {
    console.error('Failed to load trips from API:', error)

    const cachedTrips = tripStore.hydrateTripsCache()
    if (cachedTrips.length > 0) {
      ElMessage.warning('网络异常，已加载本地缓存的行程数据')
    } else {
      ElMessage.error('加载行程列表失败')
    }
  } finally {
    loading.value = false
  }
}

const viewTrip = async (index: number) => {
  const trip = tripsList.value[index]
  if (!trip) return

  if (trip.id) {
    try {
      const fullTrip = await tripApi.getTripDetail(trip.id)
      tripStore.setCurrentTrip(fullTrip)
      router.push({ name: 'Result' })
      return
    } catch (error) {
      console.error('Failed to load trip detail:', error)
      ElMessage.warning('获取详情失败，已使用当前缓存数据')
    }
  }

  tripStore.setCurrentTrip(trip)
  router.push({ name: 'Result' })
}

const editTrip = (index: number) => {
  const trip = tripsList.value[index]
  if (!trip) return

  tripStore.startEditing(trip, 'my-trips')
  router.push({
    name: 'EditPlan',
    query: {
      returnTo: 'my-trips',
    },
  })
}

const deleteTrip = async (index: number) => {
  const trip = tripsList.value[index]
  if (!trip) return

  try {
    await ElMessageBox.confirm(
      '确定要删除这个行程吗？此操作无法恢复。',
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  if (trip.id) {
    try {
      await tripApi.deleteTrip(trip.id)
    } catch (error) {
      console.error('Failed to delete trip:', error)
      ElMessage.error('删除失败，请稍后重试')
      return
    }
  }

  tripStore.removeTrip(trip.id)
  ElMessage.success('行程已删除')
}

const createNewTrip = () => {
  router.push({ name: 'Home' })
}

onMounted(() => {
  loadTrips()
})
</script>

<style scoped lang="scss">
.my-trips-container {
  position: relative;
  min-height: 100vh;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  overflow: hidden;

  .background-decoration {
    position: absolute;
    width: 100%;
    height: 100%;
    overflow: hidden;
    pointer-events: none;

    .decoration-circle {
      position: absolute;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.1);
      animation: float 20s infinite;

      &.circle-1 {
        width: 300px;
        height: 300px;
        top: -150px;
        left: -150px;
        animation-delay: 0s;
      }

      &.circle-2 {
        width: 200px;
        height: 200px;
        top: 50%;
        right: -100px;
        animation-delay: 5s;
      }

      &.circle-3 {
        width: 400px;
        height: 400px;
        bottom: -200px;
        left: 30%;
        animation-delay: 10s;
      }
    }
  }

  .header-section {
    position: relative;
    text-align: center;
    color: white;
    margin-bottom: 40px;
    z-index: 1;
    animation: fadeInDown 0.8s ease;

    h1 {
      margin: 0 0 10px 0;
      font-size: 36px;
      font-weight: 700;
      text-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    p {
      margin: 0;
      font-size: 16px;
      opacity: 0.95;
    }
  }

  .loading-state,
  .trips-content,
  .empty-state {
    position: relative;
    z-index: 1;
    max-width: 1400px;
    margin: 0 auto;
  }

  .loading-state {
    padding: 32px;
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.95);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.12);
  }

  .trip-card {
    margin-bottom: 24px;
    border-radius: 16px;
    cursor: pointer;
    transition: all 0.3s ease;
    height: 100%;
    display: flex;
    flex-direction: column;

    &:hover {
      transform: translateY(-8px);
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
    }

    .trip-card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 16px;
    }

    .trip-destination {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;

      .destination-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 48px;
        height: 32px;
        padding: 0 10px;
        border-radius: 999px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-size: 12px;
        font-weight: 700;
      }

      h3 {
        margin: 0;
        font-size: 18px;
        font-weight: 600;
        color: #303133;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .trip-badge {
      flex-shrink: 0;
      background: rgba(102, 126, 234, 0.12);
      color: #667eea;
      padding: 4px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
    }

    .trip-info {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 16px;

      .info-item {
        display: flex;
        align-items: center;
        gap: 6px;
        color: #606266;
        font-size: 14px;
      }
    }

    .trip-preview {
      margin-bottom: 16px;
      flex: 1;

      .preview-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
    }

    .trip-actions {
      display: flex;
      gap: 8px;
      margin-top: auto;

      .el-button {
        flex: 1;
      }
    }
  }

  .empty-state {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 24px;
    padding: 60px 20px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.1);

    .empty-caption {
      margin: 12px 0 18px;
      color: #6b7280;
    }

    .empty-actions {
      display: flex;
      justify-content: center;
      gap: 12px;
    }
  }
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes float {
  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-20px);
  }
}

@media (max-width: 768px) {
  .my-trips-container {
    padding: 15px;

    .header-section h1 {
      font-size: 28px;
    }

    .trip-card {
      .trip-actions {
        flex-direction: column;
      }
    }

    .empty-state {
      .empty-actions {
        flex-direction: column;
      }
    }
  }
}
</style>
