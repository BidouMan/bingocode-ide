/* BingoCode 开发者手册 · 交互脚本 */
(function () {
  'use strict'

  var doc = document
  var root = doc.documentElement
  var prefix = window.__DOCS_PREFIX__ || './'
  var searchPages = (window.__BINGO_DOCS__ && window.__BINGO_DOCS__.pages) || []

  // ─── 主题 ───

  function initTheme() {
    var button = doc.getElementById('theme-toggle')
    if (!button) return

    button.addEventListener('click', function () {
      var next = root.dataset.theme === 'dark' ? 'light' : 'dark'
      root.dataset.theme = next
      try {
        localStorage.setItem('bingo-docs-theme', next)
      } catch (error) {
        /* 忽略隐私模式下的存储异常 */
      }
    })
  }

  // ─── 侧边栏 ───

  function initSidebar() {
    var menuButton = doc.getElementById('menu-button')
    var backdrop = doc.getElementById('sidebar-backdrop')
    if (!menuButton) return

    function setOpen(open) {
      doc.body.classList.toggle('sidebar-open', open)
      menuButton.setAttribute('aria-expanded', open ? 'true' : 'false')
    }

    menuButton.addEventListener('click', function () {
      setOpen(!doc.body.classList.contains('sidebar-open'))
    })

    if (backdrop) {
      backdrop.addEventListener('click', function () {
        setOpen(false)
      })
    }

    doc.querySelectorAll('.sidebar a').forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.innerWidth <= 1024) setOpen(false)
      })
    })

    doc.querySelectorAll('.nav-group-title').forEach(function (button) {
      button.addEventListener('click', function () {
        var group = button.closest('.nav-group')
        if (!group) return
        var expanded = group.classList.toggle('expanded')
        button.setAttribute('aria-expanded', expanded ? 'true' : 'false')
      })
    })

    window.addEventListener('resize', function () {
      if (window.innerWidth > 1024) setOpen(false)
    })

    doc.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && doc.body.classList.contains('sidebar-open')) {
        setOpen(false)
      }
    })
  }

  // ─── 复制代码 ───

  function fallbackCopy(text) {
    var area = doc.createElement('textarea')
    area.value = text
    area.style.position = 'fixed'
    area.style.opacity = '0'
    doc.body.appendChild(area)
    area.select()
    try {
      doc.execCommand('copy')
    } catch (error) {
      /* 忽略 */
    }
    doc.body.removeChild(area)
  }

  function initCopyButtons() {
    doc.querySelectorAll('[data-copy]').forEach(function (button) {
      button.addEventListener('click', function () {
        var block = button.closest('.code-block')
        var code = block && block.querySelector('code')
        if (!code) return
        var text = code.innerText

        var copyPromise = navigator.clipboard && navigator.clipboard.writeText
          ? navigator.clipboard.writeText(text)
          : Promise.reject(new Error('clipboard unavailable'))

        copyPromise
          .catch(function () {
            fallbackCopy(text)
          })
          .then(function () {
            button.textContent = '已复制'
            button.classList.add('copied')
            window.setTimeout(function () {
              button.textContent = '复制'
              button.classList.remove('copied')
            }, 1400)
          })
      })
    })
  }

  // ─── 可点击卡片 ───

  function initCardLinks() {
    doc.querySelectorAll('[data-href]').forEach(function (card) {
      if (!card.hasAttribute('tabindex')) {
        card.setAttribute('tabindex', '0')
        card.setAttribute('role', 'link')
      }

      function go() {
        var href = card.getAttribute('data-href')
        if (href) window.location.href = href
      }

      card.addEventListener('click', function (event) {
        if (event.target.closest('a')) return
        go()
      })

      card.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          go()
        }
      })
    })
  }

  // ─── 表格横向滚动 ───

  function initTables() {
    doc.querySelectorAll('.article table').forEach(function (table) {
      if (table.parentElement && table.parentElement.classList.contains('table-scroll')) return
      var wrapper = doc.createElement('div')
      wrapper.className = 'table-scroll'
      table.parentNode.insertBefore(wrapper, table)
      wrapper.appendChild(table)
    })
  }

  // ─── 阅读进度 ───

  function initReadingProgress() {
    var bar = doc.getElementById('reading-progress')
    if (!bar) return

    var ticking = false

    function update() {
      var scrollTop = window.scrollY || doc.documentElement.scrollTop
      var height = doc.documentElement.scrollHeight - window.innerHeight
      var percent = height > 0 ? Math.min(100, Math.max(0, (scrollTop / height) * 100)) : 0
      bar.style.width = percent + '%'
      ticking = false
    }

    function onScroll() {
      if (ticking) return
      ticking = true
      window.requestAnimationFrame(update)
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    update()
  }

  // ─── 右侧目录滚动高亮 ───

  function initTocSpy() {
    var links = Array.prototype.slice.call(doc.querySelectorAll('.toc-link'))
    if (!links.length) return

    var entries = links
      .map(function (link) {
        var id = decodeURIComponent((link.getAttribute('href') || '').replace(/^#/, ''))
        var target = doc.getElementById(id)
        return target ? { link: link, target: target } : null
      })
      .filter(Boolean)

    if (!entries.length) return

    var ticking = false

    function update() {
      var offset = 110
      var active = entries[0]

      for (var i = 0; i < entries.length; i += 1) {
        if (entries[i].target.getBoundingClientRect().top <= offset) {
          active = entries[i]
        } else {
          break
        }
      }

      entries.forEach(function (entry) {
        entry.link.classList.toggle('active', entry === active)
      })

      ticking = false
    }

    function onScroll() {
      if (ticking) return
      ticking = true
      window.requestAnimationFrame(update)
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    update()
  }

  // ─── 搜索 ───

  function initSearch() {
    var overlay = doc.getElementById('search-overlay')
    var input = doc.getElementById('search-input')
    var resultsBox = doc.getElementById('search-results')
    if (!overlay || !input || !resultsBox) return

    var selectedIndex = 0
    var currentResults = []

    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
    }

    function highlight(text, query) {
      var safe = escapeHtml(text)
      if (!query) return safe
      var index = safe.toLowerCase().indexOf(query.toLowerCase())
      if (index < 0) return safe
      var end = index + query.length
      return (
        safe.slice(0, index) +
        '<mark>' +
        safe.slice(index, end) +
        '</mark>' +
        safe.slice(end)
      )
    }

    function makeSnippet(page, query) {
      var text = page.text || ''
      var lower = text.toLowerCase()
      var index = lower.indexOf(query.toLowerCase())
      if (index < 0) {
        var heading = (page.headings || []).find(function (item) {
          return item.title.toLowerCase().indexOf(query.toLowerCase()) >= 0
        })
        if (heading) return heading.title
        return text.slice(0, 88)
      }
      var start = Math.max(0, index - 30)
      var end = Math.min(text.length, index + query.length + 58)
      return (start > 0 ? '…' : '') + text.slice(start, end) + (end < text.length ? '…' : '')
    }

    function search(query) {
      var q = query.trim().toLowerCase()
      if (!q) return []

      return searchPages
        .map(function (page) {
          var score = 0
          var title = (page.title || '').toLowerCase()
          var description = (page.description || '').toLowerCase()
          var headings = (page.headings || [])
            .map(function (item) {
              return item.title.toLowerCase()
            })
            .join(' ')
          var text = (page.text || '').toLowerCase()

          if (title === q) score += 160
          else if (title.indexOf(q) === 0) score += 120
          else if (title.indexOf(q) >= 0) score += 80

          if (headings.indexOf(q) >= 0) score += 40
          if (description.indexOf(q) >= 0) score += 24
          if (text.indexOf(q) >= 0) score += 8

          return { page: page, score: score }
        })
        .filter(function (item) {
          return item.score > 0
        })
        .sort(function (a, b) {
          return b.score - a.score
        })
        .slice(0, 12)
        .map(function (item) {
          return item.page
        })
    }

    function render(query) {
      var q = query.trim()
      currentResults = search(q)
      selectedIndex = 0

      if (!q) {
        resultsBox.innerHTML =
          '<div class="search-empty">输入函数名、属性名或关键词开始搜索</div>'
        return
      }

      if (!currentResults.length) {
        resultsBox.innerHTML =
          '<div class="search-empty">没有找到「' + escapeHtml(q) + '」相关内容</div>'
        return
      }

      resultsBox.innerHTML = currentResults
        .map(function (page, index) {
          return (
            '<a class="search-result' +
            (index === 0 ? ' selected' : '') +
            '" href="' +
            prefix +
            page.path +
            '">' +
            '<span class="search-result-top">' +
            '<span class="search-result-title">' +
            highlight(page.title, q) +
            '</span>' +
            '<span class="search-result-group">' +
            escapeHtml(page.group || '') +
            '</span>' +
            '<span class="search-result-path">' +
            escapeHtml(page.path.replace(/\.html$/, '')) +
            '</span>' +
            '</span>' +
            '<span class="search-result-snippet">' +
            highlight(makeSnippet(page, q), q) +
            '</span>' +
            '</a>'
          )
        })
        .join('')
    }

    function setSelected(nextIndex) {
      var items = resultsBox.querySelectorAll('.search-result')
      if (!items.length) return
      selectedIndex = (nextIndex + items.length) % items.length
      items.forEach(function (item, index) {
        item.classList.toggle('selected', index === selectedIndex)
      })
      items[selectedIndex].scrollIntoView({ block: 'nearest' })
    }

    function open() {
      overlay.hidden = false
      doc.body.classList.add('search-open')
      input.value = ''
      render('')
      window.setTimeout(function () {
        input.focus()
      }, 10)
    }

    function close() {
      overlay.hidden = true
      doc.body.classList.remove('search-open')
      input.blur()
    }

    doc.querySelectorAll('[data-search-open]').forEach(function (button) {
      button.addEventListener('click', open)
    })

    input.addEventListener('input', function () {
      render(input.value)
    })

    input.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setSelected(selectedIndex + 1)
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        setSelected(selectedIndex - 1)
      } else if (event.key === 'Enter') {
        var selected = resultsBox.querySelectorAll('.search-result')[selectedIndex]
        if (selected) {
          event.preventDefault()
          window.location.href = selected.getAttribute('href')
        }
      }
    })

    overlay.addEventListener('click', function (event) {
      if (event.target === overlay) close()
    })

    doc.addEventListener('keydown', function (event) {
      var isShortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k'
      if (isShortcut) {
        event.preventDefault()
        if (overlay.hidden) open()
        else close()
        return
      }

      if (
        event.key === '/' &&
        overlay.hidden &&
        !/^(INPUT|TEXTAREA|SELECT)$/.test(doc.activeElement.tagName) &&
        !doc.activeElement.isContentEditable
      ) {
        event.preventDefault()
        open()
        return
      }

      if (event.key === 'Escape' && !overlay.hidden) {
        event.preventDefault()
        close()
      }
    })
  }

  // ─── 大图查看 ───

  function initLightbox() {
    var lightbox = doc.getElementById('lightbox')
    var image = doc.getElementById('lightbox-image')
    var closeButton = doc.getElementById('lightbox-close')
    if (!lightbox || !image) return

    var lastFocus = null

    function open(src, alt) {
      lastFocus = doc.activeElement
      image.src = src
      image.alt = alt || ''
      lightbox.hidden = false
      doc.body.classList.add('search-open')
      if (closeButton) closeButton.focus()
    }

    function close() {
      lightbox.hidden = true
      image.src = ''
      doc.body.classList.remove('search-open')
      if (lastFocus && lastFocus.focus) lastFocus.focus()
    }

    doc.querySelectorAll('[data-lightbox]').forEach(function (button) {
      button.addEventListener('click', function () {
        open(button.getAttribute('data-lightbox'), button.getAttribute('aria-label'))
      })
    })

    if (closeButton) closeButton.addEventListener('click', close)

    lightbox.addEventListener('click', function (event) {
      if (event.target === lightbox) close()
    })

    doc.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !lightbox.hidden) close()
    })
  }

  // ─── 启动 ───

  function boot() {
    initTheme()
    initSidebar()
    initCopyButtons()
    initCardLinks()
    initTables()
    initReadingProgress()
    initTocSpy()
    initSearch()
    initLightbox()
  }

  if (doc.readyState === 'loading') {
    doc.addEventListener('DOMContentLoaded', boot)
  } else {
    boot()
  }
})()
