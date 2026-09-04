import { APIProvider, AdvancedMarker, InfoWindow, Map, Pin, useMap } from '@vis.gl/react-google-maps'
import { useEffect, useMemo, useRef, useState } from 'react'

const COLORS = {
  pickup: '#16a34a',
  stop: '#f59e0b',
  dropoff: '#dc2626',
  volunteer: '#2563eb',
  donor: '#f59e0b',
  ngo: '#16a34a',
  admin: '#7c3aed',
}

const LEGENDS = {
  delivery: [
    ['bg-blue-600', 'Volunteer'],
    ['bg-brand-600', 'Pickup'],
    ['bg-amber-500', 'Delivery stop'],
    ['bg-red-600', 'Drop-off'],
  ],
  platform: [
    ['bg-amber-500', 'Donor'],
    ['bg-brand-600', 'NGO'],
    ['bg-blue-600', 'Volunteer'],
  ],
}

function FitBounds({ points, padding = 40, maxZoom = 15 }) {
  const map = useMap()
  const fittedSignature = useRef('')
  useEffect(() => {
    if (!map || !points.length || !window.google?.maps) return
    const signature = points.map((point) => `${point.lat.toFixed(5)},${point.lng.toFixed(5)}`).join('|')
    if (signature === fittedSignature.current) return
    fittedSignature.current = signature
    const bounds = new window.google.maps.LatLngBounds()
    points.forEach((point) => bounds.extend(point))
    map.fitBounds(bounds, padding)
    const listener = map.addListener('bounds_changed', () => {
      if (map.getZoom() > maxZoom) map.setZoom(maxZoom)
      listener.remove()
    })
  }, [map, points, padding, maxZoom])
  return null
}

function routePoints(route) {
  return (route || []).filter((point) => Array.isArray(point) && point.length >= 2)
    .map(([lat, lng]) => ({ lat: Number(lat), lng: Number(lng) }))
    .filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lng))
}

function RouteLine({ route, color = '#16a34a' }) {
  const map = useMap()
  const path = useMemo(() => routePoints(route), [route])
  useEffect(() => {
    if (!map || !path.length) return undefined
    const casing = new window.google.maps.Polyline({
      path,
      strokeColor: '#0f172a',
      strokeOpacity: 0.88,
      strokeWeight: 9,
      strokeLineCap: 'ROUND',
      strokeLineJoin: 'ROUND',
      zIndex: 10,
      map,
    })
    const polyline = new window.google.maps.Polyline({
      path,
      strokeColor: color,
      strokeOpacity: 1,
      strokeWeight: 5,
      strokeLineCap: 'ROUND',
      strokeLineJoin: 'ROUND',
      zIndex: 11,
      map,
    })
    return () => {
      casing.setMap(null)
      polyline.setMap(null)
    }
  }, [map, path, color])
  return null
}

export default function MapView({
  markers = [],
  route = null,
  routes = [],
  routeError = null,
  fitPadding = 40,
  maxFitZoom = 15,
  height = 380,
  center = { lat: 12.3052, lng: 76.6552 },
  zoom = 13,
  legendVariant = 'delivery',
}) {
  const [selectedMarker, setSelectedMarker] = useState(null)
  const points = useMemo(() => [...markers.filter((point) => !point.live), ...routePoints(route), ...routes.flatMap((item) => routePoints(item.route))]
    .filter((point) => Number.isFinite(Number(point.lat)) && Number.isFinite(Number(point.lng)))
    .map((point) => ({ lat: Number(point.lat), lng: Number(point.lng) })), [markers, route, routes])
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY

  if (!apiKey) return <div style={{ height }} className="flex items-center justify-center rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">Google Maps could not be loaded. Configure VITE_GOOGLE_MAPS_API_KEY.</div>
  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
      <div style={{ height }} className="overflow-hidden rounded-t-2xl">
        <APIProvider apiKey={apiKey} libraries={['places']}>
          <Map defaultCenter={center} defaultZoom={zoom} gestureHandling="greedy" mapId="foodbridge-operations" style={{ width: '100%', height: '100%' }}>
            <FitBounds points={points} padding={fitPadding} maxZoom={maxFitZoom} />
            {markers.map((marker, index) => {
              const position = { lat: Number(marker.lat), lng: Number(marker.lng) }
              if (!Number.isFinite(position.lat) || !Number.isFinite(position.lng)) return null
              return <AdvancedMarker key={marker.id || `${marker.type || 'marker'}-${index}`} position={position} onClick={() => setSelectedMarker({ marker, position })}>
                <Pin background={COLORS[marker.type] || COLORS.admin} borderColor="#ffffff" glyphColor="#ffffff" glyph={marker.glyph} />
              </AdvancedMarker>
            })}
            {selectedMarker && <InfoWindow position={selectedMarker.position} onCloseClick={() => setSelectedMarker(null)}><span className="text-sm font-medium text-gray-900">{selectedMarker.marker.popup || selectedMarker.marker.label || selectedMarker.marker.type}</span></InfoWindow>}
            <RouteLine route={route} />
            {routes.map((item) => <RouteLine key={item.id} route={item.route} color={item.color || '#16a34a'} />)}
          </Map>
        </APIProvider>
      </div>
      {legendVariant !== 'none' && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-gray-100 bg-white px-4 py-3 text-sm text-gray-600" aria-label="Map legend">
          {LEGENDS[legendVariant]?.map(([color, label]) => <span key={label} className="inline-flex items-center gap-2"><span className={`h-3 w-3 rounded-full ${color}`} aria-hidden="true" />{label}</span>)}
          <span className="inline-flex items-center gap-2"><span className="h-0.5 w-5 rounded-full bg-brand-600" aria-hidden="true" />Real Google route</span>
        </div>
      )}
      {routeError && <p className="bg-red-50 p-2 text-xs text-red-600">{routeError}</p>}
    </div>
  )
}