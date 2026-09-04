import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { APIProvider, AdvancedMarker, Map, Pin } from '@vis.gl/react-google-maps'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner } from '../../components/UI'
import { UploadCloud, LocateFixed } from 'lucide-react'

const DEFAULT_LOCATION = {
  lat: 12.3052,
  lng: 76.6552,
}

function PickupMap({ position, setPosition }) {
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
  if (!apiKey) return <div className="flex h-full items-center justify-center bg-red-50 p-4 text-sm text-red-700">Google Maps could not be loaded. Configure VITE_GOOGLE_MAPS_API_KEY.</div>
  return (
    <APIProvider apiKey={apiKey}>
      <Map defaultCenter={DEFAULT_LOCATION} defaultZoom={15} gestureHandling="greedy" mapId="foodbridge-pickup" onClick={(event) => event.detail.latLng && setPosition(event.detail.latLng.toJSON())} style={{ width: '100%', height: '100%' }}>
        {position && <AdvancedMarker position={position}><Pin background="#16a34a" borderColor="#ffffff" glyphColor="#ffffff" glyph="P" /></AdvancedMarker>}
      </Map>
    </APIProvider>
  )
}

export default function NewDonation() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)

  const [position, setPosition] = useState(null)

  const [locationLoading, setLocationLoading] = useState(true)
  const [locationError, setLocationError] = useState('')
  const [geocodeLoading, setGeocodeLoading] = useState(false)

  const [form, setForm] = useState({
    food_type: 'rice',
    quantity_plates: 30,
    pickup_address: '',
    hours_since_cooked: 1.0,
    ambient_temp_c: 30,
    has_cold_storage: false,
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [riskEstimate, setRiskEstimate] = useState(null)
  const [riskLoading, setRiskLoading] = useState(false)
  const [riskError, setRiskError] = useState('')
  const locationRequestRef = useRef(0)

  const navigate = useNavigate()

  const update = (key, value) => {
    setForm((f) => ({
      ...f,
      [key]: value,
    }))
  }

  const resolvePickupAddress = async () => {
    if (form.pickup_address.trim().length < 3) return
    if (!window.google?.maps?.Geocoder) {
      setLocationError('Google location search is still loading. Please try again.')
      return
    }
    setGeocodeLoading(true)
    setLocationError('')
    try {
      const geocoder = new window.google.maps.Geocoder()
      const response = await geocoder.geocode({ address: form.pickup_address })
      const result = response.results?.[0]
      if (!result) throw new Error('Location could not be found.')
      const location = result.geometry.location.toJSON()
      setPosition(location)
      update('pickup_address', result.formatted_address)
    } catch (error) {
      setLocationError(error.message)
    } finally {
      setGeocodeLoading(false)
    }
  }

  const onFile = (f) => {
    if (!f) return

    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  useEffect(() => {
    const request = {
      food_type: form.food_type,
      hours_since_cooked: form.hours_since_cooked,
      ambient_temp_c: form.ambient_temp_c,
      has_cold_storage: form.has_cold_storage,
      quantity_plates: form.quantity_plates,
    }

    if (!Number.isFinite(request.hours_since_cooked)
      || !Number.isFinite(request.ambient_temp_c)
      || !Number.isFinite(request.quantity_plates)
      || request.quantity_plates < 1) {
      setRiskEstimate(null)
      setRiskError('Enter valid food details to estimate risk.')
      return undefined
    }

    let active = true
    setRiskLoading(true)
    setRiskError('')
    api.estimateRisk(request)
      .then((estimate) => {
        if (active) setRiskEstimate(estimate)
      })
      .catch((err) => {
        if (active) {
          setRiskEstimate(null)
          setRiskError(err.message)
        }
      })
      .finally(() => {
        if (active) setRiskLoading(false)
      })

    return () => {
      active = false
    }
  }, [form.food_type, form.hours_since_cooked, form.ambient_temp_c, form.has_cold_storage, form.quantity_plates])

  const getCurrentLocation = () => {
    if (!navigator.geolocation) {
      setLocationError(
        'Geolocation is not supported by this browser.'
      )
      setLocationLoading(false)
      return
    }

    const requestId = locationRequestRef.current + 1
    locationRequestRef.current = requestId
    setLocationLoading(true)
    setLocationError('')

    navigator.geolocation.getCurrentPosition(
      (location) => {
        if (locationRequestRef.current !== requestId) return
        setPosition({
          lat: location.coords.latitude,
          lng: location.coords.longitude,
        })
        setLocationLoading(false)
      },
      (err) => {
        if (locationRequestRef.current !== requestId) return
        if (err.code === 1) {
          setLocationError(
            'Location permission denied. Please allow location access in Chrome.'
          )
        } else if (err.code === 2) {
          setLocationError(
            'Unable to determine your current location.'
          )
        } else if (err.code === 3) {
          setLocationError(
            'Location request timed out. Please try again.'
          )
        } else {
          setLocationError(
            'Unable to get your current location.'
          )
        }

        setLocationLoading(false)
      },
      {
        enableHighAccuracy: true,
        timeout: 8000,
        maximumAge: 300000,
      }
    )
  }

  useEffect(() => {
    getCurrentLocation()
    return () => {
      locationRequestRef.current += 1
    }
  }, [])

  const submit = async (e) => {
    e.preventDefault()

    if (!file) {
      setError('Please attach a photo of the food.')
      return
    }

    if (!position) {
      setError('Please select a pickup location.')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const fd = new FormData()

      fd.append('file', file)
      fd.append('food_type', form.food_type)
      fd.append(
        'quantity_plates',
        form.quantity_plates
      )

      fd.append(
        'pickup_lat',
        position.lat
      )

      fd.append(
        'pickup_lng',
        position.lng
      )

      fd.append(
        'pickup_address',
        form.pickup_address
      )

      fd.append(
        'hours_since_cooked',
        form.hours_since_cooked
      )

      fd.append(
        'ambient_temp_c',
        form.ambient_temp_c
      )

      fd.append(
        'has_cold_storage',
        form.has_cold_storage
      )

      const res = await api.createDonation(fd)

      setResult(res)

      if (res.status !== 'rejected_quality') {
        setTimeout(() => {
          navigate('/donor')
        }, 2500)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
      <div>
        <PageHeader
          title="New Donation"
          subtitle="Upload a photo — the platform checks quality, predicts spoilage time, and finds the best NGO automatically."
        />

        <ErrorBanner message={error} />

        {result && (
          <div
            className={`card mb-6 ${result.status === 'rejected_quality'
              ? 'bg-red-50'
              : 'bg-brand-50'
              }`}
          >
            <p className="font-semibold text-gray-900">
              {result.quality_label}
            </p>

            <p className="text-sm text-gray-600 mt-1">
              Status:{' '}
              <span className="font-medium">
                {result.status}
              </span>
            </p>

            {result.degradation_hours != null && (
              <p className="text-sm text-gray-600">
                Predicted safe window:{' '}
                {result.degradation_hours} hours
              </p>
            )}

            {result.match_reason && (
              <p className="text-sm text-gray-600 mt-1 italic">
                "{result.match_reason}"
              </p>
            )}

            {result.match_explanation?.length > 0 && (
              <div className="mt-3">
                <p className="text-sm font-medium text-gray-800">Why this NGO?</p>
                <ul className="list-disc pl-5 text-sm text-gray-600 mt-1">
                  {result.match_explanation.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
            )}

            {result.status !== 'rejected_quality' && (
              <p className="text-xs text-gray-400 mt-2">
                Redirecting to your donations…
              </p>
            )}
          </div>
        )}

        <div className="card mb-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-semibold text-gray-900">Estimated spoilage risk</p>
              <p className="text-xs text-gray-500 mt-1">Decision support only, not laboratory food-safety certification.</p>
            </div>
            {riskLoading && <span className="text-sm text-gray-500">Estimating…</span>}
          </div>

          {riskError && <p className="text-sm text-red-700 mt-3">{riskError}</p>}
          {riskEstimate && !riskLoading && (
            <div className="mt-3 space-y-2">
              <p className="text-lg font-semibold text-gray-900">
                Risk: <span className={riskEstimate.risk_level === 'High' ? 'text-red-700' : riskEstimate.risk_level === 'Medium' ? 'text-yellow-700' : 'text-green-700'}>{riskEstimate.risk_level}</span>
                <span className="text-sm font-normal text-gray-500"> · Score: {riskEstimate.risk_score}/100</span>
              </p>
              <ul className="list-disc pl-5 text-sm text-gray-600">
                {riskEstimate.reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
              <p className="text-sm text-gray-700"><span className="font-medium">Recommendation:</span> {riskEstimate.recommendation}</p>
            </div>
          )}
        </div>

        <form
          onSubmit={submit}
          className="grid grid-cols-1 lg:grid-cols-2 gap-6"
        >
          {/* LEFT SIDE */}
          <div className="card space-y-4">

            <label
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                onFile(e.dataTransfer.files[0])
              }}
              className="border-2 border-dashed border-gray-200 rounded-xl h-40 flex flex-col items-center justify-center gap-2 cursor-pointer hover:border-brand-400 overflow-hidden"
            >
              {preview ? (
                <img
                  src={preview}
                  className="h-full w-full object-cover rounded-xl"
                  alt="Food preview"
                />
              ) : (
                <>
                  <UploadCloud
                    className="text-gray-400"
                    size={24}
                  />

                  <p className="text-sm text-gray-500">
                    Click or drag a food photo
                  </p>
                </>
              )}

              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) =>
                  onFile(e.target.files[0])
                }
              />
            </label>

            <div>
              <label className="label">
                Food type
              </label>

              <select
                className="input-field"
                value={form.food_type}
                onChange={(e) =>
                  update(
                    'food_type',
                    e.target.value
                  )
                }
              >
                <option value="rice">
                  Rice / Biryani
                </option>

                <option value="curry">
                  Curry / Gravy
                </option>

                <option value="bread">
                  Bread / Baked
                </option>

                <option value="dairy">
                  Dairy-based
                </option>

                <option value="snacks">
                  Snacks / Fried
                </option>

                <option value="mixed">
                  Mixed
                </option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">

              <div>
                <label className="label">
                  Quantity (plates)
                </label>

                <input
                  type="number"
                  className="input-field"
                  value={form.quantity_plates}
                  onChange={(e) =>
                    update(
                      'quantity_plates',
                      parseInt(e.target.value)
                    )
                  }
                />
              </div>

              <div>
                <label className="label">
                  Hours since cooked
                </label>

                <input
                  type="number"
                  step="0.5"
                  className="input-field"
                  value={form.hours_since_cooked}
                  onChange={(e) =>
                    update(
                      'hours_since_cooked',
                      parseFloat(e.target.value)
                    )
                  }
                />
              </div>

              <div>
                <label className="label">
                  Ambient temp (°C)
                </label>

                <input
                  type="number"
                  className="input-field"
                  value={form.ambient_temp_c}
                  onChange={(e) =>
                    update(
                      'ambient_temp_c',
                      parseFloat(e.target.value)
                    )
                  }
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-gray-600 self-end pb-2">

                <input
                  type="checkbox"
                  checked={form.has_cold_storage}
                  onChange={(e) =>
                    update(
                      'has_cold_storage',
                      e.target.checked
                    )
                  }
                />

                Cold storage available
              </label>
            </div>

            <div>
              <label className="label">
                Pickup address (optional label)
              </label>

              <input
                className="input-field"
                value={form.pickup_address}
                onChange={(e) =>
                  update(
                    'pickup_address',
                    e.target.value
                  )
                }
                onBlur={resolvePickupAddress}
                placeholder="e.g. Wedding Hall, JLB Road"
              />
              {geocodeLoading && <p className="mt-1 text-xs text-gray-500">Resolving pickup location…</p>}
            </div>

            <button
              className="btn-primary w-full"
              disabled={loading}
            >
              {loading
                ? 'Processing (quality → matching → routing)…'
                : 'Submit donation'}
            </button>
          </div>

          {/* PICKUP MAP */}
          <div className="card">

            <div className="flex items-center justify-between mb-2">

              <p className="label mb-0">
                Pickup location
              </p>

              <button
                type="button"
                onClick={getCurrentLocation}
                className="flex items-center gap-2 text-sm px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50"
              >
                <LocateFixed size={16} />

                {locationLoading
                  ? 'Locating…'
                  : 'Use my location'}
              </button>
            </div>

            {locationError && (
              <div className="mb-3 rounded-lg bg-yellow-50 border border-yellow-200 p-3 text-sm text-yellow-700">
                {locationError}
              </div>
            )}

            <p className="text-xs text-gray-500 mb-2">
              Your device location is selected automatically.
              You can click anywhere on the map to change the
              pickup location.
            </p>

            <div
              className="rounded-xl overflow-hidden"
              style={{ height: '320px' }}
            >
              <PickupMap
                position={position}
                setPosition={setPosition}
              />
            </div>

            <div className="mt-3 p-3 bg-gray-50 rounded-lg">

              <p className="text-xs text-gray-500">
                Selected pickup coordinates
              </p>

              <p className="text-sm font-medium text-gray-700">
                Latitude: {position ? position.lat.toFixed(6) : 'Location unavailable'}
              </p>

              <p className="text-sm font-medium text-gray-700">
                Longitude: {position ? position.lng.toFixed(6) : 'Location unavailable'}
              </p>
            </div>

          </div>
        </form>
      </div>
  )
}