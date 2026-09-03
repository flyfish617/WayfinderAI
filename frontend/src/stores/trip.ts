import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { EditReturnTarget, TripListItem, TripPlanResponse } from '@/types'
import { normalizeTrip, sanitizeTripPlan } from '@/utils/trip'

const CURRENT_TRIP_KEY = 'currentTripPlan'
const TRIPS_CACHE_KEY = 'myTrips'
const EDIT_RETURN_KEY = 'tripEditReturnTo'

export const useTripStore = defineStore('trip', () => {
  const currentTrip = ref<TripPlanResponse | null>(null)
  const tripsCache = ref<TripListItem[]>([])
  const editReturnTo = ref<EditReturnTarget>('result')

  const hasCurrentTrip = computed(() => !!currentTrip.value)

  const persistCurrentTrip = (trip: TripPlanResponse | null) => {
    if (!trip) {
      sessionStorage.removeItem(CURRENT_TRIP_KEY)
      return
    }

    sessionStorage.setItem(CURRENT_TRIP_KEY, JSON.stringify(trip))
  }

  const persistTripsCache = (trips: TripListItem[]) => {
    localStorage.setItem(TRIPS_CACHE_KEY, JSON.stringify(trips))
  }

  const persistEditReturnTo = (target: EditReturnTarget) => {
    sessionStorage.setItem(EDIT_RETURN_KEY, target)
  }

  const hydrateCurrentTrip = () => {
    if (currentTrip.value) {
      return currentTrip.value
    }

    const savedTrip = sessionStorage.getItem(CURRENT_TRIP_KEY)
    if (!savedTrip) {
      return null
    }

    try {
      currentTrip.value = sanitizeTripPlan(JSON.parse(savedTrip) as TripPlanResponse)
      persistCurrentTrip(currentTrip.value)
      return currentTrip.value
    } catch (error) {
      console.error('Failed to restore current trip:', error)
      sessionStorage.removeItem(CURRENT_TRIP_KEY)
      return null
    }
  }

  const setCurrentTrip = (trip: TripPlanResponse | null) => {
    currentTrip.value = trip ? sanitizeTripPlan(trip) : null
    persistCurrentTrip(currentTrip.value)
  }

  const hydrateTripsCache = () => {
    if (tripsCache.value.length > 0) {
      return tripsCache.value
    }

    const savedTrips = localStorage.getItem(TRIPS_CACHE_KEY)
    if (!savedTrips) {
      return []
    }

    try {
      tripsCache.value = (JSON.parse(savedTrips) as TripPlanResponse[]).map(normalizeTrip)
      persistTripsCache(tripsCache.value)
      return tripsCache.value
    } catch (error) {
      console.error('Failed to restore trips cache:', error)
      localStorage.removeItem(TRIPS_CACHE_KEY)
      return []
    }
  }

  const setTripsCache = (trips: TripPlanResponse[]) => {
    tripsCache.value = trips.map(normalizeTrip)
    persistTripsCache(tripsCache.value)
  }

  const upsertTrip = (trip: TripPlanResponse) => {
    const normalizedTrip = normalizeTrip(trip)
    const index = tripsCache.value.findIndex((item) => item.id === normalizedTrip.id)

    if (index >= 0) {
      tripsCache.value.splice(index, 1, normalizedTrip)
    } else {
      tripsCache.value.unshift(normalizedTrip)
    }

    if (tripsCache.value.length > 100) {
      tripsCache.value = tripsCache.value.slice(0, 100)
    }

    persistTripsCache(tripsCache.value)
    return normalizedTrip
  }

  const removeTrip = (tripId: string) => {
    tripsCache.value = tripsCache.value.filter((trip) => trip.id !== tripId)
    persistTripsCache(tripsCache.value)

    if (currentTrip.value?.id === tripId) {
      setCurrentTrip(null)
    }
  }

  const hydrateEditReturnTo = () => {
    const savedTarget = sessionStorage.getItem(EDIT_RETURN_KEY)
    if (savedTarget === 'result' || savedTarget === 'my-trips') {
      editReturnTo.value = savedTarget
    }
    return editReturnTo.value
  }

  const setEditReturnTo = (target: EditReturnTarget) => {
    editReturnTo.value = target
    persistEditReturnTo(target)
  }

  const startEditing = (trip: TripPlanResponse, target: EditReturnTarget) => {
    setCurrentTrip(trip)
    setEditReturnTo(target)
  }

  hydrateCurrentTrip()
  hydrateTripsCache()
  hydrateEditReturnTo()

  return {
    currentTrip,
    tripsCache,
    editReturnTo,
    hasCurrentTrip,
    hydrateCurrentTrip,
    setCurrentTrip,
    hydrateTripsCache,
    setTripsCache,
    upsertTrip,
    removeTrip,
    hydrateEditReturnTo,
    setEditReturnTo,
    startEditing,
  }
})
