const numberFormatter = new Intl.NumberFormat("zh-CN");
const compactFormatter = new Intl.NumberFormat("zh-CN", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatNumber(value) {
  return value === null || value === undefined ? "--" : numberFormatter.format(value);
}

export function formatCompact(value) {
  return value === null || value === undefined ? "--" : compactFormatter.format(value);
}

export function formatDateTime(value) {
  return value ? dateTimeFormatter.format(new Date(value)) : "--";
}

export function formatDuration(start, end) {
  if (!start || !end) return "--";
  const seconds = (new Date(end) - new Date(start)) / 1000;
  return `${seconds.toFixed(2)} 秒`;
}

export function statusText(status) {
  return {
    COMPLETED: "已完成",
    RUNNING: "运行中",
    FAILED: "失败",
    PENDING: "等待中",
  }[status] || status;
}
