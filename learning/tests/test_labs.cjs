"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
require("../assets/labs.js");
const {asOf,splitRows,fit,validateProgress} = globalThis.CoachLearning;

test("future perturbations never change a historical feature", () => {
  const past = [{time:590,value:0},{time:598,value:1200}];
  const expected = {value:1200,age:2,missing:false,time:598};
  assert.deepEqual(asOf([...past,{time:606,value:1800}],600,10),expected);
  assert.deepEqual(asOf([{time:606,value:99999},...past],600,10),expected);
  assert.deepEqual(asOf(past,598,0),{value:1200,age:0,missing:false,time:598});
});

test("zero, absent observations and stale observations remain distinct", () => {
  assert.deepEqual(asOf([{time:590,value:0}],590,0),{value:0,age:0,missing:false,time:590});
  assert.deepEqual(asOf([],600,10),{value:null,age:null,missing:true,time:null});
  assert.deepEqual(asOf([{time:606,value:1800}],600,10),{value:null,age:null,missing:true,time:null});
  assert.deepEqual(asOf([{time:598,value:1200}],600,1),{value:null,age:2,missing:true,time:598});
});

test("grouping keeps every window of a match within one split", () => {
  const grouped = splitRows(true);
  assert.equal(grouped.length,6);
  assert.equal(grouped.flatMap(row=>row.windows).length,18);
  assert.ok(grouped.every(row=>new Set(row.windows).size===1));
  assert.deepEqual(grouped.map(row=>row.windows[0]),["train","train","train","train","validation","test"]);
  assert.equal(splitRows(false).filter(row=>new Set(row.windows).size>1).length,6);
});

test("training-only fit remains unchanged when holdout values change", () => {
  const train = [100,200,300];
  const stats = fit(train);
  assert.equal(stats.mean,200);
  assert.ok(Math.abs(stats.sd-Math.sqrt(20000/3))<1e-10);
  const transform = (value, fitted) => (value-fitted.mean)/fitted.sd;
  for(const holdout of [400,1000,2000]) {
    assert.deepEqual(fit(train),stats);
    assert.ok(Number.isFinite(transform(holdout,stats)));
    assert.notEqual(fit([...train,holdout]).mean,stats.mean);
  }
  assert.notEqual(fit([...train,400]).mean,fit([...train,2000]).mean);
});

const componentIds = new Set(["ingest","dataset"]);
const taskIds = new Set(["L01","L02"]);
const record = () => ({schema_version:"coach-personal-learning/1",learned_components:["ingest"],reviewed_tasks:["L01"],notes:{L01:"<script>plain note</script>"}});

test("personal records round-trip without gaining engineering state", () => {
  const source = record();
  source.learned_components.push("ingest");
  source.engineering_status = {W01:"done"};
  const validated = validateProgress(JSON.parse(JSON.stringify(source)),componentIds,taskIds);
  assert.deepEqual(validated.learned_components,["ingest"]);
  assert.equal(validated.notes.L01,"<script>plain note</script>");
  assert.equal(Object.hasOwn(validated,"engineering_status"),false);
  validated.notes.L01="changed";
  assert.notEqual(source.notes.L01,validated.notes.L01);
});

test("malformed and foreign personal records are rejected", () => {
  for(const mutate of [
    value=>value.schema_version="unknown",
    value=>value.learned_components=["unknown"],
    value=>value.reviewed_tasks=["W01"],
    value=>value.notes={unknown:"note"},
    value=>value.notes={L01:"a".repeat(4001)},
    value=>value.notes=[],
    value=>value.notes={L01:42}
  ]) {
    const value=record(); mutate(value);
    assert.throws(()=>validateProgress(value,componentIds,taskIds));
  }
  assert.throws(()=>validateProgress(null,componentIds,taskIds));
});
