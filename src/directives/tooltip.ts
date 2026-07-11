import type { Directive, DirectiveBinding } from 'vue'

interface TooltipElement extends HTMLElement {
  _tooltip?: {
    element: HTMLDivElement
    showTimeout: ReturnType<typeof setTimeout> | 0
    hideTimeout: ReturnType<typeof setTimeout> | 0
  }
}

function createTooltipElement(text: string): HTMLDivElement {
  const el = document.createElement('div')
  el.className = 'custom-tooltip'
  el.textContent = text
  el.style.cssText = `
    position: fixed;
    z-index: 10000;
    padding: 6px 10px;
    background: rgba(30, 30, 30, 0.95);
    color: rgb(220, 220, 220);
    font-size: 12px;
    line-height: 1.4;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s ease;
    white-space: nowrap;
    max-width: 200px;
  `
  return el
}

function positionTooltip(element: HTMLElement, tooltip: HTMLDivElement): void {
  const rect = element.getBoundingClientRect()
  const tooltipRect = tooltip.getBoundingClientRect()
  
  let left = rect.left + (rect.width - tooltipRect.width) / 2
  let top = rect.bottom + 8
  
  // Keep within viewport
  if (left < 8) left = 8
  if (left + tooltipRect.width > window.innerWidth - 8) {
    left = window.innerWidth - tooltipRect.width - 8
  }
  if (top + tooltipRect.height > window.innerHeight - 8) {
    top = rect.top - tooltipRect.height - 8
  }
  
  tooltip.style.left = `${left}px`
  tooltip.style.top = `${top}px`
}

function showTooltip(el: TooltipElement, text: string): void {
  if (!text) return
  
  // Clear any pending hide
  if (el._tooltip?.hideTimeout) {
    clearTimeout(el._tooltip.hideTimeout)
  }
  
  // Create tooltip if not exists
  if (!el._tooltip) {
    const tooltipEl = createTooltipElement(text)
    document.body.appendChild(tooltipEl)
    el._tooltip = {
      element: tooltipEl,
      showTimeout: 0,
      hideTimeout: 0
    }
  }
  
  // Update text if changed
  const tooltip = el._tooltip!
  if (tooltip.element.textContent !== text) {
    tooltip.element.textContent = text
  }
  
  // Position and show after delay
  tooltip.showTimeout = setTimeout(() => {
    positionTooltip(el, el._tooltip!.element)
    el._tooltip!.element.style.opacity = '1'
  }, 500)
}

function hideTooltip(el: TooltipElement): void {
  if (!el._tooltip) return
  
  // Clear any pending show
  if (el._tooltip.showTimeout) {
    clearTimeout(el._tooltip.showTimeout)
  }
  
  // Hide immediately
  el._tooltip.element.style.opacity = '0'
  
  // Remove from DOM after transition
  el._tooltip.hideTimeout = setTimeout(() => {
    if (el._tooltip?.element.parentNode) {
      el._tooltip.element.parentNode.removeChild(el._tooltip.element)
    }
    delete el._tooltip
  }, 150)
}

export const vTooltip: Directive = {
  mounted(el: TooltipElement, binding: DirectiveBinding) {
    el.addEventListener('mouseenter', () => showTooltip(el, binding.value))
    el.addEventListener('mouseleave', () => hideTooltip(el))
    el.addEventListener('focus', () => showTooltip(el, binding.value))
    el.addEventListener('blur', () => hideTooltip(el))
  },
  
  updated(el: TooltipElement, binding: DirectiveBinding) {
    // Update tooltip text if binding value changed
    if (el._tooltip && binding.value !== binding.oldValue) {
      el._tooltip.element.textContent = binding.value || ''
    }
  },
  
  unmounted(el: TooltipElement) {
    // Clean up
    if (el._tooltip) {
      clearTimeout(el._tooltip.showTimeout)
      clearTimeout(el._tooltip.hideTimeout)
      if (el._tooltip.element.parentNode) {
        el._tooltip.element.parentNode.removeChild(el._tooltip.element)
      }
      delete el._tooltip
    }
  }
}
