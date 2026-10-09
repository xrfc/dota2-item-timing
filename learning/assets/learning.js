"use strict";
(() => {
  const data = JSON.parse(document.getElementById("learning-data").textContent);
  const taskById = Object.fromEntries(data.tasks.map(task => [task.id, task]));
  const learningTasks = data.tasks.filter(task => /^L\d{2}$/.test(task.id));
  const componentIds = new Set(data.components.map(component => component.id));
  const taskIds = new Set(learningTasks.map(task => task.id));
  const storageKey = "dota-coach-learning:v1";
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
  const statusNames = {pending:"待做",in_progress:"进行中",partial:"部分完成",done:"已验收",blocked:"阻塞"};
  const componentNames = {ready:"已实现",partial:"部分完成",planned:"待实现",blocked:"阻塞"};
  const repository = "https://github.com/xrfc/dota2-item-timing/blob/feat/coach-workflow-infrastructure/";
  const blankProgress = () => ({schema_version:"coach-personal-learning/1",learned_components:[],reviewed_tasks:[],notes:{}});
  let personal = blankProgress();
  let persistent = true;
  let view = "architecture";
  let selectedComponent = data.components[0].id;
  let selectedTask = learningTasks[0]?.id;
  let selectedStage = null;
  let taskFilter = "all";
  let choiceFocus = null;
  let grouped = true;
  let trainOnly = true;
  let toastTimer;

  const {asOf,splitRows,fit} = globalThis.CoachLearning;
  const validateProgress = value => globalThis.CoachLearning.validateProgress(value,componentIds,taskIds);

  try {
    const stored = localStorage.getItem(storageKey);
    if (stored) personal = validateProgress(JSON.parse(stored));
  } catch (_) {
    persistent = false;
  }

  function toast(message) {
    const node = $("#toast");
    node.textContent = message;
    node.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.hidden = true; }, 4000);
  }

  function savePersonal() {
    try { localStorage.setItem(storageKey, JSON.stringify(personal)); }
    catch (_) { persistent = false; }
    updatePersonal();
  }

  function updatePersonal() {
    $("#personal-count").textContent = personal.learned_components.length + " / " + componentIds.size;
    $("#personal-meter").style.width = (personal.learned_components.length / componentIds.size * 100) + "%";
    $("#storage-status").textContent = persistent
      ? "学习记录保存在此浏览器，可导出迁移"
      : "本次会话记录 · 请导出保存";
  }

  const matches = (...parts) => parts.join(" ").toLowerCase().includes($("#search").value.trim().toLowerCase());
  const dependenciesDone = task => task.dependencies.every(id => taskById[id].status === "done");
  const statusTag = (status, label) => '<span class="status-tag ' + esc(status) + '">' + esc(label) + "</span>";
  const chips = ids => ids.map(id => '<button class="chip" data-task="' + esc(id) + '">' + esc(id) + "</button>").join("");
  const sourceLinks = paths => paths.map(path => '<a target="_blank" rel="noopener noreferrer" href="'
    + repository + path.split("/").map(encodeURIComponent).join("/") + '">' + esc(path) + " ↗</a>").join("");

  function setView(next, clearSearch = false) {
    if (!["architecture","path","choices","lab"].includes(next)) next = "architecture";
    view = next;
    if (clearSearch) $("#search").value = "";
    document.querySelectorAll(".view").forEach(section => { section.hidden = section.id !== view + "-view"; });
    document.querySelectorAll(".nav-item").forEach(button => {
      const active = button.dataset.view === view;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current","page");
      else button.removeAttribute("aria-current");
    });
    $("#view-label").textContent = {architecture:"组件地图",path:"学习路线",choices:"技术选型",lab:"交互实验"}[view];
    if (location.hash !== "#" + view) {
      try { history.replaceState(null, "", "#" + view); }
      catch (_) { location.hash = view; }
    }
    render();
  }

  function renderArchitecture() {
    $("#component-map").innerHTML = data.components.map((component, index) => {
      const state = component.state;
      const label = state === "ready" ? (component.ready_label || componentNames[state]) : componentNames[state];
      const reverse = index >= 5;
      const column = reverse ? 10 - index : index + 1;
      const dim = !matches(component.title,component.purpose,component.technology.join(" "),component.files.join(" "));
      return '<button class="component-node ' + (selectedComponent === component.id ? "selected " : "")
        + (state === "planned" ? "planned-node " : "") + (reverse ? "reverse " : "") + (dim ? "dim" : "")
        + '" data-component="' + esc(component.id) + '" style="grid-column:' + column + ";grid-row:" + (reverse ? 2 : 1)
        + '" aria-pressed="' + (selectedComponent === component.id) + '"><span class="node-index">'
        + String(index + 1).padStart(2,"0") + '</span><strong>' + esc(component.title) + "</strong><small>"
        + esc(component.subtitle) + '</small><span class="node-state"><i class="' + state + '"></i>'
        + esc(label) + "</span>" + (index !== 4 && index !== 9 ? '<span class="map-arrow" aria-hidden="true">'
        + (reverse ? "←" : "→") + "</span>" : "") + "</button>";
    }).join("") + '<span class="map-turn" aria-hidden="true"></span>';
    const component = data.components.find(item => item.id === selectedComponent);
    const label = component.state === "ready" ? component.ready_label || "已实现" : componentNames[component.state];
    $("#component-detail").innerHTML =
      '<div class="detail-eyebrow"><span>COMPONENT / ' + esc(component.subtitle) + "</span>"
      + statusTag(component.state,label) + "</div><h3>" + esc(component.title) + "</h3><p>" + esc(component.purpose)
      + '</p><div class="io-grid"><div><b>INPUT</b><span>' + esc(component.input)
      + "</span></div><div><b>OUTPUT</b><span>" + esc(component.output) + "</span></div></div>"
      + '<div class="detail-title">为什么这样实现</div><p>' + esc(component.reason) + "</p>"
      + '<div class="detail-title">连接已有知识</div><p>' + esc(component.analogy) + "</p>"
      + '<div class="chip-row">' + component.technology.map(id => '<button class="chip" data-choice="' + id + '">'
        + esc(data.choices.find(choice => choice.id === id).title) + " ↗</button>").join("") + "</div>"
      + '<div class="limit-box"><div class="detail-title">当前边界</div><p>' + esc(component.limits) + "</p></div>"
      + '<div class="question-box"><span>CHECK YOUR UNDERSTANDING</span>' + esc(component.question) + "</div>"
      + '<div class="detail-title">关联学习任务</div><div class="chip-row">' + chips(component.learning) + "</div>"
      + '<div class="source-links">' + sourceLinks(component.files) + "</div>"
      + '<label class="learn-check"><input type="checkbox" id="learn-component" '
        + (personal.learned_components.includes(component.id) ? "checked" : "") + '>我已能解释这个组件（个人记录）</label>';
  }

  function renderPath() {
    $("#stages").innerHTML = data.stages.map((stage,index) => {
      const done = stage.tasks.filter(id => taskById[id]?.status === "done").length;
      return '<button class="stage-card ' + (selectedStage === stage.id ? "selected" : "") + '" data-stage="'
        + esc(stage.id) + '" aria-pressed="' + (selectedStage === stage.id) + '"><small>ITERATION '
        + String(index+1).padStart(2,"0") + "</small><strong>" + esc(stage.title) + "</strong><span>"
        + done + " / " + stage.tasks.length + ' 已验收</span><div class="stage-progress"><i style="width:'
        + (done / stage.tasks.length * 100) + '%"></i></div></button>';
    }).join("");
    document.querySelectorAll("[data-filter]").forEach(button => button.classList.toggle("selected", button.dataset.filter === taskFilter));
    const stageIds = selectedStage ? data.stages.find(stage => stage.id === selectedStage).tasks : null;
    const filtered = learningTasks.filter(task => (!stageIds || stageIds.includes(task.id))
      && matches(task.id, task.title, task.description, task.acceptance)
      && (taskFilter !== "done" || task.status === "done")
      && (taskFilter !== "ready" || (dependenciesDone(task) && !["done","blocked"].includes(task.status))));
    $("#task-filter-count").textContent = filtered.length + " 项任务 · 已复盘 " + personal.reviewed_tasks.length + " 项";
    $("#task-list").innerHTML = filtered.length ? filtered.map(task =>
      '<button class="task-card ' + (selectedTask === task.id ? "selected" : "") + '" data-task="' + esc(task.id)
      + '"><span class="task-id">' + esc(task.id) + '</span><span class="task-body"><strong>' + esc(task.title)
      + "</strong><small>" + (task.dependencies.length ? "验收依赖 " + esc(task.dependencies.join(" / ")) : "可以从这里开始")
      + "</small></span>" + statusTag(task.status,task.source_status) + "</button>"
    ).join("") : '<div class="empty-state">当前条件下没有任务。切换阶段、筛选条件或清空搜索。</div>';
    const task = taskById[selectedTask];
    if (!task) return;
    const related = data.components.filter(component => component.learning.includes(task.id));
    $("#task-detail").innerHTML =
      '<div class="detail-eyebrow"><span>LEARNING TASK / ' + esc(task.id) + "</span>" + statusTag(task.status,task.source_status)
      + "</div><h3>" + esc(task.title) + "</h3><p>" + esc(task.description) + "</p>"
      + '<div class="detail-title">实践依赖 · 来自 learning ToDo</div><div class="chip-row">'
      + (task.dependencies.length ? chips(task.dependencies) : '<span class="subtle-label">无前置任务</span>') + "</div>"
      + '<p>' + (dependenciesDone(task) ? "正式验收依赖已满足。" : "先完成关联依赖；可阅读并设计接口，完成需提供实际证据。") + "</p>"
      + '<div class="detail-title">要留下什么证据</div><ul class="acceptance-list">'
      + task.acceptance.split("；").filter(Boolean).map(item => "<li>" + esc(item) + "</li>").join("") + "</ul>"
      + '<div class="detail-title">回到组件</div><div class="chip-row">' + related.map(component =>
        '<button class="chip" data-component="' + component.id + '">' + esc(component.title) + "</button>").join("") + "</div>"
      + '<div class="detail-title">学习笔记</div><textarea id="task-note" class="note-field" maxlength="4000" placeholder="用自己的话说明：为什么采用这条规则？哪个例子可能让它失效？">'
      + esc(personal.notes[task.id] || "") + "</textarea>"
      + '<label class="learn-check"><input id="review-task" type="checkbox" ' + (personal.reviewed_tasks.includes(task.id) ? "checked" : "")
      + '>我已阅读并复盘这项任务（不会修改项目状态）</label>'
      + '<div class="source-links">' + sourceLinks(["learning/docs/roadmap.md","learning/templates/task-record.md","learning/templates/data-audit.md"]) + "</div>";
  }

  function renderChoices() {
    const choices = data.choices.filter(choice => matches(choice.title,choice.summary,choice.why,choice.cost,choice.lesson));
    $("#choice-grid").innerHTML = choices.length ? choices.map((choice,index) =>
      '<article class="choice-card ' + (choice.id === choiceFocus ? "highlight" : "") + '" id="choice-' + choice.id
      + '"><div class="choice-meta"><span>DECISION ' + String(index+1).padStart(2,"0") + "</span><span>"
      + esc(choice.tag) + "</span></div><h3>" + esc(choice.title) + '</h3><div class="choice-summary">'
      + esc(choice.summary) + "</div><dl><dt>采用原因</dt><dd>" + esc(choice.why)
      + "</dd><dt>付出的成本</dt><dd>" + esc(choice.cost) + "</dd><dt>替代方向</dt><dd>"
      + esc(choice.alternative) + "</dd><dt>什么时候重新选择</dt><dd>" + esc(choice.trigger)
      + '</dd></dl><div class="choice-lesson">' + esc(choice.lesson) + "</div></article>"
    ).join("") : '<div class="empty-state">没有匹配的技术选型，试试其他关键词。</div>';
  }

  function renderLab() {
    const cutoff = Number($("#cutoff").value);
    const maxAge = Number($("#max-age").value);
    const gold = $("#missing-gold").checked ? [] : [{time:590,value:0},{time:598,value:1200},{time:606,value:1800}];
    const positions = [{time:596,value:"(-3200, -4100)"},{time:599,value:"(-3150, -4050)"},{time:602,value:"(-3000, -3900)"}];
    $("#cutoff-label").textContent = cutoff + " 秒";
    $("#age-label").textContent = maxAge + " 秒";
    const x = time => 95+(time-580)/40*630;
    const point = (row,y,color,result) => {
      const future = row.time > cutoff;
      const selected = !result.missing && row.time === result.time;
      return '<circle cx="' + x(row.time) + '" cy="' + y + '" r="' + (selected?7:5) + '" fill="'
        + (future?"#d9dfd7":color) + '" stroke="' + (selected?"#31573b":"#fff") + '" stroke-width="'
        + (selected?2:1) + '"/><text x="' + x(row.time) + '" y="' + (y-13)
        + '" text-anchor="middle" fill="' + (future?"#a0aaa0":"#64765c") + '" font-size="10">' + row.time + "</text>";
    };
    const results = [asOf(gold,cutoff,maxAge),asOf(positions,cutoff,maxAge)];
    $("#timeline").innerHTML = '<svg viewBox="0 0 800 155" role="img" aria-label="金币和位置观测时间轴，绿色背景为截止时刻之前">'
      + '<rect x="95" y="25" width="' + (x(cutoff)-95) + '" height="106" fill="#edf4e8" rx="4"/>'
      + '<text x="17" y="63" fill="#6b7c63" font-size="11">金币</text><text x="17" y="113" fill="#6b7c63" font-size="11">位置</text>'
      + '<line x1="95" y1="60" x2="725" y2="60" stroke="#d9e3d1"/><line x1="95" y1="110" x2="725" y2="110" stroke="#d9e3d1"/>'
      + gold.map(row => point(row,60,"#6d925d",results[0])).join("")
      + positions.map(row => point(row,110,"#7894ae",results[1])).join("")
      + '<line x1="' + x(cutoff) + '" y1="16" x2="' + x(cutoff) + '" y2="139" stroke="#416940" stroke-dasharray="4 3"/>'
      + '<text x="' + Math.min(x(cutoff)+7,660) + '" y="13" fill="#416940" font-size="10">cutoff ' + cutoff + "</text>"
      + '<text x="95" y="151" fill="#a0ac97" font-size="9">580 秒</text><text x="725" y="151" text-anchor="end" fill="#a0ac97" font-size="9">620 秒</text></svg>';
    $("#asof-results").innerHTML = results.map((result,index) =>
      '<div class="asof-result ' + (result.missing?"missing":"") + '"><strong>' + (index?"位置":"金币") + "："
      + esc(result.missing ? "缺失" : result.value) + "</strong><span>"
      + (result.time===null?"没有历史观测":"最近历史观测 "+result.time+" 秒 · age "+result.age+" 秒")
      + '</span><code>missing_mask = ' + Number(result.missing) + (result.missing?" · 不能把缺失当成真实零值":"") + "</code></div>"
    ).join("");
    const rows = splitRows(grouped);
    const leakage = rows.filter(row => new Set(row.windows).size>1).length;
    $("#split-group").classList.toggle("selected",grouped);
    $("#split-window").classList.toggle("selected",!grouped);
    $("#split-matrix").innerHTML = '<div class="split-grid"><span></span><span>窗口 1</span><span>窗口 2</span><span>窗口 3</span>'
      + rows.map(row => "<span>"+row.match+"</span>"+row.windows.map(split =>
        '<span class="split-cell '+split+'">'+({train:"训练",validation:"验证",test:"测试"}[split])+"</span>").join("")).join("") + "</div>";
    $("#split-result").className = "lab-result" + (leakage?" warning":"");
    $("#split-result").textContent = leakage
      ? leakage+" / 6 场同时出现在不同 split。窗口数量增加，不会增加独立比赛数。"
      : "0 / 6 场跨 split。保留了比赛级隔离；仍需独立检查时间泄漏。";
    const holdout = Number($("#holdout").value);
    const stats = fit(trainOnly?[100,200,300]:[100,200,300,holdout]);
    $("#holdout-label").textContent = holdout;
    $("#fit-train").classList.toggle("selected",trainOnly);
    $("#fit-all").classList.toggle("selected",!trainOnly);
    $("#fit-result").innerHTML = '<div><span>拟合均值</span><strong>'+stats.mean.toFixed(2)+"</strong></div>"
      + "<div><span>总体标准差</span><strong>"+stats.sd.toFixed(2)+"</strong></div>"
      + "<div><span>训练值 100 的 z</span><strong>"+((100-stats.mean)/stats.sd).toFixed(2)+"</strong></div>"
      + '<div class="fit-verdict '+(trainOnly?"":"warning")+'">'
      + (trainOnly?"改变留出值，训练统计量保持不变。transform 应复用这份训练产物。":"训练统计量已受到留出值影响。评估数据参与了预处理拟合。")+"</div>";
  }

  function render() {
    if (view==="architecture") renderArchitecture();
    else if (view==="path") renderPath();
    else if (view==="choices") renderChoices();
    else renderLab();
    updatePersonal();
  }

  document.addEventListener("click",event => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.view) setView(button.dataset.view,true);
    if (button.dataset.component) {
      selectedComponent=button.dataset.component;
      setView("architecture",true);
    }
    if (button.dataset.task) {
      selectedTask=button.dataset.task;
      selectedStage=data.stages.find(stage => stage.tasks.includes(selectedTask))?.id || null;
      taskFilter="all";
      setView("path",true);
    }
    if (button.dataset.stage) {
      selectedStage=selectedStage===button.dataset.stage?null:button.dataset.stage;
      renderPath();
    }
    if (button.dataset.filter) { taskFilter=button.dataset.filter; renderPath(); }
    if (button.dataset.choice) {
      choiceFocus=button.dataset.choice;
      setView("choices",true);
      $("#choice-"+choiceFocus)?.scrollIntoView({block:"center",behavior:"smooth"});
    }
  });

  document.addEventListener("change",event => {
    if (event.target.id==="learn-component") {
      personal.learned_components=personal.learned_components.filter(id => id!==selectedComponent);
      if (event.target.checked) personal.learned_components.push(selectedComponent);
      savePersonal();
    }
    if (event.target.id==="review-task") {
      personal.reviewed_tasks=personal.reviewed_tasks.filter(id => id!==selectedTask);
      if (event.target.checked) personal.reviewed_tasks.push(selectedTask);
      savePersonal();
      renderPath();
    }
  });
  document.addEventListener("input",event => {
    if (event.target.id==="task-note") {
      personal.notes[selectedTask]=event.target.value;
      savePersonal();
    }
  });
  $("#search").addEventListener("input",render);
  $("#next-task").addEventListener("click",() => {
    selectedTask=learningTasks.find(task => task.status!=="done" && dependenciesDone(task))?.id || learningTasks[0]?.id;
    selectedStage=null;
    taskFilter="all";
    setView("path",true);
  });
  $("#export-progress").addEventListener("click",() => {
    const url=URL.createObjectURL(new Blob([JSON.stringify(personal,null,2)],{type:"application/json"}));
    const link=document.createElement("a");
    link.href=url; link.download="dota-coach-learning-record.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url),1500);
    toast("已导出个人学习记录，任务状态保持原来源。");
  });
  $("#import-progress").addEventListener("click",() => $("#progress-file").click());
  $("#progress-file").addEventListener("change",async event => {
    const file=event.target.files[0];
    if (!file) return;
    try {
      if (file.size>1024*1024) throw new Error("学习记录文件不能超过 1 MiB。");
      const imported=validateProgress(JSON.parse(await file.text()));
      personal=imported; savePersonal(); render();
      toast("已导入个人记录，工程与实践进度仍来自各自 ToDo。");
    } catch (error) { toast(error.message); }
    event.target.value="";
  });
  ["cutoff","max-age","missing-gold","holdout"].forEach(id => $("#"+id).addEventListener("input",renderLab));
  $("#split-group").addEventListener("click",() => {grouped=true;renderLab();});
  $("#split-window").addEventListener("click",() => {grouped=false;renderLab();});
  $("#fit-train").addEventListener("click",() => {trainOnly=true;renderLab();});
  $("#fit-all").addEventListener("click",() => {trainOnly=false;renderLab();});
  window.addEventListener("hashchange",() => setView(location.hash.slice(1)));
  const workflows=data.tasks.filter(task => /^W\d{2}$/.test(task.id));
  $("#workflow-count").textContent=workflows.filter(task => task.status==="done").length+" / "+workflows.length;
  $("#task-count").textContent=learningTasks.filter(task => task.status==="done").length+" / "+learningTasks.length;
  $("#component-count").textContent=data.components.length;
  $("#workspace-count").textContent=data.workspace.available?data.workspace.matches+" 场":"待初始化";
  $("#workspace-note").textContent=data.workspace.available
    ? data.workspace.datasets+" 个数据集 · "+data.workspace.models+" 个模型；数量不表示质量"
    : data.workspace.reason;
  $("#snapshot-info").textContent="进度快照 "+data.generated_at.slice(0,10)+" · "+"工程 "+data.roadmap_sha256.slice(0,8)+" · 学习 "+data.learning_roadmap_sha256.slice(0,8);
  const first=learningTasks.find(task => task.status!=="done" && dependenciesDone(task));
  $("#next-task").textContent=first?"从 "+first.id+" 开始学习 ↗":"浏览学习路线 ↗";
  setView(location.hash.slice(1));
})();
