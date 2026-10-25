<section class="home-hero">
  <div class="home-hero-copy">
    <span class="home-eyebrow">BingoCodeIDE 帮助文档</span>
    <h1>用 Python，<br>做出能玩的游戏。</h1>
    <p class="home-lede">从画第一个角色开始，到让角色跑、跳、碰撞、切换场景。编辑器的每个操作、引擎的每个函数，这里都写清楚了。</p>
    <div class="home-actions">
      <a class="home-btn primary" href="getting-started/first-game.md">从第一个游戏开始</a>
      <a class="home-btn ghost" href="api/sprite.md">浏览 API 参考</a>
    </div>
    <p class="home-meta">v{{VERSION}} · 23 篇文档 · 离线可读，可部署到局域网</p>
  </div>

  <figure class="home-app">
    <img class="home-app-shot" src="{{RELATIVE_PATH}}static/screenshots/ide-hero.png?v={{BUILD_STAMP}}" alt="BingoCodeIDE 游戏模式主界面" />
    <div class="home-app-empty">
      <span class="home-app-empty-tag">docs/static/screenshots/ide-hero.png</span>
      <strong class="home-app-empty-title">这里放一张主界面截图</strong>
      <span class="home-app-empty-desc">截取应用窗口本身，宽度 1600px 以上，不要带窗口阴影和外框；页面会自动裁圆角并贴到卡片底部。</span>
    </div>
  </figure>
</section>

<p class="home-app-caption">游戏模式主界面：左侧实时预览与资源列表，中间写代码，底部看运行输出。实际界面以安装版本为准。</p>

<section class="home-section">
  <h2>从这里开始</h2>
  <p class="home-section-desc">第一次打开手册，不用从头读到尾。选一个最接近当前目标的方向。</p>

  <div class="home-cards">
    <a class="home-card" href="getting-started/first-game.md">
      <span class="home-card-head">
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 4.5A1.5 1.5 0 0 1 4.5 3H15v10H4.5A1.5 1.5 0 0 0 3 14.5v-10Z"/><path d="M3 14.5A1.5 1.5 0 0 1 4.5 13H15"/></svg>
        <span class="home-card-title">快速入门</span>
      </span>
      <span class="home-card-desc">跟着做第一个小游戏，理解坐标、精灵与游戏循环。</span>
    </a>
    <a class="home-card" href="editor/sprite-editor.md">
      <span class="home-card-head">
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3 15 1.2-3.6L12.4 3.2a1.6 1.6 0 0 1 2.3 2.3L6.6 13.8 3 15Z"/><path d="m11 4.6 2.4 2.4"/></svg>
        <span class="home-card-title">编辑器指南</span>
      </span>
      <span class="home-card-desc">角色、地图、资源面板，把素材变成能用的游戏内容。</span>
    </a>
    <a class="home-card" href="api/sprite.md">
      <span class="home-card-head">
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6.5 4.5-4 4.5 4 4.5M11.5 4.5l4 4.5-4 4.5"/></svg>
        <span class="home-card-title">API 参考</span>
      </span>
      <span class="home-card-desc">按分类查函数：签名、参数、返回值、注意事项与示例。</span>
    </a>
    <a class="home-card" href="tutorials/platformer.md">
      <span class="home-card-head">
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 14V6.5L9 3l6 3.5V14"/><path d="M3 14h12M7 14v-4h4v4"/></svg>
        <span class="home-card-title">教学案例</span>
      </span>
      <span class="home-card-desc">跟着完整项目做平台跳跃、射击和益智游戏。</span>
    </a>
  </div>
</section>

<section class="home-section">
  <h2>API 参考</h2>
  <p class="home-section-desc">10 个分类，覆盖引擎提供的全部函数。也可以直接在左上角搜索函数名。</p>

  <div class="home-api">
    <a href="api/sprite.md"><span class="home-api-name">精灵 Sprite</span><span class="home-api-desc">创建、坐标、外观、分组</span></a>
    <a href="api/movement.md"><span class="home-api-name">运动</span><span class="home-api-desc">移动、跳跃、碰撞与物理</span></a>
    <a href="api/appearance.md"><span class="home-api-name">外观</span><span class="home-api-desc">造型、动画、旋转与显隐</span></a>
    <a href="api/detection.md"><span class="home-api-name">侦测</span><span class="home-api-desc">键盘、鼠标与碰撞检测</span></a>
    <a href="api/events.md"><span class="home-api-name">事件</span><span class="home-api-desc">广播、接收与自定义事件</span></a>
    <a href="api/control.md"><span class="home-api-name">控制</span><span class="home-api-desc">等待、循环、条件与暂停</span></a>
    <a href="api/time.md"><span class="home-api-name">时间</span><span class="home-api-desc">计时器、帧时间与节流</span></a>
    <a href="api/sound.md"><span class="home-api-name">声音</span><span class="home-api-desc">播放音效与背景音乐</span></a>
    <a href="api/map.md"><span class="home-api-name">地图</span><span class="home-api-desc">加载地图、图层与相机</span></a>
    <a href="api/tools.md"><span class="home-api-name">工具函数</span><span class="home-api-desc">随机数、数学与常用工具</span></a>
  </div>
</section>

<section class="home-section">
  <h2>学习路径</h2>
  <p class="home-section-desc">按顺序走一遍，基本就能独立做一个小游戏了。</p>

  <ol class="home-path">
    <li><a href="getting-started/install.md">安装与环境配置</a> — 把编辑器装好并跑起来</li>
    <li><a href="getting-started/first-game.md">第一个游戏</a> — 做一个能玩的小作品</li>
    <li><a href="getting-started/basic-concepts.md">核心概念</a> — 理解坐标、精灵与游戏循环</li>
    <li><a href="tutorials/platformer.md">教学案例</a> — 跟着完整项目练习</li>
    <li>需要查具体函数时，打开 <a href="api/sprite.md">API 参考</a>，或在左上角搜索函数名</li>
  </ol>

  <p class="home-note">这份手册是纯静态页面，可以直接用浏览器打开，也可以放到局域网或服务器上给多人访问。它独立于客户端发布，不会被打包进安装程序。</p>
</section>
