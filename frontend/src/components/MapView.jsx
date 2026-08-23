import {
  APIProvider,
  Map,
  AdvancedMarker,
  InfoWindow,
  useMap,
} from '@vis.gl/react-google-maps'

import { useEffect, useState } from 'react'

const iconFor = (color) => ({
  background: color,
  width: '16px',
  height: '16px',
  borderRadius: '50%',
  border: '2px solid white',
  boxShadow: '0 1px 4px rgba(0,0,0,0.4)',
})

export const ICONS = {
  donor: iconFor('#f59e0b'),
  ngo: iconFor('#16a34a'),
  volunteer: iconFor('#2563eb'),
  admin: iconFor('#7c3aed'),
}

function FitBounds({ points }) {
  const map = useMap()

  useEffect(() => {
    if (!map || !points || points.length === 0) return

    const bounds = new google.maps.LatLngBounds()

    points.forEach((p) => {
      bounds.extend({
        lat: p.lat,
        lng: p.lng,
      })
    })

    map.fitBounds(bounds, 40)
  }, [map, points])

  return null
}

function RouteLine({ route }) {
  const map = useMap()

  useEffect(() => {
    if (!map || !route || route.length < 2) return

    const polyline = new google.maps.Polyline({
      path: route.map(([lat, lng]) => ({
        lat,
        lng,
      })),
      geodesic: true,
      strokeColor: '#16a34a',
      strokeOpacity: 0.7,
      strokeWeight: 4,
      map,
    })

    return () => {
      polyline.setMap(null)
    }
  }, [map, route])

  return null
}

export default function MapView({
  markers = [],
  route = null,
  height = 380,
  center = { lat: 12.3052, lng: 76.6552 },
  zoom = 13,
}) {
  const [selectedMarker, setSelectedMarker] = useState(null)

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY

  if (!apiKey) {
    return (
      <div className="p-4 text-red-600">
        Google Maps API key is missing.
      </div>
    )
  }

  return (
    <div
      style={{ height }}
      className="rounded-xl overflow-hidden border border-gray-100"
    >
      <APIProvider apiKey={apiKey}>
        <Map
          defaultCenter={center}
          defaultZoom={zoom}
          mapId="FOODBRIDGE_MAP"
          gestureHandling="greedy"
          disableDefaultUI={false}
        >
          <FitBounds points={markers} />

          {markers.map((m, i) => (
            <AdvancedMarker
              key={i}
              position={{
                lat: m.lat,
                lng: m.lng,
              }}
              onClick={() => setSelectedMarker(m)}
            >
              <div style={ICONS[m.type] || ICONS.admin} />
            </AdvancedMarker>
          ))}

          {selectedMarker && (
            <InfoWindow
              position={{
                lat: selectedMarker.lat,
                lng: selectedMarker.lng,
              }}
              onCloseClick={() => setSelectedMarker(null)}
            >
              <div>
                {selectedMarker.popup ||
                  selectedMarker.label ||
                  selectedMarker.type}
              </div>
            </InfoWindow>
          )}

          {route && route.length > 1 && (
            <RouteLine route={route} />
          )}
        </Map>
      </APIProvider>
    </div>
  )
}