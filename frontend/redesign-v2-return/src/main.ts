import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import './styles/base.css';
import './styles/components.css';
import { activeAdapter, computeSha256 } from './adapters/mock-adapter';

const app = createApp(App);
app.use(router);
app.mount('#app');

// Expose adapter and sha256 in DEV or when explicitly enabled via test hook / query / flag
if (
  typeof window !== 'undefined' &&
  (import.meta.env.DEV ||
    (window as any).__CATOS_ENABLE_TEST__ ||
    window.location.search.includes('enable_test_adapter=1') ||
    window.sessionStorage.getItem('catos_test_adapter') === '1')
) {
  (window as any).__CATOS_ADAPTER__ = activeAdapter;
  (window as any).__CATOS_SHA256__ = computeSha256;
}


