"use strict";
// Pure teaching rules: shared by the offline UI and dependency-free Node tests.
globalThis.CoachLearning = (() => {
  function asOf(rows, cutoff, maxAge) {
    const past = rows.filter(row => row.time <= cutoff).sort((a,b) => b.time-a.time);
    const row = past[0];
    if (!row) return {value:null,age:null,missing:true,time:null};
    const age = cutoff - row.time;
    return {value:age <= maxAge ? row.value : null,age,missing:age > maxAge,time:row.time};
  }

  function splitRows(byMatch) {
    const splits = ["train","validation","test"];
    return Array.from({length:6},(_,index) => ({
      match:"M" + (index+1),
      windows:Array.from({length:3},(_,window) => byMatch
        ? (index<4 ? "train" : index===4 ? "validation" : "test")
        : splits[(index+window)%3])
    }));
  }

  function fit(values) {
    const mean = values.reduce((total,value) => total+value,0)/values.length;
    return {mean,sd:Math.sqrt(values.reduce((total,value) => total+(value-mean)**2,0)/values.length)};
  }

  function validateProgress(value, componentIds, taskIds) {
    if (!value || value.schema_version !== "coach-personal-learning/1"
        || !Array.isArray(value.learned_components) || !Array.isArray(value.reviewed_tasks)
        || !value.notes || typeof value.notes !== "object" || Array.isArray(value.notes)) {
      throw new Error("学习记录格式不正确，请导入本页面导出的 JSON。");
    }
    if (value.learned_components.some(id => typeof id !== "string" || !componentIds.has(id))
        || value.reviewed_tasks.some(id => typeof id !== "string" || !taskIds.has(id))) {
      throw new Error("记录中含有此版本未识别的组件或任务。");
    }
    for (const [id, note] of Object.entries(value.notes)) {
      if (!taskIds.has(id) || typeof note !== "string" || note.length > 4000) {
        throw new Error("笔记的任务 ID 或长度不符合要求。");
      }
    }
    return {schema_version:value.schema_version,
      learned_components:[...new Set(value.learned_components)],
      reviewed_tasks:[...new Set(value.reviewed_tasks)],
      notes:Object.fromEntries(Object.entries(value.notes))};
  }

  return {asOf,splitRows,fit,validateProgress};
})();
