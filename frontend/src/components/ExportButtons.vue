<template>
  <div class="export-buttons">
    <el-button-group>
      <el-button
        type="primary"
        :loading="exporting"
        @click="handleExport('pdf')"
      >
        <el-icon><Document /></el-icon>
        Export PDF
      </el-button>
      <el-button
        type="success"
        :loading="exporting"
        @click="handleExport('image')"
      >
        <el-icon><Picture /></el-icon>
        Export Image
      </el-button>
    </el-button-group>

    <el-dialog
      v-model="dialogVisible"
      title="Export Options"
      width="400px"
    >
      <el-form label-width="100px">
        <el-form-item label="Include">
          <el-checkbox-group v-model="exportOptions.includes">
            <el-checkbox label="budget">Budget</el-checkbox>
            <el-checkbox label="map">Map</el-checkbox>
            <el-checkbox label="hotels">Hotels</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="confirmExport">Confirm</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue'
import { ElMessage, ElLoading } from 'element-plus'
import { Document, Picture } from '@element-plus/icons-vue'
import type { TripPlanResponse } from '@/types'

interface Props {
  tripPlan: TripPlanResponse
  contentRef?: HTMLElement
}

const props = defineProps<Props>()

const exporting = ref(false)
const dialogVisible = ref(false)
const currentFormat = ref<'pdf' | 'image'>('pdf')

const exportOptions = reactive({
  includes: ['budget', 'map', 'hotels']
})

let html2canvasLoader: Promise<typeof import('html2canvas').default> | null = null
let jsPdfLoader: Promise<typeof import('jspdf').default> | null = null

const loadHtml2Canvas = async () => {
  if (!html2canvasLoader) {
    html2canvasLoader = import('html2canvas').then((mod) => mod.default)
  }
  return html2canvasLoader
}

const loadJsPdf = async () => {
  if (!jsPdfLoader) {
    jsPdfLoader = import('jspdf').then((mod) => mod.default)
  }
  return jsPdfLoader
}

const handleExport = (format: 'pdf' | 'image') => {
  currentFormat.value = format
  dialogVisible.value = true
}

const confirmExport = async () => {
  dialogVisible.value = false
  exporting.value = true

  let loadingInstance: ReturnType<typeof ElLoading.service> | null = null

  try {
    await new Promise((resolve) => setTimeout(resolve, 100))
    await nextTick()
    await new Promise((resolve) => setTimeout(resolve, 300))

    loadingInstance = ElLoading.service({
      lock: true,
      text: 'Generating file...',
      background: 'rgba(0, 0, 0, 0.7)'
    })

    if (currentFormat.value === 'pdf') {
      await exportToPDF()
    } else {
      await exportToImage()
    }

    ElMessage.success('Export completed')
  } catch (error) {
    console.error('Export failed:', error)
    ElMessage.error('Export failed, please try again')
  } finally {
    exporting.value = false
    loadingInstance?.close()
  }
}

const exportToPDF = async () => {
  if (!props.contentRef) {
    ElMessage.warning('No export content found')
    return
  }

  const [html2canvas, JsPdf] = await Promise.all([
    loadHtml2Canvas(),
    loadJsPdf()
  ])

  const canvas = await html2canvas(props.contentRef, {
    scale: 2,
    useCORS: true,
    logging: false,
    backgroundColor: '#ffffff'
  })

  const imgWidth = 210
  const imgHeight = (canvas.height * imgWidth) / canvas.width
  const pdf = new JsPdf('p', 'mm', 'a4')

  let heightLeft = imgHeight
  let position = 0

  const imgData = canvas.toDataURL('image/jpeg', 1.0)
  pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight)
  heightLeft -= 297

  while (heightLeft > 0) {
    position = heightLeft - imgHeight
    pdf.addPage()
    pdf.addImage(imgData, 'JPEG', 0, position, imgWidth, imgHeight)
    heightLeft -= 297
  }

  const filename = `${props.tripPlan.trip_title || 'trip-plan'}_${Date.now()}.pdf`
  pdf.save(filename)
}

const exportToImage = async () => {
  if (!props.contentRef) {
    ElMessage.warning('No export content found')
    return
  }

  const html2canvas = await loadHtml2Canvas()
  const canvas = await html2canvas(props.contentRef, {
    scale: 2,
    useCORS: true,
    logging: false,
    backgroundColor: '#ffffff'
  })

  canvas.toBlob((blob) => {
    if (!blob) {
      ElMessage.error('Failed to generate image')
      return
    }

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${props.tripPlan.trip_title || 'trip-plan'}_${Date.now()}.png`
    link.click()
    URL.revokeObjectURL(url)
  }, 'image/png')
}

const quickExport = async (format: 'pdf' | 'image') => {
  currentFormat.value = format
  await confirmExport()
}

defineExpose({
  quickExport
})
</script>

<style scoped lang="scss">
.export-buttons {
  :deep(.el-button-group) {
    display: flex;
  }
}
</style>
