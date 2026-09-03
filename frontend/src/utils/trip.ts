import type { TripListItem, TripPlanResponse } from '@/types'

export function cloneTrip<T>(value: T): T {
  return JSON.parse(JSON.stringify(value))
}

export function sanitizeTripPlan(plan: TripPlanResponse): TripPlanResponse {
  const clonedPlan = cloneTrip(plan)

  clonedPlan.days.forEach((day) => {
    day.attractions.forEach((attraction) => {
      if (attraction.location) {
        attraction.location.lat = Number(attraction.location.lat)
        attraction.location.lng = Number(attraction.location.lng)
      }
    })

    day.dinings.forEach((dining) => {
      if (dining.location) {
        dining.location.lat = Number(dining.location.lat)
        dining.location.lng = Number(dining.location.lng)
      }
    })

    if (day.recommended_hotel?.location) {
      day.recommended_hotel.location.lat = Number(day.recommended_hotel.location.lat)
      day.recommended_hotel.location.lng = Number(day.recommended_hotel.location.lng)
    }
  })

  clonedPlan.hotels.forEach((hotel) => {
    if (hotel.location) {
      hotel.location.lat = Number(hotel.location.lat)
      hotel.location.lng = Number(hotel.location.lng)
    }
  })

  return clonedPlan
}

export function normalizeTrip(trip: TripPlanResponse): TripListItem {
  const sanitizedTrip = sanitizeTripPlan(trip)

  return {
    ...sanitizedTrip,
    id: sanitizedTrip.id || Date.now().toString(),
    created_at: sanitizedTrip.created_at || new Date().toISOString(),
  }
}
