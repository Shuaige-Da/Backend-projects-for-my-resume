export const AQI_LEVELS = [
  { maximum: 50, label: "良好", className: "good", color: "#2f9b70" },
  { maximum: 100, label: "普通", className: "moderate", color: "#e0bd32" },
  { maximum: 150, label: "敏感提醒", className: "sensitive", color: "#ef9135" },
  { maximum: 200, label: "不健康", className: "unhealthy", color: "#d94d55" },
  { maximum: 300, label: "非常不健康", className: "very-unhealthy", color: "#8a5ca8" },
  { maximum: Number.POSITIVE_INFINITY, label: "危害", className: "hazardous", color: "#7b3442" },
];

export function aqiLevel(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return { label: "数据不足", className: "unknown", color: "#78909f" };
  }
  return AQI_LEVELS.find((level) => Number(value) <= level.maximum);
}

export function aqiStatusText(status) {
  return {
    GOOD: "良好",
    MODERATE: "普通",
    UNHEALTHY_FOR_SENSITIVE_GROUPS: "敏感族群不健康",
    UNHEALTHY: "所有族群不健康",
    VERY_UNHEALTHY: "非常不健康",
    HAZARDOUS: "危害",
  }[status] || status || "--";
}
