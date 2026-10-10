import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import './styles/base.css';
import './styles/components.css';
import { activeAdapter, computeSha256 } from './adapters/mock-adapter';

const app = createApp(App);
app.use(router);
app.mount('#app');

// Expose adapter and sha256 for local testing and browser automation
if (typeof window !== 'undefined') {
  (window as any).__CATOS_ADAPTER__ = activeAdapter;
  (window as any).__CATOS_SHA256__ = computeSha256;
}

