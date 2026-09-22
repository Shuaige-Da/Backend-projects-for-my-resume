const PARAMETER_DESCRIPTIONS = {
  start: "分析开始时间，包含该时刻",
  end: "分析结束时间，不包含该时刻",
  county: "县市名称，例如“新北市”",
  station_id: "监测站数据库编号",
  interval: "时间聚合粒度",
  limit: "本次最多返回的记录数",
  offset: "分页偏移量",
  cursor: "游标分页起点",
  status: "任务状态筛选条件",
  name: "监测站名称模糊查询",
};

const TYPE_LABELS = {
  string: "字符串",
  integer: "整数",
  number: "数值",
  boolean: "布尔值",
  array: "数组",
};

export function groupOpenApi(document) {
  if (!document) return [];
  const groups = new Map();
  Object.entries(document.paths || {}).forEach(([path, methods]) => {
    Object.entries(methods).forEach(([method, operation]) => {
      if (!operation || typeof operation !== "object" || !operation.responses) return;
      const tag = operation.tags?.[0] || "其他";
      const item = { id: `${method}-${path}`, method: method.toUpperCase(), path, tag, ...operation };
      if (!groups.has(tag)) groups.set(tag, []);
      groups.get(tag).push(item);
    });
  });
  return [...groups.entries()].map(([tag, operations]) => ({ tag, operations }));
}

export function parameterType(parameter) {
  const schema = parameter.schema || {};
  const candidate = schema.type ? schema : schema.anyOf?.find((item) => item.type !== "null") || {};
  if (candidate.format === "date-time") return "日期时间";
  return TYPE_LABELS[candidate.type] || candidate.type || "--";
}

export function parameterDescription(parameter) {
  return parameter.description || PARAMETER_DESCRIPTIONS[parameter.name] || "接口查询参数";
}

export function responseSchema(operation) {
  const schema = operation.responses?.["200"]?.content?.["application/json"]?.schema;
  return JSON.stringify(schema || { message: "该接口成功返回数据" }, null, 2);
}
