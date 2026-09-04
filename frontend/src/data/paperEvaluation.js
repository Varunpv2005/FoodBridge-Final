// Values reported in the FoodBridge paper's simulation/pilot-oriented evaluation setup.
// These are presentation evidence, not live production measurements.
export const PAPER_EVALUATION = {
  context: [
    '12 months of historical regional data',
    '80/20 time-aware train/test split for demand prediction',
    'Routing evaluation: 5-20 stop routes',
    'Expiry windows: 30-120 minutes',
    'Evaluation includes matching, delivery time, spoilage risk, volunteer utilization, and demand forecasting',
  ],
  optimization: [
    { key: 'matching', label: 'Matching Accuracy', before: 58.3, after: 91.7, unit: '%', direction: 'higher' },
    { key: 'delivery', label: 'Average Delivery Time', before: 78, after: 42, unit: ' min', direction: 'lower' },
    { key: 'risk', label: 'Spoilage Risk Score', before: 0.72, after: 0.28, unit: '', direction: 'lower' },
    { key: 'utilization', label: 'Volunteer Utilization', before: 45, after: 82, unit: '%', direction: 'higher' },
    { key: 'forecast', label: 'Demand Forecast RMSE', before: 18.4, after: 7.2, unit: '%', direction: 'lower' },
  ],
  comparison: [
    { label: 'Matching Accuracy', unit: '%', manual: 52.1, ruleBased: 68.4, foodbridge: 91.7 },
    { label: 'Avg Delivery Time', unit: ' min', manual: 95, ruleBased: 71, foodbridge: 42 },
    { label: 'Demand Forecast RMSE', unit: '%', manual: null, ruleBased: null, foodbridge: 7.2 },
    { label: 'Spoilage Incidents', unit: '%', manual: 23.5, ruleBased: 15.2, foodbridge: 6.8 },
  ],
}

export function improvement(metric) {
  if (metric.direction === 'higher') return `+${(metric.after - metric.before).toFixed(1)} percentage points`
  return `${(((metric.before - metric.after) / metric.before) * 100).toFixed(1)}% reduction`
}

export function displayMetric(value, unit = '') {
  return value == null ? 'N/A' : `${value}${unit}`
}
