<template>
  <div class="home-container">
    <!-- 背景装饰 -->
    <div class="background-decoration">
      <div class="decoration-circle circle-1"></div>
      <div class="decoration-circle circle-2"></div>
      <div class="decoration-circle circle-3"></div>
    </div>

    <!-- 顶部标题区 -->
    <div class="hero-section">
      <div class="hero-content">
        <h1 class="hero-title">
          <span class="icon">🌍</span>
          智能行程规划
        </h1>
        <p class="hero-subtitle">让AI为您规划完美旅程，专属定制、智能优化</p>
        <div class="hero-features">
          <div class="feature-item">
            <span class="feature-icon">✨</span>
            <span>AI智能推荐</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon">📍</span>
            <span>精准地图导航</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon">💰</span>
            <span>预算智能管理</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 表单卡片 -->
    <el-card class="form-card">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="120px" label-position="top">
        <el-row :gutter="20">
          <!-- 目的地 -->
          <el-col :span="12">
            <el-form-item label="目的地" prop="destination">
              <el-select
                v-model="formData.destination"
                placeholder="请选择您想去的城市"
                clearable
                filterable
                default-first-option
                size="large"
                style="width: 100%"
                :loading="cityOptionsLoading"
              >
                <template #prefix>
                  <el-icon><Location /></el-icon>
                </template>
                <el-option
                  v-for="city in cityOptions"
                  :key="city"
                  :label="city"
                  :value="city"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <!-- 日期范围 -->
          <el-col :span="12">
            <el-form-item label="出行日期" prop="dateRange">
              <el-date-picker
                v-model="formData.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                size="large"
                style="width: 100%"
                :disabled-date="disabledDate"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <!-- 旅行偏好 -->
          <el-col :span="12">
            <el-form-item label="旅行偏好" prop="preferences">
              <el-select
                v-model="formData.preferences"
                multiple
                placeholder="选择您感兴趣的类型"
                size="large"
                style="width: 100%"
                collapse-tags
                collapse-tags-tooltip
              >
                <el-option label="🏯 历史文化" value="历史" />
                <el-option label="🌄 自然风光" value="自然" />
                <el-option label="🍜 美食体验" value="美食" />
                <el-option label="🛍️ 购物娱乐" value="购物" />
                <el-option label="👶 亲子游玩" value="亲子" />
                <el-option label="📸 摄影打卡" value="摄影" />
                <el-option label="☘️ 休闲放松" value="休闲" />
              </el-select>
            </el-form-item>
          </el-col>

          <!-- 酒店偏好 -->
          <el-col :span="12">
            <el-form-item label="酒店偏好" prop="hotelPreferences">
              <el-select
                v-model="formData.hotelPreferences"
                multiple
                placeholder="选择酒店类型"
                size="large"
                style="width: 100%"
                collapse-tags
                collapse-tags-tooltip
              >
                <el-option label="🏠 经济型" value="经济型" />
                <el-option label="🏡 舒适型" value="舒适型" />
                <el-option label="🏪 高档型" value="高档型" />
                <el-option label="🏨 豪华型" value="豪华型" />
                <el-option label="🏕️ 民宿客栈" value="民宿" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 预算 -->
        <el-form-item label="预算范围" prop="budget">
          <el-radio-group v-model="formData.budget" size="large" class="budget-group">
            <el-radio-button label="经济">
              <div class="budget-option">
                <span class="budget-icon">👛</span>
                <span class="budget-text">经济</span>
              </div>
            </el-radio-button>
            <el-radio-button label="中等">
              <div class="budget-option">
                <span class="budget-icon">👜</span>
                <span class="budget-text">中等</span>
              </div>
            </el-radio-button>
            <el-radio-button label="宽裕">
              <div class="budget-option">
                <span class="budget-icon">💄</span>
                <span class="budget-text">宽裕</span>
              </div>
            </el-radio-button>
            <el-radio-button label="豪华">
              <div class="budget-option">
                <span class="budget-icon">💎</span>
                <span class="budget-text">豪华</span>
              </div>
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 提交按钮 -->
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleSubmit"
            class="submit-button"
          >
            <el-icon v-if="!loading" class="mr-2"><Search /></el-icon>
            {{ loading ? '正在规划中...' : '开始规划您的旅程' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 示例行程卡片 -->
    <div class="example-section">
      <div class="section-header">
        <h3>🔥 热门行程推荐</h3>
        <p>点击卡片快速填充示例数据</p>
      </div>
      <el-row :gutter="24">
        <el-col :span="8" v-for="example in examples" :key="example.title">
          <div class="example-card" @click="fillExample(example)">
            <div class="example-icon-wrapper">
              <div class="example-icon">{{ example.icon }}</div>
            </div>
            <h4>{{ example.title }}</h4>
            <p>{{ example.description }}</p>
            <div class="example-tags">
              <el-tag size="small" type="info">{{ example.data.days }}天{{ example.data.days - 1 }}晚</el-tag>
              <el-tag size="small" type="warning">{{ example.data.budget }}</el-tag>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 加载进度弹窗 -->
    <LoadingProgress 
      ref="loadingProgressRef"
      v-model:visible="loadingProgressVisible"
      :task-progress="taskProgress"
      :task-title="taskTitle"
      :task-description="taskDescription"
      :task-step="taskStep"
      @cancel="handleCancelRequest"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Location, Search } from '@element-plus/icons-vue'
import { tripApi, authApi } from '@/services/api'
import LoadingProgress from '@/components/LoadingProgress.vue'
import type { TripFormData, TripPlanRequest } from '@/types'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useTripStore } from '@/stores/trip'

const CITY_OPTIONS_CACHE_KEY = 'citySupportOptions'

const router = useRouter()
const authStore = useAuthStore()
const tripStore = useTripStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const loadingProgressVisible = ref(false)
const loadingProgressRef = ref<InstanceType<typeof LoadingProgress>>()
const taskPollingTimer = ref<number | null>(null)
const taskProgress = ref<number | undefined>(undefined)
const taskTitle = ref<string | undefined>(undefined)
const taskDescription = ref<string | undefined>(undefined)
const taskStep = ref<number | undefined>(undefined)
const currentTaskId = ref<string | null>(null)
const cityOptions = ref<string[]>([])
const cityOptionsLoading = ref(false)

// 表单数据
const formData = reactive<TripFormData>({
  destination: '',
  dateRange: ['', ''],
  preferences: [],
  hotelPreferences: [],
  budget: '中等'
})

// 表单验证规则
const rules: FormRules = {
  destination: [
    { required: true, message: '请选择目的地', trigger: 'change' }
  ],
  dateRange: [
    { required: true, message: '请选择出行日期', trigger: 'change' }
  ]
}

// 禁用过去的日期
const disabledDate = (time: Date) => {
  return time.getTime() < Date.now() - 24 * 60 * 60 * 1000
}

// 示例行程
const examples = [
  {
    title: '北京文化之旅',
    description: '3天2晚 · 历史文化 · 中等预算',
    icon: '🏯',
    data: {
      destination: '北京',
      days: 3,
      preferences: ['历史', '美食'],
      hotelPreferences: ['舒适型', '高档型'],
      budget: '中等'
    }
  },
  {
    title: '杭州休闲游',
    description: '2天1晚 · 自然风光 · 经济预算',
    icon: '🌊',
    data: {
      destination: '杭州',
      days: 2,
      preferences: ['自然', '休闲'],
      hotelPreferences: ['经济型', '民宿'],
      budget: '经济'
    }
  },
  {
    title: '成都美食探索',
    description: '4天3晚 · 美食体验 · 宽裕预算',
    icon: '🍜',
    data: {
      destination: '成都',
      days: 4,
      preferences: ['美食', '休闲'],
      hotelPreferences: ['舒适型', '高档型'],
      budget: '宽裕'
    }
  }
]

// 填充示例数据
const fillExample = (example: any) => {
  formData.destination = example.data.destination
  formData.preferences = example.data.preferences || []
  formData.hotelPreferences = example.data.hotelPreferences || []
  formData.budget = example.data.budget
  
  // 设置日期范围
  const today = new Date()
  const startDate = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000)
  const endDate = new Date(startDate.getTime() + (example.data.days - 1) * 24 * 60 * 60 * 1000)
  
  formData.dateRange = [
    startDate.toISOString().split('T')[0],
    endDate.toISOString().split('T')[0]
  ]
  
  ElMessage.success('已填充示例数据，您可以直接开始规划！')
}

const mapTaskToStep = (progress: number) => {
  if (progress < 25) return 0
  if (progress < 50) return 1
  if (progress < 80) return 2
  return 3
}

const loadCityOptions = async () => {
  if (cityOptions.value.length === 0) {
    cityOptionsLoading.value = true
  }
  try {
    const response = await tripApi.listCitySupport()
    cityOptions.value = response.cities || []
    localStorage.setItem(CITY_OPTIONS_CACHE_KEY, JSON.stringify(cityOptions.value))
  } catch {
    if (cityOptions.value.length === 0) {
      cityOptions.value = []
    }
  } finally {
    cityOptionsLoading.value = false
  }
}

const hydrateCityOptions = () => {
  try {
    const cachedCities = localStorage.getItem(CITY_OPTIONS_CACHE_KEY)
    if (!cachedCities) {
      return
    }

    const parsedCities = JSON.parse(cachedCities)
    if (Array.isArray(parsedCities)) {
      cityOptions.value = parsedCities.filter((city): city is string => typeof city === 'string')
    }
  } catch {
    localStorage.removeItem(CITY_OPTIONS_CACHE_KEY)
  }
}

const stopTaskPolling = () => {
  if (taskPollingTimer.value) {
    clearInterval(taskPollingTimer.value)
    taskPollingTimer.value = null
  }
}

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    if (!authStore.isAuthenticated) {
      try {
        await authApi.createGuestSession()
        ElMessage.info('当前以访客模式规划行程：可保存和查看历史，跨设备/清理Cookie后可能丢失')
      } catch {
        ElMessage.warning('访客会话初始化失败，将继续尝试请求')
      }
    }
    
    loading.value = true
    loadingProgressVisible.value = true
    taskProgress.value = 0
    taskTitle.value = '任务创建中...'
    taskDescription.value = '系统正在初始化行程生成任务'
    taskStep.value = 0
    
    try {
      // 构建请求数据
      const request: TripPlanRequest = {
        destination: formData.destination,
        start_date: formData.dateRange[0],
        end_date: formData.dateRange[1],
        preferences: formData.preferences,
        hotel_preferences: formData.hotelPreferences,
        budget: formData.budget
      }
      
      // 改为异步任务模式
      const task = await tripApi.createTripPlanTask(request)
      currentTaskId.value = task.task_id
      taskTitle.value = '任务已创建'
      taskDescription.value = task.message

      const maxPollMs = 5 * 60 * 1000
      const startedAt = Date.now()

      // 立即拉一次
      const pollOnce = async () => {
        if (!currentTaskId.value) return
        const status = await tripApi.getTripTask(currentTaskId.value)
        taskProgress.value = status.progress
        taskTitle.value = status.status === 'failed' ? '任务失败' : '行程生成中...'
        taskDescription.value = status.message || '系统正在生成行程'
        taskStep.value = mapTaskToStep(status.progress)

        if (status.status === 'succeeded' && status.result_trip_id) {
          stopTaskPolling()
          const result = await tripApi.getTripDetail(status.result_trip_id)
          loadingProgressRef.value?.completeProgress()
          setTimeout(() => {
            loading.value = false
            loadingProgressVisible.value = false
            currentTaskId.value = null
            const currentTrip = tripStore.upsertTrip(result)
            tripStore.setCurrentTrip(currentTrip)
            tripStore.setEditReturnTo('result')
            ElMessage.success('行程规划成功')
            router.push({
              name: 'Result'
            })
          }, 400)
          return
        }

        if (status.status === 'failed') {
          stopTaskPolling()
          loading.value = false
          loadingProgressVisible.value = false
          currentTaskId.value = null
          throw new Error(status.error || status.message || '任务执行失败')
        }

        if (Date.now() - startedAt > maxPollMs) {
          stopTaskPolling()
          loading.value = false
          loadingProgressVisible.value = false
          currentTaskId.value = null
          throw new Error('任务超时，请稍后重试')
        }
      }

      await pollOnce()
      taskPollingTimer.value = window.setInterval(() => {
        pollOnce().catch((err) => {
          stopTaskPolling()
          loading.value = false
          loadingProgressVisible.value = false
          currentTaskId.value = null
          ElMessage.error(err.message || '规划失败，请重试')
        })
      }, 1500)
    } catch (error: any) {
      loadingProgressVisible.value = false
      ElMessage.error(error.message || '规划失败，请重试')
      console.error('规划失败:', error)
    } finally {
      // 这里不能立即置false，交给任务结束逻辑处理
      if (!currentTaskId.value) {
        loading.value = false
      }
    }
  })
}

// 处理取消请求
const handleCancelRequest = () => {
  stopTaskPolling()
  currentTaskId.value = null
  loading.value = false
  taskProgress.value = undefined
  taskTitle.value = undefined
  taskDescription.value = undefined
  taskStep.value = undefined
  // 表单数据会自动保留（因为是reactive的）
  ElMessage.info('已取消请求，您的表单信息已保留')
}

onMounted(() => {
  hydrateCityOptions()
  loadCityOptions()
})
</script>

<style scoped lang="scss">
.home-container {
  position: relative;
  min-height: 100vh;
  padding: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  overflow: hidden;

  // 背景装饰
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

  // 英雄区
  .hero-section {
    position: relative;
    padding: 80px 20px 60px;
    text-align: center;
    color: white;
    z-index: 1;

    .hero-content {
      max-width: 800px;
      margin: 0 auto;

      .hero-title {
        margin: 0 0 20px 0;
        font-size: 48px;
        font-weight: 700;
        text-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        animation: fadeInDown 0.8s ease;

        .icon {
          display: inline-block;
          animation: rotate 3s ease-in-out infinite;
        }
      }

      .hero-subtitle {
        margin: 0 0 40px 0;
        font-size: 18px;
        opacity: 0.95;
        animation: fadeInUp 0.8s ease 0.2s backwards;
      }

      .hero-features {
        display: flex;
        justify-content: center;
        gap: 40px;
        animation: fadeInUp 0.8s ease 0.4s backwards;

        .feature-item {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 16px;

          .feature-icon {
            font-size: 20px;
          }
        }
      }
    }
  }

  // 表单卡片
  .form-card {
    position: relative;
    max-width: 900px;
    margin: 0 auto 60px;
    border-radius: 24px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    animation: fadeInUp 0.8s ease 0.6s backwards;
    z-index: 1;

    :deep(.el-card__body) {
      padding: 40px;
    }

    .budget-group {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      width: 100%;

      :deep(.el-radio-button) {
        flex: 1;

        .el-radio-button__inner {
          width: 100%;
          border-radius: 12px;
          border: 2px solid #e4e7ed;
          padding: 16px;
          transition: all 0.3s;

          &:hover {
            border-color: #409eff;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(64, 158, 255, 0.2);
          }
        }

        &.is-active .el-radio-button__inner {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          border-color: #667eea;
          box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4);
        }
      }

      .budget-option {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;

        .budget-icon {
          font-size: 28px;
        }

        .budget-text {
          font-size: 14px;
          font-weight: 500;
        }
      }
    }

    .submit-button {
      width: 100%;
      height: 50px;
      font-size: 16px;
      font-weight: 600;
      border-radius: 12px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none;
      box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
      transition: all 0.3s;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 32px rgba(102, 126, 234, 0.5);
      }

      &:active {
        transform: translateY(0);
      }
    }

  }

  // 示例区域
  .example-section {
    position: relative;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px 80px;
    z-index: 1;

    .section-header {
      text-align: center;
      margin-bottom: 40px;
      color: white;

      h3 {
        margin: 0 0 8px 0;
        font-size: 28px;
        font-weight: 600;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      }

      p {
        margin: 0;
        font-size: 14px;
        opacity: 0.9;
      }
    }

    .example-card {
      background: white;
      border-radius: 16px;
      padding: 32px 24px;
      cursor: pointer;
      transition: all 0.3s;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
      height: 100%;

      &:hover {
        transform: translateY(-8px);
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);

        .example-icon-wrapper {
          transform: scale(1.1) rotate(5deg);
        }
      }

      .example-icon-wrapper {
        margin-bottom: 20px;
        display: flex;
        justify-content: center;
        transition: transform 0.3s;

        .example-icon {
          width: 80px;
          height: 80px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 48px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          border-radius: 20px;
          box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
        }
      }

      h4 {
        margin: 0 0 12px 0;
        font-size: 20px;
        color: #303133;
        font-weight: 600;
        text-align: center;
      }

      p {
        margin: 0 0 16px 0;
        font-size: 14px;
        color: #909399;
        text-align: center;
        line-height: 1.6;
      }

      .example-tags {
        display: flex;
        justify-content: center;
        gap: 8px;
      }
    }
  }
}

.mr-2 {
  margin-right: 8px;
}

// 动画
@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes rotate {
  0%, 100% {
    transform: rotate(0deg);
  }
  50% {
    transform: rotate(20deg);
  }
}

@keyframes float {
  0%, 100% {
    transform: translateY(0) translateX(0);
  }
  33% {
    transform: translateY(-30px) translateX(30px);
  }
  66% {
    transform: translateY(30px) translateX(-30px);
  }
}

// 响应式
@media (max-width: 768px) {
  .home-container {
    .hero-section {
      padding: 60px 20px 40px;

      .hero-content {
        .hero-title {
          font-size: 36px;
        }

        .hero-subtitle {
          font-size: 16px;
        }

        .hero-features {
          flex-direction: column;
          gap: 16px;
        }
      }
    }

    .form-card {
      :deep(.el-card__body) {
        padding: 24px;
      }

      .budget-group {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    .example-section {
      .example-card {
        margin-bottom: 20px;
      }
    }
  }
}
</style>
