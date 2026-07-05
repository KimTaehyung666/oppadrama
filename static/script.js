// ===== PERFORMANCE OPTIMIZATION =====

// Lazy Loading Images
function initLazyLoad() {
  if ('IntersectionObserver' in window) {
    const images = document.querySelectorAll('img[data-src]');
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src;
          img.removeAttribute('data-src');
          img.classList.add('loaded');
          observer.unobserve(img);
        }
      });
    }, { rootMargin: '50px' });
    images.forEach(img => imageObserver.observe(img));
  } else {
    // Fallback untuk browser lama
    document.querySelectorAll('img[data-src]').forEach(img => {
      img.src = img.dataset.src;
      img.removeAttribute('data-src');
      img.classList.add('loaded');
    });
  }
}

// Call on page load
document.addEventListener('DOMContentLoaded', initLazyLoad);

// Re-init lazy load setelah AJAX/dynamic content
function reloadLazyLoad() {
  initLazyLoad();
}

// Debounce function untuk optimize scroll events
function debounce(func, delay) {
  let timeoutId;
  return function(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
}

// ===== CACHE BUSTING UNTUK DEVELOPMENT =====
const CACHE_VERSION = 'v1';

// ===== UTILITY: Image optimization
function getOptimizedImageUrl(url) {
  if (!url || url.includes('data:')) return url;
  return url;
}

// ===== PREFETCH OPTIMIZATION =====
function prefetchResource(url, type = 'prefetch') {
  const link = document.createElement('link');
  link.rel = type;
  link.href = url;
  document.head.appendChild(link);
}

// Prefetch next page (untuk pagination optimization)
function prefetchNextPage() {
  const nextLink = document.querySelector('a[href*="page="]');
  if (nextLink) {
    const href = nextLink.href;
    prefetchResource(href, 'prefetch');
  }
}

// ===== PERFORMANCE MONITORING =====
function logPerformanceMetrics() {
  if (window.performance && window.performance.timing) {
    const perfData = window.performance.timing;
    const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
    const connectTime = perfData.responseEnd - perfData.requestStart;
    const renderTime = perfData.domComplete - perfData.domLoading;
    
    console.log('📊 Performance Metrics:');
    console.log(`⏱️ Page Load Time: ${pageLoadTime}ms`);
    console.log(`📡 Connect Time: ${connectTime}ms`);
    console.log(`🎨 Render Time: ${renderTime}ms`);
  }
}

// Log metrics on page load
window.addEventListener('load', () => {
  setTimeout(logPerformanceMetrics, 0);
});

// ===== MOBILE OPTIMIZATIONS =====
function optimizeForMobile() {
  if (window.matchMedia('(max-width: 768px)').matches) {
    // Disable hover effects on mobile
    document.body.classList.add('is-mobile');
  }
}

document.addEventListener('DOMContentLoaded', optimizeForMobile);
