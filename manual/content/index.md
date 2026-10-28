---
title: BingoCode 开发者手册
description: 比 API 速查更详细的函数用法手册，包含签名、参数、返回值、注意事项和可直接运行的示例。
layout: home
toc: false
---

<section class="hero">
  <div class="hero-copy">
    <span class="eyebrow"><span class="dot"></span>BingoCodeIDE v0.6.3 · 完整用法手册</span>
    <h1>把每一个函数<br><em>真正讲清楚。</em></h1>
    <p class="lead">比客户端里的 API 速查更详细。每个函数都写清签名、参数、返回值、边界情况和能直接运行的例子，适合边做边查。</p>
    <div class="hero-actions">
      <a class="btn primary" href="{{PREFIX}}guide/getting-started.html">从快速入门开始 →</a>
      <a class="btn ghost" href="{{PREFIX}}api/sprite.html">浏览 API</a>
    </div>
    <div class="hero-points">
      <span>完整参数说明</span>
      <span>可直接运行示例</span>
      <span>离线 / 局域网部署</span>
    </div>
  </div>

  <div class="hero-code" aria-label="代码示例">
    <div class="window-bar">
      <span class="window-dot"></span>
      <span class="window-dot"></span>
      <span class="window-dot"></span>
      <span class="window-title">player.py</span>
    </div>
    <pre><code><span class="tok-comment"># 角色在每一帧里听玩家的话</span>
<span class="tok-var">hero</span> = <span class="tok-fn">Sprite</span>(<span class="tok-str">"玩家"</span>)
<span class="tok-var">hero</span>.<span class="tok-fn">goto</span>(<span class="tok-num">320</span>, <span class="tok-num">120</span>)
<span class="tok-var">hero</span>.<span class="tok-fn">set_rotation_mode</span>(<span class="tok-str">"left_right"</span>)

<span class="tok-key">while</span> <span class="tok-key">True</span>:
    <span class="tok-key">if</span> <span class="tok-fn">key_down</span>(<span class="tok-str">"left"</span>):
        <span class="tok-var">hero</span>.<span class="tok-fn">add_x</span>(<span class="tok-num">-4</span>)
        <span class="tok-var">hero</span>.<span class="tok-fn">set_angle</span>(<span class="tok-num">180</span>)

    <span class="tok-key">if</span> <span class="tok-fn">key_down</span>(<span class="tok-str">"right"</span>):
        <span class="tok-var">hero</span>.<span class="tok-fn">add_x</span>(<span class="tok-num">4</span>)
        <span class="tok-var">hero</span>.<span class="tok-fn">set_angle</span>(<span class="tok-num">0</span>)

    <span class="tok-key">if</span> <span class="tok-fn">key_down</span>(<span class="tok-str">"space"</span>):
        <span class="tok-var">hero</span>.<span class="tok-fn">smart_jump</span>(<span class="tok-num">12</span>)</code></pre>
    <span class="code-bubble">按住空格 → 跳得更高</span>
  </div>
</section>

<section class="section">
  <div class="section-head">
    <span class="kicker">START HERE</span>
    <h2>三条路线，选一条开始</h2>
    <p>第一次打开手册，不需要从头读到尾。先选一个最接近当前目标的方向。</p>
  </div>
  <div class="path-grid">
    <article class="path-card" data-href="{{PREFIX}}guide/getting-started.html" role="link" tabindex="0">
      <span class="path-num">01 / 第一次运行</span>
      <h3>让角色动起来</h3>
      <p>从认识主界面，到写下第一段游戏循环，完整走一遍。</p>
      <span class="card-link">进入快速入门 →</span>
    </article>
    <article class="path-card" data-href="{{PREFIX}}api/sprite.html" role="link" tabindex="0">
      <span class="path-num">02 / 查一个函数</span>
      <h3>精灵 Sprite</h3>
      <p>角色对象是所有玩法的起点：坐标、大小、朝向、动画和分组。</p>
      <span class="card-link">查看精灵 API →</span>
    </article>
    <article class="path-card" data-href="{{PREFIX}}editor/sprite-editor.html" role="link" tabindex="0">
      <span class="path-num">03 / 做一次标注</span>
      <h3>角色编辑器</h3>
      <p>中心点、碰撞体和标记，决定角色怎样旋转、碰撞和挂接武器。</p>
      <span class="card-link">打开编辑器指南 →</span>
    </article>
  </div>
</section>

<section class="section">
  <div class="section-head">
    <span class="kicker">API MAP</span>
    <h2>按能力查 API</h2>
    <p>和客户端内置速查同一套分类，但每一项都会展开讲清楚。首批演示页已经可以点开。</p>
  </div>
  <div class="api-grid">
    <article class="api-card" data-href="{{PREFIX}}api/sprite.html" role="link" tabindex="0">
      <div class="api-card-top"><span class="api-dot"></span><span class="api-card-tag">对象</span></div>
      <h3>精灵 Sprite</h3>
      <p>创建、删除、属性、动画、分组和挂点。</p>
      <footer><span class="api-count">17 项</span><span class="api-count">打开 →</span></footer>
    </article>
    <article class="api-card" data-href="{{PREFIX}}api/movement.html" role="link" tabindex="0">
      <div class="api-card-top"><span class="api-dot blue"></span><span class="api-card-tag">运动</span></div>
      <h3>移动与跳跃</h3>
      <p>坐标、朝向、持续速度、跳跃和边界反弹。</p>
      <footer><span class="api-count">13 项</span><span class="api-count">打开 →</span></footer>
    </article>
    <article class="api-card">
      <div class="api-card-top"><span class="api-dot orange"></span><span class="api-card-tag">外观</span></div>
      <h3>显示与动画</h3>
      <p>说话气泡、动画播放、透明度和旋转方式。</p>
      <footer><span class="api-count">6 项</span><span class="api-soon">待编写</span></footer>
    </article>
    <article class="api-card">
      <div class="api-card-top"><span class="api-dot purple"></span><span class="api-card-tag">侦测</span></div>
      <h3>键盘、鼠标与碰撞</h3>
      <p>按键状态、鼠标位置、碰撞检测和距离。</p>
      <footer><span class="api-count">10 项</span><span class="api-soon">待编写</span></footer>
    </article>
    <article class="api-card">
      <div class="api-card-top"><span class="api-dot pink"></span><span class="api-card-tag">事件</span></div>
      <h3>广播与接收</h3>
      <p>角色之间传递消息，让多个对象协同行动。</p>
      <footer><span class="api-count">4 项</span><span class="api-soon">待编写</span></footer>
    </article>
    <article class="api-card">
      <div class="api-card-top"><span class="api-dot"></span><span class="api-card-tag">时间</span></div>
      <h3>计时与延时</h3>
      <p>每隔几秒做一件事，或者构建可暂停的计时器。</p>
      <footer><span class="api-count">3 项</span><span class="api-soon">待编写</span></footer>
    </article>
    <article class="api-card">
      <div class="api-card-top"><span class="api-dot blue"></span><span class="api-card-tag">声音</span></div>
      <h3>音效播放</h3>
      <p>播放、循环和停止音效，处理找不到资源的情况。</p>
      <footer><span class="api-count">2 项</span><span class="api-soon">待编写</span></footer>
    </article>
    <article class="api-card">
      <div class="api-card-top"><span class="api-dot orange"></span><span class="api-card-tag">地图</span></div>
      <h3>地图与摄像机</h3>
      <p>加载地图、摄像机跟随和摄像机边界。</p>
      <footer><span class="api-count">2 项</span><span class="api-soon">待编写</span></footer>
    </article>
    <article class="api-card">
      <div class="api-card-top"><span class="api-dot purple"></span><span class="api-card-tag">工具</span></div>
      <h3>随机数与屏幕效果</h3>
      <p>随机数、屏幕震动、文字显示和碰撞盒调试。</p>
      <footer><span class="api-count">6 项</span><span class="api-soon">待编写</span></footer>
    </article>
  </div>
</section>

<section class="section">
  <div class="section-head">
    <span class="kicker">READING GUIDE</span>
    <h2>先认识四种标记</h2>
    <p>每个 API 条目都会在签名栏标出类型，查文档时可以先看标记再决定怎么用。</p>
  </div>
  <div class="legend-grid">
    <div class="legend-item">
      <span class="badge class">类</span>
      <div><strong>创建对象</strong><span>用类名创建实例，例如 <code>Sprite("玩家")</code>。</span></div>
    </div>
    <div class="legend-item">
      <span class="badge method">方法</span>
      <div><strong>对象能做的事</strong><span>需要先有对象，例如 <code>hero.jump(10)</code>。</span></div>
    </div>
    <div class="legend-item">
      <span class="badge prop">属性</span>
      <div><strong>对象身上的数据</strong><span>可读可写，例如 <code>hero.x = 100</code>。</span></div>
    </div>
    <div class="legend-item">
      <span class="badge func">函数</span>
      <div><strong>直接调用的能力</strong><span>不需要对象，例如 <code>key_down("space")</code>。</span></div>
    </div>
  </div>
</section>

<section class="section">
  <div class="section-head">
    <span class="kicker">PROGRESS</span>
    <h2>手册开发进度</h2>
    <p>当前是视觉与交互演示版，只开放少量页面。确认版式后再批量补齐内容。</p>
  </div>
  <div class="progress-list">
    <div class="progress-row"><span>站点框架</span><div class="progress-bar"><i style="width:100%"></i></div><span>100%</span></div>
    <div class="progress-row"><span>快速入门</span><div class="progress-bar"><i style="width:100%"></i></div><span>100%</span></div>
    <div class="progress-row"><span>精灵 Sprite</span><div class="progress-bar"><i style="width:100%"></i></div><span>100%</span></div>
    <div class="progress-row"><span>运动</span><div class="progress-bar"><i style="width:100%"></i></div><span>100%</span></div>
    <div class="progress-row"><span>角色编辑器</span><div class="progress-bar"><i style="width:100%"></i></div><span>100%</span></div>
    <div class="progress-row"><span>其余 API</span><div class="progress-bar"><i style="width:18%"></i></div><span>18%</span></div>
    <div class="progress-row"><span>示意图截图</span><div class="progress-bar"><i style="width:0%"></i></div><span>0%</span></div>
  </div>
</section>

<section class="section">
  <div class="section-head">
    <span class="kicker">OFFLINE FIRST</span>
    <h2>可以离线，也可以放在局域网</h2>
    <p>手册是纯静态 HTML，不依赖客户端运行，也不需要联网。构建后既能直接双击打开，也能放到任意静态服务器。</p>
  </div>
  <div class="callout tip">
    <strong>本地预览</strong>
    <p>在项目根目录运行 <code>pnpm manual:serve</code>，终端会同时打印 localhost 和局域网访问地址。</p>
  </div>
</section>
