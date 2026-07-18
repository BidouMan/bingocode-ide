<script setup lang="ts">
// 学习面板 - Python 入门知识速查，适合新手小白
const categories = [
  {
    name: '基础语法',
    items: [
      { title: 'print() 输出', tip: 'print("内容") — 在屏幕上显示文字' },
      { title: 'input() 输入', tip: 'input("提示") — 获取用户输入，返回字符串' },
      { title: '变量赋值', tip: 'name = "小明" — 用等号给变量赋值' },
      { title: '数据类型', tip: 'int整数 / float小数 / str字符串 / bool布尔' },
      { title: '类型转换', tip: 'int("3") / str(3) / float("3.14")' },
    ]
  },
  {
    name: '条件判断',
    items: [
      { title: 'if 语句', tip: 'if 条件:\n    执行代码' },
      { title: 'if-else', tip: 'if 条件:\n    代码A\nelse:\n    代码B' },
      { title: 'if-elif-else', tip: '多个条件分支，elif 可以写多个' },
      { title: '比较运算符', tip: '== != > < >= <= — 注意双等号才是比较' },
      { title: '逻辑运算', tip: 'and 同时满足 / or 满足一个 / not 取反' },
    ]
  },
  {
    name: '循环',
    items: [
      { title: 'for 循环', tip: 'for i in range(5): — 重复5次，i从0到4' },
      { title: 'while 循环', tip: 'while 条件: — 条件为真就一直执行' },
      { title: 'break', tip: '立即跳出循环' },
      { title: 'continue', tip: '跳过本次，继续下一轮循环' },
      { title: 'range()', tip: 'range(5)=0~4 / range(2,6)=2~5 / range(0,10,2)=0,2,4,6,8' },
    ]
  },
  {
    name: '数据结构',
    items: [
      { title: '列表 list', tip: 'fruits = ["苹果", "香蕉"] — 有序，可修改' },
      { title: '字典 dict', tip: 'info = {"name": "小明", "age": 12} — 键值对' },
      { title: '元组 tuple', tip: 'point = (3, 4) — 有序，不可修改' },
      { title: '集合 set', tip: 's = {1, 2, 3} — 无序，不重复' },
    ]
  },
  {
    name: '函数',
    items: [
      { title: '定义函数', tip: 'def say_hello(name):\n    print(f"你好{name}")' },
      { title: '返回值', tip: 'return 结果 — 把结果返回给调用者' },
      { title: '默认参数', tip: 'def greet(name="朋友"): — 调用时可省略该参数' },
    ]
  },
  {
    name: '绘图 (turtle)',
    items: [
      { title: '前进/后退', tip: 't.forward(100) / t.backward(50)' },
      { title: '转向', tip: 't.left(90) 左转90° / t.right(90) 右转90°' },
      { title: '画圆', tip: 't.circle(50) — 画半径50的圆' },
      { title: '颜色', tip: 't.pencolor("red") 画笔 / t.fillcolor("blue") 填充' },
      { title: '填充', tip: 't.begin_fill() ... t.end_fill()' },
    ]
  },
]

const expanded = ref<Set<string>>(new Set())

function toggleCategory(name: string) {
  if (expanded.value.has(name)) {
    expanded.value.delete(name)
  } else {
    expanded.value.add(name)
  }
}
</script>

<script lang="ts">
import { ref } from 'vue'
</script>

<template>
  <div class="learn-panel">
    <div class="learn-header">Python 速查</div>
    <div class="learn-hint">点击展开查看语法提示</div>
    <div class="learn-list">
      <div v-for="cat in categories" :key="cat.name" class="learn-category">
        <div class="learn-cat-header" @click="toggleCategory(cat.name)">
          <span class="learn-cat-arrow" :class="{ 'learn-cat-arrow-open': expanded.has(cat.name) }">▶</span>
          <span class="learn-cat-name">{{ cat.name }}</span>
        </div>
        <div v-if="expanded.has(cat.name)" class="learn-cat-items">
          <div v-for="item in cat.items" :key="item.title" class="learn-item">
            <div class="learn-item-title">{{ item.title }}</div>
            <pre class="learn-item-tip">{{ item.tip }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.learn-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-root);
  user-select: none;
}
.learn-header {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  padding: 10px 12px 2px;
  background: rgba(0, 0, 0, 0.15);
}
.learn-hint {
  font-size: 10px;
  color: var(--text-muted);
  padding: 0 12px 8px;
  background: rgba(0, 0, 0, 0.15);
}
.learn-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px 6px;
}
.learn-category {
  margin-bottom: 2px;
}
.learn-cat-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s;
}
.learn-cat-header:hover { background: var(--bg-hover); }
.learn-cat-arrow {
  font-size: 8px;
  color: var(--text-muted);
  transition: transform 0.12s;
}
.learn-cat-arrow-open { transform: rotate(90deg); }
.learn-cat-name {
  font-size: 12px;
  color: var(--text);
  font-weight: 500;
}
.learn-cat-items {
  padding-left: 8px;
}
.learn-item {
  padding: 4px 8px;
  border-radius: 3px;
  cursor: default;
}
.learn-item:hover { background: var(--bg-hover); }
.learn-item-title {
  font-size: 11px;
  color: var(--accent);
  margin-bottom: 2px;
}
.learn-item-tip {
  font-size: 10px;
  color: var(--text-muted);
  font-family: monospace;
  white-space: pre-wrap;
  margin: 0;
  line-height: 1.4;
}
</style>
